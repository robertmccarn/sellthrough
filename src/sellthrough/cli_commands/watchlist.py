from __future__ import annotations

import argparse

from sellthrough.config import Settings, SettingsError
from sellthrough.services.watchlist import (
    add_watchlist_item,
    disable_watchlist_item,
    list_watchlist_items,
)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    watchlist_parser = subparsers.add_parser("watchlist", help="Manage sourcing watchlist rows")
    watchlist_subparsers = watchlist_parser.add_subparsers(dest="action", required=True)

    watchlist_add = watchlist_subparsers.add_parser("add", help="Add a watchlist row")
    watchlist_add.add_argument("label", help="Human-readable label")
    watchlist_add.add_argument(
        "--query",
        default=None,
        help="Search query; defaults to the label",
    )
    watchlist_add.add_argument(
        "--category-id",
        default=None,
        help="Optional eBay category ID",
    )
    watchlist_add.set_defaults(handler=handle_add)

    watchlist_list = watchlist_subparsers.add_parser("list", help="List watchlist rows")
    watchlist_list.add_argument(
        "--all",
        action="store_true",
        dest="include_inactive",
        help="Include disabled rows",
    )
    watchlist_list.set_defaults(handler=handle_list)

    watchlist_disable = watchlist_subparsers.add_parser(
        "disable",
        help="Disable a watchlist row without deleting it",
    )
    watchlist_disable.add_argument("id", type=int, help="Watchlist row ID")
    watchlist_disable.set_defaults(handler=handle_disable)


def handle_add(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        settings = Settings.from_environment(require_ebay_credentials=False)
        item = add_watchlist_item(
            db_path=settings.db_path,
            label=args.label,
            query=args.query,
            category_id=args.category_id,
        )
    except (SettingsError, ValueError) as exc:
        parser.error(str(exc))

    print(
        f"Added watchlist item {item.id}: {item.label} "
        f"(query={item.query}, category_id={item.category_id or 'none'})"
    )
    return 0


def handle_list(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        settings = Settings.from_environment(require_ebay_credentials=False)
        items = list_watchlist_items(
            db_path=settings.db_path,
            include_inactive=args.include_inactive,
        )
    except (SettingsError, ValueError) as exc:
        parser.error(str(exc))

    if not items:
        print("No watchlist items found.")
        return 0

    print("ID\tActive\tLabel\tQuery\tCategory ID\tAdded")
    for item in items:
        active = "yes" if item.active else "no"
        print(
            f"{item.id}\t{active}\t{item.label}\t{item.query}\t"
            f"{item.category_id or ''}\t{item.added_at}"
        )
    return 0


def handle_disable(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        settings = Settings.from_environment(require_ebay_credentials=False)
        disabled = disable_watchlist_item(db_path=settings.db_path, watchlist_id=args.id)
    except (SettingsError, ValueError) as exc:
        parser.error(str(exc))

    if disabled:
        print(f"Disabled watchlist item {args.id}.")
        return 0
    print(f"No active watchlist item found for ID {args.id}.")
    return 1
