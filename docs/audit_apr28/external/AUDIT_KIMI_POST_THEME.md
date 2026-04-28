# Kimi UI Overhaul Audit — post commit 7ea57cc

**Date**: 2026-04-28
**Auditor**: Kimi Code CLI
**Scope**: theme reskin (app.css), ticketing entry points (domain-workflow.html), compliance integration banner (domain-compliance-summary.html), sidebar scroll persistence (shell.js), cache-bust consistency

---

**Verdict: 78/100 — Theme reskin is structurally sound, but three light-theme bleeds and accessibility gaps remain that would be visible in a customer demo.**

Full inline report (Kimi also wrote a copy to `docs/audit_apr28/UI_OVERHAUL_AUDIT.md`).

### Top-Line Summary

| Area | Status | Notes |
|------|--------|-------|
| **Theme Consistency** | Mostly Pass | `app.css :root` correctly remapped to landing's navy/teal palette; Inter font, teal CTAs, navy gradient sidebar, and dark card chrome are all present. **BUT** `threat-map.html` has a white search input (`background: #fff`) with white-ish text (`color: var(--gray-700)` remapped to `rgba(255,255,255,0.86)`) — **text is invisible**. It also has a white-gradient word-cloud canvas. `dashboard.css` is still loaded by `dashboard.html` (not removed in this commit). |
| **Ticketing Entry Points** | Pass | "Connect Ticketing" CTA in header; 3 sync widgets with auto-showing Connect links; sidebar "Workflow & Ticketing" correctly routes to `domain-workflow.html`. |
| **Compliance Integration** | Pass | 3 header CTAs present; Integration Points banner with Vanta/Drata/OneTrust/Upload chips present above moduleTools. |
| **Sidebar Scroll Persistence** | Pass | Double `requestAnimationFrame` restore, 80ms debounced scroll save, and capture-phase click persistence all implemented correctly in `shell.js`. |
| **Cache Bust** | Pass | 39/39 dashboard HTMLs use `?v=20260434` for both `app.css` and `shell.js`. |
| **Other Demo Blockers** | 3 found | Empty icon buttons without `aria-label` in `dashboard.html`; missing `alt` text on `home.html:732`; `tool-catalog.js` uses stale cache-bust `?v=20260428`. |

### Critical Fixes Before Demo
1. **`frontend/threat-map.html:267`** — `.ti-search-input` has `background: #fff` + `color: var(--gray-700)` (remapped to white). Change to `background: var(--u-card); color: var(--u-fg);`.
2. **`frontend/threat-map.html:313`** — `.ti-cloud-canvas` uses `linear-gradient(180deg, #fafbfc, #ffffff)`. Override with `background: var(--u-card);`.
3. **`frontend/dashboard.html:137, 170`** — Add `aria-label` to empty `<button class="btn btn-ghost btn-icon">` elements.
