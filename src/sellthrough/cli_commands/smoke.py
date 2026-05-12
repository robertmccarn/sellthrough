from __future__ import annotations

import argparse

from sellthrough.config import Settings, SettingsError
from sellthrough.ebay.client import EbayApiError
from sellthrough.services.smoke import format_smoke_checks, run_smoke_checks


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
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
    smoke_parser.set_defaults(handler=handle)


def handle(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
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
