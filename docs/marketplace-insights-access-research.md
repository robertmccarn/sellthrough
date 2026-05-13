# Marketplace Insights Access Research

Last updated: 2026-05-13

Related issues: #43, #19, #34, #36, #54, #55

## 1. Current Marketplace Insights Access Status

- SellThrough code includes a Marketplace Insights adapter and sold-search interface.
- Runtime behavior indicates Marketplace Insights access is still pending for the
  current keyset.
- The adapter explicitly treats access denial as a known blocked state
  (`MarketplaceInsightsAccessError`), rather than pretending sold data exists.
- V1 sold-side analytics remain blocked until access approval and sold
  normalization are complete.

## 2. Official Access Path / Application Growth Check

- Marketplace Insights remains the primary preferred source for sold-history
  data in SellThrough.
- The official path to unlock approval-sensitive access is eBay's Application
  Growth Check / developer-review path.
- Current project stance:
  - continue active-side delivery while waiting on approval.
  - keep sold-side work blocked, explicit, and traceable.
  - avoid undocumented access workarounds.

## 3. Marketplace Insights Dependency Map

Marketplace Insights approval is a hard dependency for:

- sold listing ingestion workflow (#54)
- sold listing normalization (#36)
- sold-side snapshot population (#55)
- sell-through calculations (#19)
- opportunity scoring/confidence surfaces (#34)

Without access, these items remain blocked and should not be represented as
partially shipped sold analytics.

## 4. Compliance Guardrails

- Do not fabricate sold-side metrics.
- Do not fabricate sell-through rates.
- Do not fabricate opportunity scores.
- Do not fabricate sold-sample confidence.
- Do not assume scraping as a compliant fallback.
- Keep credentials server-side and local env based.
- Keep raw payload handling sanitized and security-audited.

These guardrails align with current workflow and security docs.

## 5. Browse API Active-Side Capabilities

Browse API supports active-side market intelligence, including:

- active listing keyword search
- active asking prices
- conditions
- category hints/filtering
- refinements/pagination
- item web URLs
- image URL capability when present in payload (workstream tracked separately)
- active-side supply snapshots over time

Browse API is useful and sufficient for active-side V1, but it is not a
sold-history replacement.

## 6. Alternatives Matrix

| Option | Compliance risk | Data quality | Time to value | Recommendation |
|---|---|---|---|---|
| Marketplace Insights approval (primary path) | Low | High | Medium | **Preferred** |
| Stronger Application Growth Check / support package | Low | High (if approved) | Medium | **Pursue in parallel** |
| Active-side-only V1 continuation | Low | Medium (active only) | High | **Continue now** |
| User-provided sold/comps CSV import | Medium | Variable | Medium | **Possible scoped fallback (separate issue)** |
| Licensed third-party data provider | Medium | Variable to high | Medium to low | **Future evaluation only** |
| Manual comparable-sales entry | Low to medium | Low to variable | Medium | **Potential auxiliary workflow only** |
| Scraping eBay sold listings | High | Variable | Medium | **Rejected / out of scope** |

Notes:

- CSV/manual/licensed-provider options require separate legal/compliance review
  and should not be silently treated as equivalent to native Marketplace
  Insights data.
- None of these alternatives should unblock fake sold-side analytics.

## 7. Decision Record

### Decision

SellThrough will keep Marketplace Insights approval as the primary sold-history
path and continue active-side V1 progress while sold-side analytics remain
blocked.

### Why

- Aligns with existing architecture and security posture.
- Avoids compliance ambiguity from scraping-style approaches.
- Preserves analytical honesty: active-side is real; sold-side remains pending.
- Supports near-term product value through active-side market intelligence.

### Consequence

- Sold-side stories remain blocked.
- Active-side roadmap continues on `test-main`.
- #43 remains open/blocked as the canonical access dependency tracker.

## 8. eBay Developer Support Follow-up Draft

Subject: Marketplace Insights access request follow-up for SellThrough

Hello eBay Developer Support,

I am following up on Marketplace Insights API access for my production keyset.
I am building a local-first resale analytics tool and currently use Browse and
Taxonomy successfully. Sold-history analytics are intentionally blocked until
Marketplace Insights approval is granted.

Could you confirm:

1. Current Application Growth Check status for this keyset.
2. Any additional material needed to complete review.
3. Expected timeline and next review checkpoint.
4. Any policy constraints specific to sold-history usage for local analytics.

Thank you for your guidance.

## 9. Downstream Issue Impact

Blocked until Marketplace Insights approval and sold normalization:

- #19 Calculate Keyword Sell-Through Rate
- #34 View Opportunity Scores & Confidence
- #36 Implement Sold Listing Normalization
- #54 Add sold listing ingestion service after Marketplace Insights approval
- #55 Populate sold-side snapshot fields

## 10. Recommended Next Steps

1. Keep #43 open and blocked as the access dependency tracker.
2. Submit/refresh Application Growth Check follow-up with the support draft.
3. Continue active-side V1 roadmap work that does not depend on sold-history:
   - #33, #37, #41, #56, #57, #60, #61, #62, #63, #71
4. If approval delays persist, open a separate scoped issue to evaluate
   user-provided sold/comps CSV import feasibility with explicit compliance
   review and no fake sold metrics.
