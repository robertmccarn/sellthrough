# Active Polling Design

Active polling turns saved watchlist rows into a repeatable Browse ETL loop.

## Workflow

```text
active watchlist rows
  -> Browse API search per row
  -> sanitized raw_api_responses row per response page
  -> active_listings upsert per returned item
```

The first CLI command is:

```powershell
python -m sellthrough watchlist poll-active --limit 25
```

## Design Notes

- The poller reads only active watchlist rows.
- Each watchlist row currently pulls one Browse page. Pagination support already
  exists in the Browse client and can be added to the poller when scheduled jobs
  need deeper result sets.
- Raw responses are saved before normalization. This preserves source payloads
  for replay and audit if normalized fields change later.
- Normalization currently upserts by eBay `item_id`, updating price, shipping,
  condition, URL, category fields, `last_seen_at`, and `raw_response_id`.
- Watchlist category IDs are passed to Browse as filters when present.

## Current Boundaries

- `sellthrough.services.active_polling` owns the workflow.
- `BrowseClient` owns the eBay API call and raw payload parsing.
- `RawResponseRepository` owns raw storage.
- `ActiveListingRepository` owns normalized `active_listings` upserts.
