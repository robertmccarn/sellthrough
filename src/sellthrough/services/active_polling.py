"""Active-listing polling workflow.

This service is the first repeatable ETL loop in SellThrough:

1. Read active watchlist rows from SQLite.
2. Call eBay Browse for each watchlist target.
3. Save each raw Browse response page after sanitization.
4. Normalize the returned item summaries into `active_listings`.

The important boundary is raw-first storage. Normalized rows make the data easy
to query, but the raw response remains available for replay when the transform
logic improves.
"""

from __future__ import annotations

from dataclasses import dataclass

from sellthrough.config import Settings
from sellthrough.db import ActiveListingRecord, ActiveListingRepository
from sellthrough.ebay.browse import BrowseClient, BrowseItemSummary
from sellthrough.services.raw_storage import save_raw_api_page
from sellthrough.services.watchlist import list_watchlist_items


BROWSE_SEARCH_ENDPOINT = "/buy/browse/v1/item_summary/search"


@dataclass(frozen=True)
class ActivePollResult:
    """Summary of one watchlist row poll."""

    watchlist_id: int
    label: str
    query: str
    raw_response_id: int
    returned: int
    normalized: int


def poll_active_watchlist(
    *,
    settings: Settings,
    marketplace_id: str = "EBAY_US",
    limit: int = 50,
    offset: int = 0,
) -> tuple[ActivePollResult, ...]:
    """Poll active watchlist rows through Browse and normalize the results.

    Args:
        settings: Validated runtime configuration.
        marketplace_id: eBay marketplace header value for Browse.
        limit: Browse page size per watchlist row.
        offset: Browse pagination offset per watchlist row.

    Returns:
        One result row per active watchlist item.
    """

    watchlist_items = list_watchlist_items(db_path=settings.db_path)
    if not watchlist_items:
        return ()

    browse_client = BrowseClient.from_settings(settings, marketplace_id=marketplace_id)
    listing_repository = ActiveListingRepository(settings.db_path)
    results: list[ActivePollResult] = []

    for watchlist_item in watchlist_items:
        category_ids = [watchlist_item.category_id] if watchlist_item.category_id else None
        browse_result = browse_client.search_active_items(
            watchlist_item.query,
            limit=limit,
            offset=offset,
            category_ids=category_ids,
        )

        saved = save_raw_api_page(
            db_path=settings.db_path,
            source="browse_watchlist",
            endpoint=BROWSE_SEARCH_ENDPOINT,
            request_url=browse_result.href or "",
            response_json=browse_result.raw_payload,
            query=watchlist_item.query,
            category_id=watchlist_item.category_id,
        )
        normalized = tuple(
            active_listing_from_browse_item(item, raw_response_id=saved.raw_response_id)
            for item in browse_result.items
            if item.item_id
        )
        normalized_count = listing_repository.upsert_many(normalized)
        results.append(
            ActivePollResult(
                watchlist_id=watchlist_item.id,
                label=watchlist_item.label,
                query=watchlist_item.query,
                raw_response_id=saved.raw_response_id,
                returned=len(browse_result.items),
                normalized=normalized_count,
            )
        )

    return tuple(results)


def active_listing_from_browse_item(
    item: BrowseItemSummary,
    *,
    raw_response_id: int,
) -> ActiveListingRecord:
    """Convert a Browse item summary into a normalized active-listing row."""

    return ActiveListingRecord(
        item_id=item.item_id,
        title=item.title,
        category_id=item.category_id,
        category_name=item.category_name,
        condition=item.condition,
        price_value=item.price_value,
        price_currency=item.price_currency,
        shipping_value=item.shipping_value,
        shipping_currency=item.shipping_currency,
        item_web_url=item.item_web_url,
        item_creation_date=item.item_creation_date,
        raw_response_id=raw_response_id,
    )
