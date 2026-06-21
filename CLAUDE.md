# CLAUDE.md — Arete developer reference

> **Rule: whenever you change any code in this project, update the relevant section(s) of this file (and README.md if it touches user-facing behaviour). Keep documentation in sync with the code.**

---

## What this project is

Arete is a **local, single-user, AI-powered endurance training planner**. It is a personal tool — no auth, no multi-user support. One athlete record in the DB at all times.

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| ORM / DB | SQLModel + SQLite (`arete.db`, auto-created) |
| Templates | Jinja2 + HTMX (server-side HTML fragments, no JS framework) |
| Frontend libs | FullCalendar.js 6, Chart.js 4, Leaflet.js 1.9 — all via CDN |
| AI | Anthropic Python SDK (`anthropic[mcp]`), models: `claude-sonnet-4-6` and `claude-haiku-4-5-20251001` |
| Strava | `@r-huijts/strava-mcp-server` via `npx` (stdio subprocess) — Arete never calls Strava REST directly |

---

## How to run

```
make start    # starts uvicorn in background, writes PID to .server.pid, logs to .server.log
make stop     # kills the process
make reload   # stop + start
```

The app is at `http://localhost:8000`. Root redirects to `/setup`.

The Strava MCP subprocess (`npx -y @r-huijts/strava-mcp-server`) is spawned automatically on startup inside FastAPI's `lifespan` function (`app/main.py`). Allow ~4 seconds for it to fully connect.

Strava OAuth state lives in `~/.config/strava-mcp/config.json` — not in the app DB.

---

## Environment variables (`.env`)

```
ANTHROPIC_API_KEY=sk-ant-...
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
DATABASE_URL=sqlite:///./arete.db        # default
STRAVA_ROUTE_EXPORT_PATH=./data/routes   # where MCP server writes GPX/TCX
```

Loaded by `app/config.py` via pydantic-settings. Copy `.env.example` to get started.

---

## Project file map

```
app/
├── main.py           FastAPI app + lifespan (starts/stops MCP subprocess)
│                     HTTP middleware: injects request.state.has_plan for nav gating
├── config.py         Settings (env vars via pydantic-settings)
├── db.py             SQLite engine, create_db_and_tables(), migrate_db(), get_session(), get_or_create_athlete()
├── models.py         All SQLModel table definitions (see below)
├── mcp_client.py     StravaMCPClient — wraps MCP stdio session; exposes list_tools() / call_tool()
│                     Singleton `strava_mcp` imported everywhere
├── claude_client.py  All Claude calls (see below)
├── planner.py        Plan generation, session expansion, adjustment, Strava sync (see below)
└── routers/
    ├── setup.py      /setup routes (chat intake, plan generation, refine)
    ├── calendar.py   /calendar routes (events API, session/activity detail, week expand, session adjust)
    └── dashboard.py  /dashboard routes (load chart, re-adjust)

app/templates/
├── base.html             Nav, global CSS (design tokens), generation overlay, HTMX CDN
├── setup.html            Chat intake UI (bubbles, typing indicator, input bar)
├── calendar.html         FullCalendar + Leaflet + Chart.js, side panel JS
├── dashboard.html        Stat cards, Chart.js bar chart, weekly table
├── refine.html           Post-generation plan refine chat
├── _chat_bubble.html     HTMX partial: one chat exchange + optional plan-confirmed CTA
├── _session_detail.html  HTMX partial: planned session side panel (timeline, adjust form)
├── _activity_detail.html HTMX partial: Strava activity side panel (map, HR, pace charts)
├── _plan_generated.html  HTMX partial: success/error after plan generation
├── _plan_table.html      Shared partial: table of PlannedSessions (used in refine.html)
└── _refine_response.html HTMX partial: refine chat reply + oob plan table update

app/static/              Exists but is empty — app mounts it so it must be present
```

---

## Database models (`app/models.py`)

| Model | Purpose |
|---|---|
| `Athlete` | Single row. Tracks `display_name`, `strava_connected`, `last_strava_sync`. |
| `Goal` | Race goals: name, date, distance, target time, weekly hours, notes, sport_types (JSON), goals_json (full multi-race data). |
| `TrainingPlan` | Links athlete → goal. `status`: `active` or `archived`. Only one active plan at a time. |
| `PlannedSession` | One per calendar day. Fields: date, sport_type, title, description, hr_zone, structure (JSON blocks), planned_duration_min, planned_load, status (always `"planned"` — never updated), strava_activity_id FK (never populated). |
| `SetupConversation` | Full message history for the intake chat (JSON). `status`: `chatting` or `done`. Stores `strava_context` (cached Strava summary) and `goal_json` (extracted on PLAN_CONFIRMED). |
| `MacroPlan` | One full-season macro skeleton per TrainingPlan. Links training_plan_id → athlete_id, season dates. |
| `MacroWeek` | One row per week in the macro plan. Stores phase, sport_focus, hour targets per sport, theme, `is_expanded` flag. |
| `StravaActivity` | Cached Strava activities. `gpx_data`, `hr_data`, `pace_data` fetched lazily on first view. `ai_summary` generated on first view (or skipped during bulk history import). |

### DB migrations

`db.py:migrate_db()` adds columns via `ALTER TABLE` on startup (SQLite, no IF NOT EXISTS — uses PRAGMA check). Add new migrations there when adding columns to existing tables.

---

## Claude calls (`app/claude_client.py`)

### Models used

- `claude-sonnet-4-6` — setup intake chat, plan generation (macro plan), agentic loop
- `claude-haiku-4-5-20251001` — activity summaries, expanding individual MacroWeeks into sessions

### Key functions

| Function | What it does |
|---|---|
| `_agentic_loop()` | Core loop: calls Claude, executes MCP tool calls, repeats until `stop_reason != "tool_use"`. Caches tools array and last tool_result with `cache_control: ephemeral, ttl: 1h`. Uses `output_config={"effort": effort}` — **verify this param is valid on current SDK**. |
| `run_agentic_text()` | Single-prompt agentic call returning plain text. |
| `run_agentic_json()` | Single-prompt agentic call expecting JSON back. Has a retry if parsing fails. Prepends a cached athlete context block when a system prompt is present. |
| `cached_tools()` | Builds Claude tool list from live MCP tools. Marks last tool with `cache_control` so the ~5k-token tools array is cached. |
| `get_cached_athlete_context()` | Fetches athlete profile + HR zones once per process (in-memory cache). Returns a 3-5 sentence summary string. |
| `setup_chat_response()` | Direct Claude call (no MCP tools) for the conversational intake. Prepends greeting as prior assistant turn. |
| `extract_goal_json()` | Parses `<GOAL_JSON>…</GOAL_JSON>` block from Claude's PLAN_CONFIRMED response. |
| `clean_claude_message()` | Strips `<GOAL_JSON>` and `PLAN_CONFIRMED` markers before showing text to users. |
| `generate_macro_plan()` | Direct Claude call (no MCP) to produce full-season macro plan JSON. Uses Sonnet. |
| `expand_macro_week()` | Direct Claude call (no MCP) to expand one MacroWeek into 7 PlannedSession records. Uses Haiku. |
| `generate_activity_summary()` | Lightweight Haiku call (no MCP) for 2-3 sentence coaching summary of a Strava activity. |
| `verify_strava_connection()` / `connect_strava()` | Agentic calls that use MCP tools to check/start Strava OAuth. |

### Prompt caching strategy

Tools array → cached (breakpoint on last tool). System prompts → `cache_control: ephemeral, ttl: 1h`. Athlete context block → prepended with cache_control when doing planning calls. Accumulated conversation history in agentic loop → cached via last tool_result breakpoint.

---

## Plan generation flow (`app/planner.py`)

### Two-layer system

**Layer 1 — Macro plan (generate_macro_plan):**
- Called once at plan generation time (`generate_initial_plan`)
- Sonnet call with full history summary + athlete context
- Returns `{"weeks": [{week_number, start_date, phase, sport_focus, hours_*, theme}]}`
- Stored as `MacroPlan` + N `MacroWeek` rows, all with `is_expanded=False`
- Phases: base → build → specific → taper → race → recovery

**Layer 2 — Week expansion (expand_macro_week / _expand_week):**
- Haiku call, lightweight, ~1500 tokens output
- Converts one MacroWeek's hour targets and theme into 7 `PlannedSession` rows
- Replaces existing sessions for that week range, sets `is_expanded=True`

**Initial generation** (`generate_initial_plan`):
1. Archives any existing active plan
2. Syncs 12 months of Strava history (force=True, skip_summaries=True) → `build_activity_summary()` for context
3. Generates macro plan (Sonnet)
4. Stores MacroPlan + MacroWeeks
5. Immediately expands first 3 weeks into daily sessions

**Rolling auto-expansion** (`maybe_auto_expand`):
- Triggered on every `/calendar` page load
- If fewer than 14 future `PlannedSession` rows exist, expands the next unexpanded MacroWeek
- This keeps a rolling ~2-week detailed horizon

**Manual expansion:** `POST /calendar/week/{macro_week_id}/expand` (user clicks macro banner on calendar)

### Adjustment functions

| Function | Behaviour |
|---|---|
| `adjust_session()` | Replaces sessions from clicked date to `_bounded_range_end` (≤13 days ahead) — `MAX_TOKENS_ADJUSTMENT = 4096` |
| `refine_plan()` | Replaces all future sessions based on freeform instruction — `MAX_TOKENS_PLAN_GENERATION = 8192` |
| `weekly_reonadjust()` | Compares last week planned vs actual load; regenerates from today — bounded to 13 days |
| `regenerate_sessions_from()` | Core replacement primitive: deletes sessions in range, calls `run_agentic_json`, inserts new sessions |

### Sport colors (calendar event colors)
```python
run: #2563eb, bike: #16a34a, swim: #0891b2,
strength: #9333ea, brick: #ea580c, rest/other: #6b7280
```

### Strava sync (`sync_strava_activities`)
- Freshness window: 1 hour (`STRAVA_SYNC_FRESHNESS`)
- Force-refetch: `force=True` bypasses cache
- Skips AI summaries during bulk import (`skip_summaries=True`) — generated lazily on first activity click
- Called on every `/calendar/events` request (calendar view) and dashboard load

---

## Routes reference

### `/setup` router

| Method | Path | What it does |
|---|---|---|
| GET | `/setup` | Chat intake page. Loads existing active conversation or blank. |
| POST | `/setup/chat` | One chat turn. Fetches Strava context on first turn. Detects PLAN_CONFIRMED. Returns HTMX partial `_chat_bubble.html`. |
| POST | `/setup/reset` | Marks current conversation `done`; redirects to fresh `/setup`. |
| POST | `/setup/generate` | Reads `goal_json` from conversation, creates Goal, calls `generate_initial_plan`, redirects to `/calendar` via HX-Redirect. Shows overlay during generation. |
| GET | `/setup/refine` | Refine page showing current plan table + chat form. |
| POST | `/setup/refine/chat` | Applies freeform instruction via `refine_plan()`. Returns `_refine_response.html` with OOB plan table update. |
| POST | `/setup/connect-strava` | Calls `connect_strava()` via MCP. |
| POST | `/setup/verify-connection` | Calls `verify_strava_connection()` via MCP. |

### `/calendar` router

| Method | Path | What it does |
|---|---|---|
| GET | `/calendar` | Full calendar page. Triggers `maybe_auto_expand` before rendering. |
| GET | `/calendar/events` | FullCalendar events API. Returns planned sessions + macro week banners (unexpanded) + Strava activities as JSON. |
| GET | `/calendar/session/{id}` | Session detail HTMX partial (side panel). |
| GET | `/calendar/activity/{id}` | Activity detail HTMX partial. Fetches GPS/HR/pace streams lazily; generates AI summary if missing. |
| POST | `/calendar/week/{macro_week_id}/expand` | Expands a MacroWeek on demand. Returns JSON `{ok, sessions_count}`. |
| POST | `/calendar/session/{id}/adjust` | Adjusts session + following sessions via Claude. Body: `{"instruction": "..."}`. Returns JSON `{ok}`. |

### `/dashboard` router

| Method | Path | What it does |
|---|---|---|
| GET | `/dashboard` | Dashboard page with stat cards, Chart.js bar chart, weekly table. |
| POST | `/dashboard/re-adjust` | Calls `weekly_reonadjust`, redirects to `/dashboard`. |

### `/` (main.py)
- `GET /` → redirects to `/setup`
- HTTP middleware `inject_plan_state` → sets `request.state.has_plan` (used by base.html nav to gate Calendar/Dashboard links)

---

## Frontend / templates

### Design system (base.html)

All CSS is inline in a single `<style>` block in `base.html`. The design uses CSS custom properties defined in three layers:
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

### Middleware-injected template state (app/main.py)

`inject_plan_state` middleware adds to `request.state`:
- `has_plan` (bool) — gates nav links to Calendar/Dashboard
- `days_to_race` (int | None) — from active Goal.race_date
- `race_name_short` (str | None) — first 14 chars of race name, uppercased
- `athlete_initials` (str) — 1-2 char initials from Athlete.display_name

### Calendar (calendar.html + calendar.py)

- FullCalendar 6 with `dayGridMonth` default; Month/Week toggle via `calSetView()`.
- Event CSS classes: `.planned`, `.actual`, `.macro-week`, `.sport-{type}`.
- "This week" strip rendered from server context vars: `phase_tag`, `week_theme`, `week_total_sessions`, `week_planned_load`.
- `openPanel(html)` / `closePanel()` — desktop: `ar-pop-modal` centered modal (520px); mobile: full-screen slide-in from right.
- Backdrop click closes panel. Escape key: not yet implemented.
- Session adjustment: `fetch()` JSON POST (not HTMX) + `calendar.refetchEvents()` on success.

### Sport colors (calendar & templates)
- Run: `#FF5A1F`, Bike: `#34A9F0`, Swim: `#2FD3C0`, Strength: `#E2B23C`, Other: `#3A5A7A`
- Note: `planner.py:SPORT_COLORS` still uses old values (`run:#2563eb` etc.) — these drive FullCalendar event colors. The template sport dots use the new design values above.

### Responsive breakpoint: 760px
- Below 760px: hamburger nav, h1 = 34px, 2-col stat grid, full-screen slide-in panel.
- Above 760px: desktop nav, desktop modal for session detail.

---

## Known gaps / incomplete items

- `PlannedSession.strava_activity_id` FK exists but is never populated (no matching logic)
- `PlannedSession.status` field is never updated from `"planned"` (no completion tracking)
- `Goal.target_time` collected in intake but not passed to Claude in prompts
- `output_config={"effort": effort}` in `_agentic_loop` — verify this is a valid API param; Claude's extended thinking uses `thinking`, not `output_config`
- `app/static/` is empty (mounted, must exist)
- No tests of any kind
- No way to view/manage archived plans or edit goals after generation
- Sport colors in `planner.py:SPORT_COLORS` use old values (run=`#2563eb` etc.) — FullCalendar event pills use these; template sport dots use new design values
- `weekly_reonadjust` has a typo in its function name (extra `o`)

---

## Important code invariants to preserve

1. **Only one active TrainingPlan per athlete.** `generate_initial_plan` archives all existing active plans before creating the new one.
2. **MacroWeek → PlannedSession expansion is idempotent.** `_expand_week` deletes the week's sessions before inserting new ones.
3. **Strava token is not in Arete's DB.** It lives in `~/.config/strava-mcp/config.json`, managed by the MCP server.
4. **Cascading regeneration is bounded.** `_bounded_range_end` caps regeneration to 13 days so it fits within `MAX_TOKENS_ADJUSTMENT`.
5. **`clean_claude_message()` must be applied before any Claude response is shown to the user.** The raw response may contain `<GOAL_JSON>…</GOAL_JSON>` and `PLAN_CONFIRMED` markers.
6. **Prompt caching breakpoints.** The last tool in the tools list and the last tool_result in each loop iteration carry `cache_control: ephemeral`. Don't remove these — they significantly reduce API costs on multi-turn agentic calls.
