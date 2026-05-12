from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from sellthrough.db import RawResponseRepository


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


if __name__ == "__main__":
    unittest.main()
