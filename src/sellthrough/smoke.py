"""Smoke-check orchestration for the current SellThrough stack.

A smoke command is intentionally shallow: it does not prove every edge case, but
it tells a learner/developer whether the main moving pieces can talk to each
other right now. For SellThrough that means local config, SQLite bootstrap,
Browse active listings, Taxonomy category metadata, and Marketplace Insights
access status.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SmokeCheck:
    """One line of smoke-check output.

    `status` stays text rather than an enum to keep CLI formatting simple and
    readable. The accepted values are `PASS`, `WARN`, and `FAIL`.
    """

    name: str
    status: str
    detail: str


def format_smoke_checks(checks: list[SmokeCheck]) -> str:
    """Render smoke checks as compact terminal-friendly text."""

    return "\n".join(f"[{check.status}] {check.name}: {check.detail}" for check in checks)
