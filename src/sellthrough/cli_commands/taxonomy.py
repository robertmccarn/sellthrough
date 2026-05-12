from __future__ import annotations

import argparse

from sellthrough.config import Settings, SettingsError
from sellthrough.ebay.client import EbayApiError
from sellthrough.ebay.taxonomy import TaxonomyClient


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
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
    tree_parser.set_defaults(handler=handle_default_tree)

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
    suggest_parser.set_defaults(handler=handle_suggest)

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
    subtree_parser.set_defaults(handler=handle_subtree)


def handle_default_tree(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        client = _client_from_environment()
        tree = client.get_default_category_tree_id(marketplace_id=args.marketplace)
    except (SettingsError, EbayApiError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Marketplace: {tree.marketplace_id}")
    print(f"Category tree ID: {tree.category_tree_id}")
    print(f"Category tree version: {tree.category_tree_version or 'unknown'}")
    return 0


def handle_suggest(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        client = _client_from_environment()
        suggestions = client.get_category_suggestions(
            args.query,
            category_tree_id=args.tree_id,
            marketplace_id=args.marketplace,
        )
    except (SettingsError, EbayApiError, ValueError) as exc:
        parser.error(str(exc))

    for node in suggestions[: args.limit]:
        leaf = "leaf" if node.leaf else "branch"
        print(f"{node.category_id}\t{leaf}\t{node.category_name}")
    return 0


def handle_subtree(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        client = _client_from_environment()
        tree_id = args.tree_id
        if tree_id is None:
            tree_id = client.get_default_category_tree_id(
                marketplace_id=args.marketplace
            ).category_tree_id
        nodes = client.get_category_subtree(tree_id, args.category_id)
    except (SettingsError, EbayApiError, ValueError) as exc:
        parser.error(str(exc))

    for node in nodes[: args.limit]:
        indent = "  " * node.level
        leaf = "leaf" if node.leaf else "branch"
        print(f"{indent}{node.category_id}\t{leaf}\t{node.category_name}")
    return 0


def _client_from_environment() -> TaxonomyClient:
    settings = Settings.from_environment()
    return TaxonomyClient.from_settings(settings)
