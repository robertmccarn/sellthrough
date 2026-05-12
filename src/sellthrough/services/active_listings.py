"""Transforms for normalized active listing rows.

This module is the first explicit ETL transform in SellThrough. It accepts raw
Browse payloads at the boundary, converts them into stable `ActiveListingRecord`
rows, and preserves the `raw_response_id` linkage so every normalized row can be
traced back to the exact API page that produced it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sellthrough.db import ActiveListingRecord, ActiveListingRepository
from sellthrough.ebay.browse import BrowseItemSummary, BrowseSearchResult


def normalize_active_browse_payload(
    *,
    db_path: Path,
    raw_response_id: int,
    payload: dict[str, Any],
    query: str = "",
    limit: int = 0,
    offset: int = 0,
) -> int:
    """Transform one raw Browse page and upsert it into `active_listings`.

    Args:
        db_path: SQLite database path containing the raw response row.
        raw_response_id: `raw_api_responses.id` for lineage.
        payload: Raw Browse JSON payload.
        query: Query metadata used only to build the in-memory page object.
        limit: Page-size metadata used only to build the in-memory page object.
        offset: Offset metadata used only to build the in-memory page object.

    Returns:
        Number of normalized listing rows upserted.
    """

    records = active_listing_records_from_browse_payload(
        payload=payload,
        raw_response_id=raw_response_id,
        query=query,
        limit=limit,
        offset=offset,
    )
    return ActiveListingRepository(db_path).upsert_many(records)


def active_listing_records_from_browse_payload(
    *,
    payload: dict[str, Any],
    raw_response_id: int,
    query: str = "",
    limit: int = 0,
    offset: int = 0,
) -> tuple[ActiveListingRecord, ...]:
    """Convert raw Browse JSON into stable active-listing records.

    Rows without `item_id` are skipped because `item_id` is the stable eBay key
    and the primary key of `active_listings`.
    """

    page = BrowseSearchResult.from_payload(
        query=query,
        limit=limit,
        offset=offset,
        payload=payload,
    )
    return tuple(
        active_listing_from_browse_item(item, raw_response_id=raw_response_id)
        for item in page.items
        if item.item_id
    )


def active_listing_from_browse_item(
    item: BrowseItemSummary,
    *,
    raw_response_id: int,
) -> ActiveListingRecord:
    """Convert a parsed Browse item summary into a normalized DB row."""

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
