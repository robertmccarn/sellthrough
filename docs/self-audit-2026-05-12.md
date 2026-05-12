# Self-Audit Against Original Design

Date: 2026-05-12

## Summary

The project is on a healthy path and has shifted from the original Finding API
based ETL idea to a supported Buy API architecture. The code now has a
learning-oriented local data foundation: OAuth, Browse, Taxonomy, Marketplace
Insights adapter, raw storage, watchlist-driven active polling, active listing
normalization, observation lineage, active-side snapshots, lookup services,
dashboard summary service, local web skeleton, and tests.

The important boundary is still honesty: active-side metrics are real, while
sold metrics, sell-through scoring, opportunity ranking, and real trend charts
remain pending Marketplace Insights approval and sold-listing normalization.

## What Matches the Original Design

- Python 3 package with CLI-first workflow.
- SQLite-first local storage.
- Raw JSON staging before transformation.
- eBay active listing access through Browse API.
- Category normalization direction through Taxonomy API.
- Marketplace Insights identified as the correct sold-history source.
- Watchlist-driven ingestion and active-side metric snapshots.
- Learning documentation is explicit and durable in `docs/`.

## What Changed

- Finding API is removed from the architecture.
- Browse API is active-listing only.
- Marketplace Insights is modeled as an approval-gated dependency.
- MVP should be watchlist-query first, not category-snapshot first.
- Raw response storage moved earlier because it is useful for learning, replay,
  and API-call conservation.

## Current Remaining Gaps

- No sold-history ingestion until Marketplace Insights approval.
- No sold listing normalization.
- No sold-side metric snapshots.
- No sell-through scoring or opportunity scoring yet.
- No real trend charts based on active + sold snapshots yet.
- No weekly digest yet.
- No hosted deployment or native mobile app.

## Implementation Quality Notes

- The current clients are intentionally small and well documented.
- SQLite connection handling was corrected for Windows file-lock behavior.
- CLI command handlers are modularized under `src/sellthrough/cli_commands/`.
- Tests cover parsing, persistence, services, security, snapshots, and local web
  readiness without requiring live eBay calls.
- Generated files are ignored and were pruned after verification.

## Recommended Next Work

1. Keep improving local dashboard consumption of real active-side data.
2. Add sold ingestion after Marketplace Insights approval.
3. Normalize sold listings and populate sold-side snapshot fields.
4. Add confidence rules based on sold sample size.
5. Add sell-through and opportunity scoring only after active + sold metrics are
   both real.
