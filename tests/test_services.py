from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from sellthrough.config import Settings
from sellthrough.ebay.browse import BrowseSearchResult
from sellthrough.services.active_listings import (
    active_listing_records_from_browse_payload,
    normalize_active_browse_payload,
)
from sellthrough.services.active_polling import poll_active_watchlist, run_active_poll_worker
from sellthrough.services.dashboard import get_dashboard_summary
from sellthrough.services.lookup import lookup_active_listings, lookup_watchlist_active_listings
from sellthrough.services.raw_storage import save_raw_api_page
from sellthrough.services.snapshots import (
    capture_all_watchlist_metric_snapshots,
    capture_watchlist_metric_snapshot,
)
from sellthrough.services.smoke import SmokeCheck, format_smoke_checks, run_smoke_checks
from sellthrough.services.watchlist import add_watchlist_item
from sellthrough.web.app import create_app, create_health_summary


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
                observation = connection.execute(
                    """
                    SELECT
                        watchlist_id,
                        item_id,
                        raw_response_id,
                        price_value,
                        price_currency,
                        shipping_value,
                        shipping_currency,
                        condition
                    FROM active_listing_observations
                    """
                ).fetchone()

            self.assertEqual(raw_count[0], 1)
            self.assertEqual(
                listing,
                ("Example Drill", "184655", 42.5, 7.99, results[0].raw_response_id),
            )
            self.assertEqual(
                observation,
                (
                    results[0].watchlist_id,
                    "v1|123|0",
                    results[0].raw_response_id,
                    42.5,
                    "USD",
                    7.99,
                    "USD",
                    "Used",
                ),
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

    def test_poll_active_watchlist_processes_multiple_watchlist_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            first = add_watchlist_item(
                db_path=db_path,
                label="DeWalt drill",
                query="dewalt 20v drill",
                category_id="184655",
            )
            second = add_watchlist_item(
                db_path=db_path,
                label="TI-84 Plus CE",
                query="ti-84 plus ce",
                category_id="15032",
            )
            settings = Settings(
                ebay_env="production",
                ebay_client_id="client-id",
                ebay_client_secret="secret",
                ebay_dev_id="dev-id",
                db_path=db_path,
            )
            first_payload = {
                "total": 1,
                "href": "https://api.ebay.com/buy/browse/v1/item_summary/search?q=dewalt",
                "itemSummaries": [
                    {"itemId": "v1|201|0", "title": "DeWalt Drill", "price": {"value": "80.00", "currency": "USD"}}
                ],
            }
            second_payload = {
                "total": 2,
                "href": "https://api.ebay.com/buy/browse/v1/item_summary/search?q=ti84",
                "itemSummaries": [
                    {"itemId": "v1|301|0", "title": "TI-84 Plus CE A", "price": {"value": "60.00", "currency": "USD"}},
                    {"itemId": "v1|302|0", "title": "TI-84 Plus CE B", "price": {"value": "70.00", "currency": "USD"}},
                ],
            }

            with patch("sellthrough.services.active_polling.BrowseClient") as browse_client:
                browse_client.from_settings.return_value.search_active_items.side_effect = (
                    BrowseSearchResult.from_payload(query=first.query, limit=10, offset=0, payload=first_payload),
                    BrowseSearchResult.from_payload(query=second.query, limit=10, offset=0, payload=second_payload),
                )

                results = poll_active_watchlist(
                    settings=settings,
                    marketplace_id="EBAY_US",
                    limit=10,
                )

            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].watchlist_id, first.id)
            self.assertEqual(results[0].returned, 1)
            self.assertEqual(results[0].normalized, 1)
            self.assertEqual(results[1].watchlist_id, second.id)
            self.assertEqual(results[1].returned, 2)
            self.assertEqual(results[1].normalized, 2)

            calls = browse_client.from_settings.return_value.search_active_items.call_args_list
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0].kwargs["query"] if "query" in calls[0].kwargs else calls[0].args[0], first.query)
            self.assertEqual(calls[0].kwargs["category_ids"] if "category_ids" in calls[0].kwargs else calls[0].args[3], ["184655"])
            self.assertEqual(calls[1].kwargs["query"] if "query" in calls[1].kwargs else calls[1].args[0], second.query)
            self.assertEqual(calls[1].kwargs["category_ids"] if "category_ids" in calls[1].kwargs else calls[1].args[3], ["15032"])

            with closing(sqlite3.connect(db_path)) as connection:
                raw_count = connection.execute("SELECT COUNT(*) FROM raw_api_responses").fetchone()
                listing_count = connection.execute("SELECT COUNT(*) FROM active_listings").fetchone()
            self.assertEqual(raw_count[0], 2)
            self.assertEqual(listing_count[0], 3)

    def test_run_active_poll_worker_runs_cycles_and_sleeps_between(self) -> None:
        settings = Settings(
            ebay_env="production",
            ebay_client_id="client-id",
            ebay_client_secret="secret",
            ebay_dev_id="dev-id",
            db_path=Path("data/sellthrough.sqlite3"),
        )
        sleep_calls: list[float] = []

        with (
            patch("sellthrough.services.active_polling.poll_active_watchlist") as poll_active,
            patch("sellthrough.services.active_polling.capture_all_watchlist_metric_snapshots") as capture_snapshots,
        ):
            poll_active.return_value = (
                type("Result", (), {"normalized": 2})(),
                type("Result", (), {"normalized": 3})(),
            )
            capture_snapshots.return_value = type(
                "SnapshotResult",
                (),
                {"rows": (object(), object())},
            )()

            results = run_active_poll_worker(
                settings=settings,
                cycles=2,
                interval_seconds=7,
                sleep_fn=lambda s: sleep_calls.append(s),
            )

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].polled_watchlist_rows, 2)
        self.assertEqual(results[0].normalized_rows, 5)
        self.assertEqual(results[0].snapshot_rows, 2)
        self.assertEqual(sleep_calls, [7])
        self.assertEqual(poll_active.call_count, 2)
        self.assertEqual(capture_snapshots.call_count, 2)

    def test_run_active_poll_worker_validates_interval_and_cycles(self) -> None:
        settings = Settings(
            ebay_env="production",
            ebay_client_id="client-id",
            ebay_client_secret="secret",
            ebay_dev_id="dev-id",
            db_path=Path("data/sellthrough.sqlite3"),
        )

        with self.assertRaisesRegex(ValueError, "interval_seconds"):
            run_active_poll_worker(settings=settings, interval_seconds=0)

        with self.assertRaisesRegex(ValueError, "cycles"):
            run_active_poll_worker(settings=settings, cycles=0)


class ActiveListingTransformTests(unittest.TestCase):
    def test_active_listing_records_from_browse_payload_preserves_raw_linkage(self) -> None:
        payload = {
            "total": 2,
            "itemSummaries": [
                {
                    "itemId": "v1|123|0",
                    "title": "Example Drill",
                    "price": {"value": "42.50", "currency": "USD"},
                    "shippingOptions": [
                        {"shippingCost": {"value": "7.99", "currency": "USD"}}
                    ],
                    "categories": [{"categoryId": "184655", "categoryName": "Drills"}],
                    "condition": "Used",
                    "itemWebUrl": "https://www.ebay.com/itm/123",
                    "itemCreationDate": "2026-05-01T00:00:00.000Z",
                },
                {
                    "title": "Missing ID should not become a stable row",
                },
            ],
        }

        records = active_listing_records_from_browse_payload(
            payload=payload,
            raw_response_id=99,
            query="dewalt drill",
            limit=10,
            offset=0,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].item_id, "v1|123|0")
        self.assertEqual(records[0].category_id, "184655")
        self.assertEqual(records[0].shipping_value, 7.99)
        self.assertEqual(records[0].raw_response_id, 99)

    def test_active_listing_records_from_browse_payload_handles_missing_fields(self) -> None:
        payload = {
            "itemSummaries": [
                {
                    "itemId": "v1|price-missing|0",
                    "title": "No Price",
                    "categories": [{"categoryId": "1", "categoryName": "Tools"}],
                    "shippingOptions": [
                        {"shippingCost": {"value": "12.00", "currency": "USD"}}
                    ],
                },
                {
                    "itemId": "v1|shipping-missing|0",
                    "title": "No Shipping",
                    "price": {"value": "45.00", "currency": "USD"},
                    "categories": [{"categoryId": "2", "categoryName": "Electronics"}],
                },
                {
                    "itemId": "v1|category-missing|0",
                    "title": "No Category",
                    "price": {"value": "9.99", "currency": "USD"},
                    "shippingOptions": [
                        {"shippingCost": {"value": "2.00", "currency": "USD"}}
                    ],
                },
                {
                    "title": "Missing ID should be skipped",
                    "price": {"value": "1.00", "currency": "USD"},
                },
            ]
        }

        records = active_listing_records_from_browse_payload(
            payload=payload,
            raw_response_id=321,
            query="mixed",
            limit=20,
            offset=0,
        )

        self.assertEqual(len(records), 3)

        by_id = {record.item_id: record for record in records}
        self.assertIn("v1|price-missing|0", by_id)
        self.assertIn("v1|shipping-missing|0", by_id)
        self.assertIn("v1|category-missing|0", by_id)

        self.assertIsNone(by_id["v1|price-missing|0"].price_value)
        self.assertEqual(by_id["v1|price-missing|0"].shipping_value, 12.0)
        self.assertEqual(by_id["v1|price-missing|0"].category_id, "1")

        self.assertEqual(by_id["v1|shipping-missing|0"].price_value, 45.0)
        self.assertIsNone(by_id["v1|shipping-missing|0"].shipping_value)
        self.assertEqual(by_id["v1|shipping-missing|0"].category_id, "2")

        self.assertEqual(by_id["v1|category-missing|0"].price_value, 9.99)
        self.assertEqual(by_id["v1|category-missing|0"].shipping_value, 2.0)
        self.assertIsNone(by_id["v1|category-missing|0"].category_id)

        self.assertTrue(all(record.raw_response_id == 321 for record in records))

    def test_normalize_active_browse_payload_upserts_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            watchlist_item = add_watchlist_item(
                db_path=db_path,
                label="Example saw",
                query="saw",
            )
            payload = {
                "total": 1,
                "itemSummaries": [
                    {
                        "itemId": "v1|456|0",
                        "title": "Example Saw",
                        "price": {"value": "55.00", "currency": "USD"},
                        "categoryId": "177003",
                        "categoryName": "Saws",
                    }
                ],
            }
            saved = save_raw_api_page(
                db_path=db_path,
                source="browse_watchlist",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example",
                response_json=payload,
                query="saw",
            )

            normalized = normalize_active_browse_payload(
                db_path=db_path,
                raw_response_id=saved.raw_response_id,
                payload=payload,
                watchlist_id=watchlist_item.id,
                query="saw",
                limit=5,
                offset=0,
            )

            with closing(sqlite3.connect(db_path)) as connection:
                row = connection.execute(
                    """
                    SELECT item_id, title, category_id, price_value, raw_response_id
                    FROM active_listings
                    """
                ).fetchone()
                observation = connection.execute(
                    """
                    SELECT
                        watchlist_id,
                        item_id,
                        raw_response_id,
                        price_value,
                        price_currency,
                        shipping_value,
                        shipping_currency
                    FROM active_listing_observations
                    """
                ).fetchone()

            self.assertEqual(normalized, 1)
            self.assertEqual(
                row,
                ("v1|456|0", "Example Saw", "177003", 55.0, saved.raw_response_id),
            )
            self.assertEqual(
                observation,
                (watchlist_item.id, "v1|456|0", saved.raw_response_id, 55.0, "USD", None, None),
            )

    def test_normalize_active_browse_payload_appends_repeated_observations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            watchlist_item = add_watchlist_item(
                db_path=db_path,
                label="Repeat drill",
                query="drill",
            )
            payload = {
                "itemSummaries": [
                    {
                        "itemId": "v1|999|0",
                        "title": "Repeat Drill",
                        "price": {"value": "10.00", "currency": "USD"},
                    }
                ]
            }

            for _ in range(2):
                saved = save_raw_api_page(
                    db_path=db_path,
                    source="browse_watchlist",
                    endpoint="/buy/browse/v1/item_summary/search",
                    request_url="https://api.ebay.com/example",
                    response_json=payload,
                    query="drill",
                )
                normalize_active_browse_payload(
                    db_path=db_path,
                    raw_response_id=saved.raw_response_id,
                    payload=payload,
                    watchlist_id=watchlist_item.id,
                    query="drill",
                    limit=5,
                    offset=0,
                )

            with closing(sqlite3.connect(db_path)) as connection:
                row = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM active_listing_observations
                    WHERE item_id = 'v1|999|0'
                    """
                ).fetchone()
            self.assertEqual(row[0], 2)


class LookupServiceTests(unittest.TestCase):
    def test_lookup_active_listings_reads_normalized_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            saved = save_raw_api_page(
                db_path=db_path,
                source="browse_watchlist",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example",
                response_json={
                    "itemSummaries": [
                        {
                            "itemId": "v1|789|0",
                            "title": "DeWalt Drill Kit",
                            "price": {"value": "64.00", "currency": "USD"},
                        }
                    ]
                },
                query="dewalt",
            )
            normalize_active_browse_payload(
                db_path=db_path,
                raw_response_id=saved.raw_response_id,
                payload={
                    "itemSummaries": [
                        {
                            "itemId": "v1|789|0",
                            "title": "DeWalt Drill Kit",
                            "price": {"value": "64.00", "currency": "USD"},
                        }
                    ]
                },
                query="dewalt",
            )

            result = lookup_active_listings(db_path=db_path, query="drill")

            self.assertEqual(result.active_count, 1)
            self.assertEqual(result.price_median, 64.0)
            self.assertEqual(result.samples[0].item_id, "v1|789|0")

    def test_lookup_active_listings_returns_metrics_and_sample_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            for item_id, title, price in (
                ("v1|10|0", "DeWalt Drill A", "30.00"),
                ("v1|11|0", "DeWalt Drill B", "50.00"),
                ("v1|12|0", "DeWalt Drill C", "70.00"),
            ):
                payload = {
                    "itemSummaries": [
                        {
                            "itemId": item_id,
                            "title": title,
                            "price": {"value": price, "currency": "USD"},
                        }
                    ]
                }
                saved = save_raw_api_page(
                    db_path=db_path,
                    source="browse_watchlist",
                    endpoint="/buy/browse/v1/item_summary/search",
                    request_url=f"https://api.ebay.com/example/{item_id}",
                    response_json=payload,
                    query="dewalt drill",
                )
                normalize_active_browse_payload(
                    db_path=db_path,
                    raw_response_id=saved.raw_response_id,
                    payload=payload,
                    query="dewalt drill",
                )

            result = lookup_active_listings(db_path=db_path, query="dewalt drill", sample_limit=2)

            self.assertEqual(result.active_count, 3)
            self.assertEqual(result.price_min, 30.0)
            self.assertEqual(result.price_median, 50.0)
            self.assertEqual(result.price_max, 70.0)
            self.assertEqual(result.price_currency, "USD")
            self.assertEqual(len(result.samples), 2)

    def test_lookup_active_listings_validates_blank_query(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            with self.assertRaisesRegex(ValueError, "Lookup query cannot be blank."):
                lookup_active_listings(db_path=db_path, query="   ")

    def test_lookup_active_listings_handles_empty_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            result = lookup_active_listings(db_path=db_path, query="does-not-exist")

            self.assertEqual(result.active_count, 0)
            self.assertIsNone(result.price_min)
            self.assertIsNone(result.price_median)
            self.assertIsNone(result.price_max)
            self.assertIsNone(result.price_currency)
            self.assertIsNone(result.last_seen_at)
            self.assertEqual(result.samples, ())

    def test_lookup_watchlist_active_listings_scopes_to_watchlist_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            first = add_watchlist_item(
                db_path=db_path,
                label="DeWalt Drill",
                query="dewalt drill",
            )
            second = add_watchlist_item(
                db_path=db_path,
                label="Milwaukee Saw",
                query="milwaukee saw",
            )
            first_payload = {
                "itemSummaries": [
                    {
                        "itemId": "v1|100|0",
                        "title": "DeWalt Drill 20V",
                        "price": {"value": "89.99", "currency": "USD"},
                    }
                ]
            }
            second_payload = {
                "itemSummaries": [
                    {
                        "itemId": "v1|200|0",
                        "title": "Milwaukee Saw M18",
                        "price": {"value": "129.99", "currency": "USD"},
                    }
                ]
            }

            first_raw = save_raw_api_page(
                db_path=db_path,
                source="browse_watchlist",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example?first",
                response_json=first_payload,
                query=first.query,
            )
            normalize_active_browse_payload(
                db_path=db_path,
                raw_response_id=first_raw.raw_response_id,
                payload=first_payload,
                watchlist_id=first.id,
                query=first.query,
            )

            second_raw = save_raw_api_page(
                db_path=db_path,
                source="browse_watchlist",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example?second",
                response_json=second_payload,
                query=second.query,
            )
            normalize_active_browse_payload(
                db_path=db_path,
                raw_response_id=second_raw.raw_response_id,
                payload=second_payload,
                watchlist_id=second.id,
                query=second.query,
            )

            result = lookup_watchlist_active_listings(
                db_path=db_path,
                watchlist_id=first.id,
                sample_limit=5,
            )

            self.assertEqual(result.watchlist_id, first.id)
            self.assertEqual(result.watchlist_label, "DeWalt Drill")
            self.assertEqual(result.watchlist_query, "dewalt drill")
            self.assertEqual(result.active_count, 1)
            self.assertEqual(result.price_median, 89.99)
            self.assertEqual(len(result.samples), 1)
            self.assertEqual(result.samples[0].item_id, "v1|100|0")


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


class DashboardServiceTests(unittest.TestCase):
    def test_get_dashboard_summary_returns_pipeline_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            watchlist_item = add_watchlist_item(
                db_path=db_path,
                label="DeWalt Drill",
                query="dewalt drill",
            )
            payload = {
                "itemSummaries": [
                    {
                        "itemId": "v1|314|0",
                        "title": "DeWalt Drill 20V",
                        "price": {"value": "89.99", "currency": "USD"},
                    }
                ]
            }
            saved = save_raw_api_page(
                db_path=db_path,
                source="browse_watchlist",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example",
                response_json=payload,
                query=watchlist_item.query,
            )
            normalize_active_browse_payload(
                db_path=db_path,
                raw_response_id=saved.raw_response_id,
                payload=payload,
                watchlist_id=watchlist_item.id,
                query=watchlist_item.query,
            )

            summary = get_dashboard_summary(db_path)

            self.assertEqual(summary.active_listing_count, 1)
            self.assertEqual(summary.watchlist_count, 1)
            self.assertIsNotNone(summary.latest_poll_run)
            self.assertEqual(summary.latest_poll_run.status, "completed")
            self.assertIsNotNone(summary.latest_raw_response)
            self.assertEqual(summary.latest_raw_response.id, saved.raw_response_id)
            self.assertEqual(summary.recent_failed_poll_count, 0)
            self.assertEqual(len(summary.sample_recent_active_listings), 1)
            self.assertEqual(summary.sample_recent_active_listings[0].item_id, "v1|314|0")
            self.assertEqual(summary.recent_snapshot_rows, ())
            self.assertEqual(summary.sold_metrics_status, "pending")
            self.assertEqual(summary.opportunity_metrics_status, "pending")

    def test_get_dashboard_summary_includes_recent_snapshot_preview_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            watchlist_item = add_watchlist_item(
                db_path=db_path,
                label="Snapshot drill",
                query="snapshot drill",
            )
            payload = {
                "itemSummaries": [
                    {
                        "itemId": "v1|515|0",
                        "title": "Snapshot Drill",
                        "price": {"value": "50.00", "currency": "USD"},
                    }
                ]
            }
            saved = save_raw_api_page(
                db_path=db_path,
                source="browse_watchlist",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example",
                response_json=payload,
                query=watchlist_item.query,
            )
            normalize_active_browse_payload(
                db_path=db_path,
                raw_response_id=saved.raw_response_id,
                payload=payload,
                watchlist_id=watchlist_item.id,
                query=watchlist_item.query,
            )
            capture_watchlist_metric_snapshot(db_path=db_path, watchlist_id=watchlist_item.id)

            summary = get_dashboard_summary(db_path)

            self.assertEqual(len(summary.recent_snapshot_rows), 1)
            self.assertEqual(summary.recent_snapshot_rows[0].watchlist_label, "Snapshot drill")
            self.assertEqual(summary.recent_snapshot_rows[0].active_count, 1)
            self.assertEqual(summary.recent_snapshot_rows[0].active_price_median, 50.0)


class WebHealthSummaryTests(unittest.TestCase):
    def test_create_health_summary_reports_missing_database_before_initialization(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "missing.sqlite3"
            settings = Settings(
                ebay_env="production",
                ebay_client_id=None,
                ebay_client_secret=None,
                ebay_dev_id=None,
                db_path=db_path,
            )

            summary = create_health_summary(settings)

            self.assertFalse(summary.database_exists)
            self.assertEqual(summary.raw_responses_count, 0)
            self.assertEqual(summary.active_listings_count, 0)
            self.assertEqual(summary.watchlist_count, 0)
            self.assertFalse(summary.browse_credentials_configured)
            self.assertEqual(summary.marketplace_insights_status, "pending")

    def test_create_health_summary_reports_local_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            add_watchlist_item(
                db_path=db_path,
                label="Health drill",
                query="health drill",
            )
            saved = save_raw_api_page(
                db_path=db_path,
                source="browse_watchlist",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example",
                response_json={
                    "itemSummaries": [
                        {
                            "itemId": "v1|901|0",
                            "title": "Health Drill",
                            "price": {"value": "10.00", "currency": "USD"},
                        }
                    ]
                },
                query="health drill",
            )
            normalize_active_browse_payload(
                db_path=db_path,
                raw_response_id=saved.raw_response_id,
                payload={
                    "itemSummaries": [
                        {
                            "itemId": "v1|901|0",
                            "title": "Health Drill",
                            "price": {"value": "10.00", "currency": "USD"},
                        }
                    ]
                },
                query="health drill",
            )
            settings = Settings(
                ebay_env="production",
                ebay_client_id="client-id",
                ebay_client_secret="secret",
                ebay_dev_id="dev-id",
                db_path=db_path,
            )

            summary = create_health_summary(settings)

            self.assertTrue(summary.database_exists)
            self.assertEqual(summary.raw_responses_count, 1)
            self.assertEqual(summary.active_listings_count, 1)
            self.assertEqual(summary.watchlist_count, 1)
            self.assertTrue(summary.browse_credentials_configured)
            self.assertEqual(summary.marketplace_insights_status, "pending")


class WebRouteTests(unittest.TestCase):
    def test_web_routes_are_available_without_live_credentials(self) -> None:
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test client is unavailable without optional web dependencies.")

        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings(
                ebay_env="production",
                ebay_client_id=None,
                ebay_client_secret=None,
                ebay_dev_id=None,
                db_path=Path(temp_dir) / "sellthrough.sqlite3",
            )
            client = TestClient(create_app(settings=settings))

            for path in ("/health", "/dashboard", "/watchlist", "/lookup"):
                response = client.get(path)
                self.assertEqual(response.status_code, 200)

            health = client.get("/health").json()
            self.assertFalse(health["browse_credentials_configured"])
            self.assertEqual(health["marketplace_insights_status"], "pending")

    def test_lookup_route_supports_active_and_watchlist_modes(self) -> None:
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test client is unavailable without optional web dependencies.")

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            watchlist_item = add_watchlist_item(
                db_path=db_path,
                label="Lookup Drill",
                query="lookup drill",
            )
            payload = {
                "itemSummaries": [
                    {
                        "itemId": "v1|620|0",
                        "title": "Lookup Drill",
                        "price": {"value": "77.00", "currency": "USD"},
                    }
                ]
            }
            saved = save_raw_api_page(
                db_path=db_path,
                source="browse_watchlist",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example",
                response_json=payload,
                query=watchlist_item.query,
            )
            normalize_active_browse_payload(
                db_path=db_path,
                raw_response_id=saved.raw_response_id,
                payload=payload,
                watchlist_id=watchlist_item.id,
                query=watchlist_item.query,
            )

            settings = Settings(
                ebay_env="production",
                ebay_client_id=None,
                ebay_client_secret=None,
                ebay_dev_id=None,
                db_path=db_path,
            )
            client = TestClient(create_app(settings=settings))

            active_lookup = client.get(
                "/lookup",
                params={"mode": "active", "query": "lookup drill", "samples": 3},
            )
            self.assertEqual(active_lookup.status_code, 200)
            self.assertIn("Active Lookup Summary", active_lookup.text)
            self.assertIn("Lookup Drill", active_lookup.text)

            watchlist_lookup = client.get(
                "/lookup",
                params={"mode": "watchlist", "watchlist_id": watchlist_item.id, "samples": 3},
            )
            self.assertEqual(watchlist_lookup.status_code, 200)
            self.assertIn("Watchlist-Scoped Lookup Summary", watchlist_lookup.text)
            self.assertIn("Lookup Drill", watchlist_lookup.text)


class SnapshotServiceTests(unittest.TestCase):
    def test_capture_watchlist_metric_snapshot_persists_active_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            watchlist_item = add_watchlist_item(
                db_path=db_path,
                label="DeWalt drill",
                query="dewalt drill",
            )
            payload = {
                "itemSummaries": [
                    {
                        "itemId": "v1|700|0",
                        "title": "DeWalt Drill A",
                        "price": {"value": "80.00", "currency": "USD"},
                    },
                    {
                        "itemId": "v1|701|0",
                        "title": "DeWalt Drill B",
                        "price": {"value": "100.00", "currency": "USD"},
                    },
                ]
            }
            saved = save_raw_api_page(
                db_path=db_path,
                source="browse_watchlist",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example",
                response_json=payload,
                query=watchlist_item.query,
            )
            normalize_active_browse_payload(
                db_path=db_path,
                raw_response_id=saved.raw_response_id,
                payload=payload,
                watchlist_id=watchlist_item.id,
                query=watchlist_item.query,
            )

            snapshot = capture_watchlist_metric_snapshot(
                db_path=db_path,
                watchlist_id=watchlist_item.id,
            )

            self.assertEqual(snapshot.watchlist_id, watchlist_item.id)
            self.assertEqual(snapshot.active_count, 2)
            self.assertEqual(snapshot.active_price_min, 80.0)
            self.assertEqual(snapshot.active_price_median, 90.0)
            self.assertEqual(snapshot.active_price_max, 100.0)
            self.assertEqual(snapshot.sample_confidence, "low")
            self.assertIsNone(snapshot.sold_count_30d)

    def test_capture_all_watchlist_metric_snapshots_handles_empty_observations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            with_data = add_watchlist_item(
                db_path=db_path,
                label="With data",
                query="with data",
            )
            no_data = add_watchlist_item(
                db_path=db_path,
                label="No data yet",
                query="no data",
            )
            payload = {
                "itemSummaries": [
                    {
                        "itemId": "v1|800|0",
                        "title": "With Data Item",
                        "price": {"value": "12.00", "currency": "USD"},
                    }
                ]
            }
            saved = save_raw_api_page(
                db_path=db_path,
                source="browse_watchlist",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example",
                response_json=payload,
                query=with_data.query,
            )
            normalize_active_browse_payload(
                db_path=db_path,
                raw_response_id=saved.raw_response_id,
                payload=payload,
                watchlist_id=with_data.id,
                query=with_data.query,
            )

            result = capture_all_watchlist_metric_snapshots(db_path=db_path)

            self.assertEqual(result.captured, 2)
            self.assertEqual(result.empty_snapshots, 1)
            by_watchlist_id = {row.watchlist_id: row for row in result.rows}
            self.assertEqual(by_watchlist_id[with_data.id].active_count, 1)
            self.assertEqual(by_watchlist_id[no_data.id].active_count, 0)


if __name__ == "__main__":
    unittest.main()
