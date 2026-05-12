# SellThrough

SellThrough is a personal data analytics learning project for eBay marketplace
research. The goal is to practice API integration, ETL pipeline design,
database modeling, and lightweight analytics around resale market signals.

## Current Status

- Production OAuth access: verified
- Browse API active listings: verified
- Taxonomy API: verified
- Marketplace Insights API: pending Application Growth Check approval
- Finding API: intentionally not used; it has been decommissioned

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

Check the default eBay category tree:

```powershell
python -m sellthrough taxonomy default-tree --marketplace EBAY_US
```

Check Marketplace Insights access after eBay approval:

```powershell
python -m sellthrough insights search "dewalt drill" --days-back 30 --limit 5
```

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
