from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from sellthrough.config import Settings
from sellthrough.db import RawResponseRepository
from sellthrough.ebay.client import EbayApiError, EbayClient
from sellthrough.security import REDACTED, redact_text, sanitize_payload


class SecuritySanitizerTests(unittest.TestCase):
    def test_sanitize_payload_redacts_nested_sensitive_fields(self) -> None:
        payload = {
            "itemId": "v1|123|0",
            "seller": {"username": "seller-name", "feedback": 100},
            "buyerEmail": "buyer@example.test",
            "items": [{"paymentStatus": "PAID", "title": "Drill"}],
        }

        sanitized = sanitize_payload(payload)

        self.assertEqual(sanitized["itemId"], "v1|123|0")
        self.assertEqual(sanitized["seller"], REDACTED)
        self.assertEqual(sanitized["buyerEmail"], REDACTED)
        self.assertEqual(sanitized["items"][0]["paymentStatus"], REDACTED)
        self.assertEqual(sanitized["items"][0]["title"], "Drill")

    def test_redact_text_hides_bearer_tokens(self) -> None:
        self.assertEqual(
            redact_text("Authorization: Bearer abc123\nnext line"),
            f"Authorization: Bearer {REDACTED}\nnext line",
        )


class ConfigRedactionTests(unittest.TestCase):
    def test_redacted_summary_never_prints_secret_values(self) -> None:
        settings = Settings(
            ebay_env="production",
            ebay_client_id="client-id",
            ebay_client_secret="super-secret",
            ebay_dev_id="dev-id",
            db_path=Path("data/sellthrough.sqlite3"),
        )

        summary = settings.redacted_summary()

        self.assertIn("EBAY_CLIENT_SECRET_SET=True", summary)
        self.assertNotIn("super-secret", summary)
        self.assertNotIn("client-id", summary)


class RawStorageSanitizationTests(unittest.TestCase):
    def test_raw_response_storage_sanitizes_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            repository = RawResponseRepository(db_path)

            raw = repository.save_raw_response(
                source="browse",
                endpoint="/example",
                request_url="https://api.ebay.com/example",
                response_json={
                    "itemId": "v1|123|0",
                    "sellerUsername": "seller-name",
                    "access_token": "token-value",
                },
            )

            with closing(sqlite3.connect(db_path)) as connection:
                row = connection.execute(
                    "SELECT response_json FROM raw_api_responses WHERE id = ?",
                    (raw.id,),
                ).fetchone()

            stored = json.loads(row[0])
            self.assertEqual(stored["itemId"], "v1|123|0")
            self.assertEqual(stored["sellerUsername"], REDACTED)
            self.assertEqual(stored["access_token"], REDACTED)


class EbayClientErrorRedactionTests(unittest.TestCase):
    def test_token_error_does_not_include_raw_response_text(self) -> None:
        class FakeResponse:
            ok = False
            status_code = 400
            text = "access_token=leaked-token client_secret=leaked-secret"
            headers = {}

            def json(self):
                raise ValueError

        class FakeSession:
            def post(self, *args, **kwargs):
                return FakeResponse()

        settings = Settings(
            ebay_env="production",
            ebay_client_id="client-id",
            ebay_client_secret="secret-value",
            ebay_dev_id="dev-id",
            db_path=Path("data/sellthrough.sqlite3"),
        )
        client = EbayClient(settings=settings, session=FakeSession())

        with self.assertRaises(EbayApiError) as context:
            client.mint_application_token()

        error_text = str(context.exception)
        self.assertEqual(error_text, "Token request failed: 400")
        self.assertNotIn("leaked-token", repr(context.exception.payload))
        self.assertNotIn("leaked-secret", repr(context.exception.payload))


if __name__ == "__main__":
    unittest.main()
