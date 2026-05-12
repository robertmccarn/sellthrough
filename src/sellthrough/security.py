"""Security helpers for redaction and raw payload sanitization.

SellThrough is local-first, but it still handles credentials and third-party API
payloads. These helpers centralize the "do not leak secrets or personal data"
rules so CLI commands, database storage, and future web code do not invent their
own partial redaction logic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


REDACTED = "[REDACTED]"

# These names are intentionally broad. Raw eBay payloads should not contain most
# of them for the current listing-only use case, but if future APIs add user,
# order, or financial fields, the sanitizer should fail closed by removing them.
SENSITIVE_KEY_FRAGMENTS = (
    "access_token",
    "authorization",
    "bearer",
    "buyer",
    "client_secret",
    "email",
    "financial",
    "message",
    "order",
    "password",
    "payment",
    "phone",
    "seller",
    "secret",
    "token",
    "user",
    "username",
)


def sanitize_payload(payload: Any) -> Any:
    """Return a JSON-compatible copy with sensitive fields removed/redacted.

    Lists and dictionaries are traversed recursively. Keys that look sensitive
    are retained with a redacted value instead of deleted so a learner can still
    see that a field existed without storing the sensitive content itself.
    """

    if isinstance(payload, Mapping):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            key_text = str(key)
            if is_sensitive_key(key_text):
                sanitized[key_text] = REDACTED
            else:
                sanitized[key_text] = sanitize_payload(value)
        return sanitized

    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return [sanitize_payload(item) for item in payload]

    if isinstance(payload, str):
        return redact_text(payload)

    return payload


def redact_text(value: str) -> str:
    """Redact obvious bearer/token fragments from human-facing text."""

    redacted = value
    markers = ("Bearer ", "access_token=", "client_secret=", "EBAY_CLIENT_SECRET=")
    for marker in markers:
        if marker in redacted:
            before, _, after = redacted.partition(marker)
            tail = _text_after_secret(after)
            redacted = f"{before}{marker}{REDACTED}{tail}"
    return redacted


def is_sensitive_key(key: str) -> bool:
    """Return true when a JSON key name is unsafe to persist verbatim."""

    normalized = key.lower().replace("-", "_")
    return any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)


def _text_after_secret(value: str) -> str:
    """Return text after the first token-like value, preserving separators."""

    index = 0
    while index < len(value) and value[index] not in (" ", "&", "\n", "\r", "\t", '"', "'"):
        index += 1
    return value[index:]
