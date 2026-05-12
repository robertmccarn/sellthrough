from __future__ import annotations

import unittest

from sellthrough.ebay.browse import BrowseSearchResult


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


if __name__ == "__main__":
    unittest.main()
