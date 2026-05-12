from __future__ import annotations

import argparse

from sellthrough.cli_commands import browse, config, db, insights, lookup, smoke, taxonomy, watchlist


COMMAND_MODULES = (config, db, browse, taxonomy, insights, lookup, smoke, watchlist)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sellthrough",
        description="eBay resale market intelligence tools",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command_module in COMMAND_MODULES:
        command_module.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args, parser)
