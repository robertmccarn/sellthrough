"""Services for storing raw API responses.

The raw response repository knows how to write rows. This service layer knows
when a user workflow should create a poll run, save a page, and mark the run
complete. Keeping that orchestration here prevents every interface from
relearning the same transaction pattern.

Think of this module as application workflow glue. It does not parse CLI flags,
does not know eBay endpoint semantics beyond labels supplied by callers, and
does not execute SQL directly. It coordinates repository calls into one
business operation: "save this API page as part of an auditable poll run."
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sellthrough.db import RawResponseRepository


@dataclass(frozen=True)
class SavedRawResponse:
    """Result of saving one raw API response page.

    Returning both IDs gives callers enough information to print useful CLI
    diagnostics now and to link later normalized rows back to their raw source.
    """

    poll_run_id: int
    raw_response_id: int


def save_raw_api_page(
    *,
    db_path: Path,
    source: str,
    endpoint: str,
    request_url: str,
    response_json: dict[str, Any],
    query: str | None = None,
    category_id: str | None = None,
) -> SavedRawResponse:
    """Create a poll run, persist one raw page, and complete the run.

    If the save fails, the poll run is marked failed before the exception is
    re-raised. This is the first tiny example of service-level workflow
    semantics: the repository performs writes, while the service preserves the
    business rule that every raw save belongs to an auditable poll run.
    """

    repository = RawResponseRepository(db_path)
    # Create the parent run first so success and failure can both be represented
    # in the database. This mirrors production ETL systems where job metadata is
    # recorded before the risky extraction step begins.
    poll_run = repository.create_poll_run(
        source=source,
        query=query,
        category_id=category_id,
    )
    try:
        # The repository sanitizes and encodes JSON; the service supplies the
        # workflow context that connects the raw page to the poll run.
        raw_record = repository.save_raw_response(
            poll_run_id=poll_run.id,
            source=source,
            endpoint=endpoint,
            request_url=request_url,
            response_json=response_json,
        )
        repository.complete_poll_run(poll_run.id)
        return SavedRawResponse(
            poll_run_id=poll_run.id,
            raw_response_id=raw_record.id,
        )
    except Exception as exc:
        # A failed save is still useful operational information. Marking the
        # poll run failed before re-raising preserves the original exception for
        # callers while leaving an audit trail in SQLite.
        repository.fail_poll_run(poll_run.id, str(exc))
        raise
