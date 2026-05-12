"""Service orchestration for SellThrough smoke checks.

Smoke checks answer "can the major pieces talk to each other?" rather than
"does every edge case work?" This service is intentionally shallow: one config
check, one DB bootstrap, one Browse call, one Taxonomy call, and one Marketplace
Insights probe.
"""

from __future__ import annotations

from dataclasses import dataclass

from sellthrough.config import Settings
from sellthrough.db import initialize_database
from sellthrough.ebay.browse import BrowseClient
from sellthrough.ebay.marketplace_insights import (
    MarketplaceInsightsAccessError,
    MarketplaceInsightsClient,
)
from sellthrough.ebay.taxonomy import TaxonomyClient
from sellthrough.services.raw_storage import save_raw_api_page


@dataclass(frozen=True)
class SmokeCheck:
    """One line of smoke-check output.

    `status` stays text rather than an enum to keep CLI formatting simple and
    readable. The accepted values are `PASS`, `WARN`, and `FAIL`.
    """

    name: str
    status: str
    detail: str


def run_smoke_checks(
    *,
    settings: Settings,
    query: str,
    limit: int,
    marketplace_id: str,
    save_raw: bool = False,
) -> list[SmokeCheck]:
    """Run the shallow end-to-end health check used by the CLI.

    This service intentionally returns structured check rows instead of printing
    so future web routes can render the same facts without shell parsing.

    Side effects:
        Initializes the local database, may call live eBay APIs, and optionally
        stores the raw Browse response page.
    """

    # Accumulate structured facts first, then let the interface layer decide how
    # to render them. This is the same separation used throughout the app:
    # services return data, CLI modules print text.
    checks: list[SmokeCheck] = [
        SmokeCheck(
            "config",
            "PASS",
            f"environment={settings.ebay_env}; db={settings.db_path}",
        )
    ]

    initialize_database(settings.db_path)
    checks.append(SmokeCheck("sqlite", "PASS", "schema initialized"))

    browse_client = BrowseClient.from_settings(settings, marketplace_id=marketplace_id)
    browse_result = browse_client.search_active_items(query, limit=limit)
    checks.append(
        SmokeCheck(
            "browse",
            "PASS",
            f"{browse_result.total} active results; returned {len(browse_result.items)}",
        )
    )

    if save_raw:
        # The smoke command saves only the Browse response for now because
        # Marketplace Insights may be access-blocked during normal development.
        saved = save_raw_api_page(
            db_path=settings.db_path,
            source="browse_smoke",
            endpoint="/buy/browse/v1/item_summary/search",
            request_url=browse_result.href or "",
            response_json=browse_result.raw_payload,
            query=query,
        )
        checks.append(
            SmokeCheck(
                "raw storage",
                "PASS",
                f"saved Browse response as raw_api_responses.id={saved.raw_response_id}",
            )
        )

    taxonomy_client = TaxonomyClient.from_settings(settings)
    tree = taxonomy_client.get_default_category_tree_id(marketplace_id=marketplace_id)
    checks.append(
        SmokeCheck(
            "taxonomy",
            "PASS",
            f"{tree.marketplace_id} tree={tree.category_tree_id} version={tree.category_tree_version}",
        )
    )

    insights_client = MarketplaceInsightsClient.from_settings(
        settings,
        marketplace_id=marketplace_id,
    )
    try:
        insights_result = insights_client.search_sold_items(query, limit=limit)
        checks.append(
            SmokeCheck(
                "marketplace insights",
                "PASS",
                f"{insights_result.total} sold results; access approved",
            )
        )
    except MarketplaceInsightsAccessError:
        # Access pending is not treated as a hard smoke failure because it is a
        # known account approval state. The rest of the stack can still be
        # healthy while this one product permission is unavailable.
        checks.append(
            SmokeCheck(
                "marketplace insights",
                "WARN",
                "access pending; Application Growth Check approval still required",
            )
        )

    return checks


def format_smoke_checks(checks: list[SmokeCheck]) -> str:
    """Render smoke checks as compact terminal-friendly text.

    Formatting is deliberately tiny and deterministic so tests can compare the
    exact string. Any richer presentation can be built by consuming the
    structured `SmokeCheck` rows directly.
    """

    return "\n".join(f"[{check.status}] {check.name}: {check.detail}" for check in checks)
