# Metric Snapshots Design

Last updated: 2026-05-12

## Purpose

`watchlist_metric_snapshots` is the first trend-oriented analytics table in
SellThrough. It captures point-in-time metrics from active listing observations
so future charts do not depend on mutable "latest state" rows only.

Active-side snapshots exist. Full sell-through analytics do not exist yet.

## Current Scope (Implemented)

Snapshot capture now supports active-side metrics only:

- `active_count`
- `active_price_min`
- `active_price_median`
- `active_price_max`
- `sample_confidence` (temporary active-count-based heuristic)

Sold-related fields are intentionally left null:

- `sold_count_30d`
- `median_sold_price`
- `sell_through_rate`

This is deliberate. Marketplace Insights ingestion is still pending approval, so
the project avoids fabricated demand metrics.

## Table

```sql
CREATE TABLE watchlist_metric_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    active_count INTEGER NOT NULL,
    active_price_min REAL,
    active_price_median REAL,
    active_price_max REAL,
    sold_count_30d INTEGER,
    median_sold_price REAL,
    sell_through_rate REAL,
    sample_confidence TEXT,
    FOREIGN KEY (watchlist_id) REFERENCES watchlist(id)
);
```

## Capture Flow

1. Read active watchlist rows.
2. For each row, compute scoped active metrics from normalized/lineage-backed
   lookup.
3. Insert one immutable snapshot row.
4. Keep sold-demand fields pending until real sold ingestion exists.

If a watchlist has no observed active listings yet, snapshot capture writes a
zero-active-count row with null price fields and low confidence. This makes the
absence of data visible without inventing demand or pricing metrics.

CLI helper:

```powershell
python -m sellthrough watchlist capture-snapshots
```

## Future Focus

Next upgrades after Marketplace Insights approval:

1. Populate sold metrics fields from normalized sold listings.
2. Compute `sell_through_rate` only when both active and sold counts are real.
3. Add confidence rules that consider sold sample size, not active count alone.
4. Feed dashboard trend components from snapshot history.
