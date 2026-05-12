from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from sellthrough.db import ActiveListingRecord, ActiveListingRepository, RawResponseRepository


class RawResponseRepositoryTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
