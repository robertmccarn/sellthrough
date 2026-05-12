# eBay API Design Notes

SellThrough uses eBay APIs as separate data sources with separate jobs, not as
one generic "eBay call." That separation makes the ETL easier to debug and
keeps each metric tied to the API that actually supports it.

## API Roles

- OAuth client credentials identify this application for app-level REST calls.
- Browse API provides active listings and current supply-side market data.
- Marketplace Insights API provides historical sold-item data after access is
  approved.
- Taxonomy API provides category tree and category normalization support.
- Finding API is intentionally excluded because eBay has decommissioned it.

## Browse Client Behavior

The Browse client currently supports active keyword search through
`/buy/browse/v1/item_summary/search`.

Important details:

- The default marketplace is `EBAY_US`.
- Results are paginated with explicit `limit` and `offset` arguments.
- ETL jobs can also use the page iterator, which advances offsets one page at a
  time and stops when eBay returns no `next` URL.
- `limit` is capped at eBay's documented single-page maximum of 200.
- Rate-limit responses are represented as typed errors with optional
  `Retry-After` metadata so scheduler code can pause instead of blindly looping.
- Raw payloads remain attached to result objects so future storage code can save
  source truth before normalization.
- Warnings are surfaced because eBay can return successful HTTP responses while
  ignoring or rejecting a filter in the response body.

## Learning Note

Browse is not used for sold history. Earlier testing showed that sold-style
filters such as `lastSoldDate` produce Browse warnings and still return active
listings. Sold-item history belongs in Marketplace Insights once access is
approved.

## Marketplace Insights Adapter

The Marketplace Insights adapter is designed before access is approved so the
ETL can target a stable sold-history interface.

Important details:

- The live service path is `/buy/marketplace_insights/v1_beta/item_sales/search`.
  The similar hyphenated path returns `404`.
- Access currently returns eBay error `1100` until Application Growth Check is
  approved.
- The adapter mirrors Browse pagination with explicit `limit`, `offset`, and a
  page iterator.
- `lastSoldDate` filtering is built from Python dates/datetimes so ETL jobs can
  request bounded lookback windows, such as 30 days.
- Result objects normalize sold price, last sold date, condition, item ID, and
  category IDs while preserving the raw page payload for replay.

CLI smoke command once access is approved:

```powershell
python -m sellthrough insights search "dewalt drill" --days-back 30 --limit 5
```

## Taxonomy Client Behavior

The Taxonomy client supports the category lookups needed before reliable
watchlist design:

- `default-tree` resolves the marketplace-specific category tree ID, such as
  tree `0` for `EBAY_US`.
- `suggest` maps human search phrases to likely eBay categories.
- `subtree` flattens nested category branches into parent-aware rows.

Category IDs should be treated as marketplace-scoped identifiers. A future
watchlist row should store both the category ID and the marketplace/category
tree context used to select it.
