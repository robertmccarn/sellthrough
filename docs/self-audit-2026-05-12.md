# Self-Audit Against Original Design

Date: 2026-05-12

## Summary

The project is on a healthy path, but the design has shifted from the original
Finding API based ETL to a supported Buy API architecture. The code now has a
good learning-oriented foundation: OAuth, Browse, Taxonomy, Marketplace Insights
adapter, raw storage, smoke command, and tests. It is not yet an ETL pipeline in
the analytical sense because normalization, watchlist polling, snapshots, and
metrics are still missing.

## What Matches the Original Design

- Python 3 package with CLI-first workflow.
- SQLite-first local storage.
- Raw JSON staging before transformation.
- eBay active listing access through Browse API.
- Category normalization direction through Taxonomy API.
- Marketplace Insights identified as the correct sold-history source.
- Learning documentation is now explicit and durable in `docs/`.

## What Changed

- Finding API is removed from the architecture.
- Browse API is active-listing only.
- Marketplace Insights is modeled as an approval-gated dependency.
- MVP should be watchlist-query first, not category-snapshot first.
- Raw response storage moved earlier because it is useful for learning, replay,
  and API-call conservation.

## Gaps Before Original MVP Is Satisfied

- No watchlist CLI commands yet.
- No polling command yet.
- No normalization from raw Browse responses into `active_listings` yet.
- No sold-history ingestion until Marketplace Insights approval.
- No metric snapshots or opportunity scoring yet.
- No lookup command yet.
- No weekly digest yet.

## Implementation Quality Notes

- The current clients are intentionally small and well documented.
- SQLite connection handling was corrected for Windows file-lock behavior.
- CLI code is now large enough that the next few features should consider
  extracting command handlers into separate modules.
- Tests cover parsing and persistence behavior, but not full CLI argument flows.
- Generated files are ignored and were pruned after verification.

## Recommended Next Work

1. Add watchlist CRUD commands and tests.
2. Add active polling that saves raw Browse pages for watchlist rows.
3. Add normalization from raw Browse pages into `active_listings`.
4. Add CLI lookup using active data first.
5. Add Marketplace Insights live parsing once access is approved.
