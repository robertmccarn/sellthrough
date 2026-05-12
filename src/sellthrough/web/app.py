from dataclasses import dataclass
from pathlib import Path

from sellthrough.config import Settings
from sellthrough.db import ActiveListingRepository, RawResponseRepository, WatchlistRepository
from sellthrough.services.dashboard import get_dashboard_summary


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
    def lookup(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="lookup.html",
            context={},
        )

    return app
