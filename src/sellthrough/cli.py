from __future__ import annotations

import argparse
from pathlib import Path

from sellthrough.config import Settings, SettingsError
from sellthrough.db import initialize_database
from sellthrough.ebay.browse import BrowseClient
from sellthrough.ebay.client import EbayApiError


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

    browse_parser = subparsers.add_parser("browse", help="Browse API utilities")
    browse_subparsers = browse_parser.add_subparsers(dest="action", required=True)
    search_parser = browse_subparsers.add_parser("search", help="Search active eBay listings")
    search_parser.add_argument("query", help="Keyword search text, such as 'dewalt drill'")
    search_parser.add_argument("--limit", type=int, default=5, help="Results to return")
    search_parser.add_argument("--offset", type=int, default=0, help="Pagination offset")
    search_parser.add_argument(
        "--marketplace",
        default="EBAY_US",
        help="eBay marketplace ID, default EBAY_US",
    )
    search_parser.add_argument(
        "--category-id",
        action="append",
        dest="category_ids",
        help="Optional category ID filter; repeat for multiple categories",
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

    if args.command == "browse" and args.action == "search":
        try:
            settings = Settings.from_environment()
            client = BrowseClient.from_settings(settings, marketplace_id=args.marketplace)
            result = client.search_active_items(
                args.query,
                limit=args.limit,
                offset=args.offset,
                category_ids=args.category_ids,
            )
        except (SettingsError, EbayApiError, ValueError) as exc:
            parser.error(str(exc))

        print(f"Query: {result.query}")
        print(f"Total active results: {result.total}")
        print(f"Returned: {len(result.items)}")
        if result.warnings:
            print("Warnings:")
            for warning in result.warnings:
                print(f"- {warning.get('errorId')}: {warning.get('message')}")
        print()
        for index, item in enumerate(result.items, start=1):
            price = (
                f"{item.price_value:.2f} {item.price_currency}"
                if item.price_value is not None and item.price_currency
                else "price unavailable"
            )
            print(f"{index}. {item.title}")
            print(f"   {price} | condition={item.condition or 'unknown'}")
            print(f"   item_id={item.item_id}")
            if item.item_web_url:
                print(f"   url={item.item_web_url}")
        return 0

    parser.error("Unsupported command")
    return 2
