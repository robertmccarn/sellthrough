"""Dashboard-summary service contract for future UI surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sellthrough.db import (
    ActiveListingSample,
    ActiveListingRepository,
    PollRunSummary,
    RawResponseRepository,
    RawResponseSummary,
    WatchlistMetricSnapshotRepository,
    WatchlistRepository,
)


@dataclass(frozen=True)
class DashboardSnapshotPreviewRow:
    """Recent active-side snapshot row prepared for dashboard rendering."""

    watchlist_label: str
    active_count: int
    active_price_median: float | None
    sample_confidence: str | None
    captured_at: str


@dataclass(frozen=True)
class DashboardSummary:
    """Top-level dashboard snapshot for local status and freshness views."""

    active_listing_count: int
    watchlist_count: int
    latest_poll_run: PollRunSummary | None
    latest_raw_response: RawResponseSummary | None
    recent_failed_poll_count: int
    sample_recent_active_listings: tuple[ActiveListingSample, ...]
    recent_snapshot_rows: tuple[DashboardSnapshotPreviewRow, ...]
    sold_metrics_status: str
    opportunity_metrics_status: str


def get_dashboard_summary(db_path: Path) -> DashboardSummary:
    """Return a web-friendly summary of current pipeline state.

    This service intentionally returns concrete status values for sold and
    opportunity metrics so downstream UI callers can render roadmap-aware
    placeholders without encoding project state rules in the frontend.
    """

    raw_repository = RawResponseRepository(db_path)
    active_repository = ActiveListingRepository(db_path)
    watchlist_repository = WatchlistRepository(db_path)
    snapshot_repository = WatchlistMetricSnapshotRepository(db_path)
    watchlist_labels = {row.id: row.label for row in watchlist_repository.list(include_inactive=True)}
    snapshot_rows = snapshot_repository.list_recent(limit=5)
    return DashboardSummary(
        active_listing_count=active_repository.count(),
        watchlist_count=watchlist_repository.count(),
        latest_poll_run=raw_repository.get_latest_completed_poll_run(),
        latest_raw_response=raw_repository.get_latest_raw_response(),
        recent_failed_poll_count=raw_repository.count_failed_poll_runs(days_back=7),
        sample_recent_active_listings=active_repository.list_recent(sample_limit=5),
        recent_snapshot_rows=tuple(
            DashboardSnapshotPreviewRow(
                watchlist_label=watchlist_labels.get(row.watchlist_id, f"Watchlist {row.watchlist_id}"),
                active_count=row.active_count,
                active_price_median=row.active_price_median,
                sample_confidence=row.sample_confidence,
                captured_at=row.captured_at,
            )
            for row in snapshot_rows
        ),
        sold_metrics_status="pending",
        opportunity_metrics_status="pending",
    )
