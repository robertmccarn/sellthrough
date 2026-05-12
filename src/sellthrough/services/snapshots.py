"""Metric snapshot services built from active observation lineage.

This is phase-one scaffolding for trend-friendly analytics. Snapshot rows are
captured from current active observations now, while sold-demand fields remain
intentionally pending until Marketplace Insights ingestion is available.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    empty_snapshots: int
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
        sample_limit=1,
    )
    confidence = _active_sample_confidence(scoped.active_count)
    return WatchlistMetricSnapshotRepository(db_path).insert(
        watchlist_id=watchlist_id,
        active_count=scoped.active_count,
        active_price_min=scoped.price_min,
        active_price_median=scoped.price_median,
        active_price_max=scoped.price_max,
        sold_count_30d=None,
        median_sold_price=None,
        sell_through_rate=None,
        sample_confidence=confidence,
    )


def capture_all_watchlist_metric_snapshots(*, db_path: Path) -> CaptureAllSnapshotsResult:
    """Capture snapshots for every active watchlist row."""

    watchlist_rows = list_watchlist_items(db_path=db_path)
    captured_rows: list[WatchlistMetricSnapshotRecord] = []
    empty_snapshots = 0
    for row in watchlist_rows:
        snapshot = capture_watchlist_metric_snapshot(
            db_path=db_path,
            watchlist_id=row.id,
        )
        if snapshot.active_count == 0:
            empty_snapshots += 1
        captured_rows.append(snapshot)

    return CaptureAllSnapshotsResult(
        captured=len(captured_rows),
        empty_snapshots=empty_snapshots,
        rows=tuple(captured_rows),
    )


def _active_sample_confidence(active_count: int) -> str:
    """Map current active sample size into a simple confidence label."""

    if active_count >= 50:
        return "high"
    if active_count >= 15:
        return "medium"
    return "low"
