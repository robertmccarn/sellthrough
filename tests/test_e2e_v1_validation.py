from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from sellthrough.config import Settings
from sellthrough.ebay.browse import BrowseSearchResult
from sellthrough.services.active_polling import poll_active_watchlist
from sellthrough.services.dashboard import get_dashboard_summary
from sellthrough.services.snapshots import capture_all_watchlist_metric_snapshots
from sellthrough.services.watchlist import add_watchlist_item


class V1ValidationFlowTests(unittest.TestCase):
    def test_v1_flow_watchlist_poll_snapshot_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sellthrough.sqlite3"
            watchlist = add_watchlist_item(
                db_path=db_path,
                label="DeWalt drill",
                query="dewalt 20v drill",
                category_id="184655",
            )
            settings = Settings(
                ebay_env="production",
                ebay_client_id="client-id",
                ebay_client_secret="secret",
                ebay_dev_id="dev-id",
                db_path=db_path,
            )

            browse_payload = {
                "total": 2,
                "href": "https://api.ebay.com/buy/browse/v1/item_summary/search?q=dewalt",
                "next": None,
                "itemSummaries": [
                    {
                        "itemId": "v1|123|0",
                        "title": "DeWalt 20V Drill Kit",
                        "price": {"value": "89.99", "currency": "USD"},
                        "shippingOptions": [
                            {"shippingCost": {"value": "7.99", "currency": "USD"}}
                        ],
                        "categories": [
                            {"categoryId": "184655", "categoryName": "Power Drills"}
                        ],
                        "condition": "Used",
                    },
                    {
                        "itemId": "v1|124|0",
                        "title": "DeWalt 20V Hammer Drill",
                        "price": {"value": "109.99", "currency": "USD"},
                        "shippingOptions": [
                            {"shippingCost": {"value": "9.99", "currency": "USD"}}
                        ],
                        "categories": [
                            {"categoryId": "184655", "categoryName": "Power Drills"}
                        ],
                        "condition": "Seller refurbished",
                    },
                ],
            }

            with patch("sellthrough.services.active_polling.BrowseClient") as browse_client:
                browse_client.from_settings.return_value.search_active_items.return_value = (
                    BrowseSearchResult.from_payload(
                        query="dewalt 20v drill",
                        limit=25,
                        offset=0,
                        payload=browse_payload,
                    )
                )

                poll_results = poll_active_watchlist(
                    settings=settings,
                    marketplace_id="EBAY_US",
                    limit=25,
                    offset=0,
                )

            self.assertEqual(len(poll_results), 1)
            self.assertEqual(poll_results[0].watchlist_id, watchlist.id)
            self.assertEqual(poll_results[0].returned, 2)
            self.assertEqual(poll_results[0].normalized, 2)

            with closing(sqlite3.connect(db_path)) as connection:
                raw_count = connection.execute("SELECT COUNT(*) FROM raw_api_responses").fetchone()[0]
                listing_count = connection.execute("SELECT COUNT(*) FROM active_listings").fetchone()[0]
                observation_count = connection.execute("SELECT COUNT(*) FROM active_listing_observations").fetchone()[0]

            self.assertEqual(raw_count, 1)
            self.assertEqual(listing_count, 2)
            self.assertEqual(observation_count, 2)

            snapshot_result = capture_all_watchlist_metric_snapshots(db_path=db_path)
            self.assertEqual(snapshot_result.captured, 1)
            self.assertEqual(len(snapshot_result.rows), 1)
            self.assertEqual(snapshot_result.rows[0].watchlist_id, watchlist.id)
            self.assertEqual(snapshot_result.rows[0].active_count, 2)

            dashboard = get_dashboard_summary(db_path=db_path)
            self.assertEqual(dashboard.watchlist_count, 1)
            self.assertEqual(dashboard.active_listing_count, 2)
            self.assertIsNotNone(dashboard.latest_poll_run)
            self.assertIsNotNone(dashboard.latest_raw_response)
            self.assertEqual(len(dashboard.recent_snapshot_rows), 1)
            self.assertEqual(dashboard.recent_snapshot_rows[0].watchlist_label, "DeWalt drill")
            self.assertEqual(dashboard.sold_metrics_status, "pending")
            self.assertEqual(dashboard.opportunity_metrics_status, "pending")


if __name__ == "__main__":
    unittest.main()
