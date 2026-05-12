"""SQLite schema bootstrap for the local analytics store.

The schema starts with raw API response capture plus a small normalized surface.
That is intentional for ETL learning: raw storage preserves source truth, while
normalized tables make lookup, metrics, and later transformations easier.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterator

from sellthrough.security import sanitize_payload


SCHEMA = """
CREATE TABLE IF NOT EXISTS poll_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    query TEXT,
    category_id TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'started',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS raw_api_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_run_id INTEGER,
    source TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_url TEXT NOT NULL,
    response_json TEXT NOT NULL,
    pulled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (poll_run_id) REFERENCES poll_runs(id)
);

CREATE TABLE IF NOT EXISTS active_listings (
    item_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category_id TEXT,
    category_name TEXT,
    condition TEXT,
    price_value REAL,
    price_currency TEXT,
    shipping_value REAL,
    shipping_currency TEXT,
    item_web_url TEXT,
    item_creation_date TEXT,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    raw_response_id INTEGER,
    FOREIGN KEY (raw_response_id) REFERENCES raw_api_responses(id)
);

CREATE TABLE IF NOT EXISTS active_listing_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER,
    item_id TEXT NOT NULL,
    raw_response_id INTEGER,
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    price_value REAL,
    price_currency TEXT,
    shipping_value REAL,
    shipping_currency TEXT,
    condition TEXT,
    FOREIGN KEY (watchlist_id) REFERENCES watchlist(id),
    FOREIGN KEY (item_id) REFERENCES active_listings(item_id),
    FOREIGN KEY (raw_response_id) REFERENCES raw_api_responses(id)
);

CREATE TABLE IF NOT EXISTS sold_listings (
    item_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category_id TEXT,
    category_name TEXT,
    condition TEXT,
    sold_price_value REAL,
    sold_price_currency TEXT,
    shipping_value REAL,
    shipping_currency TEXT,
    last_sold_date TEXT,
    raw_response_id INTEGER,
    FOREIGN KEY (raw_response_id) REFERENCES raw_api_responses(id)
);

CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    query TEXT NOT NULL,
    category_id TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@dataclass(frozen=True)
class PollRunRecord:
    """A persisted extraction attempt.

    A poll run groups one or more raw API pages pulled for the same source and
    query. Keeping this separate from raw responses lets future jobs mark a run
    failed even if some pages were saved before the failure.
    """

    id: int
    source: str
    query: str | None
    category_id: str | None
    status: str


@dataclass(frozen=True)
class RawApiResponseRecord:
    """A persisted raw API page.

    The normalized listing tables can always be rebuilt from these rows. That is
    the learning value of a raw-first ETL design: transforms become replayable,
    inspectable, and less scary to change.
    """

    id: int
    poll_run_id: int | None
    source: str
    endpoint: str
    request_url: str


@dataclass(frozen=True)
class PollRunSummary:
    """Compact poll-run summary for operational status views."""

    id: int
    source: str
    query: str | None
    category_id: str | None
    started_at: str
    completed_at: str | None
    status: str
    error_message: str | None


@dataclass(frozen=True)
class RawResponseSummary:
    """Compact raw-response summary for freshness checks."""

    id: int
    source: str
    endpoint: str
    pulled_at: str


@dataclass(frozen=True)
class WatchlistRecord:
    """A user-defined sourcing target.

    Watchlist rows are the first durable business object in SellThrough. They
    represent item families worth polling repeatedly, such as "DeWalt 20V drill"
    or "TI-84 Plus CE", and become the bridge between ad hoc searches and a
    repeatable ETL loop.
    """

    id: int
    label: str
    query: str
    category_id: str | None
    active: bool
    added_at: str


@dataclass(frozen=True)
class ActiveListingRecord:
    """A normalized active listing row.

    Raw Browse payloads remain the source of truth. This record is the compact
    query-friendly shape used by the first active-listing analytics surface.
    """

    item_id: str
    title: str
    category_id: str | None
    category_name: str | None
    condition: str | None
    price_value: float | None
    price_currency: str | None
    shipping_value: float | None
    shipping_currency: str | None
    item_web_url: str | None
    item_creation_date: str | None
    raw_response_id: int | None


@dataclass(frozen=True)
class ActiveListingObservationRecord:
    """A lineage record for one observed active listing during a poll.

    `active_listings` stores the latest normalized state by item. Observation
    rows capture the event history: which watchlist trigger saw the item, from
    which raw response page, and what core pricing/context fields were present
    at that time.
    """

    watchlist_id: int | None
    item_id: str
    raw_response_id: int | None
    price_value: float | None
    price_currency: str | None
    shipping_value: float | None
    shipping_currency: str | None
    condition: str | None


@dataclass(frozen=True)
class ActiveListingSample:
    """A small normalized row for lookup output."""

    item_id: str
    title: str
    price_value: float | None
    price_currency: str | None
    condition: str | None
    item_web_url: str | None
    last_seen_at: str


@dataclass(frozen=True)
class ActiveListingLookup:
    """Aggregate lookup result for normalized active listings."""

    query: str
    active_count: int
    price_min: float | None
    price_median: float | None
    price_max: float | None
    price_currency: str | None
    last_seen_at: str | None
    samples: tuple[ActiveListingSample, ...]


@dataclass(frozen=True)
class WatchlistActiveLookup:
    """Aggregate lookup scoped to one watchlist lineage stream."""

    watchlist_id: int
    watchlist_label: str
    watchlist_query: str
    active_count: int
    price_min: float | None
    price_median: float | None
    price_max: float | None
    price_currency: str | None
    latest_poll_at: str | None
    samples: tuple[ActiveListingSample, ...]


def initialize_database(path: Path) -> None:
    """Create the SQLite database and all known tables if they do not exist."""

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA)
        _apply_schema_migrations(connection)
        connection.commit()
    finally:
        connection.close()


def _apply_schema_migrations(connection: sqlite3.Connection) -> None:
    """Apply additive schema updates for existing local SQLite files."""

    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(active_listing_observations)")}
    if "shipping_value" not in columns:
        connection.execute("ALTER TABLE active_listing_observations ADD COLUMN shipping_value REAL")
    if "shipping_currency" not in columns:
        connection.execute("ALTER TABLE active_listing_observations ADD COLUMN shipping_currency TEXT")


class RawResponseRepository:
    """Persistence boundary for extraction metadata and raw API payloads."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        initialize_database(db_path)

    def create_poll_run(
        self,
        *,
        source: str,
        query: str | None = None,
        category_id: str | None = None,
    ) -> PollRunRecord:
        """Insert a started poll run and return its generated ID."""

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO poll_runs (source, query, category_id)
                VALUES (?, ?, ?)
                """,
                (source, query, category_id),
            )
            poll_run_id = int(cursor.lastrowid)
            return PollRunRecord(
                id=poll_run_id,
                source=source,
                query=query,
                category_id=category_id,
                status="started",
            )

    def complete_poll_run(self, poll_run_id: int) -> None:
        """Mark a poll run successful after all intended pages are saved."""

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE poll_runs
                SET status = 'completed', completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (poll_run_id,),
            )

    def fail_poll_run(self, poll_run_id: int, error_message: str) -> None:
        """Mark a poll run failed while preserving any raw pages already saved."""

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE poll_runs
                SET status = 'failed',
                    completed_at = CURRENT_TIMESTAMP,
                    error_message = ?
                WHERE id = ?
                """,
                (error_message, poll_run_id),
            )

    def save_raw_response(
        self,
        *,
        source: str,
        endpoint: str,
        request_url: str,
        response_json: dict[str, Any],
        poll_run_id: int | None = None,
    ) -> RawApiResponseRecord:
        """Persist one sanitized raw API response as canonical JSON text.

        Raw storage is still sensitive-by-default. The project keeps source
        structure for replay/learning, but it scrubs fields that look like user,
        auth, order, message, or payment data before writing to disk.
        """

        sanitized_payload = sanitize_payload(response_json)
        encoded_payload = json.dumps(sanitized_payload, sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO raw_api_responses (
                    poll_run_id,
                    source,
                    endpoint,
                    request_url,
                    response_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (poll_run_id, source, endpoint, request_url, encoded_payload),
            )
            return RawApiResponseRecord(
                id=int(cursor.lastrowid),
                poll_run_id=poll_run_id,
                source=source,
                endpoint=endpoint,
                request_url=request_url,
            )

    def count_raw_responses(self) -> int:
        """Return the number of raw response rows, useful for smoke checks."""

        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM raw_api_responses").fetchone()
            return int(row[0])

    def list_recent_poll_runs(self, *, limit: int = 10) -> tuple[PollRunSummary, ...]:
        """Return the most recent poll runs, newest first."""

        if limit < 1:
            raise ValueError("Limit must be at least 1.")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    source,
                    query,
                    category_id,
                    started_at,
                    completed_at,
                    status,
                    error_message
                FROM poll_runs
                ORDER BY started_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(
            PollRunSummary(
                id=int(row[0]),
                source=str(row[1]),
                query=row[2],
                category_id=row[3],
                started_at=str(row[4]),
                completed_at=row[5],
                status=str(row[6]),
                error_message=row[7],
            )
            for row in rows
        )

    def count_failed_poll_runs(self, *, days_back: int = 7) -> int:
        """Return failed poll-run count within a recent time window."""

        if days_back < 1:
            raise ValueError("days_back must be at least 1.")
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*)
                FROM poll_runs
                WHERE status = 'failed'
                  AND started_at >= datetime('now', '-' || ? || ' days')
                """,
                (days_back,),
            ).fetchone()
        return int(row[0])

    def get_latest_completed_poll_run(self) -> PollRunSummary | None:
        """Return the most recent completed poll run."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    source,
                    query,
                    category_id,
                    started_at,
                    completed_at,
                    status,
                    error_message
                FROM poll_runs
                WHERE status = 'completed'
                ORDER BY completed_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return PollRunSummary(
            id=int(row[0]),
            source=str(row[1]),
            query=row[2],
            category_id=row[3],
            started_at=str(row[4]),
            completed_at=row[5],
            status=str(row[6]),
            error_message=row[7],
        )

    def get_latest_raw_response(self) -> RawResponseSummary | None:
        """Return the most recent raw API response row."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, source, endpoint, pulled_at
                FROM raw_api_responses
                ORDER BY pulled_at DESC, id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return RawResponseSummary(
            id=int(row[0]),
            source=str(row[1]),
            endpoint=str(row[2]),
            pulled_at=str(row[3]),
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a SQLite connection with foreign keys enabled.

        SQLite connections are not closed automatically by `with
        sqlite3.connect(...)`; that context manager commits or rolls back but
        leaves the handle alive. On Windows, the open handle prevents temporary
        test databases from being deleted, so this repository owns explicit
        close behavior in one place.
        """

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


class WatchlistRepository:
    """Persistence boundary for watchlist rows."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        initialize_database(db_path)

    def add(
        self,
        *,
        label: str,
        query: str,
        category_id: str | None = None,
    ) -> WatchlistRecord:
        """Create an active watchlist row."""

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO watchlist (label, query, category_id)
                VALUES (?, ?, ?)
                """,
                (label, query, category_id),
            )
            row = connection.execute(
                """
                SELECT id, label, query, category_id, active, added_at
                FROM watchlist
                WHERE id = ?
                """,
                (int(cursor.lastrowid),),
            ).fetchone()
            return _watchlist_record_from_row(row)

    def list(self, *, include_inactive: bool = False) -> tuple[WatchlistRecord, ...]:
        """Return watchlist rows in stable ID order."""

        sql = """
            SELECT id, label, query, category_id, active, added_at
            FROM watchlist
        """
        params: tuple[Any, ...] = ()
        if not include_inactive:
            sql += " WHERE active = ?"
            params = (1,)
        sql += " ORDER BY id ASC"

        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
            return tuple(_watchlist_record_from_row(row) for row in rows)

    def count(self, *, include_inactive: bool = False) -> int:
        """Return watchlist row count."""

        sql = "SELECT COUNT(*) FROM watchlist"
        params: tuple[Any, ...] = ()
        if not include_inactive:
            sql += " WHERE active = ?"
            params = (1,)
        with self._connect() as connection:
            row = connection.execute(sql, params).fetchone()
        return int(row[0])

    def disable(self, watchlist_id: int) -> bool:
        """Mark a watchlist row inactive; return false when no row matched."""

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE watchlist
                SET active = 0
                WHERE id = ? AND active = 1
                """,
                (watchlist_id,),
            )
            return cursor.rowcount > 0

    def get(self, watchlist_id: int) -> WatchlistRecord | None:
        """Return one watchlist row by ID."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, label, query, category_id, active, added_at
                FROM watchlist
                WHERE id = ?
                """,
                (watchlist_id,),
            ).fetchone()
        if row is None:
            return None
        return _watchlist_record_from_row(row)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a SQLite connection with foreign keys enabled."""

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _watchlist_record_from_row(row: sqlite3.Row | tuple[Any, ...]) -> WatchlistRecord:
    """Convert a SQLite row tuple into the domain record used above the DB."""

    return WatchlistRecord(
        id=int(row[0]),
        label=str(row[1]),
        query=str(row[2]),
        category_id=row[3],
        active=bool(row[4]),
        added_at=str(row[5]),
    )


def _active_listing_sample_from_row(row: sqlite3.Row | tuple[Any, ...]) -> ActiveListingSample:
    """Convert a SQLite row tuple into a lookup sample."""

    return ActiveListingSample(
        item_id=str(row[0]),
        title=str(row[1]),
        price_value=float(row[2]) if row[2] is not None else None,
        price_currency=row[3],
        condition=row[4],
        item_web_url=row[5],
        last_seen_at=str(row[6]),
    )


class ActiveListingRepository:
    """Persistence boundary for normalized active Browse listings."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        initialize_database(db_path)

    def upsert_many(self, listings: tuple[ActiveListingRecord, ...]) -> int:
        """Insert or update active listing rows; return rows processed."""

        if not listings:
            return 0

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO active_listings (
                    item_id,
                    title,
                    category_id,
                    category_name,
                    condition,
                    price_value,
                    price_currency,
                    shipping_value,
                    shipping_currency,
                    item_web_url,
                    item_creation_date,
                    raw_response_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_id) DO UPDATE SET
                    title = excluded.title,
                    category_id = excluded.category_id,
                    category_name = excluded.category_name,
                    condition = excluded.condition,
                    price_value = excluded.price_value,
                    price_currency = excluded.price_currency,
                    shipping_value = excluded.shipping_value,
                    shipping_currency = excluded.shipping_currency,
                    item_web_url = excluded.item_web_url,
                    item_creation_date = excluded.item_creation_date,
                    last_seen_at = CURRENT_TIMESTAMP,
                    raw_response_id = excluded.raw_response_id
                """,
                (
                    (
                        listing.item_id,
                        listing.title,
                        listing.category_id,
                        listing.category_name,
                        listing.condition,
                        listing.price_value,
                        listing.price_currency,
                        listing.shipping_value,
                        listing.shipping_currency,
                        listing.item_web_url,
                        listing.item_creation_date,
                        listing.raw_response_id,
                    )
                    for listing in listings
                ),
            )
        return len(listings)

    def count(self) -> int:
        """Return the number of normalized active listing rows."""

        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM active_listings").fetchone()
            return int(row[0])

    def list_recent(self, *, sample_limit: int = 5) -> tuple[ActiveListingSample, ...]:
        """Return recent normalized active listings for dashboard previews."""

        if sample_limit < 1:
            raise ValueError("Sample limit must be at least 1.")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    item_id,
                    title,
                    price_value,
                    price_currency,
                    condition,
                    item_web_url,
                    last_seen_at
                FROM active_listings
                ORDER BY last_seen_at DESC, price_value ASC, title ASC
                LIMIT ?
                """,
                (sample_limit,),
            ).fetchall()
        return tuple(_active_listing_sample_from_row(row) for row in rows)

    def insert_observations(
        self,
        observations: tuple[ActiveListingObservationRecord, ...],
    ) -> int:
        """Insert watchlist-scoped observation lineage rows.

        This method is intentionally append-only. It records each poll's view
        of an item, even when the same item appears repeatedly across runs.
        """

        if not observations:
            return 0

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO active_listing_observations (
                    watchlist_id,
                    item_id,
                    raw_response_id,
                    price_value,
                    price_currency,
                    shipping_value,
                    shipping_currency,
                    condition
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (
                        observation.watchlist_id,
                        observation.item_id,
                        observation.raw_response_id,
                        observation.price_value,
                        observation.price_currency,
                        observation.shipping_value,
                        observation.shipping_currency,
                        observation.condition,
                    )
                    for observation in observations
                ),
            )
        return len(observations)

    def lookup(self, query: str, *, sample_limit: int = 5) -> ActiveListingLookup:
        """Query normalized active listing rows by case-insensitive title text."""

        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("Lookup query cannot be blank.")
        if sample_limit < 1:
            raise ValueError("Sample limit must be at least 1.")

        pattern = f"%{cleaned_query.lower()}%"
        with self._connect() as connection:
            aggregate = connection.execute(
                """
                SELECT COUNT(*), MAX(last_seen_at)
                FROM active_listings
                WHERE lower(title) LIKE ?
                """,
                (pattern,),
            ).fetchone()
            price_rows = connection.execute(
                """
                SELECT price_value, price_currency
                FROM active_listings
                WHERE lower(title) LIKE ?
                  AND price_value IS NOT NULL
                ORDER BY price_value ASC
                """,
                (pattern,),
            ).fetchall()
            sample_rows = connection.execute(
                """
                SELECT
                    item_id,
                    title,
                    price_value,
                    price_currency,
                    condition,
                    item_web_url,
                    last_seen_at
                FROM active_listings
                WHERE lower(title) LIKE ?
                ORDER BY last_seen_at DESC, price_value ASC, title ASC
                LIMIT ?
                """,
                (pattern, sample_limit),
            ).fetchall()

        prices = [float(row[0]) for row in price_rows]
        currencies = [str(row[1]) for row in price_rows if row[1]]
        return ActiveListingLookup(
            query=cleaned_query,
            active_count=int(aggregate[0]),
            price_min=min(prices) if prices else None,
            price_median=float(median(prices)) if prices else None,
            price_max=max(prices) if prices else None,
            price_currency=currencies[0] if currencies else None,
            last_seen_at=aggregate[1],
            samples=tuple(_active_listing_sample_from_row(row) for row in sample_rows),
        )

    def lookup_for_watchlist(
        self,
        *,
        watchlist: WatchlistRecord,
        sample_limit: int = 5,
    ) -> WatchlistActiveLookup:
        """Query active listings scoped to one watchlist's observation lineage."""

        if sample_limit < 1:
            raise ValueError("Sample limit must be at least 1.")

        with self._connect() as connection:
            aggregate = connection.execute(
                """
                SELECT
                    COUNT(DISTINCT active_listings.item_id),
                    MAX(active_listing_observations.observed_at)
                FROM active_listing_observations
                JOIN active_listings
                    ON active_listings.item_id = active_listing_observations.item_id
                WHERE active_listing_observations.watchlist_id = ?
                """,
                (watchlist.id,),
            ).fetchone()
            price_rows = connection.execute(
                """
                SELECT DISTINCT
                    active_listings.item_id,
                    active_listings.price_value,
                    active_listings.price_currency
                FROM active_listing_observations
                JOIN active_listings
                    ON active_listings.item_id = active_listing_observations.item_id
                WHERE active_listing_observations.watchlist_id = ?
                  AND active_listings.price_value IS NOT NULL
                ORDER BY active_listings.price_value ASC
                """,
                (watchlist.id,),
            ).fetchall()
            sample_rows = connection.execute(
                """
                SELECT
                    active_listings.item_id,
                    active_listings.title,
                    active_listings.price_value,
                    active_listings.price_currency,
                    active_listings.condition,
                    active_listings.item_web_url,
                    active_listings.last_seen_at
                FROM active_listings
                JOIN (
                    SELECT
                        item_id,
                        MAX(observed_at) AS latest_observed_at
                    FROM active_listing_observations
                    WHERE watchlist_id = ?
                    GROUP BY item_id
                ) scoped_items
                    ON scoped_items.item_id = active_listings.item_id
                ORDER BY
                    scoped_items.latest_observed_at DESC,
                    active_listings.price_value ASC,
                    active_listings.title ASC
                LIMIT ?
                """,
                (watchlist.id, sample_limit),
            ).fetchall()

        prices = [float(row[1]) for row in price_rows]
        currencies = [str(row[2]) for row in price_rows if row[2]]
        return WatchlistActiveLookup(
            watchlist_id=watchlist.id,
            watchlist_label=watchlist.label,
            watchlist_query=watchlist.query,
            active_count=int(aggregate[0]),
            price_min=min(prices) if prices else None,
            price_median=float(median(prices)) if prices else None,
            price_max=max(prices) if prices else None,
            price_currency=currencies[0] if currencies else None,
            latest_poll_at=aggregate[1],
            samples=tuple(_active_listing_sample_from_row(row) for row in sample_rows),
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a SQLite connection with foreign keys enabled."""

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
