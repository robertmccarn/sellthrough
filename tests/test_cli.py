from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from contextlib import redirect_stdout
from pathlib import Path

from sellthrough.cli import build_parser, main
from sellthrough.cli_commands import lookup, watchlist, web


class CliParserTests(unittest.TestCase):
    def test_nested_command_sets_handler(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["watchlist", "list", "--all"])

        self.assertIs(args.handler, watchlist.handle_list)
        self.assertTrue(args.include_inactive)

    def test_poll_active_command_sets_polling_handler(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["watchlist", "poll-active", "--limit", "25"])

        self.assertIs(args.handler, watchlist.handle_poll_active)
        self.assertEqual(args.limit, 25)

    def test_capture_snapshots_command_sets_handler(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["watchlist", "capture-snapshots"])

        self.assertIs(args.handler, watchlist.handle_capture_snapshots)

    def test_run_worker_command_sets_handler(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["watchlist", "run-worker", "--cycles", "2"])

        self.assertIs(args.handler, watchlist.handle_run_worker)
        self.assertEqual(args.cycles, 2)

    def test_lookup_active_command_sets_lookup_handler(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["lookup", "active", "dewalt drill", "--samples", "3"])

        self.assertIs(args.handler, lookup.handle_active)
        self.assertEqual(args.query, "dewalt drill")
        self.assertEqual(args.samples, 3)

    def test_lookup_watchlist_command_sets_lookup_handler(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["lookup", "watchlist", "1", "--samples", "4"])

        self.assertIs(args.handler, lookup.handle_watchlist)
        self.assertEqual(args.watchlist_id, 1)
        self.assertEqual(args.samples, 4)

    def test_web_serve_command_sets_web_handler(self) -> None:
        parser = build_parser()

        args = parser.parse_args(["web", "serve", "--port", "9000"])

        self.assertIs(args.handler, web.handle_serve)
        self.assertEqual(args.port, 9000)


class CliMainTests(unittest.TestCase):
    def test_db_init_command_uses_path_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            output = io.StringIO()

            with redirect_stdout(output):
                result = main(["db", "init", "--path", str(db_path)])

            self.assertEqual(result, 0)
            self.assertIn(f"Initialized database at {db_path}", output.getvalue())
            with closing(sqlite3.connect(db_path)) as connection:
                table_names = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            self.assertIn("raw_api_responses", table_names)


if __name__ == "__main__":
    unittest.main()
