from __future__ import annotations

import argparse

from sellthrough.config import Settings, SettingsError
from sellthrough.services.lookup import (
    lookup_active_listings,
    lookup_watchlist_active_listings,
)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    lookup_parser = subparsers.add_parser("lookup", help="Query normalized listing data")
    lookup_subparsers = lookup_parser.add_subparsers(dest="action", required=True)

    active_parser = lookup_subparsers.add_parser(
        "active",
        help="Summarize normalized active listings",
    )
    active_parser.add_argument("query", help="Title text to search in active_listings")
    active_parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Sample listings to print",
    )
    active_parser.set_defaults(handler=handle_active)

    watchlist_parser = lookup_subparsers.add_parser(
        "watchlist",
        help="Summarize normalized active listings for one watchlist row",
    )
    watchlist_parser.add_argument("watchlist_id", type=int, help="Watchlist row ID")
    watchlist_parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Sample listings to print",
    )
    watchlist_parser.set_defaults(handler=handle_watchlist)


def handle_active(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        settings = Settings.from_environment(require_ebay_credentials=False)
        result = lookup_active_listings(
            db_path=settings.db_path,
            query=args.query,
            sample_limit=args.samples,
        )
    except (SettingsError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Query: {result.query}")
    print(f"Active listings: {result.active_count}")
    print(f"Last seen: {result.last_seen_at or 'none'}")
    print(f"Sold metrics: pending Marketplace Insights access")
    if result.price_min is None:
        print("Active price range: unavailable")
        print("Active median price: unavailable")
    else:
        currency = result.price_currency or "unknown"
        print(
            "Active price range: "
            f"{result.price_min:.2f} - {result.price_max:.2f} {currency}"
        )
        print(f"Active median price: {result.price_median:.2f} {currency}")

    if not result.samples:
        print()
        print("No sample listings found.")
        return 0

    print()
    print("Sample listings:")
    for index, item in enumerate(result.samples, start=1):
        price = (
            f"{item.price_value:.2f} {item.price_currency}"
            if item.price_value is not None and item.price_currency
            else "price unavailable"
        )
        print(f"{index}. {item.title}")
        print(f"   {price} | condition={item.condition or 'unknown'}")
        print(f"   item_id={item.item_id} | last_seen={item.last_seen_at}")
        if item.item_web_url:
            print(f"   url={item.item_web_url}")
    return 0


def handle_watchlist(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        settings = Settings.from_environment(require_ebay_credentials=False)
        result = lookup_watchlist_active_listings(
            db_path=settings.db_path,
            watchlist_id=args.watchlist_id,
            sample_limit=args.samples,
        )
    except (SettingsError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Watchlist: {result.watchlist_label}")
    print(f"Query: {result.watchlist_query}")
    print(f"Active listings: {result.active_count}")
    print(f"Latest poll: {result.latest_poll_at or 'none'}")
    print("Sold metrics: pending Marketplace Insights access")
    if result.price_min is None:
        print("Active price range: unavailable")
        print("Active median price: unavailable")
    else:
        currency = result.price_currency or "unknown"
        print(f"Active price range: {result.price_min:.2f} - {result.price_max:.2f} {currency}")
        print(f"Median active price: {result.price_median:.2f} {currency}")

    if not result.samples:
        print()
        print("No sample listings found.")
        return 0

    print()
    print("Sample listings:")
    for index, item in enumerate(result.samples, start=1):
        price = (
            f"{item.price_value:.2f} {item.price_currency}"
            if item.price_value is not None and item.price_currency
            else "price unavailable"
        )
        print(f"{index}. {item.title}")
        print(f"   {price} | condition={item.condition or 'unknown'}")
        print(f"   item_id={item.item_id} | last_seen={item.last_seen_at}")
        if item.item_web_url:
            print(f"   url={item.item_web_url}")
    return 0
