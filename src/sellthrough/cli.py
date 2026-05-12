from __future__ import annotations

import argparse
from pathlib import Path

from sellthrough.config import Settings, SettingsError
from sellthrough.db import initialize_database
from sellthrough.ebay.browse import BrowseClient
from sellthrough.ebay.client import EbayApiError
from sellthrough.ebay.marketplace_insights import (
    MarketplaceInsightsAccessError,
    MarketplaceInsightsClient,
)
from sellthrough.ebay.taxonomy import TaxonomyClient
from sellthrough.services.raw_storage import save_raw_api_page
from sellthrough.services.smoke import format_smoke_checks, run_smoke_checks
from sellthrough.services.watchlist import (
    add_watchlist_item,
    disable_watchlist_item,
    list_watchlist_items,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sellthrough",
        description="eBay resale market intelligence tools",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Inspect local config")
    config_parser.add_argument("action", choices=["check"])

    db_parser = subparsers.add_parser("db", help="Database utilities")
    db_parser.add_argument("action", choices=["init"])
    db_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Override the SQLite database path",
    )

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

    taxonomy_parser = subparsers.add_parser("taxonomy", help="Taxonomy API utilities")
    taxonomy_subparsers = taxonomy_parser.add_subparsers(dest="action", required=True)

    tree_parser = taxonomy_subparsers.add_parser(
        "default-tree",
        help="Get the default category tree for a marketplace",
    )
    tree_parser.add_argument(
        "--marketplace",
        default="EBAY_US",
        help="eBay marketplace ID, default EBAY_US",
    )

    suggest_parser = taxonomy_subparsers.add_parser(
        "suggest",
        help="Suggest eBay categories for a keyword query",
    )
    suggest_parser.add_argument("query", help="Keyword text, such as 'cordless drill'")
    suggest_parser.add_argument(
        "--marketplace",
        default="EBAY_US",
        help="eBay marketplace ID, default EBAY_US",
    )
    suggest_parser.add_argument(
        "--tree-id",
        default=None,
        help="Optional category tree ID; defaults from marketplace",
    )
    suggest_parser.add_argument("--limit", type=int, default=10, help="Rows to print")

    subtree_parser = taxonomy_subparsers.add_parser(
        "subtree",
        help="Print a flattened category subtree",
    )
    subtree_parser.add_argument("category_id", help="Root category ID")
    subtree_parser.add_argument(
        "--tree-id",
        default=None,
        help="Category tree ID; defaults to EBAY_US tree",
    )
    subtree_parser.add_argument(
        "--marketplace",
        default="EBAY_US",
        help="Marketplace used when --tree-id is omitted",
    )
    subtree_parser.add_argument("--limit", type=int, default=25, help="Rows to print")

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

    smoke_parser = subparsers.add_parser(
        "smoke",
        help="Run a shallow end-to-end check of local config and eBay API access",
    )
    smoke_parser.add_argument(
        "--query",
        default="dewalt drill",
        help="Keyword used for Browse and Marketplace Insights probes",
    )
    smoke_parser.add_argument("--limit", type=int, default=1, help="Small API page size")
    smoke_parser.add_argument(
        "--marketplace",
        default="EBAY_US",
        help="eBay marketplace ID, default EBAY_US",
    )
    smoke_parser.add_argument(
        "--save-raw",
        action="store_true",
        help="Persist the Browse smoke response to raw_api_responses",
    )

    watchlist_parser = subparsers.add_parser("watchlist", help="Manage sourcing watchlist rows")
    watchlist_subparsers = watchlist_parser.add_subparsers(dest="action", required=True)

    watchlist_add = watchlist_subparsers.add_parser("add", help="Add a watchlist row")
    watchlist_add.add_argument("label", help="Human-readable label")
    watchlist_add.add_argument(
        "--query",
        default=None,
        help="Search query; defaults to the label",
    )
    watchlist_add.add_argument(
        "--category-id",
        default=None,
        help="Optional eBay category ID",
    )

    watchlist_list = watchlist_subparsers.add_parser("list", help="List watchlist rows")
    watchlist_list.add_argument(
        "--all",
        action="store_true",
        dest="include_inactive",
        help="Include disabled rows",
    )

    watchlist_disable = watchlist_subparsers.add_parser(
        "disable",
        help="Disable a watchlist row without deleting it",
    )
    watchlist_disable.add_argument("id", type=int, help="Watchlist row ID")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config" and args.action == "check":
        try:
            settings = Settings.from_environment()
        except SettingsError as exc:
            parser.error(str(exc))
        print(settings.redacted_summary())
        return 0

    if args.command == "db" and args.action == "init":
        settings = Settings.from_environment(require_ebay_credentials=False)
        db_path = args.path or settings.db_path
        initialize_database(db_path)
        print(f"Initialized database at {db_path}")
        return 0

    if args.command == "browse" and args.action == "search":
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

    if args.command == "taxonomy":
        try:
            settings = Settings.from_environment()
            client = TaxonomyClient.from_settings(settings)

            if args.action == "default-tree":
                tree = client.get_default_category_tree_id(marketplace_id=args.marketplace)
                print(f"Marketplace: {tree.marketplace_id}")
                print(f"Category tree ID: {tree.category_tree_id}")
                print(f"Category tree version: {tree.category_tree_version or 'unknown'}")
                return 0

            if args.action == "suggest":
                suggestions = client.get_category_suggestions(
                    args.query,
                    category_tree_id=args.tree_id,
                    marketplace_id=args.marketplace,
                )
                for node in suggestions[: args.limit]:
                    leaf = "leaf" if node.leaf else "branch"
                    print(f"{node.category_id}\t{leaf}\t{node.category_name}")
                return 0

            if args.action == "subtree":
                tree_id = args.tree_id
                if tree_id is None:
                    tree_id = client.get_default_category_tree_id(
                        marketplace_id=args.marketplace
                    ).category_tree_id
                nodes = client.get_category_subtree(tree_id, args.category_id)
                for node in nodes[: args.limit]:
                    indent = "  " * node.level
                    leaf = "leaf" if node.leaf else "branch"
                    print(f"{indent}{node.category_id}\t{leaf}\t{node.category_name}")
                return 0
        except (SettingsError, EbayApiError, ValueError) as exc:
            parser.error(str(exc))

    if args.command == "insights" and args.action == "search":
        try:
            settings = Settings.from_environment()
            client = MarketplaceInsightsClient.from_settings(
                settings,
                marketplace_id=args.marketplace,
            )
            end = None
            start = None
            if args.days_back:
                from datetime import UTC, datetime, timedelta

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

    if args.command == "smoke":
        try:
            settings = Settings.from_environment()
            checks = run_smoke_checks(
                settings=settings,
                query=args.query,
                limit=args.limit,
                marketplace_id=args.marketplace,
                save_raw=args.save_raw,
            )
        except (SettingsError, EbayApiError, ValueError) as exc:
            print(f"[FAIL] smoke: {exc}")
            return 1

        print(format_smoke_checks(checks))
        return 0

    if args.command == "watchlist":
        try:
            settings = Settings.from_environment(require_ebay_credentials=False)
            if args.action == "add":
                item = add_watchlist_item(
                    db_path=settings.db_path,
                    label=args.label,
                    query=args.query,
                    category_id=args.category_id,
                )
                print(
                    f"Added watchlist item {item.id}: {item.label} "
                    f"(query={item.query}, category_id={item.category_id or 'none'})"
                )
                return 0

            if args.action == "list":
                items = list_watchlist_items(
                    db_path=settings.db_path,
                    include_inactive=args.include_inactive,
                )
                if not items:
                    print("No watchlist items found.")
                    return 0
                print("ID\tActive\tLabel\tQuery\tCategory ID\tAdded")
                for item in items:
                    active = "yes" if item.active else "no"
                    print(
                        f"{item.id}\t{active}\t{item.label}\t{item.query}\t"
                        f"{item.category_id or ''}\t{item.added_at}"
                    )
                return 0

            if args.action == "disable":
                disabled = disable_watchlist_item(db_path=settings.db_path, watchlist_id=args.id)
                if disabled:
                    print(f"Disabled watchlist item {args.id}.")
                    return 0
                print(f"No active watchlist item found for ID {args.id}.")
                return 1
        except (SettingsError, ValueError) as exc:
            parser.error(str(exc))

    parser.error("Unsupported command")
    return 2
