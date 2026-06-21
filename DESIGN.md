# DESIGN.md — Arete frontend design system reference

> Open this only when working on templates, CSS, or frontend JS. It's split out
> of CLAUDE.md so routine backend sessions don't load it every turn.

---

## Design system (`base.html`)

All CSS is inline in a single `<style>` block in `base.html`. The design uses CSS
custom properties defined in three layers:

- `:root` (dark defaults), `[data-theme="dark"]`, `[data-theme="light"]`
- Compat aliases: `--text:var(--ink)`, `--surface:var(--panel)`, `--surface2:var(--panel2)`, `--border:var(--line)`, `--accent:var(--hot)`, `--secondary:var(--muted)`

**Token names (preferred):**
- `--bg` (page bg), `--panel` (card bg), `--panel2` (secondary bg), `--chip` (badge bg)
- `--line`, `--line2` (borders), `--ink`, `--ink2` (text), `--muted`, `--muted2` (subdued text)
- `--hot` (brand orange: `#FF5A1F` dark / `#E8480E` light)
- `--barbg` (chart bar bg), `--actual`, `--actual-bg`, `--actual-bd` (Strava activity color)
- `--hot-bd`, `--hot-wash` (orange callout border/bg)

**Fonts:**
- `'Newsreader', serif` — display headings, stat values
- `'Space Grotesk', sans-serif` — body, UI, buttons
- `'JetBrains Mono', monospace` — labels, eyebrows, numbers, table mono

**Typography scale:** h1 = 48px Newsreader (34px mobile), h2 = 29px, h3 = 21px, h4 = 9.5px JetBrains Mono uppercase

**Component CSS classes in base.html:**
- `.card` — bordered card (14px radius)
- `.badge`, `.badge.zone-1` through `.badge.zone-5` — inline chip
- `.stat-grid` / `.stat-card` / `.stat-label` / `.stat-value` / `.stat-sub` — KPI card grid
- `.btn`, `.btn-primary`, `.btn-ghost` — buttons
- `.setup-eyebrow` — JetBrains Mono 11px hot-colored label
- `.step-chip`, `.step-num` (`.active`=hot, `.done`=#2FD3C0, default=muted2) — step indicator
- `.chat-layout`, `.chat-window`, `.msg-row`, `.bubble` (`.user`=hot bg, `.claude`=panel2 bg) — chat UI
- `.typing-dots` — animated three-dot loader
- `.chat-input-bar`, `.chat-input-row`, `.chat-send-btn` — rounded pill input + circle send button
- `.gen-cta-btn` — pill-shaped orange generate button with box-shadow
- `.ai-callout` — orange-border callout for Claude summaries
- `.act-stat-grid` / `.act-stat-cell` / `.act-stat-label` / `.act-stat-value` — activity stats 3-col grid
- `.ar-desktop-only` / `.ar-mobile-only` — visibility breakpoint helpers (760px)
- `#gen-overlay` + `.visible` class — generation full-screen spinner

**Theme toggling:**
- JS: `arApplyTheme(theme)`, `arSetTheme(theme)`. Applied before first paint from `localStorage['arete-theme']`.
- Pages with charts set `window.arRebuildCharts = buildChart` so theme toggle refreshes them.
- `window.arRebuildCharts` hook is called by `arApplyTheme`.

**Animations:** `ar-spin` (spinner), `ar-td` (typing dots), `ar-slide`, `ar-fade`, `ar-rise`, `ar-pop-modal` (centered modal keyframe including translate in both states).

---

## Calendar (`calendar.html` + `calendar.py`)

- FullCalendar 6 with `dayGridMonth` default; Month/Week toggle via `calSetView()`.
- Event CSS classes: `.planned`, `.actual`, `.macro-week`, `.sport-{type}`.
- "This week" strip rendered from server context vars: `phase_tag`, `week_theme`, `week_total_sessions`, `week_planned_load`.
- `openPanel(html)` / `closePanel()` — desktop: `ar-pop-modal` centered modal (520px); mobile: full-screen slide-in from right.
- Backdrop click closes panel. Escape key: not yet implemented.
- Session adjustment: `fetch()` JSON POST (not HTMX) + `calendar.refetchEvents()` on success.

---

## Sport colors (calendar & templates, current design values)

- Run: `#FF5A1F`, Bike: `#34A9F0`, Swim: `#2FD3C0`, Strength: `#E2B23C`, Other: `#3A5A7A`

⚠️ **Known mismatch:** `planner.py:SPORT_COLORS` (backend, drives FullCalendar event
pills) still uses older values (`run:#2563eb` etc. — see CLAUDE.md → Plan generation
flow). The template sport dots above use these current design values instead. See
CLAUDE.md → Known gaps for the recommended fix (single shared source of truth).

---

## Responsive breakpoint: 760px

- Below 760px: hamburger nav, h1 = 34px, 2-col stat grid, full-screen slide-in panel.
- Above 760px: desktop nav, desktop modal for session detail.
