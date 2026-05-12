from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from sellthrough.config import Settings
from sellthrough.ebay.browse import BrowseSearchResult
from sellthrough.services.active_polling import poll_active_watchlist
from sellthrough.services.raw_storage import save_raw_api_page
from sellthrough.services.smoke import SmokeCheck, format_smoke_checks, run_smoke_checks
from sellthrough.services.watchlist import add_watchlist_item


class RawStorageServiceTests(unittest.TestCase):
    def test_save_raw_api_page_creates_completed_poll_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"

            saved = save_raw_api_page(
                db_path=db_path,
                source="browse",
                endpoint="/example",
                request_url="https://api.ebay.com/example",
                response_json={"total": 1},
                query="dewalt drill",
            )

            with closing(sqlite3.connect(db_path)) as connection:
                row = connection.execute(
                    """
                    SELECT poll_runs.status, raw_api_responses.source
                    FROM raw_api_responses
                    JOIN poll_runs ON poll_runs.id = raw_api_responses.poll_run_id
                    WHERE raw_api_responses.id = ?
                    """,
                    (saved.raw_response_id,),
                ).fetchone()

            self.assertEqual(row, ("completed", "browse"))


class ActivePollingServiceTests(unittest.TestCase):
    def test_poll_active_watchlist_saves_raw_and_normalizes_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            add_watchlist_item(
                db_path=db_path,
                label="DeWalt drill",
                query="dewalt 20v drill",
                category_id="184655",
            )
            settings = Settings(
                ebay_env="production",
                ebay_client_id="client-id",
                ebay_client_secret="secret",
                ebay_dev_id="dev-id",
                db_path=db_path,
            )
            browse_payload = {
                "total": 1,
                "href": "https://api.ebay.com/buy/browse/v1/item_summary/search?q=dewalt",
                "itemSummaries": [
                    {
                        "itemId": "v1|123|0",
                        "title": "Example Drill",
                        "price": {"value": "42.50", "currency": "USD"},
                        "shippingOptions": [
                            {"shippingCost": {"value": "7.99", "currency": "USD"}}
                        ],
                        "categories": [
                            {"categoryId": "184655", "categoryName": "Drills"}
                        ],
                        "condition": "Used",
                        "itemWebUrl": "https://www.ebay.com/itm/123",
                        "itemCreationDate": "2026-05-01T00:00:00.000Z",
                    }
                ],
            }

            with patch("sellthrough.services.active_polling.BrowseClient") as browse_client:
                browse_client.from_settings.return_value.search_active_items.return_value = (
                    BrowseSearchResult.from_payload(
                        query="dewalt 20v drill",
                        limit=5,
                        offset=0,
                        payload=browse_payload,
                    )
                )

                results = poll_active_watchlist(
                    settings=settings,
                    marketplace_id="EBAY_US",
                    limit=5,
                )

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].returned, 1)
            self.assertEqual(results[0].normalized, 1)
            browse_client.from_settings.return_value.search_active_items.assert_called_once_with(
                "dewalt 20v drill",
                limit=5,
                offset=0,
                category_ids=["184655"],
            )

            with closing(sqlite3.connect(db_path)) as connection:
                raw_count = connection.execute("SELECT COUNT(*) FROM raw_api_responses").fetchone()
                listing = connection.execute(
                    """
                    SELECT title, category_id, price_value, shipping_value, raw_response_id
                    FROM active_listings
                    WHERE item_id = ?
                    """,
                    ("v1|123|0",),
                ).fetchone()

            self.assertEqual(raw_count[0], 1)
            self.assertEqual(
                listing,
                ("Example Drill", "184655", 42.5, 7.99, results[0].raw_response_id),
            )

    def test_poll_active_watchlist_returns_empty_when_no_active_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(
                ebay_env="production",
                ebay_client_id="client-id",
                ebay_client_secret="secret",
                ebay_dev_id="dev-id",
                db_path=Path(temp_dir) / "sellthrough.sqlite3",
            )

            with patch("sellthrough.services.active_polling.BrowseClient") as browse_client:
                results = poll_active_watchlist(settings=settings)

            self.assertEqual(results, ())
            browse_client.from_settings.assert_not_called()


class SmokeServiceTests(unittest.TestCase):
    def test_format_smoke_checks_renders_one_line_per_check(self) -> None:
        output = format_smoke_checks(
            [
                SmokeCheck("config", "PASS", "environment=production"),
                SmokeCheck("marketplace insights", "WARN", "access pending"),
            ]
        )

        self.assertEqual(
            output,
            "\n".join(
                [
                    "[PASS] config: environment=production",
                    "[WARN] marketplace insights: access pending",
                ]
            ),
        )

    def test_run_smoke_checks_returns_structured_rows(self) -> None:
        settings = Settings(
            ebay_env="production",
            ebay_client_id="client-id",
            ebay_client_secret="secret",
            ebay_dev_id="dev-id",
            db_path=Path("data/sellthrough.sqlite3"),
        )

        with (
            patch("sellthrough.services.smoke.initialize_database"),
            patch("sellthrough.services.smoke.BrowseClient") as browse_client,
            patch("sellthrough.services.smoke.TaxonomyClient") as taxonomy_client,
            patch("sellthrough.services.smoke.MarketplaceInsightsClient") as insights_client,
        ):
            browse_client.from_settings.return_value.search_active_items.return_value.total = 3
            browse_client.from_settings.return_value.search_active_items.return_value.items = (1,)
            taxonomy_client.from_settings.return_value.get_default_category_tree_id.return_value.marketplace_id = "EBAY_US"
            taxonomy_client.from_settings.return_value.get_default_category_tree_id.return_value.category_tree_id = "0"
            taxonomy_client.from_settings.return_value.get_default_category_tree_id.return_value.category_tree_version = "134"
            insights_client.from_settings.return_value.search_sold_items.return_value.total = 2

            checks = run_smoke_checks(
                settings=settings,
                query="dewalt drill",
                limit=1,
                marketplace_id="EBAY_US",
            )

        self.assertEqual([check.name for check in checks], ["config", "sqlite", "browse", "taxonomy", "marketplace insights"])
        self.assertEqual(checks[-1].status, "PASS")


if __name__ == "__main__":
    unittest.main()
