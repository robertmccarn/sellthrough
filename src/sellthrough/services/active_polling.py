"""Active-listing polling workflow.

This service is the first repeatable ETL loop in SellThrough:

1. Read active watchlist rows from SQLite.
2. Call eBay Browse for each watchlist target.
3. Save each raw Browse response page after sanitization.
4. Normalize the returned item summaries into `active_listings`.

The important boundary is raw-first storage. Normalized rows make the data easy
to query, but the raw response remains available for replay when the transform
logic improves.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Callable

from sellthrough.config import Settings
from sellthrough.ebay.browse import BrowseClient
from sellthrough.services.active_listings import normalize_active_browse_payload
from sellthrough.services.raw_storage import save_raw_api_page
from sellthrough.services.snapshots import capture_all_watchlist_metric_snapshots
from sellthrough.services.watchlist import list_watchlist_items


BROWSE_SEARCH_ENDPOINT = "/buy/browse/v1/item_summary/search"


@dataclass(frozen=True)
class ActivePollResult:
    """Summary of one watchlist row poll."""

    watchlist_id: int
    label: str
    query: str
    raw_response_id: int
    returned: int
    normalized: int


@dataclass(frozen=True)
class ActivePollWorkerCycleResult:
    """Summary of one worker cycle."""

    cycle: int
    polled_watchlist_rows: int
    normalized_rows: int
    snapshot_rows: int


def poll_active_watchlist(
    *,
    settings: Settings,
    marketplace_id: str = "EBAY_US",
    limit: int = 50,
    offset: int = 0,
) -> tuple[ActivePollResult, ...]:
    """Poll active watchlist rows through Browse and normalize the results.

    Args:
        settings: Validated runtime configuration.
        marketplace_id: eBay marketplace header value for Browse.
        limit: Browse page size per watchlist row.
        offset: Browse pagination offset per watchlist row.

    Returns:
        One result row per active watchlist item.
    """

    watchlist_items = list_watchlist_items(db_path=settings.db_path)
    if not watchlist_items:
        return ()

    browse_client = BrowseClient.from_settings(settings, marketplace_id=marketplace_id)
    results: list[ActivePollResult] = []

    for watchlist_item in watchlist_items:
        category_ids = [watchlist_item.category_id] if watchlist_item.category_id else None
        browse_result = browse_client.search_active_items(
            watchlist_item.query,
            limit=limit,
            offset=offset,
            category_ids=category_ids,
        )

        saved = save_raw_api_page(
            db_path=settings.db_path,
            source="browse_watchlist",
            endpoint=BROWSE_SEARCH_ENDPOINT,
            request_url=browse_result.href or "",
            response_json=browse_result.raw_payload,
            query=watchlist_item.query,
            category_id=watchlist_item.category_id,
        )
        normalized_count = normalize_active_browse_payload(
            db_path=settings.db_path,
            raw_response_id=saved.raw_response_id,
            payload=browse_result.raw_payload,
            watchlist_id=watchlist_item.id,
            query=browse_result.query,
            limit=browse_result.limit,
            offset=browse_result.offset,
        )
        results.append(
            ActivePollResult(
                watchlist_id=watchlist_item.id,
                label=watchlist_item.label,
                query=watchlist_item.query,
                raw_response_id=saved.raw_response_id,
                returned=len(browse_result.items),
                normalized=normalized_count,
            )
        )

    return tuple(results)


def run_active_poll_worker(
    *,
    settings: Settings,
    marketplace_id: str = "EBAY_US",
    limit: int = 50,
    offset: int = 0,
    interval_seconds: int = 300,
    cycles: int = 1,
    capture_snapshots: bool = True,
    sleep_fn: Callable[[float], None] = sleep,
) -> tuple[ActivePollWorkerCycleResult, ...]:
    """Run periodic active polling cycles with optional snapshot capture.

    This simple loop is an MVP worker: deterministic, local-first, and easy to
    run under task schedulers without introducing a queue framework yet.
    """

    if interval_seconds < 1:
        raise ValueError("Worker interval_seconds must be at least 1.")
    if cycles < 1:
        raise ValueError("Worker cycles must be at least 1.")

    cycle_results: list[ActivePollWorkerCycleResult] = []
    for cycle in range(1, cycles + 1):
        poll_results = poll_active_watchlist(
            settings=settings,
            marketplace_id=marketplace_id,
            limit=limit,
            offset=offset,
        )
        normalized_rows = sum(result.normalized for result in poll_results)
        snapshot_rows = 0
        if capture_snapshots:
            snapshot_result = capture_all_watchlist_metric_snapshots(db_path=settings.db_path)
            snapshot_rows = len(snapshot_result.rows)

        cycle_results.append(
            ActivePollWorkerCycleResult(
                cycle=cycle,
                polled_watchlist_rows=len(poll_results),
                normalized_rows=normalized_rows,
                snapshot_rows=snapshot_rows,
            )
        )

        if cycle < cycles:
            sleep_fn(interval_seconds)

    return tuple(cycle_results)
