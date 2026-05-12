from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta

from sellthrough.config import Settings, SettingsError
from sellthrough.ebay.client import EbayApiError
from sellthrough.ebay.marketplace_insights import (
    MarketplaceInsightsAccessError,
    MarketplaceInsightsClient,
)
from sellthrough.services.raw_storage import save_raw_api_page


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    insights_parser = subparsers.add_parser(
        "insights",
        help="Marketplace Insights sold-item utilities",
    )
    insights_subparsers = insights_parser.add_subparsers(dest="action", required=True)
    sold_parser = insights_subparsers.add_parser(
        "search",
        help="Search historical sold listings when access is approved",
    )
    sold_parser.add_argument("query", help="Keyword search text, such as 'dewalt drill'")
    sold_parser.add_argument("--limit", type=int, default=5, help="Results to return")
    sold_parser.add_argument("--offset", type=int, default=0, help="Pagination offset")
    sold_parser.add_argument("--days-back", type=int, default=30, help="Sold-date lookback")
    sold_parser.add_argument(
        "--marketplace",
        default="EBAY_US",
        help="eBay marketplace ID, default EBAY_US",
    )
    sold_parser.add_argument(
        "--category-id",
        action="append",
        dest="category_ids",
        help="Optional category ID filter; repeat for multiple categories",
    )
    sold_parser.add_argument(
        "--save-raw",
        action="store_true",
        help="Store the raw Marketplace Insights response page in SQLite",
    )
    sold_parser.set_defaults(handler=handle_search)


def handle_search(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        settings = Settings.from_environment()
        client = MarketplaceInsightsClient.from_settings(
            settings,
            marketplace_id=args.marketplace,
        )
        end = None
        start = None
        if args.days_back:
            end = datetime.now(UTC)
            start = end - timedelta(days=args.days_back)

        result = client.search_sold_items(
            args.query,
            limit=args.limit,
            offset=args.offset,
            category_ids=args.category_ids,
            last_sold_start=start,
            last_sold_end=end,
        )
    except MarketplaceInsightsAccessError as exc:
        print(str(exc))
        print("Application Growth Check approval is still required before sold data works.")
        return 1
    except (SettingsError, EbayApiError, ValueError) as exc:
        parser.error(str(exc))

    raw_record_id = None
    if args.save_raw:
        saved = save_raw_api_page(
            db_path=settings.db_path,
            source="marketplace_insights",
            endpoint="/buy/marketplace_insights/v1_beta/item_sales/search",
            request_url=result.href or "",
            response_json=result.raw_payload,
            query=result.query,
            category_id=",".join(args.category_ids) if args.category_ids else None,
        )
        raw_record_id = saved.raw_response_id

    print(f"Query: {result.query}")
    print(f"Total sold results: {result.total}")
    print(f"Returned: {len(result.items)}")
    if raw_record_id is not None:
        print(f"Saved raw response ID: {raw_record_id}")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning.get('errorId')}: {warning.get('message')}")
    print()
    for index, item in enumerate(result.items, start=1):
        price = (
            f"{item.sold_price_value:.2f} {item.sold_price_currency}"
            if item.sold_price_value is not None and item.sold_price_currency
            else "sold price unavailable"
        )
        print(f"{index}. {item.title}")
        print(f"   {price} | condition={item.condition or 'unknown'}")
        print(f"   item_id={item.item_id} | last_sold={item.last_sold_date or 'unknown'}")
        if item.item_web_url:
            print(f"   url={item.item_web_url}")
    return 0
