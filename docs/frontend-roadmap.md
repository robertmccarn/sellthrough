# Frontend Architecture Roadmap

This roadmap captures the long-term frontend target suggested by the concept
images: a polished SellThrough dashboard that works on desktop and phone. It is
not a commitment to build the entire visual product immediately. The near-term
goal is to prepare the backend, data contracts, and local web architecture so
that a dashboard like the concept can be built honestly on real data.

## Product North Star

The target experience is a responsive research console for resale decisions:

- Desktop dashboard with sidebar navigation, search, KPI cards, watchlist,
  listing insights, market trend panels, and best-opportunity cards.
- Mobile-first lookup/detail flow for field use at yard sales, estate sales, and
  thrift stores.
- Visual hierarchy similar to the concept images: clean white surface, restrained
  blue/teal accents, compact metric cards, data tables, chart panels, and clear
  status badges.
- Honest analytics: no fake sold metrics, trend charts, or sell-through scores
  unless the underlying normalized data exists.

## Architecture Direction

The first frontend should be a localhost-only web console backed by the existing
Python package. Do not jump directly to a hosted product or native app.

Recommended approach:

- Use FastAPI with server-rendered Jinja templates for the first web layer.
- Keep SQLite as the local data store.
- Keep eBay credentials server-side only.
- Reuse existing service/repository functions; do not query SQLite directly from
  templates.
- Treat responsive web/PWA as the first mobile path.
- Keep UI routes read-first until the local data model and workflows stabilize.

The frontend should sit on top of this shape:

```text
Browser
  -> FastAPI route
  -> view-model service
  -> existing SellThrough service/repository layer
  -> SQLite / eBay client where explicitly requested
```

## Near-Term Infrastructure Tasks

These tasks prepare the codebase for the concept UI without overbuilding the UI
itself.

### 1. Web App Skeleton (Implemented)

- Add optional web dependencies: `fastapi`, `uvicorn`, and `jinja2`.
- Add a `sellthrough web serve` CLI command that starts a localhost-only server.
- Add `src/sellthrough/web/` with app creation, templates, static CSS, and
  service-backed route handlers.
- Add a `/health` route that reports config/database/API readiness without
  exposing secrets.
- Add tests using FastAPI's test client for route availability when optional web
  dependencies are installed.

### 2. Frontend View Models

- Create view-model services that convert repository/service results into
  display-ready objects.
- Keep formatting decisions, pending-state labels, and empty-state copy in the
  view-model layer rather than templates.
- Start with dashboard, lookup, watchlist, and polling-status view models.
- Include explicit status fields for unavailable metrics, especially sold data
  and trends.

### 3. Data Readiness For Concept UI

- Add optional `image_url` to normalized active listings so product thumbnails
  can render when Browse provides them.
- Add repository methods for dashboard summaries:
  - active listing count
  - latest active listing `last_seen_at`
  - watchlist item count
  - recent poll run status
  - sample active listings
- Add a lightweight poll-run summary query so the UI can show freshness and
  failures.
- Sold metrics status: Pending Marketplace Insights access and sold-listing
  normalization.

### 4. Local Dashboard V1

- Build a responsive dashboard using real current data:
  - active listing KPI
  - watchlist summary
  - active lookup/search module
  - sample active listings table/cards
  - recent poll status
  - pending sold/trend/opportunity panels
- Use concept-inspired styling, but keep the layout utilitarian and readable.
- Avoid decorative dashboards that imply unavailable analytical precision.

### 5. Mobile-Ready Structure

- Design responsive breakpoints from the beginning.
- Use a desktop sidebar and a mobile bottom nav only after route structure is
  stable.
- Prioritize a fast lookup flow before full mobile dashboard parity.
- Keep PWA/offline support parked until local web usage proves valuable.

## Long-Term Feature Backlog

These belong after the local web foundation is useful:

- Sold listing ingestion and normalization after Marketplace Insights approval.
- Extend current active-side metric snapshots with sold demand, median sold
  price, and sold-sample confidence after Marketplace Insights approval.
- Sell-through score and opportunity ranking with transparent formulas.
- Trend charts based on stored snapshots, not one-off current rows.
- Watchlist management forms in the web UI.
- Saved find detail pages with local observed price and notes.
- Hosted deployment with authentication, managed secrets, Postgres, HTTPS,
  rate limiting, structured logs, backups, and background jobs.
- PWA installability, offline-tolerant saved finds, and eventually camera or
  barcode workflows if field usage justifies them.

## Task List

Use this checklist to stage future implementation work:

- [x] Add FastAPI/Jinja dependencies and document the local web runtime.
- [x] Add `sellthrough web serve` and a minimal localhost app.
- [x] Add `/health` route and tests.
- [x] Add web package structure with templates/static assets.
- [x] Add dashboard summary service with active-data and pending-state fields.
- [ ] Add optional `image_url` to Browse parsing and `active_listings`.
- [x] Add dashboard repository summary queries.
- [x] Add poll-run summary queries for freshness/status.
- [x] Build empty-state dashboard with concept-inspired layout.
- [ ] Build real active-listing summary cards and sample listing sections.
- [ ] Add lookup page backed by existing normalized lookup service.
- [x] Add watchlist overview page backed by existing watchlist service.
- [ ] Add recent poll status section.
- [x] Add pending sold/trend/opportunity panels with honest copy.
- [ ] Add responsive desktop/mobile navigation.
- [ ] Add visual regression or screenshot checks once layout stabilizes.
- [ ] Revisit sold metrics only after Marketplace Insights ingestion works.

Active-side snapshots exist. Full sell-through analytics do not exist yet.
Opportunity scoring requires both active supply and sold demand. Do not
implement until sold ingestion and sold snapshots are available.

## Non-Goals For The First Frontend Pass

- No hosted deployment.
- No public authentication system.
- No native mobile app.
- No fake sold metrics, sell-through score, opportunity rating, or trend charts.
- No client-side secret handling.
- No heavy JavaScript application framework unless server-rendered pages become
  insufficient.
