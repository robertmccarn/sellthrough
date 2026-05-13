from dataclasses import dataclass
from pathlib import Path

from sellthrough.config import Settings
from sellthrough.db import ActiveListingRepository, RawResponseRepository, WatchlistRepository
from sellthrough.services.dashboard import get_dashboard_summary
from sellthrough.services.lookup import (
    lookup_active_listings,
    lookup_watchlist_active_listings,
)


@dataclass(frozen=True)
class HealthSummary:
    database_path: str
    database_exists: bool
    raw_responses_count: int
    active_listings_count: int
    watchlist_count: int
    browse_credentials_configured: bool
    marketplace_insights_status: str


def create_health_summary(settings: Settings) -> HealthSummary:
    database_exists = settings.db_path.exists()
    raw_repository = RawResponseRepository(settings.db_path)
    active_repository = ActiveListingRepository(settings.db_path)
    watchlist_repository = WatchlistRepository(settings.db_path)
    return HealthSummary(
        database_path=str(settings.db_path),
        database_exists=database_exists,
        raw_responses_count=raw_repository.count_raw_responses(),
        active_listings_count=active_repository.count(),
        watchlist_count=watchlist_repository.count(),
        browse_credentials_configured=bool(
            settings.ebay_client_id and settings.ebay_client_secret and settings.ebay_dev_id
        ),
        marketplace_insights_status="pending",
    )


def create_app(*, settings: Settings):
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import HTMLResponse, JSONResponse
        from fastapi.staticfiles import StaticFiles
        from fastapi.templating import Jinja2Templates
    except ImportError as exc:  # pragma: no cover - covered via CLI import guard
        raise RuntimeError(
            "Web dependencies missing. Install with: python -m pip install -e .[web]"
        ) from exc

    app = FastAPI(title="SellThrough Local Web")
    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).parent / "static")),
        name="static",
    )

    @app.get("/health", response_class=JSONResponse)
    def health() -> JSONResponse:
        summary = create_health_summary(settings)
        return JSONResponse(
            {
                "database_path": summary.database_path,
                "database_path_exists": summary.database_exists,
                "raw_responses_count": summary.raw_responses_count,
                "active_listings_count": summary.active_listings_count,
                "watchlist_count": summary.watchlist_count,
                "browse_credentials_configured": summary.browse_credentials_configured,
                "marketplace_insights_status": summary.marketplace_insights_status,
            }
        )

    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        summary = get_dashboard_summary(settings.db_path)
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={"summary": summary},
        )

    @app.get("/watchlist", response_class=HTMLResponse)
    def watchlist(request: Request) -> HTMLResponse:
        rows = WatchlistRepository(settings.db_path).list(include_inactive=True)
        return templates.TemplateResponse(
            request=request,
            name="watchlist.html",
            context={"rows": rows},
        )

    @app.get("/lookup", response_class=HTMLResponse)
    def lookup(
        request: Request,
        mode: str = "active",
        query: str = "",
        watchlist_id: int | None = None,
        samples: int = 5,
    ) -> HTMLResponse:
        rows = WatchlistRepository(settings.db_path).list(include_inactive=False)
        lookup_error: str | None = None
        lookup_notice: str | None = None
        active_result = None
        watchlist_result = None
        samples = max(1, samples)

        try:
            if mode == "watchlist" and watchlist_id is not None:
                watchlist_result = lookup_watchlist_active_listings(
                    db_path=settings.db_path,
                    watchlist_id=watchlist_id,
                    sample_limit=samples,
                )
            elif mode == "active" and query.strip():
                active_result = lookup_active_listings(
                    db_path=settings.db_path,
                    query=query,
                    sample_limit=samples,
                )
            elif mode == "active":
                lookup_notice = "Enter a title query to run an active lookup."
            elif mode == "watchlist":
                lookup_notice = "Select a watchlist row to run a watchlist-scoped lookup."
        except ValueError as exc:
            lookup_error = str(exc)

        return templates.TemplateResponse(
            request=request,
            name="lookup.html",
            context={
                "watchlist_rows": rows,
                "mode": mode,
                "query": query,
                "watchlist_id": watchlist_id,
                "samples": samples,
                "lookup_error": lookup_error,
                "lookup_notice": lookup_notice,
                "active_result": active_result,
                "watchlist_result": watchlist_result,
            },
        )

    return app
