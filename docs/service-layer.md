# Service Layer

SellThrough now has a small application service layer under
`src/sellthrough/services/`.

## Purpose

Clients and repositories are deliberately low-level:

- eBay clients know how to talk to eBay.
- Repositories know how to persist data.
- CLI commands know how to parse arguments and print output.

Services hold the reusable workflow in the middle. This matters because the
future local web console and eventual hosted/mobile surfaces should call the
same use-case code as the CLI instead of reimplementing eBay and database
orchestration.

## Current Services

- `services.raw_storage.save_raw_api_page`: creates a poll run, saves one
  sanitized raw response page, and marks the run completed or failed.
- `services.active_polling.poll_active_watchlist`: reads active watchlist rows,
  calls Browse, stores raw responses, normalizes active listings, and writes
  observation lineage.
- `services.active_listings.normalize_active_browse_payload`: turns raw Browse
  payloads into stable active listing records and optional observation rows.
- `services.lookup`: provides title-text active lookup and preferred
  watchlist-scoped lookup.
- `services.snapshots`: captures active-side watchlist metric snapshots while
  sold fields remain pending.
- `services.dashboard.get_dashboard_summary`: builds a local dashboard contract
  from real SQLite state and explicit pending statuses.
- `services.smoke.run_smoke_checks`: performs the shallow end-to-end health check
  used by the CLI and future web status pages.

## Design Rule

When a workflow needs more than one low-level dependency, put that orchestration
in a service module. Keep CLI and future web routes thin.
