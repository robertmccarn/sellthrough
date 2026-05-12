# Codex Handoff Notes

Audience: a future Codex instance working with Robert on another computer after
cloning or pulling `https://github.com/robertmccarn/sellthrough`.

## Project Identity

SellThrough is a local-first Python application for learning and practicing
data engineering through eBay resale market intelligence. It is meant to become
a practical resale intelligence tool, but the learning model is equally
important: explain data-engineering choices clearly, keep docs current, and
leave the working folder clean.

Standing directive from Robert:

- Write dense, readable inline and external documentation.
- Keep design documentation updated through feature additions.
- Preserve the app as a learning model for a developing data professional.
- Keep generated files, caches, local databases, and build outputs pruned.

## Repository State To Expect

Remote:

```text
https://github.com/robertmccarn/sellthrough.git
```

Branches change quickly. Before starting, inspect `main`, the current branch,
and any open PR branch Robert mentions rather than assuming the historical
branch list below is current.

Before starting, run:

```powershell
git fetch --all --prune
git status -sb
git branch -a
git log --oneline --decorate --graph --all -n 12
```

If Robert says he merged a PR, switch to `main`, pull with `--ff-only`, run tests,
and delete merged local feature branches.

## Local Environment Setup

Python 3.11+ is required. This machine used Python 3.14 successfully.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Credentials are stored as environment variables, not in Git:

```powershell
EBAY_ENV=production
EBAY_CLIENT_ID=<production app id>
EBAY_CLIENT_SECRET=<production cert id>
EBAY_DEV_ID=<developer id>
SELLTHROUGH_DB_PATH=data/sellthrough.sqlite3
```

On the original machine, Codex did not inherit user-level Windows env vars
automatically, so commands often loaded them explicitly:

```powershell
$env:EBAY_CLIENT_ID=[Environment]::GetEnvironmentVariable('EBAY_CLIENT_ID','User')
$env:EBAY_CLIENT_SECRET=[Environment]::GetEnvironmentVariable('EBAY_CLIENT_SECRET','User')
$env:EBAY_DEV_ID=[Environment]::GetEnvironmentVariable('EBAY_DEV_ID','User')
$env:EBAY_ENV=[Environment]::GetEnvironmentVariable('EBAY_ENV','User')
```

Do not print secrets. Boolean/redacted checks are fine.

## eBay API Reality

Current confirmed behavior:

- OAuth token generation works with Production credentials.
- Browse API works for active listings.
- Taxonomy API works for `EBAY_US`; tree ID observed as `0`, version `134`.
- Marketplace Insights is the correct sold-history API but returns access
  denied until Application Growth Check is approved.
- Finding API should not be used. It is decommissioned/unreliable and was
  removed from the architecture.

Useful verification:

```powershell
python -m sellthrough config check
python -m sellthrough browse search "dewalt drill" --limit 1
python -m sellthrough taxonomy default-tree --marketplace EBAY_US
python -m sellthrough smoke --query "dewalt drill" --limit 1
```

Expected smoke result before Marketplace Insights approval:

```text
[PASS] config: ...
[PASS] sqlite: schema initialized
[PASS] browse: ...
[PASS] taxonomy: ...
[WARN] marketplace insights: access pending; Application Growth Check approval still required
```

## Documentation Map

Read these before implementing major changes:

- `docs/development-guide.md`: standing development/documentation rules.
- `docs/design-document-v0.3.md`: current architecture and roadmap.
- `docs/self-audit-2026-05-12.md`: gaps against the original design.
- `docs/ebay-api-design.md`: API roles and endpoint decisions.
- `docs/raw-storage-design.md`: raw-first ETL storage pattern.
- `docs/cli-smoke-command.md`: smoke command behavior.
- `docs/metric-snapshots-design.md`: active-side snapshot scaffolding.
- `docs/frontend-roadmap.md`: local web/dashboard direction.
- `docs/brand-guidelines.md`: logo, palette, and UI tokens.

## Current Architecture Summary

Implemented or in-flight:

- `src/sellthrough/config.py`: env-based settings and redacted diagnostics.
- `src/sellthrough/ebay/client.py`: OAuth application-token client.
- `src/sellthrough/ebay/browse.py`: active listing search.
- `src/sellthrough/ebay/taxonomy.py`: category tree/suggestions/subtree.
- `src/sellthrough/ebay/marketplace_insights.py`: sold-history adapter with
  access-pending handling.
- `src/sellthrough/db.py`: SQLite schema, repositories, raw responses,
  normalized active listings, observations, and active-side snapshots.
- `src/sellthrough/services/`: reusable workflows for raw storage, active
  polling, normalization, lookup, snapshots, dashboard summary, and smoke
  checks.
- `src/sellthrough/cli.py`: top-level CLI assembly and dispatch.
- `src/sellthrough/cli_commands/`: command-specific parser and handler modules.
- `src/sellthrough/web/`: optional local FastAPI/Jinja web skeleton.

## Verification And Folder Hygiene

Run:

```powershell
python -m unittest discover -s tests
python -m compileall src tests
```

Then prune generated files:

```powershell
Get-ChildItem -Path . -Recurse -Directory -Filter '__pycache__' | ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }
if (Test-Path .\data) { Remove-Item -LiteralPath .\data -Recurse -Force }
```

`data/`, `.venv/`, caches, local DBs, and build artifacts are ignored and should
not be committed.

## Recommended Next Work

Stay honest about the data boundary:

1. Improve local dashboard consumption of active-side snapshots.
2. Add sold listing ingestion only after Marketplace Insights approval.
3. Normalize sold listings into `sold_listings`.
4. Populate sold-side snapshot fields.
5. Add sell-through scoring and opportunity ranking only after active supply and
   sold demand are both real.

Do not add fake sold metrics, fake trend charts, or fake opportunity scores.
