"""Watchlist application services.

The watchlist is the backbone of the near-term architecture. A row captures a
human sourcing target once, then future polling, normalization, lookup, and UI
work can operate from that repeatable target instead of ad hoc command text.
"""

from __future__ import annotations

from pathlib import Path

from sellthrough.db import WatchlistRecord, WatchlistRepository


def add_watchlist_item(
    *,
    db_path: Path,
    label: str,
    query: str | None = None,
    category_id: str | None = None,
) -> WatchlistRecord:
    """Create a watchlist row, defaulting blank query text to the label."""

    cleaned_label = label.strip()
    if not cleaned_label:
        raise ValueError("Watchlist label cannot be blank.")

    cleaned_query = query.strip() if query else cleaned_label
    if not cleaned_query:
        raise ValueError("Watchlist query cannot be blank.")

    cleaned_category_id = category_id.strip() if category_id else None
    repository = WatchlistRepository(db_path)
    return repository.add(
        label=cleaned_label,
        query=cleaned_query,
        category_id=cleaned_category_id or None,
    )


def list_watchlist_items(
    *,
    db_path: Path,
    include_inactive: bool = False,
) -> tuple[WatchlistRecord, ...]:
    """Return watchlist rows for display or future polling."""

    return WatchlistRepository(db_path).list(include_inactive=include_inactive)


def disable_watchlist_item(*, db_path: Path, watchlist_id: int) -> bool:
    """Disable a watchlist row without deleting historical context."""

    if watchlist_id < 1:
        raise ValueError("Watchlist ID must be a positive integer.")
    return WatchlistRepository(db_path).disable(watchlist_id)
