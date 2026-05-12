"""Application service layer.

Services sit between interfaces such as CLI/web routes and lower-level clients
or repositories. This keeps user workflows reusable: the CLI, a future local web
console, and eventual hosted/mobile surfaces can call the same use-case code.
"""

from sellthrough.services.dashboard import DashboardSummary, get_dashboard_summary
from sellthrough.services.snapshots import (
    CaptureAllSnapshotsResult,
    capture_all_watchlist_metric_snapshots,
    capture_watchlist_metric_snapshot,
)

__all__ = [
    "CaptureAllSnapshotsResult",
    "DashboardSummary",
    "capture_all_watchlist_metric_snapshots",
    "capture_watchlist_metric_snapshot",
    "get_dashboard_summary",
]
