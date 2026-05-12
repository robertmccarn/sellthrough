from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from sellthrough.db import (
    ActiveListingObservationRecord,
    ActiveListingRecord,
    ActiveListingRepository,
    RawResponseRepository,
    WatchlistMetricSnapshotRepository,
    WatchlistRepository,
    initialize_database,
)


class RawResponseRepositoryTests(unittest.TestCase):
    def test_initialize_database_creates_common_query_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"

            initialize_database(db_path)

            with closing(sqlite3.connect(db_path)) as connection:
                index_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'index'"
                    )
                }
            self.assertIn("idx_watchlist_active_id", index_names)
            self.assertIn("idx_active_observations_watchlist_item_observed", index_names)
            self.assertIn("idx_snapshot_watchlist_captured_at", index_names)
            self.assertIn("idx_poll_runs_status_started_at", index_names)

    def test_save_raw_response_links_to_poll_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            repository = RawResponseRepository(db_path)

            poll_run = repository.create_poll_run(source="browse", query="dewalt drill")
            raw = repository.save_raw_response(
                poll_run_id=poll_run.id,
                source="browse",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example",
                response_json={"total": 1, "itemSummaries": [{"itemId": "v1|123|0"}]},
            )
            repository.complete_poll_run(poll_run.id)

            self.assertEqual(repository.count_raw_responses(), 1)
            self.assertEqual(raw.poll_run_id, poll_run.id)

            with closing(sqlite3.connect(db_path)) as connection:
                row = connection.execute(
                    """
                    SELECT poll_runs.status, raw_api_responses.response_json
                    FROM raw_api_responses
                    JOIN poll_runs ON poll_runs.id = raw_api_responses.poll_run_id
                    WHERE raw_api_responses.id = ?
                    """,
                    (raw.id,),
                ).fetchone()

            self.assertEqual(row[0], "completed")
            self.assertEqual(json.loads(row[1])["total"], 1)

    def test_fail_poll_run_preserves_error_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = RawResponseRepository(Path(temp_dir) / "sellthrough.sqlite3")
            poll_run = repository.create_poll_run(source="browse", query="bad query")

            repository.fail_poll_run(poll_run.id, "network timeout")

            with closing(sqlite3.connect(repository.db_path)) as connection:
                row = connection.execute(
                    "SELECT status, error_message FROM poll_runs WHERE id = ?",
                    (poll_run.id,),
                ).fetchone()

            self.assertEqual(row, ("failed", "network timeout"))

    def test_poll_run_summary_queries_return_recent_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = RawResponseRepository(Path(temp_dir) / "sellthrough.sqlite3")

            first = repository.create_poll_run(source="browse", query="drill")
            repository.complete_poll_run(first.id)
            second = repository.create_poll_run(source="browse", query="saw")
            repository.fail_poll_run(second.id, "rate limited")

            recent = repository.list_recent_poll_runs(limit=10)
            latest_completed = repository.get_latest_completed_poll_run()
            failed_recent = repository.count_failed_poll_runs(days_back=7)

            self.assertEqual(len(recent), 2)
            self.assertEqual(recent[0].id, second.id)
            self.assertEqual(recent[0].status, "failed")
            self.assertEqual(recent[1].id, first.id)
            self.assertEqual(latest_completed.id, first.id)
            self.assertEqual(latest_completed.status, "completed")
            self.assertEqual(failed_recent, 1)


class ActiveListingRepositoryTests(unittest.TestCase):
    def test_upsert_many_inserts_and_updates_active_listing_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ActiveListingRepository(Path(temp_dir) / "sellthrough.sqlite3")

            first = ActiveListingRecord(
                item_id="v1|123|0",
                title="Example Drill",
                category_id="184655",
                category_name="Drills",
                condition="Used",
                price_value=42.5,
                price_currency="USD",
                shipping_value=7.99,
                shipping_currency="USD",
                item_web_url="https://www.ebay.com/itm/123",
                item_creation_date="2026-05-01T00:00:00.000Z",
                raw_response_id=None,
            )
            updated = ActiveListingRecord(
                item_id="v1|123|0",
                title="Example Drill Updated",
                category_id="184655",
                category_name="Drills",
                condition="Used",
                price_value=39.99,
                price_currency="USD",
                shipping_value=0,
                shipping_currency="USD",
                item_web_url="https://www.ebay.com/itm/123",
                item_creation_date="2026-05-01T00:00:00.000Z",
                raw_response_id=None,
            )

            self.assertEqual(repository.upsert_many((first,)), 1)
            self.assertEqual(repository.upsert_many((updated,)), 1)
            self.assertEqual(repository.count(), 1)

            with closing(sqlite3.connect(repository.db_path)) as connection:
                row = connection.execute(
                    """
                    SELECT title, price_value, shipping_value
                    FROM active_listings
                    WHERE item_id = ?
                    """,
                    ("v1|123|0",),
                ).fetchone()

            self.assertEqual(row, ("Example Drill Updated", 39.99, 0.0))

    def test_lookup_returns_active_metrics_and_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = ActiveListingRepository(Path(temp_dir) / "sellthrough.sqlite3")
            repository.upsert_many(
                (
                    ActiveListingRecord(
                        item_id="v1|1|0",
                        title="DeWalt Drill A",
                        category_id="184655",
                        category_name="Drills",
                        condition="Used",
                        price_value=30.0,
                        price_currency="USD",
                        shipping_value=None,
                        shipping_currency=None,
                        item_web_url=None,
                        item_creation_date=None,
                        raw_response_id=None,
                    ),
                    ActiveListingRecord(
                        item_id="v1|2|0",
                        title="DeWalt Drill B",
                        category_id="184655",
                        category_name="Drills",
                        condition="New",
                        price_value=50.0,
                        price_currency="USD",
                        shipping_value=None,
                        shipping_currency=None,
                        item_web_url="https://example.test/2",
                        item_creation_date=None,
                        raw_response_id=None,
                    ),
                    ActiveListingRecord(
                        item_id="v1|3|0",
                        title="Milwaukee Saw",
                        category_id="177003",
                        category_name="Saws",
                        condition="Used",
                        price_value=90.0,
                        price_currency="USD",
                        shipping_value=None,
                        shipping_currency=None,
                        item_web_url=None,
                        item_creation_date=None,
                        raw_response_id=None,
                    ),
                )
            )

            result = repository.lookup("dewalt drill", sample_limit=1)

            self.assertEqual(result.active_count, 2)
            self.assertEqual(result.price_min, 30.0)
            self.assertEqual(result.price_median, 40.0)
            self.assertEqual(result.price_max, 50.0)
            self.assertEqual(result.price_currency, "USD")
            self.assertIsNotNone(result.last_seen_at)
            self.assertEqual(len(result.samples), 1)
            self.assertIn("DeWalt Drill", result.samples[0].title)

    def test_insert_observations_persists_watchlist_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            watchlist = WatchlistRepository(db_path).add(
                label="DeWalt drill",
                query="dewalt 20v drill",
            )
            raw_repository = RawResponseRepository(db_path)
            poll_run = raw_repository.create_poll_run(source="browse_watchlist", query="dewalt 20v drill")
            raw = raw_repository.save_raw_response(
                poll_run_id=poll_run.id,
                source="browse_watchlist",
                endpoint="/buy/browse/v1/item_summary/search",
                request_url="https://api.ebay.com/example",
                response_json={"itemSummaries": []},
            )
            raw_repository.complete_poll_run(poll_run.id)

            repository = ActiveListingRepository(db_path)
            repository.upsert_many(
                (
                    ActiveListingRecord(
                        item_id="v1|1|0",
                        title="DeWalt Drill A",
                        category_id=None,
                        category_name=None,
                        condition="Used",
                        price_value=30.0,
                        price_currency="USD",
                        shipping_value=None,
                        shipping_currency=None,
                        item_web_url=None,
                        item_creation_date=None,
                        raw_response_id=raw.id,
                    ),
                )
            )
            inserted = repository.insert_observations(
                (
                    ActiveListingObservationRecord(
                        watchlist_id=watchlist.id,
                        item_id="v1|1|0",
                        raw_response_id=raw.id,
                        price_value=30.0,
                        price_currency="USD",
                        shipping_value=5.99,
                        shipping_currency="USD",
                        condition="Used",
                    ),
                )
            )

            self.assertEqual(inserted, 1)
            with closing(sqlite3.connect(db_path)) as connection:
                row = connection.execute(
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
            self.assertEqual(
                row,
                (watchlist.id, "v1|1|0", raw.id, 30.0, "USD", 5.99, "USD", "Used"),
            )


class WatchlistMetricSnapshotRepositoryTests(unittest.TestCase):
    def test_insert_and_fetch_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            watchlist = WatchlistRepository(db_path).add(
                label="DeWalt drill",
                query="dewalt 20v drill",
            )
            repository = WatchlistMetricSnapshotRepository(db_path)

            inserted = repository.insert(
                watchlist_id=watchlist.id,
                active_count=12,
                active_price_min=40.0,
                active_price_median=55.0,
                active_price_max=70.0,
                sold_count_30d=None,
                median_sold_price=None,
                sell_through_rate=None,
                sample_confidence="medium",
            )

            latest = repository.get_latest_for_watchlist(watchlist.id)
            recent = repository.list_recent(limit=5)

            self.assertEqual(inserted.watchlist_id, watchlist.id)
            self.assertEqual(inserted.active_count, 12)
            self.assertEqual(inserted.active_price_median, 55.0)
            self.assertEqual(inserted.sample_confidence, "medium")
            self.assertIsNotNone(latest)
            self.assertEqual(latest.id, inserted.id)
            self.assertEqual(len(recent), 1)


if __name__ == "__main__":
    unittest.main()
