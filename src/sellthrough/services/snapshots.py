"""Metric snapshot services built from active observation lineage.

This is phase-one scaffolding for trend-friendly analytics. Snapshot rows are
captured from current active observations now, while sold-demand fields remain
intentionally pending until Marketplace Insights ingestion is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median

from sellthrough.db import (
    WatchlistMetricSnapshotRecord,
    WatchlistMetricSnapshotRepository,
)
from sellthrough.services.lookup import lookup_watchlist_active_listings
from sellthrough.services.watchlist import list_watchlist_items


@dataclass(frozen=True)
class CaptureAllSnapshotsResult:
    """Summary of a batch snapshot capture run."""

    captured: int
    skipped: int
    rows: tuple[WatchlistMetricSnapshotRecord, ...]


def capture_watchlist_metric_snapshot(
    *,
    db_path: Path,
    watchlist_id: int,
) -> WatchlistMetricSnapshotRecord:
    """Capture one watchlist snapshot from normalized active listing state."""

    scoped = lookup_watchlist_active_listings(
        db_path=db_path,
        watchlist_id=watchlist_id,
        sample_limit=200,
    )
    prices = [
        sample.price_value for sample in scoped.samples if sample.price_value is not None
    ]
    # The scoped lookup samples may be truncated by sample limit; when present
    # we use the aggregate metrics already computed at repository level.
    active_price_min = scoped.price_min
    active_price_median = scoped.price_median
    active_price_max = scoped.price_max
    if scoped.active_count == 0 and prices:
        # Defensive fallback for future refactors of scoped lookup behavior.
        active_price_min = min(prices)
        active_price_median = float(median(prices))
        active_price_max = max(prices)

    confidence = _active_sample_confidence(scoped.active_count)
    return WatchlistMetricSnapshotRepository(db_path).insert(
        watchlist_id=watchlist_id,
        active_count=scoped.active_count,
        active_price_min=active_price_min,
        active_price_median=active_price_median,
        active_price_max=active_price_max,
        sold_count_30d=None,
        median_sold_price=None,
        sell_through_rate=None,
        sample_confidence=confidence,
    )


def capture_all_watchlist_metric_snapshots(*, db_path: Path) -> CaptureAllSnapshotsResult:
    """Capture snapshots for every active watchlist row."""

    watchlist_rows = list_watchlist_items(db_path=db_path)
    captured_rows: list[WatchlistMetricSnapshotRecord] = []
    skipped = 0
    for row in watchlist_rows:
        try:
            captured_rows.append(
                capture_watchlist_metric_snapshot(
                    db_path=db_path,
                    watchlist_id=row.id,
                )
            )
        except ValueError:
            # If a watchlist row has never produced observations yet, we still
            # write a zero snapshot so trend series can start immediately.
            captured_rows.append(
                WatchlistMetricSnapshotRepository(db_path).insert(
                    watchlist_id=row.id,
                    active_count=0,
                    active_price_min=None,
                    active_price_median=None,
                    active_price_max=None,
                    sold_count_30d=None,
                    median_sold_price=None,
                    sell_through_rate=None,
                    sample_confidence="low",
                )
            )
            skipped += 1

    return CaptureAllSnapshotsResult(
        captured=len(captured_rows),
        skipped=skipped,
        rows=tuple(captured_rows),
    )


def _active_sample_confidence(active_count: int) -> str:
    """Map current active sample size into a simple confidence label."""

    if active_count >= 50:
        return "high"
    if active_count >= 15:
        return "medium"
    return "low"
