# SellThrough Design Document v0.2

Last updated: 2026-05-12

## 1. Project Overview

SellThrough is a personal data analytics learning project for eBay marketplace
research. It is also intended to become a practical resale intelligence tool
that answers:

> What can I buy locally that is likely to sell quickly and profitably on eBay?

The project now deliberately emphasizes learning-quality implementation:
documented API boundaries, raw-first ETL storage, small verifiable CLI commands,
and a clean local workflow before dashboards or automation.

The polished dashboard/mobile concepts are a long-term target. The near-term
frontend goal is infrastructure and architecture that can support that target
honestly as real active, sold, and snapshot metrics become available.

## 2. Key Learnings Since v0.1

- The legacy Finding API is no longer a viable project dependency. It returned
  rate-limit/security failures during testing and eBay support guidance pointed
  to supported Buy APIs instead.
- Browse API is the supported source for active listing/current supply data. It
  does not provide sold-history data.
- Marketplace Insights API is the supported source for sold-item history, but it
  requires eBay approval through Application Growth Check. Until approval lands,
  the code should expose a clear "access pending" state rather than pretending
  sold data is available.
- Taxonomy API is available now and should be used to normalize categories before
  watchlist entries become serious analytical units.
- Raw API response storage belongs in the MVP. It lets later transform/scoring
  work replay real source payloads without consuming more API calls.

## 3. Current Architecture

```text
            [ eBay OAuth ]
                  |
    +-------------+-------------+
    |             |             |
[ Browse ]   [ Taxonomy ]  [ Marketplace Insights ]
 active       category       sold history
 listings     metadata       approval pending
    |             |             |
    +-------------+-------------+
                  |
           [ CLI Commands ]
                  |
           [ SQLite Store ]
      poll_runs + raw_api_responses
                  |
          [ Future Transform ]
 normalized active/sold listings,
 snapshots, lookup, scoring
```

## 4. Implemented Components

- Python package scaffold with `src/` layout and editable install support.
- Environment-based configuration with redacted diagnostics.
- OAuth application-token flow for eBay REST APIs.
- Browse client for active listing keyword search.
- Taxonomy client for category tree lookup, suggestions, and subtree flattening.
- Marketplace Insights adapter with a stable sold-search interface and explicit
  access-pending error handling.
- SQLite schema initialization.
- Raw response repository for `poll_runs` and `raw_api_responses`.
- CLI smoke command that checks config, SQLite, Browse, Taxonomy, and Marketplace
  Insights access state.
- Unit tests for client parsing, DB raw storage, and smoke output formatting.

## 5. MVP Design Going Forward

The next MVP should be query/watchlist driven rather than broad category driven.
Categories are useful context, but realistic sourcing decisions happen around
specific item families such as "TI-84 Plus CE", "DeWalt 20V drill", or "Sony
Walkman".

Recommended near-term flow:

1. Add watchlist CRUD commands backed by SQLite.
2. Pull active Browse pages for each watchlist query and save raw responses.
3. Normalize raw Browse pages into `active_listings`.
4. Once Marketplace Insights access is approved, pull sold pages and normalize
   into `sold_listings`.
5. Build the first metrics snapshot from active + sold tables.
6. Add a CLI lookup command that returns active supply, sold sample size, median
   sold price, and a simple buy/pass placeholder.

## 6. Metrics Model

The original metric set is still directionally right, but should wait until sold
data is available. Use these MVP metrics first:

- `median_sold_price`
- `sold_count_30d`
- `active_count_now`
- `completed_sell_through` once sold/completed data is available
- `active_pressure_ratio = sold_count_30d / max(active_count_now, 1)`
- `sample_confidence`, based on sold sample size

Opportunity scoring should not be implemented until the data model can separate
active supply from sold demand and can report sample-size confidence.

## 7. Updated Data Source Policy

- Use Browse API only for active listings.
- Use Marketplace Insights API only for sold-history data.
- Use Taxonomy API for marketplace-specific category metadata.
- Do not use Finding API.
- Do not store eBay user personal data, buyer data, seller contact data, order
  data, messages, payment data, or account identifiers.
- Store only listing-level marketplace fields needed for analytics.

## 8. Current Commands

```powershell
python -m sellthrough config check
python -m sellthrough db init
python -m sellthrough browse search "dewalt drill" --limit 3
python -m sellthrough browse search "dewalt drill" --limit 3 --save-raw
python -m sellthrough taxonomy default-tree --marketplace EBAY_US
python -m sellthrough taxonomy suggest "cordless drill" --limit 5
python -m sellthrough insights search "dewalt drill" --days-back 30 --limit 5
python -m sellthrough smoke --query "dewalt drill" --limit 1
```

## 9. Open Risks

- Marketplace Insights approval is not guaranteed.
- Sold-history fields may differ from inferred adapter shapes once access is
  approved; raw response preservation will make adaptation easier.
- The current CLI contains repeated command handling that should be refactored
  before it grows much further.
- No normalized transform layer exists yet.
- No watchlist table commands exist yet, even though the schema includes a
  `watchlist` table.

## 10. Next Priority

Build the watchlist + active-listing ingestion loop:

- Add `watchlist add/list/disable` CLI commands.
- Add a `poll active` command that reads active watchlist rows.
- Save raw Browse pages for each watchlist query.
- Normalize active results into `active_listings`.
- Keep all new behavior documented and covered by focused tests.

After the local data foundation is stable, start frontend infrastructure rather
than a full dashboard: add a localhost-only web app, route/view-model boundaries,
health/status pages, and read-only views over existing normalized data. See
`docs/frontend-roadmap.md`.
