"""Top-level command-line interface assembly.

The CLI deliberately uses a small "register and dispatch" pattern:

1. This module creates the root `argparse.ArgumentParser`.
2. Each module in `sellthrough.cli_commands` registers one command family.
3. Subcommands attach a callable named `handler` to the parsed namespace.
4. `main()` invokes that handler and returns its process exit code.

That keeps the public entry point stable (`sellthrough.cli:main`) while letting
command families grow independently. For a learner, the useful mental model is
"the root parser knows which command module owns each verb, but it does not know
how that verb works."
"""

from __future__ import annotations

import argparse

from sellthrough.cli_commands import browse, config, db, insights, smoke, taxonomy, watchlist


# The order here is user-facing: argparse prints subcommands in registration
# order. Keeping it explicit makes help output predictable and reviewable.
COMMAND_MODULES = (config, db, browse, taxonomy, insights, smoke, watchlist)


def build_parser() -> argparse.ArgumentParser:
    """Build and return the root parser without reading environment or network state.

    Parser construction is intentionally pure: tests can inspect the command
    surface without needing eBay credentials, a database, or an internet
    connection. Runtime side effects start only after `parse_args()` selects a
    concrete command handler.
    """

    parser = argparse.ArgumentParser(
        prog="sellthrough",
        description="eBay resale market intelligence tools",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command_module in COMMAND_MODULES:
        # Each command module receives the same subparser collection and adds
        # exactly the verbs it owns. This mirrors a lightweight plugin pattern
        # without introducing dynamic imports or framework machinery.
        command_module.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return an integer exit code.

    Passing `argv` is the test seam: production calls use `None`, which lets
    argparse read `sys.argv`; tests pass a list such as `["db", "init"]` and
    exercise the same code path without spawning a subprocess.
    """

    parser = build_parser()
    args = parser.parse_args(argv)
    # `set_defaults(handler=...)` is the handoff from argparse to application
    # code. The root dispatcher does not need a long `if args.command == ...`
    # chain because the selected subcommand already carries its handler.
    return args.handler(args, parser)
