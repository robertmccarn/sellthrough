# SellThrough v2 Feature Set Expansion

Assumption: v2 begins after sold-side implementation is complete.

That means v2 assumes the app already has:

Marketplace Insights approval
-> sold API ingestion
-> raw sold response storage
-> sold_listings normalization
-> sold observation lineage
-> sold metric snapshots

So v2 is not about "getting sold data working."
v2 is about turning active + sold data into decision support.

## v2 Baseline Product Question

Given real active supply and real sold demand, should I source this item, at what maximum buy price, with what confidence, and why?

v2 should move SellThrough from:

"What does the market look like?"

to:

"What should I do with this sourcing opportunity?"

## v2 Scope Theme

From analytics foundation to sourcing intelligence

v1 / sold-side foundation:

- Collect data
- Normalize data
- Preserve lineage
- Summarize active and sold market behavior

v2 expansion:

- Interpret the market
- Estimate profit
- Assess confidence
- Flag risk
- Recommend buy / watch / pass
- Rank opportunities
- Support real-world sourcing decisions

## Phase 1 - Item Matching and Watchlist Quality

### Feature 1.1 - Watchlist Query Refinement

Goal: Improve the quality of active/sold comparisons by making watchlist entries more specific.

Why this belongs in v2: Once sold data exists, bad matching becomes more damaging. Broad queries can distort sold counts, median prices, and sell-through rates.

Tasks:

- Add optional watchlist fields for brand
- Add optional model number field
- Add optional product family field
- Add optional condition target
- Add optional notes field
- Add query quality warnings
- Add docs explaining broad query vs specific model query

Example:

Weak watchlist query:
"dewalt drill"

Better watchlist query:
"DeWalt DCD791B tool only"

Possible output:

Query Quality: Needs refinement

Reason:
This query may include batteries, chargers, kits, cases, and unrelated drill models.

Suggested refinement:
DeWalt DCD791B tool only

### Feature 1.2 - Exclusion Keywords and Listing Filters

Goal: Reduce polluted comparisons caused by accessories, parts, broken items, empty boxes, manuals, and unrelated variants.

Tasks:

- Add exclude_terms to watchlist rows
- Apply exclude_terms to active lookup
- Apply exclude_terms to sold lookup
- Store exclusion logic with watchlist metadata
- Add CLI and web support for updating exclusions
- Add docs/examples for common exclusion terms

Example exclusions:

parts
for parts
broken
empty box
box only
manual
case only
charger only
battery only
replacement
repair

Potential command:

`python -m sellthrough watchlist update-filters 1 --exclude "parts,broken,empty box,case only"`

### Feature 1.3 - Category-Scoped Item Matching

Goal: Use eBay category context to reduce mismatched active/sold comparisons.

Tasks:

- Show category name next to category_id
- Add category suggestion workflow before watchlist creation
- Add command to update category on an existing watchlist row
- Apply category filters consistently to active and sold polling
- Add validation warning when category_id is missing for ambiguous searches

Potential commands:

`python -m sellthrough watchlist suggest-category "DeWalt DCD791B"`

`python -m sellthrough watchlist update-category 1 --category-id 184655`

## Phase 2 - Full Market Interpretation

### Feature 2.1 - Active Supply Quality Metrics

Goal: Improve interpretation of active listings beyond simple count and median price.

Tasks:

- Calculate active listing age
- Add stale active listing count
- Add median listing age
- Add fresh listing count over 7/30 days
- Add active price outlier detection
- Add trimmed active median
- Add active price interquartile range

Possible metrics:

active_count_now
active_count_stale_30d
median_listing_age_days
fresh_listing_count_7d
active_price_iqr
trimmed_active_median

Possible output:

Active Supply Quality:
- Active listings: 48
- Median active price: $82.50
- Trimmed median active price: $79.99
- Stale listings: 11
- Median listing age: 23 days

### Feature 2.2 - Sold Demand Quality Metrics

Goal: Interpret whether the item actually sells consistently, recently, and at reliable prices.

Tasks:

- Add sold_count_7d
- Add sold_count_30d
- Add sold_count_90d
- Add median_sold_price
- Add sold_price_min
- Add sold_price_max
- Add sold price interquartile range
- Add sold price volatility indicator
- Add sold recency metric

Possible output:

Sold Demand:
- Sold 30d: 42
- Median sold price: $89.99
- Sold price range: $64.00 - $119.99
- Sold price volatility: moderate
- Latest sold comp: 2 days ago

### Feature 2.3 - Supply vs Demand Interpretation

Goal: Compare active supply against sold demand in plain English.

Tasks:

- Add active_pressure_ratio
- Add supply_to_demand_ratio
- Add estimated_days_to_sell
- Add demand strength label
- Add market saturation label
- Add plain-English market interpretation

Potential formulas:

active_pressure_ratio = sold_count_30d / max(active_count_now, 1)

supply_to_demand_ratio = active_count_now / max(sold_count_30d, 1)

Possible output:

Demand signal: strong
Supply pressure: moderate
Estimated time to sell: 12-20 days

Interpretation:
Recent sold demand is high relative to active supply, but competition is not low.

## Phase 3 - Margin and Sourcing Economics

### Feature 3.1 - Local Buy Price Input

Goal: Let the user evaluate a real local sourcing opportunity.

Tasks:

- Add local_buy_price input to CLI lookup
- Add local_buy_price field to web lookup
- Validate positive numeric values
- Show profit estimate only when sold price data exists
- Allow quick one-off evaluations without saving

Potential command:

`python -m sellthrough lookup watchlist 1 --buy-price 35 --samples 5`

### Feature 3.2 - Fee, Shipping, and Packaging Estimation

Goal: Estimate net profit, not just resale price.

Tasks:

- Add configurable eBay fee percentage
- Add configurable payment fee percentage if needed
- Add configurable packaging cost
- Add optional shipping estimate
- Add default estimation profile
- Label all calculations as estimates

Formula:

estimated_net_profit =
    median_sold_price
    - local_buy_price
    - estimated_fees
    - estimated_shipping
    - packaging_cost

Possible output:

Estimated Economics:
- Median sold price: $89.99
- Local buy price: $35.00
- Estimated fees: $12.60
- Estimated shipping/packaging: $13.00
- Estimated net profit: $29.39
- Estimated margin: 32.7%

### Feature 3.3 - Max Recommended Buy Price

Goal: Convert market data into a practical sourcing threshold.

Tasks:

- Add target minimum profit setting
- Add target margin percentage setting
- Calculate max recommended buy price
- Calculate break-even buy price
- Show threshold in CLI and web lookup
- Document formula

Possible output:

Buy Price Guidance:
- Target profit: $20.00
- Target margin: 25%
- Max recommended buy price: $45.99
- Break-even buy price: $65.99

## Phase 4 - Confidence and Risk Model

### Feature 4.1 - Confidence Model

Goal: Prevent false certainty when market data is thin or noisy.

Tasks:

- Create confidence labels based primarily on sold sample size
- Use active sample size as secondary signal
- Penalize broad queries
- Penalize high price volatility
- Penalize mismatched condition/variant patterns
- Add confidence explanation text

Suggested labels:

High confidence: 50+ sold comps
Medium confidence: 15-49 sold comps
Low confidence: 5-14 sold comps
Speculative: fewer than 5 sold comps

Possible output:

Confidence: Medium

Reason:
42 sold comps in the last 30 days, moderate price spread, and clean category match.

### Feature 4.2 - Risk Flags

Goal: Surface practical sourcing risks before the user buys locally.

Tasks:

- Add manual risk tags to watchlist rows
- Add automatic low-sample-size warning
- Add high-active-competition warning
- Add price-volatility warning
- Add condition-sensitive warning
- Add high-shipping-cost warning
- Add broad-query warning

Risk flag examples:

low sold sample size
high active competition
price volatility
condition-sensitive
high shipping cost
fragile
broad query
variant mismatch

Possible output:

Risk Flags:
- Price volatility is high
- Sold comps vary strongly by condition
- Shipping may reduce margin

### Feature 4.3 - Condition and Variant Analysis

Goal: Separate materially different versions of an item.

Tasks:

- Group active and sold comps by condition
- Identify common title variants
- Separate bundles from item-only listings where possible
- Add condition-specific median sold price
- Add variant notes to lookup output

Possible output:

Variant Notes:
- Tool-only listings sell lower than kit listings
- Battery-included listings have a higher median sold price
- For-parts listings excluded from recommendation

## Phase 5 - Recommendation Engine

### Feature 5.1 - Buy / Watch / Pass Recommendation

Goal: Convert metrics into a practical sourcing action.

Tasks:

- Define transparent buy/watch/pass rules
- Require minimum confidence threshold for BUY
- Use sold demand, active supply, margin, and risk flags
- Explain recommendation in plain English
- Include data limitations in output
- Document the rule set

Possible output:

Recommendation: WATCH

Reason:
Sold demand is real, but active competition is high and profit margin is below target.

Useful numbers:
- Active listings: 42
- Sold 30d: 18
- Median sold price: $74.99
- Median active price: $69.99
- Max recommended buy price: $31.50

Risk:
Prices vary widely by condition.

### Feature 5.2 - Recommendation Explanation Trace

Goal: Make every recommendation auditable and defensible.

Tasks:

- Show which metrics drove the recommendation
- Show which rules fired
- Show confidence level
- Show risk flags
- Link recommendation back to snapshot IDs or raw lineage where possible

Possible output:

Why WATCH?
- Sold count is above minimum threshold
- Estimated net profit is below target
- Active competition is high
- Confidence is medium, not high

## Phase 6 - Opportunity Ranking

### Feature 6.1 - Watchlist Opportunity Ranking

Goal: Rank watchlist items by sourcing attractiveness.

Tasks:

- Add opportunity ranking service
- Rank only watchlist items with sufficient sold data
- Include confidence threshold
- Include risk penalties
- Include estimated margin
- Show ranking in CLI
- Show ranking in dashboard

Important boundary:

Only rank items with real active + sold metrics.

Possible output:

Top Opportunities:
1. TI-84 Plus CE
   Score: 84
   Max buy price: $42
   Confidence: High
   Reason: Strong sold demand, moderate active supply, healthy margin

2. DeWalt DCD791B
   Score: 76
   Max buy price: $46
   Confidence: Medium
   Reason: Strong demand, but price volatility is moderate

### Feature 6.2 - Opportunity Categories

Goal: Make ranking easier to understand than a single score.

Tasks:

- Add opportunity category labels
- Add plain-English category definitions
- Display categories in CLI and dashboard

Possible categories:

Strong Buy Candidate
Watch Closely
Good Demand, Low Margin
High Risk / High Reward
Oversaturated
Insufficient Data
Pass

## Phase 7 - Workflow and Operations

### Feature 7.1 - Data Freshness Tracking

Goal: Help users know whether recommendations are based on current data.

Tasks:

- Add last_active_poll_at to watchlist summary
- Add last_sold_poll_at to watchlist summary
- Add latest_snapshot_at
- Add stale data warnings
- Add freshness badges in dashboard

Possible output:

Data freshness: stale

Reason:
Sold data has not been refreshed in 12 days.

### Feature 7.2 - Watchlist Maintenance

Goal: Help users manage useful vs outdated watchlist entries.

Tasks:

- Show watchlist items with no sold observations
- Show watchlist items with low confidence
- Show watchlist items whose opportunity score declined
- Add command to refine/update query
- Add command to archive stale watchlist items

Potential commands:

`python -m sellthrough watchlist stale`

`python -m sellthrough watchlist refine 1 --query "DeWalt DCD791B tool only"`

`python -m sellthrough watchlist archive 4`

### Feature 7.3 - Digest Command

Goal: Summarize meaningful changes across the watchlist.

Tasks:

- Add manual digest command
- Show top improving opportunities
- Show declining opportunities
- Show stale data warnings
- Show failed poll warnings
- Show items requiring query refinement

Potential command:

`python -m sellthrough digest weekly`

Possible output:

Weekly Digest:
- 3 watchlist items improved
- 2 items declined
- 4 items have stale sold data
- 1 item needs query refinement
- Top candidate: TI-84 Plus CE

## Phase 8 - Web and Portfolio Polish

### Feature 8.1 - Recommendation Dashboard

Goal: Make the local web UI useful for reviewing sourcing opportunities.

Tasks:

- Add recommendation cards
- Add opportunity ranking table
- Add confidence and risk badges
- Add max buy price display
- Add recent active/sold snapshot status
- Keep all recommendation formulas transparent

### Feature 8.2 - Watchlist Web Management

Goal: Manage watchlist rows in the local web UI.

Tasks:

- Add watchlist add form
- Add watchlist edit/refine form
- Add watchlist disable/archive action
- Add category_id field
- Add exclude_terms field
- Add manual risk tags

### Feature 8.3 - Saved Finds and Notes

Goal: Support real-world local sourcing decisions.

Tasks:

- Create saved_finds table
- Store watchlist_id
- Store local price
- Store condition notes
- Store location/source
- Store timestamp
- Store recommendation result at time of evaluation
- Compare saved find against current metrics later

Possible use case:

At a thrift store, the user finds a TI-84 Plus CE for $24.99.
They enter local price and condition.
SellThrough returns max buy price, expected profit, confidence, and risks.

## Phase 9 - Responsive Field-Use Experience

### Feature 9.1 - Mobile-First Lookup Flow

Goal: Make SellThrough usable while sourcing locally.

Tasks:

- Improve responsive web layout
- Add mobile-first lookup screen
- Add quick watchlist selector
- Add local buy price input
- Add compact recommendation summary
- Add saved find action

### Feature 9.2 - PWA Support

Goal: Make the local/responsive web app more app-like if field usage proves valuable.

Tasks:

- Add PWA manifest
- Add installable web app basics
- Add simple offline-friendly saved draft flow if feasible
- Keep native mobile out of scope until later

## Phase 10 - Long-Term Deployment and Automation

### Feature 10.1 - Scheduled Polling

Goal: Move from manual refreshes to repeatable monitoring.

Tasks:

- Add local scheduler design
- Add scheduled active polling
- Add scheduled sold polling
- Add scheduled snapshot capture
- Add failed job reporting
- Add freshness warnings

### Feature 10.2 - Hosted Deployment

Goal: Move beyond local-first only after the app proves useful locally.

Tasks:

- Add authentication
- Move secrets to managed secret storage
- Migrate from SQLite to Postgres or another managed database
- Add HTTPS
- Add rate limiting
- Add structured logs
- Add backups
- Add background jobs

## v2 Recommended Build Order

1. Watchlist query refinement
2. Exclusion terms and category-scoped matching
3. Active + sold market interpretation metrics
4. Margin calculator and max recommended buy price
5. Confidence and risk model
6. Buy / watch / pass recommendation engine
7. Recommendation explanation trace
8. Opportunity ranking
9. Digest command
10. Recommendation dashboard
11. Saved finds and notes
12. Mobile-first lookup flow
13. Scheduled polling
14. Hosted deployment only after local value is proven

## v2 Hard Boundaries

Even after sold-side implementation, v2 should follow these rules:

- Do not recommend BUY unless sold sample confidence is sufficient.
- Do not hide formula logic behind unexplained scores.
- Do not treat broad queries as precise product matches.
- Do not ignore condition, bundle, shipping, or variant differences.
- Do not rank opportunities without active + sold data.
- Do not present estimates as guarantees.

## v2 Success Criteria

v2 is successful when SellThrough can answer:

Should I buy this item?
What is the maximum price I should pay?
How much profit might I make?
How fast is it likely to sell?
How confident is the recommendation?
What risks could make this a bad buy?
What evidence supports the recommendation?

The ideal v2 output is:

Recommendation: BUY under $42

Reason:
Recent sold demand is strong, active supply is moderate, median sold price supports the target margin, and sold sample confidence is high.

Expected economics:
- Median sold price: $89.99
- Max recommended buy price: $42.00
- Estimated net profit: $24.50
- Estimated margin: 27%

Risk flags:
- Moderate price volatility
- Condition matters

Confidence: High
