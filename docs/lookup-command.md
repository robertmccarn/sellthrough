# Lookup Command

The lookup command reads normalized rows from SQLite. It does not call eBay.

```powershell
python -m sellthrough lookup active "dewalt drill" --samples 5
python -m sellthrough lookup watchlist 1 --samples 5
```

## Output

`lookup active` reports:

- active listing count
- active price range
- active median price
- sample normalized listings
- most recent `last_seen_at`
- sold metrics status

Sold metrics intentionally remain pending until Marketplace Insights access is
approved and sold listings can be normalized with the same raw-first pattern.

## Current Matching Limitation

Current lookup uses case-insensitive title matching against normalized active
listings. This is sufficient for early local inspection but may include
accessories, bundles, or loosely related listings. Future lookup should support
watchlist-scoped results and stronger product matching.
