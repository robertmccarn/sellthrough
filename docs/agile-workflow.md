# SellThrough Agile Workflow

## Purpose

SellThrough uses the project board + branch model as a truth-management system:
- what is real
- what is ready
- what is blocked
- what is released
- what is future

## Branch Roles

### `main`

`main` is the stable release branch:
- updated only through release PRs
- always versioned
- must pass CI/security
- reflects latest accepted release state
- not the daily workbench

### `test-main`

`test-main` is the integration and validation branch:
- feature PRs merge into `test-main`
- Codex branches from `test-main`
- issues move to `Review` after merge into `test-main`
- Codex validation runs against `test-main`
- accepted issues move to `Done` after validation + cleanup
- release candidates are cut from `test-main`

### Feature Branches

Feature branches should branch from `test-main`.

Recommended naming:
- `codex/issue-60-poll-status-section`
- `codex/issue-61-active-snapshot-history`
- `fix/dashboard-empty-state`
- `docs/user-manual-v1`

## Branch Flow

Feature flow:

`feature branch -> PR -> test-main -> Review -> Codex validation -> Done`

Release flow:

`test-main -> release PR -> main -> version tag`

## Status Rules

### Ready
- scoped
- unblocked
- prioritized
- labeled
- ready to implement

### In Progress
- active implementation on a feature branch

### Review
- code has merged into `test-main`
- validation still required
- not Done yet

### Pending Release
- validation and issue cleanup are complete
- work is accepted on `test-main`
- item is queued for the next release batch to `main`
- use this column/status instead of `Done` when local convention holds items until release

### Done
- release inclusion is complete according to current team convention
- if using a `Pending Release` column, items move from `Pending Release` to `Done` after release acceptance
- if not using `Pending Release`, items may move directly from `Review` to `Done` after validation + cleanup

### Blocked
- external dependency (for example: Marketplace Insights approval)

### Release Candidate
- optional status, if board supports it
- use for release-prep batch on `test-main`
- if not available, use `Review` for release-prep items

## Definition of Ready

An issue is `Ready` only when:
- not blocked
- acceptance criteria exist
- priority is set
- workstream is set
- technical notes are clear
- can start without clarification
- does not rely on fake/unavailable sold data

## Definition of Done

For SellThrough:
- Issue Done = validated and accepted into `test-main`
- Release Done = merged into `main` with a version tag

If the board uses a `Pending Release` status/column:
- validated items should move `Review -> Pending Release`
- move `Pending Release -> Done` when the release decision is finalized

Done requires:
- PR merged into `test-main`
- validation passed
- acceptance criteria checked
- Delivered Scope added
- stale labels removed
- docs updated if behavior changed
- no scope-boundary violations

## Post-Merge Review Rule

After any PR merges into `test-main`, move the related issue to `Review`, not `Done`.

Then Codex runs validation.

After validation passes, move the issue to `Pending Release` when that status exists.
Use `Done` only when the team marks the item release-accepted.

## Codex Post-Merge Validation

Codex validation must:
1. Pull latest `test-main`.
2. Inspect merged PR diff.
3. Compare implementation against issue acceptance criteria.
4. Run required tests.
5. Confirm no scope-boundary violations.
6. Confirm docs updated if needed.
7. Confirm issue cleanup.
8. Recommend `Done` or return to `In Progress`/`Review`.

## Validation Test Matrix

Always run:
- `python -m unittest`
- `python -m pytest tests/test_e2e_v1_validation.py -q`

For web/dashboard work, also run:
- `python -m pytest tests/test_services.py -q`

For data/schema work, also inspect and run as relevant:
- `src/sellthrough/db.py`
- `tests/test_db.py`
- `tests/test_e2e_v1_validation.py`
- `docs/design-document-v0.3.md`

For security/CI/config changes, inspect:
- `.github/workflows/ci.yml`
- `.github/workflows/security-checks.yml`
- `docs/security-hardening.md`
- `README.md`
- `pyproject.toml`

For docs-only changes:
- inspect changed docs
- run tests only when docs describe changed executable commands

## Scope Guardrails

Allowed V1 work:
- active listing data
- active-side dashboard metrics
- watchlist state
- local lookup
- active snapshots
- pending sold/opportunity copy

Not allowed unless explicitly unblocked:
- fake sold metrics
- fake sell-through scoring
- fake opportunity score
- fake sold-sample confidence
- scraping fallback implementation
- hosted deployment
- native mobile app
- client-side eBay credentials

## Release Cadence

Release from `test-main` to `main` when:
- 10 commits have accumulated since last release, OR
- major rework/demo-significant milestone is complete

## Versioning Rules

Current version: `0.1.0`.

Format:
- `0.MINOR.PATCH`

Patch release (`0.1.x`):
- docs cleanup
- issue hygiene
- test cleanup
- small bug fixes

Minor release (`0.x.0`):
- meaningful dashboard batch
- data pipeline milestone
- CI/security milestone
- major rework

Reserve:
- `1.0.0` for true V1 product release

Recommended next:
- `v0.2.0 - Active-Side Dashboard Foundation`

## Release PR Rules

Release PRs target `main`.

Release PR title format:
- `release: v0.2.0 active-side dashboard foundation`

Release PR body should include:
- Release
- Summary
- Completed issue list
- Validation commands/results
- Known limitations
- Post-merge tag task

Release-prep checklist:
- Run baseline validation (`python -m unittest` and `python -m pytest tests/test_e2e_v1_validation.py -q`).
- Run web/dashboard validation when relevant (`python -m pytest tests/test_services.py -q`).
- Run docs-aware release secret scan (`powershell -ExecutionPolicy Bypass -File .\scripts\scan-secrets-release-docs.ps1`).
- Confirm scoped dependency audit status (`pip-audit` from CI output or a local rerun).

## Tagging Rules

Every release to `main` should be tagged:
- `v0.1.0`
- `v0.2.0`
- `v0.2.1`

## Commit Counting Rule

Use:

```powershell
git rev-list --count v0.1.0..test-main
```

If no tag exists yet, create the first release tag from stable `main`:

```powershell
git tag v0.1.0
git push origin v0.1.0
```

## Label Rules

Use `ready-for-codex` only on open, unblocked, scoped, implementation-ready issues.

Remove it from:
- closed issues
- blocked issues
- issues needing planning

Use `needs-validation` only when validation has not passed.

Remove it after validation.

Use `blocked` only for real dependencies.

Use `marketplace-insights` only for Marketplace Insights/sold-history dependent work.

## Next Item Selection Rule

After an issue reaches `Done`, select the next item using:
1. Not blocked.
2. P1/priority-high or higher.
3. Ready for implementation.
4. Improves V1 demo path.
5. Uses real active-side data.

Current likely sequence after #58 and #59:
- #60 Add recent poll status section
- #61 Add active-side snapshot history section
- #37 Apply brand design tokens
- #41 V1 User Manual & CLI Reference
- #63 Add web route rendering coverage
- #33 Active-side snapshot charts
