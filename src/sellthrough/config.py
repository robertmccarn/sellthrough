"""Runtime configuration for SellThrough.

The project deliberately reads secrets from environment variables instead of
files committed to the repository. That mirrors common data-engineering
practice: code is versioned, while credentials are injected by the local shell,
CI system, or deployment environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class SettingsError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


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
        """

        ebay_env = os.getenv("EBAY_ENV", "production").strip().lower()
        if ebay_env not in {"production", "sandbox"}:
            raise SettingsError("EBAY_ENV must be either 'production' or 'sandbox'.")

        client_id = os.getenv("EBAY_CLIENT_ID")
        client_secret = os.getenv("EBAY_CLIENT_SECRET")
        dev_id = os.getenv("EBAY_DEV_ID")
        db_path = Path(os.getenv("SELLTHROUGH_DB_PATH", "data/sellthrough.sqlite3"))

        if require_ebay_credentials:
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
        if self.ebay_env == "sandbox":
            return "https://api.sandbox.ebay.com"
        return "https://api.ebay.com"

    def redacted_summary(self) -> str:
        """Return diagnostics without leaking secrets into terminal output."""

        return "\n".join(
            [
                f"EBAY_ENV={self.ebay_env}",
                f"EBAY_CLIENT_ID_SET={bool(self.ebay_client_id)}",
                f"EBAY_CLIENT_SECRET_SET={bool(self.ebay_client_secret)}",
                f"EBAY_DEV_ID_SET={bool(self.ebay_dev_id)}",
                f"SELLTHROUGH_DB_PATH={self.db_path}",
            ]
        )
