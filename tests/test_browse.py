from __future__ import annotations

import unittest

from sellthrough.ebay.browse import BrowseClient, BrowseSearchResult, MAX_BROWSE_LIMIT
from sellthrough.ebay.client import EbayApiError, EbayRateLimitError


class BrowseSearchResultTests(unittest.TestCase):
    def test_from_payload_normalizes_item_summaries(self) -> None:
        payload = {
            "total": 1,
            "href": "https://example.test/current",
            "next": "https://example.test/next",
            "itemSummaries": [
                {
                    "itemId": "v1|123|0",
                    "title": "Example Drill",
                    "price": {"value": "42.50", "currency": "USD"},
                    "condition": "Used",
                    "itemWebUrl": "https://www.ebay.com/itm/123",
                    "itemCreationDate": "2026-05-01T00:00:00.000Z",
                    "buyingOptions": ["FIXED_PRICE"],
                }
            ],
        }

        result = BrowseSearchResult.from_payload(
            query="drill",
            limit=10,
            offset=0,
            payload=payload,
        )

        self.assertEqual(result.total, 1)
        self.assertEqual(result.next_url, "https://example.test/next")
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].price_value, 42.5)
        self.assertEqual(result.items[0].buying_options, ("FIXED_PRICE",))


class BrowseClientTests(unittest.TestCase):
    class _FakeResponse:
        def __init__(self, *, ok: bool, status_code: int, payload: dict, headers: dict | None = None) -> None:
            self.ok = ok
            self.status_code = status_code
            self._payload = payload
            self.headers = headers or {}

        def json(self):
            return self._payload

    class _FakeSession:
        def __init__(self, response):
            self._response = response
            self.last_get_kwargs = None

        def get(self, *args, **kwargs):
            self.last_get_kwargs = kwargs
            return self._response

    class _FakeEbayClient:
        class settings:
            api_base_url = "https://api.ebay.com"

        def __init__(self, session):
            self.session = session

        def bearer_token(self):
            return "token"

    def test_search_active_items_raises_rate_limit_error_on_429(self) -> None:
        response = self._FakeResponse(
            ok=False,
            status_code=429,
            headers={"Retry-After": "15"},
            payload={"errors": [{"message": "Too many requests"}]},
        )
        client = BrowseClient(self._FakeEbayClient(self._FakeSession(response)))

        with self.assertRaises(EbayRateLimitError) as ctx:
            client.search_active_items("dewalt drill")
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(ctx.exception.retry_after_seconds, 15)

    def test_search_active_items_raises_api_error_on_non_429_failure(self) -> None:
        response = self._FakeResponse(
            ok=False,
            status_code=500,
            payload={"errors": [{"message": "Server error"}]},
        )
        client = BrowseClient(self._FakeEbayClient(self._FakeSession(response)))

        with self.assertRaises(EbayApiError) as ctx:
            client.search_active_items("dewalt drill")
        self.assertEqual(ctx.exception.status_code, 500)

    def test_search_active_items_clamps_limit_to_max(self) -> None:
        response = self._FakeResponse(
            ok=True,
            status_code=200,
            payload={"total": 0, "itemSummaries": []},
        )
        session = self._FakeSession(response)
        client = BrowseClient(self._FakeEbayClient(session))

        result = client.search_active_items("dewalt drill", limit=MAX_BROWSE_LIMIT + 50)

        self.assertEqual(result.limit, MAX_BROWSE_LIMIT)
        self.assertEqual(session.last_get_kwargs["params"]["limit"], MAX_BROWSE_LIMIT)

    def test_iter_active_item_pages_stops_when_no_next_url(self) -> None:
        class FakeBrowseClient(BrowseClient):
            def __init__(self):
                pass

            def search_active_items(self, query, *, limit=10, offset=0, category_ids=None):
                return BrowseSearchResult.from_payload(
                    query=query,
                    limit=limit,
                    offset=offset,
                    payload={
                        "total": 1,
                        "href": "https://example.test/current",
                        "next": None,
                        "itemSummaries": [{"itemId": "v1|123|0", "title": "Item"}],
                    },
                )

        pages = list(FakeBrowseClient().iter_active_item_pages("drill", page_size=5))
        self.assertEqual(len(pages), 1)

    def test_iter_active_item_pages_respects_max_pages(self) -> None:
        class FakeBrowseClient(BrowseClient):
            def __init__(self):
                self.calls = 0

            def search_active_items(self, query, *, limit=10, offset=0, category_ids=None):
                self.calls += 1
                return BrowseSearchResult.from_payload(
                    query=query,
                    limit=limit,
                    offset=offset,
                    payload={
                        "total": 999,
                        "href": "https://example.test/current",
                        "next": "https://example.test/next",
                        "itemSummaries": [{"itemId": f"v1|{self.calls}|0", "title": "Item"}],
                    },
                )

        fake = FakeBrowseClient()
        pages = list(fake.iter_active_item_pages("drill", page_size=5, max_pages=2))
        self.assertEqual(len(pages), 2)
        self.assertEqual(fake.calls, 2)


if __name__ == "__main__":
    unittest.main()
