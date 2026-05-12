# Lookup Command

The lookup command reads normalized rows from SQLite. It does not call eBay.

```powershell
python -m sellthrough lookup active "dewalt drill" --samples 5
python -m sellthrough lookup watchlist 1 --samples 5
```

## Output

`lookup active <query>` is a case-insensitive title-text search across
normalized active listings. It is useful for broad local inspection.

`lookup watchlist <id>` uses observation lineage to summarize listings seen for
one watchlist row. Once watchlist polling exists for a product family, this is
the preferred lookup because it is scoped to the saved sourcing target rather
than loose title text.

Both lookup modes report:

- active listing count
- active price range
- active median price
- sample normalized listings
- most recent `last_seen_at`
- sold metrics status

Sold metrics status: Pending Marketplace Insights access and sold-listing
normalization.

## Current Matching Limitation

`lookup active` uses case-insensitive title matching against normalized active
listings. This is sufficient for early local inspection but may include
accessories, bundles, or loosely related listings. Watchlist-scoped lookup is
better once a watchlist row has been polled. Future lookup can still improve
with stronger product matching.
