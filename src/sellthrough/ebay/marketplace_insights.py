"""Marketplace Insights adapter for sold-item history.

Marketplace Insights is SellThrough's future source for historical sold
listings. Access is currently pending eBay approval, but designing this adapter
now lets the rest of the pipeline depend on a stable internal interface instead
of scattering endpoint details and access-state assumptions through the code.

The public shape intentionally mirrors `BrowseClient`: both clients return a
page object containing normalized summaries plus the original raw payload. That
symmetry is valuable for ETL because active and sold pulls can share pagination,
raw storage, and later normalization patterns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sellthrough.config import Settings
from sellthrough.ebay.browse import DEFAULT_MARKETPLACE_ID, MAX_BROWSE_LIMIT
from sellthrough.ebay.client import EbayApiError, EbayClient, EbayRateLimitError


MARKETPLACE_INSIGHTS_SEARCH_PATH = "/buy/marketplace_insights/v1_beta/item_sales/search"


class MarketplaceInsightsAccessError(EbayApiError):
    """Raised when the app keyset lacks Marketplace Insights permission.

    This is distinct from a generic 403 because it is an expected product-access
    state during development. The CLI can explain the approval requirement
    without making the user inspect raw eBay error JSON.
    """


@dataclass(frozen=True)
class SoldItemSummary:
    """A compact, analytics-friendly view of one sold listing.

    The raw payload remains available at the page level. This normalized object
    captures the fields needed for first-pass metrics: sold price, condition,
    category hints, and the date eBay says the item last sold.
    """

    item_id: str
    title: str
    sold_price_value: float | None
    sold_price_currency: str | None
    condition: str | None
    last_sold_date: str | None
    item_web_url: str | None
    category_ids: tuple[str, ...]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "SoldItemSummary":
        """Normalize one eBay sold-item payload.

        Marketplace Insights has used slightly different field names across
        examples and live payloads. Looking for `lastSoldPrice` first and then
        `price` makes the adapter tolerant while keeping that tolerance local.
        """

        price = payload.get("lastSoldPrice") or payload.get("price") or {}
        categories = payload.get("categories") or ()
        return cls(
            item_id=payload.get("itemId", ""),
            title=payload.get("title", ""),
            sold_price_value=_optional_float(price.get("value")),
            sold_price_currency=price.get("currency"),
            condition=payload.get("condition"),
            last_sold_date=payload.get("lastSoldDate"),
            item_web_url=payload.get("itemWebUrl"),
            category_ids=tuple(
                str(category.get("categoryId"))
                for category in categories
                if category.get("categoryId") is not None
            ),
        )


@dataclass(frozen=True)
class SoldSearchResult:
    """Container for one Marketplace Insights page plus normalized sold items."""

    query: str
    total: int
    limit: int
    offset: int
    href: str | None
    next_url: str | None
    warnings: tuple[dict[str, Any], ...]
    items: tuple[SoldItemSummary, ...]
    raw_payload: dict[str, Any]

    @classmethod
    def from_payload(
        cls,
        *,
        query: str,
        limit: int,
        offset: int,
        payload: dict[str, Any],
    ) -> "SoldSearchResult":
        return cls(
            query=query,
            total=int(payload.get("total") or 0),
            limit=limit,
            offset=offset,
            href=payload.get("href"),
            next_url=payload.get("next"),
            warnings=tuple(payload.get("warnings") or ()),
            items=tuple(
                SoldItemSummary.from_payload(item)
                for item in payload.get("itemSales") or ()
            ),
            raw_payload=payload,
        )


class MarketplaceInsightsClient:
    """High-level wrapper for sold-item search.

    The public methods intentionally mirror the Browse client shape. That makes
    future ETL jobs simple: active and sold pages can be pulled through parallel
    interfaces, stored as raw JSON, and then normalized into separate tables.
    """

    def __init__(
        self,
        ebay_client: EbayClient,
        *,
        marketplace_id: str = DEFAULT_MARKETPLACE_ID,
    ) -> None:
        self.ebay_client = ebay_client
        self.marketplace_id = marketplace_id

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        marketplace_id: str = DEFAULT_MARKETPLACE_ID,
    ) -> "MarketplaceInsightsClient":
        return cls(EbayClient.from_settings(settings), marketplace_id=marketplace_id)

    def search_sold_items(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        category_ids: list[str] | None = None,
        last_sold_start: date | datetime | None = None,
        last_sold_end: date | datetime | None = None,
    ) -> SoldSearchResult:
        """Search historical sold listings.

        `last_sold_start` and `last_sold_end` become the Marketplace Insights
        `lastSoldDate` filter. eBay documents sold-history coverage as a recent
        history window, so callers should pass bounded dates rather than asking
        for "all time" sales.
        """

        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("Marketplace Insights search query cannot be blank.")
        if limit < 1:
            raise ValueError("Marketplace Insights search limit must be at least 1.")
        if offset < 0:
            raise ValueError("Marketplace Insights search offset cannot be negative.")

        safe_limit = min(limit, MAX_BROWSE_LIMIT)
        params: dict[str, Any] = {
            "q": cleaned_query,
            "limit": safe_limit,
            "offset": offset,
        }
        if category_ids:
            params["category_ids"] = ",".join(category_ids)
        date_filter = build_last_sold_date_filter(last_sold_start, last_sold_end)
        if date_filter:
            # eBay filter syntax is string-based. Building the string in a
            # helper keeps date/time normalization testable and avoids scattering
            # vendor-specific syntax across command handlers.
            params["filter"] = date_filter

        payload = self._get_json(MARKETPLACE_INSIGHTS_SEARCH_PATH, params=params)
        return SoldSearchResult.from_payload(
            query=cleaned_query,
            limit=safe_limit,
            offset=offset,
            payload=payload,
        )

    def iter_sold_item_pages(
        self,
        query: str,
        *,
        page_size: int = MAX_BROWSE_LIMIT,
        max_pages: int | None = None,
        category_ids: list[str] | None = None,
        days_back: int = 30,
    ):
        """Yield sold-item pages for an ETL pull.

        The default 30-day window matches SellThrough's first planned metrics.
        A scheduler can later vary `days_back` for weekly/monthly snapshots.
        """

        if days_back < 1:
            raise ValueError("days_back must be at least 1.")

        end = datetime.now(UTC)
        start = end - timedelta(days=days_back)
        pages_seen = 0
        offset = 0
        safe_page_size = min(page_size, MAX_BROWSE_LIMIT)

        while max_pages is None or pages_seen < max_pages:
            page = self.search_sold_items(
                query,
                limit=safe_page_size,
                offset=offset,
                category_ids=category_ids,
                last_sold_start=start,
                last_sold_end=end,
            )
            yield page
            pages_seen += 1

            if not page.next_url or not page.items:
                break
            offset += safe_page_size

    def _get_json(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        """Issue an authenticated Marketplace Insights GET request.

        Response handling lives here so every Marketplace Insights method gets
        the same access-denied, rate-limit, and generic API error behavior.
        """

        response = self.ebay_client.session.get(
            f"{self.ebay_client.settings.api_base_url}{path}",
            params=params,
            headers={
                "Authorization": f"Bearer {self.ebay_client.bearer_token()}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            },
            timeout=30,
        )
        payload = _safe_response_json(response)
        if not response.ok:
            if response.status_code == 403 and _is_access_denied(payload):
                # eBay uses a normal HTTP 403 for several cases. Checking the
                # structured error ID lets the application distinguish "approval
                # pending" from other authorization failures.
                raise MarketplaceInsightsAccessError(
                    "Marketplace Insights access is not approved for this keyset yet.",
                    status_code=response.status_code,
                    payload=payload,
                )
            if response.status_code == 429:
                raise EbayRateLimitError(
                    "Marketplace Insights request was rate-limited by eBay.",
                    retry_after_seconds=_parse_retry_after(response.headers.get("Retry-After")),
                    status_code=response.status_code,
                    payload=payload,
                )
            raise EbayApiError(
                f"Marketplace Insights request failed: {response.status_code}",
                status_code=response.status_code,
                payload=payload,
            )
        return payload


def build_last_sold_date_filter(
    start: date | datetime | None,
    end: date | datetime | None,
) -> str | None:
    """Build eBay's `lastSoldDate` filter syntax from Python date objects.

    Either boundary may be omitted; eBay accepts open-ended ranges like
    `lastSoldDate:[..2026-05-01T00:00:00Z]`. Returning `None` when both are
    absent lets callers skip the query parameter entirely.
    """

    if start is None and end is None:
        return None
    start_text = _format_ebay_datetime(start) if start is not None else ""
    end_text = _format_ebay_datetime(end) if end is not None else ""
    return f"lastSoldDate:[{start_text}..{end_text}]"


def _format_ebay_datetime(value: date | datetime) -> str:
    """Format dates as UTC timestamps accepted by Buy API filters.

    A `date` has no time zone or clock time, so the project interprets it as
    the start of that date in UTC. A naive `datetime` is also treated as UTC to
    avoid silently applying the local machine's time zone.
    """

    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=UTC)
        return normalized.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return datetime.combine(value, time.min, tzinfo=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_access_denied(payload: dict[str, Any]) -> bool:
    """Detect eBay's standard insufficient-permission error payload."""

    errors = payload.get("errors") or ()
    return any(error.get("errorId") == 1100 for error in errors)


def _optional_float(value: Any) -> float | None:
    """Convert numeric API strings to floats while preserving missing values."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_response_json(response: Any) -> dict[str, Any]:
    """Return eBay JSON payloads and normalize empty/non-JSON bodies."""

    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_retry_after(value: str | None) -> int | None:
    """Parse numeric Retry-After seconds from an eBay response header."""

    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
