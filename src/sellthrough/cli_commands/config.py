"""CLI command family for local configuration diagnostics."""

from __future__ import annotations

import argparse

from sellthrough.config import Settings, SettingsError


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register `sellthrough config check`."""

    config_parser = subparsers.add_parser("config", help="Inspect local config")
    check_parser = config_parser.add_subparsers(dest="action", required=True)
    check_parser.add_parser("check").set_defaults(handler=handle_check)


def handle_check(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Validate environment settings and print a redacted summary."""

    try:
        settings = Settings.from_environment()
    except SettingsError as exc:
        parser.error(str(exc))
    print(settings.redacted_summary())
    return 0
