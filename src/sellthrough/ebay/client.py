"""Shared eBay API client primitives.

This module owns the OAuth client-credentials flow used by eBay REST APIs.
Feature-specific clients should build on this rather than reimplementing token
minting, so authentication behavior stays consistent across Browse, Taxonomy,
and Marketplace Insights.

The module intentionally stays small: it does not know about listing search,
category trees, or sold items. Its job is to turn validated settings into
authenticated HTTP requests and normalized exceptions. That boundary is useful
when learning application structure because it separates transport concerns
from domain concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from sellthrough.config import Settings
from sellthrough.security import redact_text, sanitize_payload


class EbayApiError(RuntimeError):
    """Raised when an eBay API request fails.

    The optional `status_code` and `payload` attributes let higher-level
    commands decide whether an error is retryable, rate-limit related, or a
    user-facing validation problem without parsing a string message.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class EbayRateLimitError(EbayApiError):
    """Raised when eBay tells the app to slow down.

    eBay may include a `Retry-After` response header. Capturing it as structured
    metadata lets future scheduled jobs sleep or reschedule intelligently.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: int | None = None,
        status_code: int | None = None,
        payload: Any | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, payload=payload)
        self.retry_after_seconds = retry_after_seconds


@dataclass
class EbayClient:
    """Small wrapper around a `requests.Session` and validated settings.

    `requests.Session` is used instead of top-level `requests.get/post` calls so
    future work can share connection pooling, headers, retries, or test doubles
    through one object. The current tests already exploit this by passing fake
    sessions with minimal `get`/`post` methods.
    """

    settings: Settings
    session: requests.Session
    access_token: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "EbayClient":
        """Create a client with a fresh HTTP session.

        Keeping this as a factory makes call sites expressive while still
        allowing tests to instantiate `EbayClient(settings, fake_session)`
        directly.
        """

        return cls(settings=settings, session=requests.Session())

    def mint_application_token(self, scope: str = "https://api.ebay.com/oauth/api_scope") -> str:
        """Mint an OAuth application token for app-level eBay REST calls.

        Application tokens identify this app, not an eBay user. That matches the
        current SellThrough use case because the app reads marketplace data and
        does not act on behalf of buyers or sellers.
        """

        if not self.settings.ebay_client_id or not self.settings.ebay_client_secret:
            raise EbayApiError("Missing eBay client ID or client secret.")

        # eBay's client-credentials grant uses HTTP Basic auth with the app ID
        # and cert ID. The returned token is an application token, not a user
        # token, so it is appropriate for public marketplace data APIs.
        response = self.session.post(
            f"{self.settings.api_base_url}/identity/v1/oauth2/token",
            auth=(self.settings.ebay_client_id, self.settings.ebay_client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": scope},
            timeout=30,
        )
        if not response.ok:
            if response.status_code == 429:
                # Rate limits deserve a specific exception because schedulers
                # can respond differently to "wait and retry" than to bad
                # credentials or malformed requests.
                raise EbayRateLimitError(
                    "Token request was rate-limited by eBay.",
                    retry_after_seconds=_parse_retry_after(response.headers.get("Retry-After")),
                    status_code=response.status_code,
                    payload=_safe_json(response),
                )
            raise EbayApiError(
                f"Token request failed: {response.status_code}",
                status_code=response.status_code,
                payload=_safe_json(response),
            )

        payload = response.json()
        # The token response should contain `access_token` when `response.ok` is
        # true. Letting KeyError surface here would signal a surprising API
        # contract change rather than a normal user input problem.
        self.access_token = payload["access_token"]
        return self.access_token

    def bearer_token(self) -> str:
        """Return a cached token, minting one on first use.

        Token persistence is intentionally in-memory for now. That keeps the
        MVP simple and avoids writing short-lived credentials to disk; a later
        scheduler can add expiry-aware caching if call volume makes it useful.
        """

        if self.access_token:
            return self.access_token
        return self.mint_application_token()


def _safe_json(response: requests.Response) -> Any | None:
    """Parse and sanitize JSON error bodies when eBay returns one.

    Error bodies often carry the most useful debugging details, but they may
    also echo request values. Sanitizing here keeps every raised `EbayApiError`
    safer to print or log.
    """

    try:
        return sanitize_payload(response.json())
    except ValueError:
        return {"text": redact_text(response.text)} if response.text else None


def _parse_retry_after(value: str | None) -> int | None:
    """Parse simple numeric Retry-After header values.

    The HTTP header can also be a date, but eBay commonly uses seconds. Returning
    `None` for anything more complex keeps this helper honest until the project
    needs date-based retry scheduling.
    """

    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
