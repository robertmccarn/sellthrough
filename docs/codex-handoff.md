# Codex Handoff Notes

Audience: a future Codex instance working with Robert on another computer after
cloning or pulling `https://github.com/robertmccarn/sellthrough`.

## Project Identity

SellThrough is a personal data analytics learning project for eBay marketplace
research. It is meant to become a resale intelligence tool, but the learning
model is equally important: explain data-engineering choices clearly, keep docs
current, and leave the working folder clean.

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

Important branches seen during this handoff:

- `main`: contains merged project scaffold, OAuth/Browse, Taxonomy, and
  Marketplace Insights adapter work through PR #1.
- `codex/raw-api-response-storage`: raw API response storage work, pushed but may
  or may not be merged by the time you start.
- `codex/cli-smoke-command`: smoke command work, pushed and based on raw storage.
  At the time this handoff was written, local uncommitted docs were also present
  on this branch.

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
- `docs/design-document-v0.2.md`: current architecture and updated MVP.
- `docs/self-audit-2026-05-12.md`: gaps against the original design.
- `docs/ebay-api-design.md`: API roles and endpoint decisions.
- `docs/raw-storage-design.md`: raw-first ETL storage pattern.
- `docs/cli-smoke-command.md`: smoke command behavior.

## Current Architecture Summary

Implemented or in-flight:

- `src/sellthrough/config.py`: env-based settings and redacted diagnostics.
- `src/sellthrough/ebay/client.py`: OAuth application-token client.
- `src/sellthrough/ebay/browse.py`: active listing search.
- `src/sellthrough/ebay/taxonomy.py`: category tree/suggestions/subtree.
- `src/sellthrough/ebay/marketplace_insights.py`: sold-history adapter with
  access-pending handling.
- `src/sellthrough/db.py`: SQLite schema and raw response repository.
- `src/sellthrough/smoke.py`: smoke-check output helpers.
- `src/sellthrough/cli.py`: top-level CLI assembly and dispatch.
- `src/sellthrough/cli_commands/`: command-specific parser and handler modules.

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

The next feature should probably be watchlist CRUD:

1. Add `watchlist add/list/disable` CLI commands.
2. Store watchlist rows in SQLite.
3. Test repository behavior.
4. Document watchlist design.
5. Keep output suitable for a learner: clear commands, no secrets, no hidden
   side effects beyond the requested local DB writes.

After that, build active polling that reads watchlist rows, saves raw Browse
pages, and normalizes into `active_listings`.
