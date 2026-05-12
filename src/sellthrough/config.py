"""Runtime configuration for SellThrough.

The project deliberately reads secrets from environment variables instead of
files committed to the repository. That mirrors common data-engineering
practice: code is versioned, while credentials are injected by the local shell,
CI system, or deployment environment.

The important design choice in this module is centralization. Code that talks to
eBay or SQLite should receive a `Settings` object instead of calling
`os.getenv()` directly. That gives the application one place to validate
configuration, one place to document defaults, and one easy object to replace in
tests.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class SettingsError(ValueError):
    """Raised when required runtime configuration is missing or invalid.

    This subclasses `ValueError` because configuration problems are invalid
    input to the program, not infrastructure failures. CLI commands can catch it
    and show a concise user-facing parser error.
    """


@dataclass(frozen=True)
class Settings:
    """Validated runtime settings.

    Keeping settings in one immutable object makes downstream code easier to
    test and reason about. Functions can accept `Settings` rather than reaching
    into `os.environ` from many different places.
    """

    ebay_env: str
    ebay_client_id: str | None
    ebay_client_secret: str | None
    ebay_dev_id: str | None
    db_path: Path

    @classmethod
    def from_environment(cls, *, require_ebay_credentials: bool = True) -> "Settings":
        """Build settings from process environment variables.

        `require_ebay_credentials` is false for local commands such as database
        initialization because those commands do not need network access. This
        keeps setup ergonomic while still failing fast before API calls.

        Returns:
            A validated immutable `Settings` instance.

        Raises:
            SettingsError: If `EBAY_ENV` is invalid or required eBay credential
                variables are missing.
        """

        # Normalize early so the rest of the application can compare against a
        # small known vocabulary instead of accepting every spelling variant.
        ebay_env = os.getenv("EBAY_ENV", "production").strip().lower()
        if ebay_env not in {"production", "sandbox"}:
            raise SettingsError("EBAY_ENV must be either 'production' or 'sandbox'.")

        client_id = os.getenv("EBAY_CLIENT_ID")
        client_secret = os.getenv("EBAY_CLIENT_SECRET")
        dev_id = os.getenv("EBAY_DEV_ID")
        db_path = Path(os.getenv("SELLTHROUGH_DB_PATH", "data/sellthrough.sqlite3"))

        if require_ebay_credentials:
            # Build the missing-variable list from a mapping so the error tells
            # the developer every problem in one run instead of failing one env
            # var at a time.
            missing = [
                name
                for name, value in {
                    "EBAY_CLIENT_ID": client_id,
                    "EBAY_CLIENT_SECRET": client_secret,
                    "EBAY_DEV_ID": dev_id,
                }.items()
                if not value
            ]
            if missing:
                raise SettingsError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(
            ebay_env=ebay_env,
            ebay_client_id=client_id,
            ebay_client_secret=client_secret,
            ebay_dev_id=dev_id,
            db_path=db_path,
        )

    @property
    def api_base_url(self) -> str:
        """Return the REST API host matching the configured eBay environment."""

        if self.ebay_env == "sandbox":
            return "https://api.sandbox.ebay.com"
        return "https://api.ebay.com"

    def redacted_summary(self) -> str:
        """Return diagnostics without leaking secrets into terminal output.

        The summary exposes booleans for credential presence rather than values.
        That is enough to debug setup while keeping terminal logs safe to paste
        into issues, pull requests, or chat.
        """

        return "\n".join(
            [
                f"EBAY_ENV={self.ebay_env}",
                f"EBAY_CLIENT_ID_SET={bool(self.ebay_client_id)}",
                f"EBAY_CLIENT_SECRET_SET={bool(self.ebay_client_secret)}",
                f"EBAY_DEV_ID_SET={bool(self.ebay_dev_id)}",
                f"SELLTHROUGH_DB_PATH={self.db_path}",
            ]
        )
