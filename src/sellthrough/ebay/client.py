"""Shared eBay API client primitives.

This module owns the OAuth client-credentials flow used by eBay REST APIs.
Feature-specific clients should build on this rather than reimplementing token
minting, so authentication behavior stays consistent across Browse, Taxonomy,
and Marketplace Insights.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from sellthrough.config import Settings


class EbayApiError(RuntimeError):
    """Raised when an eBay API request fails."""


@dataclass
class EbayClient:
    """Small wrapper around a `requests.Session` and validated settings."""

    settings: Settings
    session: requests.Session

    @classmethod
    def from_settings(cls, settings: Settings) -> "EbayClient":
        return cls(settings=settings, session=requests.Session())

    def mint_application_token(self, scope: str = "https://api.ebay.com/oauth/api_scope") -> str:
        """Mint an OAuth application token for app-level eBay REST calls.

        Application tokens identify this app, not an eBay user. That matches the
        current SellThrough use case because the app reads marketplace data and
        does not act on behalf of buyers or sellers.
        """

        if not self.settings.ebay_client_id or not self.settings.ebay_client_secret:
            raise EbayApiError("Missing eBay client ID or client secret.")

        response = self.session.post(
            f"{self.settings.api_base_url}/identity/v1/oauth2/token",
            auth=(self.settings.ebay_client_id, self.settings.ebay_client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"grant_type": "client_credentials", "scope": scope},
            timeout=30,
        )
        if not response.ok:
            raise EbayApiError(f"Token request failed: {response.status_code} {response.text}")

        payload = response.json()
        return payload["access_token"]
