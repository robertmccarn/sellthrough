from __future__ import annotations

import argparse
from pathlib import Path

from sellthrough.config import Settings, SettingsError
from sellthrough.db import initialize_database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sellthrough",
        description="eBay resale market intelligence tools",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Inspect local config")
    config_parser.add_argument("action", choices=["check"])

    db_parser = subparsers.add_parser("db", help="Database utilities")
    db_parser.add_argument("action", choices=["init"])
    db_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Override the SQLite database path",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config" and args.action == "check":
        try:
            settings = Settings.from_environment()
        except SettingsError as exc:
            parser.error(str(exc))
        print(settings.redacted_summary())
        return 0

    if args.command == "db" and args.action == "init":
        settings = Settings.from_environment(require_ebay_credentials=False)
        db_path = args.path or settings.db_path
        initialize_database(db_path)
        print(f"Initialized database at {db_path}")
        return 0

    parser.error("Unsupported command")
    return 2
