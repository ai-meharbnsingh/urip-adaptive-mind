# THEME_RESKIN — Dashboard aligned to landing.css brand tokens
**Date**: 2026-04-28  
**File changed**: `frontend/css/app.css` (only)

## Token changes in `:root`

| Token | Before | After | Landing source |
|---|---|---|---|
| `--u-bg` | `#0E0E10` | `#08121C` | `--navy-dark` |
| `--u-bg-elev` | `#14141A` | `#0D1B2A` | `--navy-primary` |
| `--u-card` | `#1A1A1F` | `#112236` | `--navy-mid` |
| `--u-card-2` | `#20202A` | `#1B2838` | `--navy-light` |
| `--u-border` | `#2A2A30` | `rgba(255,255,255,0.08)` | landing pattern |
| `--u-border-2` | `#34343E` | `rgba(255,255,255,0.14)` | landing pattern |
| `--u-fg` | `#ECEDEE` | `#FFFFFF` | landing `--white` |
| `--u-fg-2` | `#B6B7BC` | `rgba(255,255,255,0.78)` | landing pattern |
| `--u-fg-3` | `#7A7C84` | `rgba(255,255,255,0.5)` | landing pattern |
| `--u-primary` | `#4A6CF7` (blue) | `#1ABC9C` | `--teal-accent` |
| `--u-primary-2` | `#6883FB` | `#2ECC71` | `--teal-light` |
| `--u-primary-d` | `#2E50DD` | `#16A085` | `--teal-hover` |
| `--sev-low` | `#4A6CF7` (blue) | `#1ABC9C` | remapped to teal |

Heading `font-weight` bumped 600 → 700, `letter-spacing` tightened -0.01em → -0.02em (matches landing h1-h6).

## btn-primary / u-btn.is-primary

Both now use the teal gradient CTA matching landing's hero button:  
`background: linear-gradient(135deg, #1ABC9C 0%, #16A085 100%)` with `box-shadow: 0 6px 20px rgba(26,188,156,0.35)`. Hover lifts 1px and deepens glow.

## New override classes added

`body.urip-app` scoped overrides added before the fade-in block:
- `.kpi-card`, `.kpi-value`, `.kpi-label`, `.kpi-icon` (+ severity variants)
- `.stat-item`, `.stat-item .stat-value`, `.stat-item .stat-label`
- `.dashboard-card`, `.dashboard-card-title`
- `.framework-card` (+ `.name`, `.score`, `.score-label`)
- `.section-row`, `.section-row h2`

## Cache bust

10 domain HTML files updated: `app.css?v=20260428` → `app.css?v=20260429`.
