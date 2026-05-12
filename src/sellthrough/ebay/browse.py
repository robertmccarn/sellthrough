"""Browse API client for active eBay listings.

Browse is SellThrough's source for current market supply: active listings,
asking prices, conditions, and category hints. Historical sold-item data belongs
to Marketplace Insights, not Browse, so this module deliberately avoids sold
filters such as `lastSoldDate`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sellthrough.config import Settings
from sellthrough.ebay.client import EbayApiError, EbayClient, EbayRateLimitError


DEFAULT_MARKETPLACE_ID = "EBAY_US"
MAX_BROWSE_LIMIT = 200


@dataclass(frozen=True)
class BrowseItemSummary:
    """A compact, analytics-friendly view of a Browse search result.

    eBay returns rich nested JSON. The project stores raw JSON elsewhere, so the
    CLI/client surface can expose just the fields needed for first-pass market
    inspection while keeping the original payload available for later replay.
    """

    item_id: str
    title: str
    price_value: float | None
    price_currency: str | None
    condition: str | None
    item_web_url: str | None
    item_creation_date: str | None
    buying_options: tuple[str, ...]

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "BrowseItemSummary":
        price = payload.get("price") or {}
        return cls(
            item_id=payload.get("itemId", ""),
            title=payload.get("title", ""),
            price_value=_optional_float(price.get("value")),
            price_currency=price.get("currency"),
            condition=payload.get("condition"),
            item_web_url=payload.get("itemWebUrl"),
            item_creation_date=payload.get("itemCreationDate"),
            buying_options=tuple(payload.get("buyingOptions") or ()),
        )


@dataclass(frozen=True)
class BrowseSearchResult:
    """Container for one Browse search page plus normalized item summaries."""

    query: str
    total: int
    limit: int
    offset: int
    href: str | None
    next_url: str | None
    warnings: tuple[dict[str, Any], ...]
    items: tuple[BrowseItemSummary, ...]
    raw_payload: dict[str, Any]

    @classmethod
    def from_payload(
        cls,
        *,
        query: str,
        limit: int,
        offset: int,
        payload: dict[str, Any],
    ) -> "BrowseSearchResult":
        return cls(
            query=query,
            total=int(payload.get("total") or 0),
            limit=limit,
            offset=offset,
            href=payload.get("href"),
            next_url=payload.get("next"),
            warnings=tuple(payload.get("warnings") or ()),
            items=tuple(
                BrowseItemSummary.from_payload(item)
                for item in payload.get("itemSummaries") or ()
            ),
            raw_payload=payload,
        )


class BrowseClient:
    """High-level wrapper for Browse active-listing search."""

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
    ) -> "BrowseClient":
        return cls(EbayClient.from_settings(settings), marketplace_id=marketplace_id)

    def search_active_items(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        category_ids: list[str] | None = None,
    ) -> BrowseSearchResult:
        """Search active eBay listings by keyword.

        `limit` is capped to eBay's documented maximum for a single Browse page.
        Pagination is explicit through `offset` so future ETL jobs can checkpoint
        each page rather than hiding network loops inside a single call.
        """

        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("Browse search query cannot be blank.")
        if limit < 1:
            raise ValueError("Browse search limit must be at least 1.")
        if offset < 0:
            raise ValueError("Browse search offset cannot be negative.")

        safe_limit = min(limit, MAX_BROWSE_LIMIT)
        params: dict[str, Any] = {
            "q": cleaned_query,
            "limit": safe_limit,
            "offset": offset,
        }
        if category_ids:
            params["category_ids"] = ",".join(category_ids)

        response = self.ebay_client.session.get(
            f"{self.ebay_client.settings.api_base_url}/buy/browse/v1/item_summary/search",
            params=params,
            headers={
                "Authorization": f"Bearer {self.ebay_client.bearer_token()}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            },
            timeout=30,
        )
        payload = _safe_response_json(response)
        if not response.ok:
            if response.status_code == 429:
                raise EbayRateLimitError(
                    "Browse search was rate-limited by eBay.",
                    retry_after_seconds=_parse_retry_after(response.headers.get("Retry-After")),
                    status_code=response.status_code,
                    payload=payload,
                )
            raise EbayApiError(
                f"Browse search failed: {response.status_code}",
                status_code=response.status_code,
                payload=payload,
            )

        return BrowseSearchResult.from_payload(
            query=cleaned_query,
            limit=safe_limit,
            offset=offset,
            payload=payload,
        )

    def iter_active_item_pages(
        self,
        query: str,
        *,
        page_size: int = MAX_BROWSE_LIMIT,
        max_pages: int | None = None,
        category_ids: list[str] | None = None,
    ):
        """Yield Browse search pages by advancing `offset`.

        This is the ETL-friendly pagination interface. It yields whole pages,
        not individual items, because the pipeline will eventually store one raw
        API response per page before normalizing item summaries.
        """

        pages_seen = 0
        offset = 0
        safe_page_size = min(page_size, MAX_BROWSE_LIMIT)

        while max_pages is None or pages_seen < max_pages:
            page = self.search_active_items(
                query,
                limit=safe_page_size,
                offset=offset,
                category_ids=category_ids,
            )
            yield page
            pages_seen += 1

            if not page.next_url or not page.items:
                break
            offset += safe_page_size


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
