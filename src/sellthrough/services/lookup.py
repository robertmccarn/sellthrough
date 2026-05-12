"""Lookup services for normalized marketplace data."""

from __future__ import annotations

from pathlib import Path

from sellthrough.db import ActiveListingLookup, ActiveListingRepository


def lookup_active_listings(
    *,
    db_path: Path,
    query: str,
    sample_limit: int = 5,
) -> ActiveListingLookup:
    """Return active-listing metrics and samples for a normalized title query."""

    return ActiveListingRepository(db_path).lookup(query, sample_limit=sample_limit)
