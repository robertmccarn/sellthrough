# SellThrough Brand Guidelines

Last updated: 2026-05-12

## Purpose

This document codifies the visual direction from the approved SellThrough logo
concept so future web/mobile work stays consistent.

## Brand Signature

- Name: `SellThrough`
- Tone: analytic, trustworthy, modern, action-oriented
- Visual motif: circular flow arrows + upward market bars/line + price-tag shape

## Core Palette

Use these as default UI tokens, not ad hoc color picks:

- `--st-ink-900`: `#0b2748` (primary dark text)
- `--st-ink-700`: `#1f4fd6` (supporting brand blue)
- `--st-cyan-500`: `#1db6c6` (teal/cyan bridge)
- `--st-mint-500`: `#19c18f` (green success tone)
- `--st-bg-50`: `#f6f8fb` (app background)
- `--st-surface-0`: `#ffffff` (card/surface)
- `--st-border-200`: `#dce5f3` (borders/dividers)
- `--st-muted-500`: `#64748b` (secondary text)

Primary gradient:

- `--st-brand-gradient`: `linear-gradient(90deg, #1f4fd6 0%, #1db6c6 55%, #19c18f 100%)`

## UI Pattern

Keep the interface operational and data-first:

- Quiet background + bordered cards (`8px` radius max).
- KPI tiles with restrained typography and clear labels.
- Gradient reserved for brand accents and primary actions.
- Pending/unavailable analytics explicitly shown as `pending`, never fabricated.
- Tables and lists prioritize scanability over decoration.

## Logo Usage Rules

- Keep generous whitespace around the mark.
- Do not stretch, skew, or recolor outside approved palette/gradient.
- Prefer full wordmark on desktop headers and compact mark+name on mobile top bars.
- Avoid placing the mark on noisy/low-contrast backgrounds.

## Implementation Rule

When adding frontend code, import shared brand tokens first and reference token
variables (for example `var(--st-ink-900)`) instead of hardcoding new colors.
