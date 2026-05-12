# Source Tour

This guide explains how to read the Python source as an application, not just as
a collection of files. The code is intentionally small, but it already uses
several production-shaped boundaries: configuration, CLI adapters, service
orchestration, API clients, repositories, and security helpers.

## Mental Model

SellThrough follows a simple flow:

```text
CLI arguments
  -> command handler
  -> settings/service/client/repository
  -> eBay API or SQLite
  -> dataclass result
  -> terminal output
```

Each layer has a different job:

- `sellthrough.cli` builds the root parser and dispatches to command handlers.
- `sellthrough.cli_commands` translates terminal input into application calls.
- `sellthrough.config` validates environment variables once and returns a
  `Settings` object.
- `sellthrough.ebay` adapts eBay HTTP/JSON APIs into typed Python dataclasses.
- `sellthrough.services` owns application workflows that are bigger than one
  SQL write or one API call.
- `sellthrough.db` owns SQLite schema and repository methods.
- `sellthrough.security` centralizes redaction and payload sanitization rules.

The main design principle is separation of concerns. A CLI command should not
know SQL. A repository should not parse command-line arguments. An eBay client
should not print terminal output. Keeping those boundaries visible makes the
project easier to test, easier to teach, and easier to extend.

## CLI Dispatch Pattern

The public entry point is `sellthrough.cli:main`, configured in
`pyproject.toml`. `main()` builds one root `argparse.ArgumentParser`, then each
command module registers its own subcommands.

Command modules call `set_defaults(handler=...)`. That attaches a function to
the parsed `args` object, so the root CLI can dispatch with:

```python
return args.handler(args, parser)
```

This avoids a long `if args.command == ...` chain. When adding a new command,
create or update a module in `sellthrough.cli_commands`, add a `register()`
function, attach handlers with `set_defaults`, and add the module to
`COMMAND_MODULES`.

## Data Boundaries

The eBay API clients keep two views of response data:

- The raw payload, stored on result objects as `raw_payload`.
- A normalized dataclass view, such as `BrowseItemSummary` or
  `SoldItemSummary`.

That split is important for ETL learning. Raw payloads preserve source truth and
can be replayed if transform logic changes. Dataclasses give the rest of the
application a small, predictable Python shape for display and first-pass
analytics.

SQLite follows the same idea. `raw_api_responses` stores sanitized raw JSON.
Future normalized tables can be rebuilt from that raw source.

## Error Handling

User input and setup problems generally become `ValueError` or `SettingsError`.
CLI handlers catch those and call `parser.error(...)`, which prints usage and
exits with code 2.

eBay failures become `EbayApiError` or a subclass. Rate limits use
`EbayRateLimitError` because schedulers may eventually retry or delay. Marketplace
Insights access denial uses `MarketplaceInsightsAccessError` because that is a
known approval state, not a generic crash.

## Testing Workflow

Most tests instantiate functions/classes directly instead of shelling out to a
real CLI process. This keeps tests fast and focused. The CLI still exposes
`main(argv)` so tests can pass an argument list and exercise real parser
dispatch without depending on `sys.argv`.

Useful verification commands:

```powershell
python -m unittest discover -s tests
python -m compileall src tests
```
