"""Lookup services for normalized marketplace data."""

from __future__ import annotations

from pathlib import Path

from sellthrough.db import ActiveListingLookup, ActiveListingRepository, WatchlistActiveLookup, WatchlistRepository


def lookup_active_listings(
    *,
    db_path: Path,
    query: str,
    sample_limit: int = 5,
) -> ActiveListingLookup:
    """Return active-listing metrics and samples for a normalized title query."""

    return ActiveListingRepository(db_path).lookup(query, sample_limit=sample_limit)


def lookup_watchlist_active_listings(
    *,
    db_path: Path,
    watchlist_id: int,
    sample_limit: int = 5,
) -> WatchlistActiveLookup:
    """Return active-listing metrics scoped to one watchlist row."""

    if watchlist_id < 1:
        raise ValueError("Watchlist ID must be a positive integer.")
    watchlist = WatchlistRepository(db_path).get(watchlist_id)
    if watchlist is None:
        raise ValueError(f"Watchlist ID {watchlist_id} was not found.")
    return ActiveListingRepository(db_path).lookup_for_watchlist(
        watchlist=watchlist,
        sample_limit=sample_limit,
    )
