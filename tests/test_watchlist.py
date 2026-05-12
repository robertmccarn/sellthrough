from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sellthrough.db import WatchlistRepository
from sellthrough.services.watchlist import (
    add_watchlist_item,
    disable_watchlist_item,
    list_watchlist_items,
)


class WatchlistRepositoryTests(unittest.TestCase):
    def test_add_and_list_active_watchlist_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = WatchlistRepository(Path(temp_dir) / "sellthrough.sqlite3")

            item = repository.add(
                label="DeWalt drill",
                query="dewalt 20v drill",
                category_id="184655",
            )

            rows = repository.list()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0], item)
            self.assertTrue(rows[0].active)

    def test_list_can_include_disabled_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = WatchlistRepository(Path(temp_dir) / "sellthrough.sqlite3")
            item = repository.add(label="TI-84", query="ti-84 plus ce")

            disabled = repository.disable(item.id)

            self.assertTrue(disabled)
            self.assertEqual(repository.list(), ())
            all_rows = repository.list(include_inactive=True)
            self.assertEqual(len(all_rows), 1)
            self.assertFalse(all_rows[0].active)

    def test_disable_missing_row_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = WatchlistRepository(Path(temp_dir) / "sellthrough.sqlite3")

            self.assertFalse(repository.disable(999))


class WatchlistServiceTests(unittest.TestCase):
    def test_add_defaults_query_to_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            item = add_watchlist_item(
                db_path=Path(temp_dir) / "sellthrough.sqlite3",
                label="Sony Walkman",
            )

            self.assertEqual(item.query, "Sony Walkman")

    def test_list_returns_rows_in_id_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            first = add_watchlist_item(db_path=db_path, label="First")
            second = add_watchlist_item(db_path=db_path, label="Second")

            rows = list_watchlist_items(db_path=db_path)

            self.assertEqual([row.id for row in rows], [first.id, second.id])

    def test_disable_rejects_non_positive_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                disable_watchlist_item(
                    db_path=Path(temp_dir) / "sellthrough.sqlite3",
                    watchlist_id=0,
                )


if __name__ == "__main__":
    unittest.main()
