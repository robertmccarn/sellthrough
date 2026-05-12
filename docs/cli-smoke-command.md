# CLI Smoke Command

The `smoke` command is the fastest way to answer: "Is the local SellThrough
environment basically wired together?"

```powershell
python -m sellthrough smoke --query "dewalt drill" --limit 1
```

## What It Checks

- Environment configuration loads without printing secrets.
- The SQLite schema can initialize.
- Browse API can return active listings.
- Taxonomy API can resolve the marketplace category tree.
- Marketplace Insights can be reached, or clearly reports that approval is
  still pending.

## Expected Current Output

Marketplace Insights is still awaiting eBay approval, so its smoke result should
currently be `WARN`, not `FAIL`. The command fails only when a required local or
currently-approved dependency is broken.

Use `--save-raw` when you want the Browse smoke response persisted to SQLite:

```powershell
python -m sellthrough smoke --query "dewalt drill" --limit 1 --save-raw
```
