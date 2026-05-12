# SellThrough Design Document v0.3

Last updated: 2026-05-12

## 1. Project Overview

SellThrough is a local-first Python application for learning and practicing
data engineering through eBay resale market intelligence. It is also intended
to become a practical resale intelligence tool
that answers:

> What can I buy locally that is likely to sell quickly and profitably on eBay?

The project emphasizes learning-quality implementation: documented API
boundaries, raw-first ETL storage, normalized tables, small verifiable CLI
commands, and a clean local workflow before hosted dashboards or automation.

The polished dashboard/mobile concepts are a long-term product target. The
near-term frontend goal is infrastructure and architecture that can support that
target honestly as real active, sold, and snapshot metrics become available.

## 2. Key Design Decisions

- The legacy Finding API is not used. Browse, Taxonomy, and Marketplace
  Insights are the supported eBay API direction.
- Browse API is the source for active listing/current supply data.
- Marketplace Insights API is the intended source for sold-item history, but
  access is still pending Application Growth Check approval.
- Taxonomy API is used for marketplace-specific category discovery and
  normalization support.
- Raw API responses are stored before normalization so transforms can be replayed
  and audited without consuming more API calls.
- CLI, future web, and future mobile surfaces should reuse shared services and
  repositories rather than bypassing the data layer.

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
          [ Service Layer ]
  watchlist, polling, raw storage,
 active normalization, observations,
 snapshots, lookup, dashboard summary
                  |
           [ SQLite Store ]
 poll_runs, raw_api_responses,
 watchlist, active_listings,
 active_listing_observations,
 watchlist_metric_snapshots,
 sold_listings (schema only)
                  |
       [ CLI Commands / Local Web ]
 setup, smoke, browse, taxonomy,
 watchlist, active polling, lookup,
 localhost dashboard skeleton
```

## 4. Implemented Status

Implemented:

- Python package scaffold with `src/` layout and editable install support.
- Environment-based configuration with redacted diagnostics.
- OAuth application-token flow for eBay REST APIs.
- Browse client for active listing keyword search.
- Taxonomy client for category tree lookup, suggestions, and subtree flattening.
- Marketplace Insights adapter with explicit access-pending handling.
- SQLite schema initialization.
- Raw response repository for `poll_runs` and `raw_api_responses`.
- Watchlist CRUD.
- Modular CLI command structure.
- Active watchlist polling.
- Raw-first Browse response storage.
- Active listing normalization into `active_listings`.
- Active listing observations and watchlist lineage.
- Active-side watchlist metric snapshot scaffolding.
- Active title lookup and watchlist-scoped lookup.
- Dashboard summary service.
- Local FastAPI/Jinja web skeleton.
- Brand guidelines and shared web design tokens.
- Frontend roadmap.
- Unit tests covering API parsing, services, repositories, CLI wiring, security,
  raw storage, polling, normalization, and lookup behavior.

Still pending:

- Marketplace Insights approval.
- Sold listing ingestion.
- Sold listing normalization.
- Sold-side metric snapshots.
- Sell-through scoring.
- Opportunity ranking.
- Real trend charts based on active + sold snapshots.

## 5. Current Data Flow

The active-listing ETL flow is now implemented:

1. Add active watchlist rows with query/category context.
2. Poll active watchlist rows through Browse.
3. Save each Browse response page to `raw_api_responses`.
4. Transform raw Browse payloads into stable `active_listings` rows.
5. Persist repeated poll observations in `active_listing_observations`.
6. Capture active-side watchlist metric snapshots.
7. Query normalized active rows through lookup commands.
8. Inspect local SQLite state through a cautious local web skeleton.

Sold-listing flow is intentionally incomplete until Marketplace Insights access
is approved. The schema and adapter exist, but the application should continue
to show sold metrics as pending rather than invented.

Active-side snapshots exist. Full sell-through analytics do not exist yet.
Pending Marketplace Insights access and sold-listing normalization.

## 6. Metrics Model

Current real metrics:

- active listing count
- active price range
- active median price
- latest active listing `last_seen_at`
- sample active listings
- active-side watchlist metric snapshots

Pending metrics after sold data exists:

- `median_sold_price`
- `sold_count_30d`
- `completed_sell_through`
- `active_pressure_ratio = sold_count_30d / max(active_count_now, 1)`
- `sample_confidence`, based on sold sample size
- opportunity score/ranking

Opportunity scoring should not be implemented until the data model can separate
active supply from sold demand and report sample-size confidence.
Opportunity scoring requires both active supply and sold demand. Do not
implement until sold ingestion and sold snapshots are available.

## 7. Data Source And Storage Policy

- Use Browse API only for active listings.
- Use Marketplace Insights API only for sold-history data.
- Use Taxonomy API for marketplace-specific category metadata.
- Do not use Finding API.
- Do not store eBay user personal data, buyer data, seller contact data, order
  data, messages, payment data, or account identifiers.
- Store only listing-level marketplace fields needed for analytics.
- Preserve raw payloads first, then normalize into query-friendly tables.
- SQLite includes lightweight indexes for current local query paths: active
  watchlist rows, title lookup, observation lineage by watchlist/item, snapshot
  history by watchlist/capture time, raw response freshness, and poll-run status.

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
python -m sellthrough watchlist add "DeWalt 20V drill" --query "dewalt 20v drill" --category-id 184655
python -m sellthrough watchlist list
python -m sellthrough watchlist poll-active --limit 25
python -m sellthrough watchlist capture-snapshots
python -m sellthrough lookup active "dewalt drill" --samples 5
```

## 9. Open Risks

- Marketplace Insights approval is not guaranteed.
- Sold-history fields may differ from inferred adapter shapes once access is
  approved; raw response preservation will make adaptation easier.
- Active lookup metrics are useful but incomplete until sold-history ingestion is
  available.
- Trend charts and opportunity scoring need metrics snapshots, not just current
  normalized active rows.
- The frontend roadmap is intentionally architectural; the first web app should
  remain honest about unavailable sold/trend data.

## 10. Next Priority

- Add snapshot consumption to dashboard trend surfaces.
- Add sold listing ingestion via Marketplace Insights after approval.
- Add sold listing normalization and sold metric snapshot fields.
- Add confidence model that includes sold sample size.
- Keep opportunity scoring pending until active + sold metrics are both real.
