from __future__ import annotations

import argparse

from sellthrough.config import Settings, SettingsError
from sellthrough.db import ActiveListingSample
from sellthrough.services.lookup import (
    lookup_active_listings,
    lookup_watchlist_active_listings,
)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    lookup_parser = subparsers.add_parser("lookup", help="Query normalized listing data")
    lookup_subparsers = lookup_parser.add_subparsers(dest="action", required=True)

    active_parser = lookup_subparsers.add_parser(
        "active",
        help="Title-search normalized active listings",
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
        help="Summarize active listings scoped to one watchlist row",
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
    _print_pending_sold_metrics()
    _print_active_price_summary(
        price_min=result.price_min,
        price_median=result.price_median,
        price_max=result.price_max,
        currency=result.price_currency,
        median_label="Active median price",
    )
    _print_sample_listings(result.samples)
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
    _print_pending_sold_metrics()
    _print_active_price_summary(
        price_min=result.price_min,
        price_median=result.price_median,
        price_max=result.price_max,
        currency=result.price_currency,
        median_label="Median active price",
    )
    _print_sample_listings(result.samples)
    return 0


def _print_pending_sold_metrics() -> None:
    """Keep CLI output honest until Marketplace Insights ingestion exists."""

    print("Sold metrics: pending Marketplace Insights access")


def _print_active_price_summary(
    *,
    price_min: float | None,
    price_median: float | None,
    price_max: float | None,
    currency: str | None,
    median_label: str,
) -> None:
    """Print active price stats in the shared lookup format."""

    if price_min is None or price_median is None or price_max is None:
        print("Active price range: unavailable")
        print(f"{median_label}: unavailable")
        return

    display_currency = currency or "unknown"
    print(f"Active price range: {price_min:.2f} - {price_max:.2f} {display_currency}")
    print(f"{median_label}: {price_median:.2f} {display_currency}")


def _print_sample_listings(samples: tuple[ActiveListingSample, ...]) -> None:
    """Print normalized active-listing samples in one shared CLI format."""

    print()
    if not samples:
        print("No sample listings found.")
        return

    print("Sample listings:")
    for index, item in enumerate(samples, start=1):
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
