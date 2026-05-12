# SellThrough

SellThrough is a personal data analytics learning project for eBay marketplace
research. The goal is to practice API integration, ETL pipeline design,
database modeling, and lightweight analytics around resale market signals.

## Architecture Status

Current pipeline:

```text
Watchlist -> Browse API -> raw_api_responses -> active_listings
          -> active_listing_observations -> watchlist_metric_snapshots
          -> lookup active / lookup watchlist
```

SellThrough currently supports watchlist-driven active listing ingestion and
local active-listing lookup summaries. Snapshot scaffolding now exists for
watchlist-level active metric capture. Sold metrics, sell-through scoring,
opportunity ranking, and trend charts remain pending Marketplace Insights access
and sold-listing normalization.

## Current Status

- Production OAuth access: verified
- Browse API active listings: verified
- Taxonomy API: verified
- Marketplace Insights API: pending Application Growth Check approval
- Finding API: intentionally not used; it has been decommissioned

## Design Docs

- [Design document v0.3](docs/design-document-v0.3.md)
- [Self-audit against original design](docs/self-audit-2026-05-12.md)
- [eBay API design notes](docs/ebay-api-design.md)
- [Raw storage design](docs/raw-storage-design.md)
- [CLI smoke command](docs/cli-smoke-command.md)
- [Codex handoff notes](docs/codex-handoff.md)
- [Security hardening guide](docs/security-hardening.md)
- [Future wishlist](docs/future-wishlist.md)
- [Service layer](docs/service-layer.md)
- [Watchlist design](docs/watchlist-design.md)
- [Active polling design](docs/active-polling-design.md)
- [Lookup command](docs/lookup-command.md)
- [Frontend architecture roadmap](docs/frontend-roadmap.md)
- [Metric snapshots design](docs/metric-snapshots-design.md)
- [Brand guidelines](docs/brand-guidelines.md)

## Local Setup

Requires Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Create local environment variables from `.env.example`. Do not commit real
credentials.

```powershell
setx EBAY_CLIENT_ID "your-production-app-id"
setx EBAY_CLIENT_SECRET "your-production-cert-id"
setx EBAY_DEV_ID "your-dev-id"
setx EBAY_ENV "production"
```

Initialize the local SQLite database:

```powershell
python -m sellthrough db init
```

Run a live Browse API smoke search:

```powershell
python -m sellthrough browse search "dewalt drill" --limit 3
```

Save the raw Browse response page while searching:

```powershell
python -m sellthrough browse search "dewalt drill" --limit 3 --save-raw
```

Run the first end-to-end smoke command:

```powershell
python -m sellthrough smoke --query "dewalt drill" --limit 1
```

Check the default eBay category tree:

```powershell
python -m sellthrough taxonomy default-tree --marketplace EBAY_US
```

Check Marketplace Insights access after eBay approval:

```powershell
python -m sellthrough insights search "dewalt drill" --days-back 30 --limit 5
```

Add and inspect watchlist rows:

```powershell
python -m sellthrough watchlist add "DeWalt 20V drill" --query "dewalt 20v drill" --category-id 184655
python -m sellthrough watchlist list
```

Poll active watchlist rows through Browse, save sanitized raw pages, and upsert
normalized `active_listings` rows:

```powershell
python -m sellthrough watchlist poll-active --limit 25
python -m sellthrough watchlist capture-snapshots
```

Query normalized active listings:

```powershell
python -m sellthrough lookup active "dewalt drill" --samples 5
```

Run the local web skeleton (optional dependencies):

```powershell
python -m pip install -e .[web]
python -m sellthrough web serve
```

Initial web routes:

- `/health`
- `/dashboard`
- `/watchlist`
- `/lookup`

## Learning-First Development Standard

SellThrough is intentionally both a working tool and a learning model for data
analytics/data engineering practice. Every feature should leave behind enough
context for a developing data professional to understand why the code exists,
how data moves through it, and what tradeoffs were made.

Project documentation expectations:

- Keep external design notes in `docs/` when adding new subsystems, workflows,
  schemas, or API integrations.
- Use dense, readable inline comments around non-obvious logic, data modeling
  choices, API quirks, and failure handling.
- Prefer short explanatory comments over narration of obvious Python syntax.
- Update this README when setup, commands, or project status changes.
- Keep generated files, credentials, local databases, caches, and build outputs
  out of Git and prune them from the working folder when they are no longer
  needed.
