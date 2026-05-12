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
    WatchlistRepository,
)


@dataclass(frozen=True)
class DashboardSummary:
    """Top-level dashboard snapshot for local status and freshness views."""

    active_listing_count: int
    watchlist_count: int
    latest_poll_run: PollRunSummary | None
    latest_raw_response: RawResponseSummary | None
    recent_failed_poll_count: int
    sample_recent_active_listings: tuple[ActiveListingSample, ...]
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
    return DashboardSummary(
        active_listing_count=active_repository.count(),
        watchlist_count=watchlist_repository.count(),
        latest_poll_run=raw_repository.get_latest_completed_poll_run(),
        latest_raw_response=raw_repository.get_latest_raw_response(),
        recent_failed_poll_count=raw_repository.count_failed_poll_runs(days_back=7),
        sample_recent_active_listings=active_repository.list_recent(sample_limit=5),
        sold_metrics_status="pending",
        opportunity_metrics_status="pending",
    )
