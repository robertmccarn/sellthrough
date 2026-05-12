from __future__ import annotations

import argparse
from pathlib import Path

from sellthrough.config import Settings
from sellthrough.db import initialize_database


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    db_parser = subparsers.add_parser("db", help="Database utilities")
    init_parser = db_parser.add_subparsers(dest="action", required=True)
    init = init_parser.add_parser("init")
    init.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Override the SQLite database path",
    )
    init.set_defaults(handler=handle_init)


def handle_init(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    settings = Settings.from_environment(require_ebay_credentials=False)
    db_path = args.path or settings.db_path
    initialize_database(db_path)
    print(f"Initialized database at {db_path}")
    return 0
