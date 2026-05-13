from __future__ import annotations

import argparse

from sellthrough.config import Settings, SettingsError
from sellthrough.ebay.client import EbayApiError
from sellthrough.services.active_polling import poll_active_watchlist, run_active_poll_worker
from sellthrough.services.snapshots import capture_all_watchlist_metric_snapshots
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

    watchlist_poll = watchlist_subparsers.add_parser(
        "poll-active",
        help="Poll active watchlist rows through Browse and store results",
    )
    watchlist_poll.add_argument("--limit", type=int, default=50, help="Browse page size per row")
    watchlist_poll.add_argument("--offset", type=int, default=0, help="Browse offset per row")
    watchlist_poll.add_argument(
        "--marketplace",
        default="EBAY_US",
        help="eBay marketplace ID, default EBAY_US",
    )
    watchlist_poll.set_defaults(handler=handle_poll_active)

    watchlist_worker = watchlist_subparsers.add_parser(
        "run-worker",
        help="Run periodic watchlist polling cycles in a local worker loop",
    )
    watchlist_worker.add_argument("--limit", type=int, default=50, help="Browse page size per row")
    watchlist_worker.add_argument("--offset", type=int, default=0, help="Browse offset per row")
    watchlist_worker.add_argument(
        "--marketplace",
        default="EBAY_US",
        help="eBay marketplace ID, default EBAY_US",
    )
    watchlist_worker.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Seconds to wait between cycles",
    )
    watchlist_worker.add_argument(
        "--cycles",
        type=int,
        default=1,
        help="How many polling cycles to run before exiting",
    )
    watchlist_worker.add_argument(
        "--no-snapshots",
        action="store_true",
        help="Skip snapshot capture after each polling cycle",
    )
    watchlist_worker.set_defaults(handler=handle_run_worker)

    watchlist_snapshots = watchlist_subparsers.add_parser(
        "capture-snapshots",
        help="Capture watchlist metric snapshots from current active observations",
    )
    watchlist_snapshots.set_defaults(handler=handle_capture_snapshots)


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


def handle_poll_active(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        settings = Settings.from_environment()
        results = poll_active_watchlist(
            settings=settings,
            marketplace_id=args.marketplace,
            limit=args.limit,
            offset=args.offset,
        )
    except (SettingsError, EbayApiError, ValueError) as exc:
        parser.error(str(exc))

    if not results:
        print("No active watchlist items found.")
        return 0

    print("Watchlist ID\tLabel\tReturned\tNormalized\tRaw Response ID")
    for result in results:
        print(
            f"{result.watchlist_id}\t{result.label}\t{result.returned}\t"
            f"{result.normalized}\t{result.raw_response_id}"
        )
    return 0


def handle_capture_snapshots(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        settings = Settings.from_environment(require_ebay_credentials=False)
        result = capture_all_watchlist_metric_snapshots(db_path=settings.db_path)
    except (SettingsError, ValueError) as exc:
        parser.error(str(exc))

    if not result.rows:
        print("No active watchlist items found.")
        return 0

    print("Watchlist ID\tActive Count\tActive Median\tConfidence\tCaptured At")
    for row in result.rows:
        median_value = f"{row.active_price_median:.2f}" if row.active_price_median is not None else "n/a"
        print(
            f"{row.watchlist_id}\t{row.active_count}\t{median_value}\t"
            f"{row.sample_confidence or 'n/a'}\t{row.captured_at}"
        )
    return 0


def handle_run_worker(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        settings = Settings.from_environment()
        cycle_results = run_active_poll_worker(
            settings=settings,
            marketplace_id=args.marketplace,
            limit=args.limit,
            offset=args.offset,
            interval_seconds=args.interval_seconds,
            cycles=args.cycles,
            capture_snapshots=not args.no_snapshots,
        )
    except (SettingsError, EbayApiError, ValueError) as exc:
        parser.error(str(exc))

    print("Cycle\tPolled Rows\tNormalized Rows\tSnapshot Rows")
    for result in cycle_results:
        print(
            f"{result.cycle}\t{result.polled_watchlist_rows}\t"
            f"{result.normalized_rows}\t{result.snapshot_rows}"
        )
    return 0
