"""Backward-compatible smoke-check exports.

The implementation now lives in `sellthrough.services.smoke` so CLI and future
web code can share the same use-case layer. This module remains as a small
compatibility shim for existing imports and tests.
"""

from sellthrough.services.smoke import SmokeCheck, format_smoke_checks, run_smoke_checks

__all__ = ["SmokeCheck", "format_smoke_checks", "run_smoke_checks"]
