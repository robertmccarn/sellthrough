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
