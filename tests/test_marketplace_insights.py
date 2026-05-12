from __future__ import annotations

import unittest
from datetime import UTC, date, datetime

from sellthrough.ebay.marketplace_insights import (
    MarketplaceInsightsAccessError,
    MarketplaceInsightsClient,
    SoldSearchResult,
    build_last_sold_date_filter,
)


class SoldSearchResultTests(unittest.TestCase):
    def test_from_payload_normalizes_item_sales(self) -> None:
        payload = {
            "total": 1,
            "href": "https://example.test/current",
            "next": "https://example.test/next",
            "itemSales": [
                {
                    "itemId": "v1|123|0",
                    "title": "Example Drill",
                    "lastSoldPrice": {"value": "35.00", "currency": "USD"},
                    "condition": "Used",
                    "lastSoldDate": "2026-05-01T00:00:00.000Z",
                    "itemWebUrl": "https://www.ebay.com/itm/123",
                    "categories": [{"categoryId": "184655"}],
                }
            ],
        }

        result = SoldSearchResult.from_payload(
            query="drill",
            limit=10,
            offset=0,
            payload=payload,
        )

        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].sold_price_value, 35.0)
        self.assertEqual(result.items[0].category_ids, ("184655",))


class LastSoldDateFilterTests(unittest.TestCase):
    def test_build_filter_accepts_dates_and_datetimes(self) -> None:
        start = date(2026, 4, 1)
        end = datetime(2026, 5, 1, 12, 30, tzinfo=UTC)

        result = build_last_sold_date_filter(start, end)

        self.assertEqual(
            result,
            "lastSoldDate:[2026-04-01T00:00:00Z..2026-05-01T12:30:00Z]",
        )


class MarketplaceInsightsAccessTests(unittest.TestCase):
    def test_access_denied_payload_raises_specific_error(self) -> None:
        class FakeResponse:
            ok = False
            status_code = 403
            headers = {}

            def json(self):
                return {
                    "errors": [
                        {
                            "errorId": 1100,
                            "domain": "ACCESS",
                            "category": "REQUEST",
                            "message": "Access denied",
                        }
                    ]
                }

        class FakeSession:
            def get(self, *args, **kwargs):
                return FakeResponse()

        class FakeEbayClient:
            session = FakeSession()

            class settings:
                api_base_url = "https://api.ebay.com"

            def bearer_token(self):
                return "token"

        client = MarketplaceInsightsClient(FakeEbayClient())

        with self.assertRaises(MarketplaceInsightsAccessError):
            client.search_sold_items("dewalt drill")


if __name__ == "__main__":
    unittest.main()
