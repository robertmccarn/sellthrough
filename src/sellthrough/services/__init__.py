"""Application service layer.

Services sit between interfaces such as CLI/web routes and lower-level clients
or repositories. This keeps user workflows reusable: the CLI, a future local web
console, and eventual hosted/mobile surfaces can call the same use-case code.
"""

from sellthrough.services.dashboard import DashboardSummary, get_dashboard_summary

__all__ = [
    "DashboardSummary",
    "get_dashboard_summary",
]
