# Future Wishlist

This document captures long-range SellThrough ideas without turning them into
current commitments. It should stay separate from the MVP design document: the
MVP tells us what to build next, while this wishlist preserves the longer arc so
future decisions can stay coherent.

Future Codex instances should update this file whenever Robert expands the
product vision, especially around hosted web, smartphone, camera, barcode,
offline, or multi-user workflows.

The concept dashboard/mobile images are the long-term product north star. Use
`docs/frontend-roadmap.md` for the concrete infrastructure path that supports
that target without rushing into a full dashboard before the data is ready.

## Current Future Focus

Near-term evolution should follow this order:

1. Snapshot-driven trend surfaces from `watchlist_metric_snapshots`.
2. Sold ingestion and normalization after Marketplace Insights approval.
3. Opportunity scoring only after both active supply and sold demand are real.

This ordering keeps the product honest while still moving toward the full
dashboard vision.

## Guiding Principles

- Build the local CLI/data foundation first.
- Keep CLI, web, and future mobile experiences on top of shared service and
  repository layers.
- Prefer FastAPI with server-rendered templates for the first frontend.
- Keep SQLite for local development and move to Postgres for hosted use.
- Treat responsive web/PWA as the first smartphone path.
- Require a strong security boundary before any public hosting.
- Keep the project learning-friendly: explain tradeoffs, data flow, and why each
  new layer exists.

## Horizon 1: Local Data Foundation

Wishlist outcomes:

- Watchlist CRUD for realistic item families and queries.
- Active listing polling from Browse API.
- Raw response storage for every pull.
- Normalization into `active_listings`.
- Sold-history ingestion once Marketplace Insights access is approved.
- Metrics snapshots for active supply, sold sample size, median sold price, and
  confidence.
- CLI lookup that can answer a simple buy/pass-style question without pretending
  precision exists too early.

This layer remains the source of truth for future UI work. Web and mobile should
not bypass it.

## Horizon 2: Local Web Console

Wishlist outcomes:

- Localhost-only web app for development and personal use.
- Frontend infrastructure that can grow toward the concept dashboard/mobile
  experience without bypassing the existing Python service layer.
- Status page showing config, SQLite, Browse, Taxonomy, and Marketplace Insights
  state.
- Active search page using Browse API.
- Category helper page using Taxonomy suggestions.
- Watchlist management page.
- Raw storage summary page showing counts and poll-run status, not raw JSON by
  default.

The local console should be quiet, utilitarian, and data-work focused. It should
help inspect the pipeline, not look like a marketing site.

## Horizon 3: Internal Dashboard

Wishlist outcomes:

- Lookup view for item/query research.
- Watchlist snapshot view.
- Recent polling status and failures.
- Basic trend charts after normalized metrics exist.
- Weekly digest preview.
- Clear Marketplace Insights status and data freshness indicators.

Avoid heavy dashboards until normalized active/sold data and metrics are stable.
Charts should explain real metrics, not decorate incomplete data.

## Horizon 4: Hosted Web App

Wishlist outcomes:

- Hosted backend with managed secrets.
- Postgres database instead of SQLite.
- Background polling jobs.
- Authentication before any public access.
- HTTPS, request rate limiting, structured logs, backups, dependency audits, and
  deployment smoke checks.
- eBay credentials kept server-side only.
- Sanitized API responses sent to the browser.

Hosting should happen only after the local app has clear data flows and a useful
lookup/dashboard experience.

## Horizon 5: Smartphone / PWA Experience

Wishlist outcomes:

- Responsive web interface that works well at yard sales and estate sales.
- Fast lookup flow optimized for small screens.
- Saved finds list with observed local price and notes.
- Simple buy/pass view based on available metrics.
- Offline-tolerant behavior for saved watchlist data where practical.
- Installable PWA if the hosted web app proves useful on phones.

The first smartphone version should be a responsive web/PWA experience, not a
native app.

## Horizon 6: Native Mobile Possibilities

Native mobile should be considered only if phone-specific capabilities become
central enough to justify the extra complexity.

Possible native-only reasons:

- Camera-based item recognition.
- Barcode scanning with better device integration.
- Offline-first field workflow.
- Push notifications for watchlist or pricing alerts.
- Location-aware sourcing notes.

Until those needs are real, keep the mobile path web-first.

## Parking Lot

Ideas to revisit later:

- Image-based lookup.
- Barcode lookup.
- Estate sale company scoring.
- Cross-platform arbitrage against local marketplaces.
- Automated listing draft assistance.
- Seasonal opportunity alerts.
- Personal sourcing journal tied to watchlist outcomes.
