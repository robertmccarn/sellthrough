from __future__ import annotations

import argparse

from sellthrough.config import Settings, SettingsError
from sellthrough.ebay.browse import BrowseClient
from sellthrough.ebay.client import EbayApiError
from sellthrough.services.raw_storage import save_raw_api_page


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    browse_parser = subparsers.add_parser("browse", help="Browse API utilities")
    browse_subparsers = browse_parser.add_subparsers(dest="action", required=True)
    search_parser = browse_subparsers.add_parser("search", help="Search active eBay listings")
    search_parser.add_argument("query", help="Keyword search text, such as 'dewalt drill'")
    search_parser.add_argument("--limit", type=int, default=5, help="Results to return")
    search_parser.add_argument("--offset", type=int, default=0, help="Pagination offset")
    search_parser.add_argument(
        "--marketplace",
        default="EBAY_US",
        help="eBay marketplace ID, default EBAY_US",
    )
    search_parser.add_argument(
        "--category-id",
        action="append",
        dest="category_ids",
        help="Optional category ID filter; repeat for multiple categories",
    )
    search_parser.add_argument(
        "--save-raw",
        action="store_true",
        help="Store the raw Browse response page in SQLite",
    )
    search_parser.set_defaults(handler=handle_search)


def handle_search(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        settings = Settings.from_environment()
        client = BrowseClient.from_settings(settings, marketplace_id=args.marketplace)
        result = client.search_active_items(
            args.query,
            limit=args.limit,
            offset=args.offset,
            category_ids=args.category_ids,
        )
    except (SettingsError, EbayApiError, ValueError) as exc:
        parser.error(str(exc))

    raw_record_id = None
    if args.save_raw:
        saved = save_raw_api_page(
            db_path=settings.db_path,
            source="browse",
            endpoint="/buy/browse/v1/item_summary/search",
            request_url=result.href or "",
            response_json=result.raw_payload,
            query=result.query,
            category_id=",".join(args.category_ids) if args.category_ids else None,
        )
        raw_record_id = saved.raw_response_id

    print(f"Query: {result.query}")
    print(f"Total active results: {result.total}")
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
            f"{item.price_value:.2f} {item.price_currency}"
            if item.price_value is not None and item.price_currency
            else "price unavailable"
        )
        print(f"{index}. {item.title}")
        print(f"   {price} | condition={item.condition or 'unknown'}")
        print(f"   item_id={item.item_id}")
        if item.item_web_url:
            print(f"   url={item.item_web_url}")
    return 0
