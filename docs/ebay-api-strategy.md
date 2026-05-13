# eBay API Integration Strategy

This document outlines the strategy for integrating with eBay's REST APIs to support SellThrough V1 market intelligence.

## V1 API Integration Scope

V1 focuses on building a repeatable ETL pipeline that captures active supply data and prepares for sold demand ingestion. 

- **Primary Goal:** Establish a robust, redacted, and paginated data capture layer.
- **Data Philosophy:** Store raw JSON truth first, then normalize into structured tables.
- **Architectural Boundary:** All API calls must go through feature-specific clients building on a shared `EbayClient` base.

## Core API Roles

| API | Role in V1 | Status |
| :--- | :--- | :--- |
| **Identity API** | OAuth2 token minting (Client Credentials flow). | **Implemented** |
| **Browse API** | Active listing search and current asking prices. | **Implemented** |
| **Taxonomy API** | Category tree resolution and keyword-to-category suggestions. | **Implemented** |
| **Marketplace Insights** | Historical sold prices and volume (last 30-90 days). | **Blocked** (Access Pending) |

---

## Authentication: OAuth2 Application Flow

SellThrough uses the **Client Credentials Grant** flow. This flow mints "Application Tokens" that identify the app itself, not a specific eBay user.

- **Flow Type:** `client_credentials`
- **Scope:** `https://api.ebay.com/oauth/api_scope`
- **Implementation:** Managed by `src/sellthrough/ebay/client.py`.
- **Caching:** Tokens are cached in-memory for the duration of the process. V1 does not persist tokens to disk to maintain "sensitive-by-default" security.

## Credential Handling & Redaction

Security is foundational to V1. The project enforces strict rules to prevent credential leakage.

- **Storage:** Credentials must be provided via environment variables (`EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`, `EBAY_DEV_ID`).
- **Redaction:** `src/sellthrough/security.py` provides a `sanitize_payload` helper that recursively redacts sensitive keys (tokens, emails, secrets) before logging or database storage.
- **Diagnostics:** The `config check` command verifies that keys are set without printing their literal values.

## Rate Limiting & Reliability

eBay enforces rate limits on all REST endpoints. SellThrough handles these gracefully.

- **Typed Errors:** Rate limits return a specific `EbayRateLimitError`.
- **Backoff:** The error captures the `Retry-After` header provided by eBay.
- **Future-Proofing:** Scheduled jobs should use this metadata to pause or reschedule instead of immediate retries.
- **Timeouts:** All network calls have a hard 30-second timeout to prevent hung processes.

---

## API-Specific Details

### Browse API (Active Supply)
Used to fetch current listings, condition, and asking prices.
- **Endpoint:** `/buy/browse/v1/item_summary/search`
- **Pagination:** Explicit `limit` (max 200) and `offset`.
- **V1 Filter Strategy:** Keyword-based with optional `category_ids`.

### Taxonomy API (Metadata)
Used to ensure watchlist items are correctly categorized for better comparison accuracy.
- **Endpoints:** `/commerce/taxonomy/v1/category_tree/{id}/get_default_category_tree_id`, `/commerce/taxonomy/v1/category_tree/{id}/get_category_suggestions`.
- **Note:** Category IDs are marketplace-scoped.

### Marketplace Insights (Sold Demand) - **BLOCKED**
This is the source for "sold" price truth. Access is currently pending "Application Growth Check" approval.
- **Internal Interface:** Already designed in `src/sellthrough/ebay/marketplace_insights.py` to allow pipeline development.
- **Blocker:** All sold-data features are blocked until the `403 Forbidden` (error 1100) is resolved by eBay.

---

## Relationship to Backlog Issues

This strategy document serves as the technical baseline for the following issues:

- **#27 (Browse Client):** Defines the async/httpx refactor requirements and pagination logic.
- **#43 (Research API Access):** Documents the specific error codes (1100) and approval blockers.
- **#19, #34, #36 (Sold Data Tasks):** These rely on the `MarketplaceInsightsClient` interface defined here.

## Risks and Assumptions
- **Assumption:** eBay Marketplace Insights access will eventually be granted.
- **Risk:** If access is denied, V1 will need a fallback strategy (e.g. combining Finding API or scraping), which is currently out of scope.
- **Risk:** Rate limits for Application Tokens are significantly lower than User Tokens; V1 polling frequency must remain conservative.
