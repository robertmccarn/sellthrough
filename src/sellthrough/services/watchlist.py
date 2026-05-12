"""Watchlist application services.

The watchlist is the backbone of the near-term architecture. A row captures a
human sourcing target once, then future polling, normalization, lookup, and UI
work can operate from that repeatable target instead of ad hoc command text.

Services sit between interfaces and repositories. The CLI should not know all
watchlist validation rules, and the repository should not know which defaults
make sense for a user workflow. This module owns those application decisions.
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
    """Create a watchlist row, defaulting missing query text to the label.

    Args:
        db_path: SQLite database path.
        label: Human-readable name for the sourcing target.
        query: Optional eBay keyword query; defaults to `label`.
        category_id: Optional eBay category filter.

    Raises:
        ValueError: If label or resolved query is blank.
    """

    cleaned_label = label.strip()
    if not cleaned_label:
        raise ValueError("Watchlist label cannot be blank.")

    # A label is required for humans; a query is required for eBay searches. In
    # the common case they are the same, so the service supplies that default
    # rather than forcing every CLI/API caller to duplicate it.
    cleaned_query = query.strip() if query else cleaned_label
    if not cleaned_query:
        raise ValueError("Watchlist query cannot be blank.")

    # Normalize whitespace at the service boundary so stored rows are stable no
    # matter whether input came from CLI flags or a future form field.
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
    """Return watchlist rows for display or future polling.

    The tuple return type communicates that callers should treat the result as a
    snapshot, not mutate it in place and expect database state to change.
    """

    return WatchlistRepository(db_path).list(include_inactive=include_inactive)


def disable_watchlist_item(*, db_path: Path, watchlist_id: int) -> bool:
    """Disable a watchlist row without deleting historical context.

    Returning a boolean lets the CLI distinguish "disabled successfully" from
    "there was no active row with that ID" without using exceptions for an
    expected no-op.
    """

    if watchlist_id < 1:
        # Reject impossible IDs before touching the database. This keeps storage
        # methods focused on persistence and makes validation behavior consistent
        # for every future interface.
        raise ValueError("Watchlist ID must be a positive integer.")
    return WatchlistRepository(db_path).disable(watchlist_id)
