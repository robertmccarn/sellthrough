"""SQLite schema bootstrap for the local analytics store.

The schema starts with raw API response capture plus a small normalized surface.
That is intentional for ETL learning: raw storage preserves source truth, while
normalized tables make lookup, metrics, and later transformations easier.

This module is the persistence boundary. Higher-level services talk in terms of
small dataclasses such as `RawApiResponseRecord` and `WatchlistRecord`; this
module translates those records to SQL. Keeping SQL here prevents CLI commands
and eBay clients from learning table details.
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
-- A poll run is one extraction attempt. It can own multiple raw pages once the
-- project grows from single-page smoke checks to paginated jobs.
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

-- Raw responses are stored before normalization. This is the "source truth"
-- table: if normalization logic improves later, rows here can be replayed.
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

-- These normalized tables are intentionally thin for now. The raw payload keeps
-- every field; normalized rows keep the first fields needed for market metrics.
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

-- Watchlist rows turn one-off searches into repeatable sourcing targets. The
-- `active` flag preserves history without deleting rows that old poll runs may
-- eventually refer to.
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


def initialize_database(path: Path) -> None:
    """Create the SQLite database and all known tables if they do not exist.

    Side effects:
        Creates parent directories, creates the SQLite file if needed, and
        applies idempotent `CREATE TABLE IF NOT EXISTS` statements.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        # `executescript` is a good fit for schema bootstrap because the schema
        # is a multi-statement document. Parameterized queries are still used
        # for runtime data writes below.
        connection.executescript(SCHEMA)
        connection.commit()
    finally:
        connection.close()


class RawResponseRepository:
    """Persistence boundary for extraction metadata and raw API payloads.

    Repositories are deliberately small wrappers around SQL. They do not decide
    when a poll run should be completed or failed; that workflow belongs in the
    service layer. Their job is to make the database interaction explicit,
    typed, and easy to test.
    """

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
            # SQLite returns generated primary keys through `lastrowid`. The
            # dataclass lets callers keep working with typed Python objects
            # instead of passing loose dictionaries around the application.
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
        # Canonical-ish JSON keeps diffs and manual DB inspection stable:
        # sorted keys make repeated payloads easier to compare, and compact
        # separators avoid storing whitespace that came from Python formatting.
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
    """Persistence boundary for watchlist rows.

    The repository owns only storage mechanics. Validation such as "IDs must be
    positive" and "blank labels are invalid" lives in `services.watchlist`, so a
    future web route and the CLI can share the same business rules.
    """

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
            # Re-reading after insert proves the shape returned by `add()` is
            # exactly what `list()` returns, including database-generated
            # defaults such as `active` and `added_at`.
            return _watchlist_record_from_row(row)

    def list(self, *, include_inactive: bool = False) -> tuple[WatchlistRecord, ...]:
        """Return watchlist rows in stable ID order."""

        sql = """
            SELECT id, label, query, category_id, active, added_at
            FROM watchlist
        """
        params: tuple[Any, ...] = ()
        if not include_inactive:
            # Soft deletion is represented by `active = 0`. The default list
            # view shows only operational targets, while `--all` can reveal
            # disabled history for auditing or later reactivation work.
            sql += " WHERE active = ?"
            params = (1,)
        sql += " ORDER BY id ASC"

        with self._connect() as connection:
            rows = connection.execute(sql, params).fetchall()
            return tuple(_watchlist_record_from_row(row) for row in rows)

    def disable(self, watchlist_id: int) -> bool:
        """Mark a watchlist row inactive; return false when no active row matched.

        The `active = 1` predicate makes the operation idempotent: disabling an
        already-disabled row does not report success because no state changed.
        """

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
        """Open a SQLite connection with commit/rollback/close behavior.

        This duplicates the raw-response repository helper for now to keep each
        repository self-contained. If more repositories appear, extracting a
        shared base helper would remove the duplication without changing public
        behavior.
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


def _watchlist_record_from_row(row: sqlite3.Row | tuple[Any, ...]) -> WatchlistRecord:
    """Convert a SQLite row tuple into the domain record used above the DB.

    SQLite stores booleans as integers. Converting `active` to `bool` here keeps
    the rest of the Python code from depending on that storage detail.
    """

    return WatchlistRecord(
        id=int(row[0]),
        label=str(row[1]),
        query=str(row[2]),
        category_id=row[3],
        active=bool(row[4]),
        added_at=str(row[5]),
    )
