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

## Workflow Source of Truth

Use `docs/agile-workflow.md` as the canonical branch/release/validation rulebook.

Short version:
- Feature branches start from `test-main`.
- Feature PRs target `test-main`.
- After merge into `test-main`, issue status moves to `Review` and Codex validates.
- Issue moves to `Done` only after validation + issue cleanup.
- Release PRs target `main`.

## Repository State To Expect

Remote:

```text
https://github.com/robertmccarn/sellthrough.git
```

Branches change quickly. Before starting, inspect `main`, `test-main`, the
current branch, and any PR branch Robert mentions.

Before starting, run:

```powershell
git fetch --all --prune
git status -sb
git branch -a
git log --oneline --decorate --graph --all -n 12
```

## Branch Operating Model

### Feature work

- Switch to `test-main`.
- Pull latest with fast-forward only.
- Create feature branch from `test-main`.
- Open PR into `test-main`.

```powershell
git fetch --all --prune
git checkout test-main
git pull --ff-only origin test-main
```

### If Robert says a feature PR was merged

Do **not** default to `main`.

- Switch to `test-main`.
- Pull latest with fast-forward only.
- Validate merged behavior.
- Perform issue cleanup (checklist, delivered scope, labels, board state).

```powershell
git checkout test-main
git pull --ff-only origin test-main
python -m unittest
python -m pytest tests/test_e2e_v1_validation.py -q
```

For web/dashboard work, also run:

```powershell
python -m pytest tests/test_services.py -q
```

### If Robert says a release PR was merged

- Switch to `main`.
- Pull latest with fast-forward only.
- Verify release version/tag.
- Run release validation.

```powershell
git checkout main
git pull --ff-only origin main
git tag --list "v*"
python -m unittest
python -m pytest tests/test_e2e_v1_validation.py -q
```

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

- `docs/agile-workflow.md`: canonical workflow and release model.
- `docs/development-guide.md`: development/documentation rules.
- `docs/design-document-v0.3.md`: architecture and roadmap.
- `docs/self-audit-2026-05-12.md`: gaps against original design.
- `docs/validation-notes.md`: validation command matrix + review validation.
- `docs/frontend-roadmap.md`: local web/dashboard direction.

## Scope Guardrail Reminder

Active-side metrics are real.

Sold ingestion, sold-side snapshots, sell-through scoring, opportunity scoring,
and sold-sample confidence remain blocked until Marketplace Insights approval
and sold-listing normalization are complete.

Do not add fake sold metrics, fake trend charts, fake opportunity scores, or
scraping-assumed fallback implementation.

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
