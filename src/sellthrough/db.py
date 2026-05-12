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


def initialize_database(path: Path) -> None:
    """Create the SQLite database and all known tables if they do not exist."""

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA)
        connection.commit()
    finally:
        connection.close()


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
