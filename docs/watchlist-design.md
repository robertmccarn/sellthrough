# Watchlist Design

The watchlist is SellThrough's first durable business object. It turns a one-off
search phrase into a repeatable sourcing target that future polling,
normalization, lookup, metrics, and web UI work can share.

## Current Commands

```powershell
python -m sellthrough watchlist add "DeWalt 20V drill" --query "dewalt 20v drill" --category-id 184655
python -m sellthrough watchlist list
python -m sellthrough watchlist list --all
python -m sellthrough watchlist disable 1
python -m sellthrough watchlist poll-active --limit 25
```

## Fields

- `label`: required human-readable name.
- `query`: required search query; CLI defaults it to the label when omitted.
- `category_id`: optional eBay category ID.
- `active`: defaults to true; disabled rows are preserved for history.
- `added_at`: database timestamp.

## Design Notes

- There is no hard delete in v1. Disabling preserves context for future polling
  history and metrics.
- Category IDs are accepted as user-provided strings for now. Validation against
  Taxonomy can be added after the basic watchlist/polling loop is working.
- The service layer owns label/query cleanup so future web forms and CLI commands
  behave the same way.
- Active rows are now polling inputs. `watchlist poll-active` calls Browse for
  each active row, saves the sanitized raw response, and upserts normalized
  `active_listings` rows.
