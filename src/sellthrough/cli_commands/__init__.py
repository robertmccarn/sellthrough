"""Command modules for the SellThrough CLI.

Each module exposes a `register(subparsers)` function and one or more handlers.
The root CLI imports these modules explicitly so the command surface is easy to
audit and help output stays deterministic.
"""

from sellthrough.cli_commands import browse, config, db, insights, smoke, taxonomy, watchlist

__all__ = [
    "browse",
    "config",
    "db",
    "insights",
    "smoke",
    "taxonomy",
    "watchlist",
]
