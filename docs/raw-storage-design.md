# Raw API Response Storage

SellThrough stores raw API responses before normalization. This is the first
real ETL pattern in the project and an important learning point: raw storage
preserves the source-of-truth payload so transforms can be replayed, audited,
and improved without calling the API again.

## Tables

- `poll_runs` records one extraction attempt, such as a Browse search for
  `"dewalt drill"`.
- `raw_api_responses` records each raw response page returned during that run.
- Normalized listing tables should reference `raw_api_responses.id` so every
  derived row can be traced back to the original eBay payload.

## Current Commands

Store one raw active-listing Browse page:

```powershell
python -m sellthrough browse search "dewalt drill" --limit 3 --save-raw
```

Store one raw Marketplace Insights page after access is approved:

```powershell
python -m sellthrough insights search "dewalt drill" --limit 3 --save-raw
```

## Design Notes

- The repository layer writes compact JSON text into SQLite. The payload remains
  logically raw; compact encoding only avoids unnecessary whitespace.
- A poll run is marked `completed` only after the raw page is saved.
- A failed poll run can still retain earlier raw pages, which is useful when a
  later page fails due to rate limits or transient API errors.
- Generated local databases belong in `data/` and are ignored by Git.
