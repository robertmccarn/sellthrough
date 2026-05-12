from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from sellthrough.config import Settings
from sellthrough.services.raw_storage import save_raw_api_page
from sellthrough.services.smoke import SmokeCheck, format_smoke_checks, run_smoke_checks


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
