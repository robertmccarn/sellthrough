# Validation Notes

Last verified: 2026-05-12

This log records local validation commands for SellThrough. It is designed for
reviewers and future maintenance passes.

## Core Validation

| Command | Requires Credentials | Expected Result |
|---|---|---|
| `python -m unittest` | No | Full local test suite runs and passes. |
| `python -m pytest tests/test_e2e_v1_validation.py -q` | No (uses mocked Browse responses) | V1 end-to-end local flow (watchlist -> poll -> raw/normalized -> snapshot -> dashboard summary) passes. |
| `powershell -ExecutionPolicy Bypass -File .\scripts\run-v1-validation.ps1` | No (uses mocked Browse responses) | Runs V1 E2E validation and writes a timestamped markdown report in `reports/validation/`. |
| `python -m sellthrough --help` | No | Top-level CLI help renders with available command groups. |
| `python -m sellthrough watchlist --help` | No | Watchlist subcommand help renders, including `poll-active` and `capture-snapshots`. |
| `python -m sellthrough lookup --help` | No | Lookup subcommand help renders for `active` and `watchlist`. |
| `python -m sellthrough web --help` | No | Web command help renders. |

## Optional Web Path Validation

| Command | Requires Credentials | Expected Result |
|---|---|---|
| `python -m pip install -e .[web]` | No | Optional web dependencies install successfully. |
| `python -m sellthrough web serve` | No for startup | Local server starts on localhost and serves routes from SQLite-backed local state. |
| `GET /health` | No | Returns readiness JSON with database/path counts, credentials-configured boolean, and Marketplace Insights pending status. |
| `GET /dashboard` | No | Returns dashboard page with real active-side local metrics and explicit pending sold/opportunity/trend states. |
| `GET /watchlist` | No | Returns watchlist page from local SQLite state. |
| `GET /lookup` | No | Returns read-only lookup form supporting title-text and watchlist-scoped active summaries. |

## Notes

- Commands that call live eBay APIs, such as `watchlist poll-active`, require
  Browse credentials and internet access.
- Validation above intentionally avoids live eBay calls so reviewers can run it
  in local/offline development contexts.
