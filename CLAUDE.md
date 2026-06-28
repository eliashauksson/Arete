# CLAUDE.md — Arete developer reference

> **Rule: whenever you change any code in this project, update the relevant section(s) of this file (and README.md if it touches user-facing behaviour). Keep documentation in sync with the code.**
>
> **Reference files:** `DESIGN.md` (full CSS/design-token/component reference) and
> `ROUTES.md` (full route tables) are split out of this file on purpose. Open them
> only when actually working in that area — don't load them speculatively.

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
├── knowledge.py      Knowledge-base loader: load_knowledge(sport_types) → str
│                     Returns concatenated markdown (core + sport/combo file) prepended to
│                     plan-generation system prompts. No embeddings — pure filename lookup.
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
├── dashboard.html        Stat cards, Chart.js bar chart, full-season weekly table (all MacroWeeks; unexpanded rows are dimmed with hours×60 load proxy)
├── refine.html           Post-generation plan refine chat
├── _chat_bubble.html     HTMX partial: one chat exchange + optional plan-confirmed CTA
├── _session_detail.html  HTMX partial: planned session side panel (timeline, adjust form)
├── _activity_detail.html HTMX partial: Strava activity side panel (map, HR, pace charts)
├── _plan_generated.html  HTMX partial: success/error after plan generation
├── _plan_table.html      Shared partial: table of PlannedSessions (used in refine.html)
└── _refine_response.html HTMX partial: refine chat reply + oob plan table update

app/static/              Exists but is empty — app mounts it so it must be present

knowledge/               Sport-specific training science reference (loaded at plan-generation time)
├── core_training_science.md   Always loaded (sport-agnostic principles)
├── sports/
│   ├── road_running.md
│   ├── road_cycling.md
│   ├── swimming.md
│   └── trail_running.md
└── multisport/
    └── triathlon.md           Supersedes individual sport files for tri athletes
```

---

## Code simplicity rules (enforce these strictly)

The goal is simple code that works. These rules override the instinct to generalize,
abstract, or "clean up" surrounding code while fixing something.

### Scope — only touch what the task requires

- **Fix the bug, change the feature, stop.** Do not improve, rename, reformat, or
  restructure code that isn't directly part of the task. If you notice something
  unrelated that could be better, mention it in a comment to the user — don't fix it.
- **Don't refactor surrounding code** while adding a new feature. The new code should
  fit in as-is, even if the neighborhood isn't perfect.
- **Don't reorganize imports, reorder functions, or adjust whitespace** in files you
  touch unless the task is explicitly about that file's formatting.

### What not to create

- **No new modules.** The five modules (`claude_client.py`, `planner.py`, `db.py`,
  `mcp_client.py`, `knowledge.py`) plus three routers cover everything. Don't add a
  `services/`, `utils/`, `helpers/`, or `schemas/` layer. If logic doesn't fit an
  existing module, put it in the router that needs it.
- **No new classes.** `planner.py` and `claude_client.py` are intentionally
  function-based. Don't introduce a `PlanGenerator`, `SessionBuilder`, or any
  wrapper class. Use functions.
- **No new Pydantic/SQLModel request models** for simple payloads. A route that
  takes `{"instruction": "..."}` can use `body: dict = Body(...)` or read the key
  directly. Don't create an `AdjustRequest` model for a one-field body.
- **No new template partials** for HTML that's only rendered in one place. Inline
  it in the parent template.

### What not to extract

- **Don't extract a function** unless the exact same logic appears in 3+ call sites.
  A 10-line block in a route handler is fine. A one-call wrapper function is noise.
- **Don't extract constants** for values used once. A value used in one place can
  stay inline with a comment.
- **Don't split a working function** into smaller pieces because it "does two things."
  FastAPI route handlers do several things by design.

### SQLModel / DB rules

- Add columns via `migrate_db()` in `db.py`, not by creating new models.
- Don't add a repository layer. Queries go directly in routers or `planner.py`.
- Don't add relationships/FKs unless you need to query across them. A stored JSON
  field (like `structure` on `PlannedSession`) is often the right call.

### When editing templates

- Don't reorganize CSS or move tokens while fixing a layout bug. Fix the bug, stop.
- Don't add a CSS class for a style used once — inline the property.
- All CSS stays in `base.html`'s single `<style>` block. Don't create `.css` files.

### The test: before adding anything new, ask

1. Does this already exist somewhere in the codebase?
2. Would a future reader need this abstraction to understand the code, or does it
   just add a layer to navigate?
3. Is this solving a problem that exists right now, or one that might exist later?

If the answer to (1) is no and (2-3) are "no / might exist later" — don't add it.

---

## Working on this repo with Claude Code (usage/token efficiency)

This project is worked on heavily via Claude Code on a Pro plan, so context and
model/effort choices directly affect how fast the usage limit is hit.

- **Default model: Sonnet.** Escalate to Opus only for: `claude_client.py`
  prompt/caching logic, `planner.py` regeneration/adjustment logic, or any change
  touching 3+ files. Use `/model opusplan` for planning-with-Opus → execute-with-Sonnet
  on larger changes; it preserves conversation context across the switch.
- **Default effort: medium.** Use `low` for template/CSS tweaks, route wiring, copy
  edits, config changes. Use `high` only when debugging the agentic loop, DB
  migrations, or cross-file regressions.
- **Pick model + effort at session start and leave them.** Switching either mid-session
  invalidates the cached prompt prefix and forces a full, expensive re-read.
- **Open `DESIGN.md` / `ROUTES.md` only when editing that area.** They exist
  specifically so routine backend work doesn't load the full design-token and
  route-table reference every turn.
- **Reference files by path, not `@path`.** `@` pulls in the whole file plus its
  CLAUDE.md tree; a bare path (e.g. "look at `_agentic_loop` in `app/claude_client.py`")
  lets Claude read selectively.
- **`/clear` when switching areas** (e.g. `calendar.py` work → `claude_client.py`
  work). **`/compact`** when staying in the same area but a sub-task just finished.
- Don't open `app/templates/base.html` in full unless editing its CSS/JS directly —
  it's large by design (the whole theme system lives there); see `DESIGN.md` instead
  for the reference version.

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
| `_agentic_loop()` | Core loop: calls Claude, executes MCP tool calls, repeats until `stop_reason != "tool_use"`. Caches tools array and last tool_result with `cache_control: ephemeral, ttl: 1h`. Uses `output_config={"effort": effort}` — confirmed valid API param. |
| `run_agentic_text()` | Single-prompt agentic call returning plain text. |
| `run_agentic_json()` | Single-prompt agentic call expecting JSON back. Has a retry if parsing fails. Prepends a cached athlete context block when a system prompt is present. |
| `cached_tools()` | Builds Claude tool list from live MCP tools. Marks last tool with `cache_control` so the ~5k-token tools array is cached. |
| `get_cached_athlete_context()` | Fetches athlete profile + HR zones once per process (in-memory cache). Returns a 3-5 sentence summary string. |
| `setup_chat_response()` | Direct Claude call (no MCP tools) for the conversational intake. Prepends greeting as prior assistant turn. |
| `extract_goal_json()` | Parses `<GOAL_JSON>…</GOAL_JSON>` block from Claude's PLAN_CONFIRMED response. |
| `clean_claude_message()` | Strips `<GOAL_JSON>` and `PLAN_CONFIRMED` markers before showing text to users. |
| `generate_macro_plan()` | Direct Claude call (no MCP) to produce full-season macro plan JSON. Uses Sonnet. Knowledge base prepended to system prompt via `load_knowledge(sport_types)`. |
| `expand_macro_week()` | Direct Claude call (no MCP) to expand one MacroWeek into 7 PlannedSession records. Uses Haiku. Takes optional `sport_types` list; knowledge base prepended to system prompt. |
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

### Sport colors (calendar event colors, backend)
```python
run: #2563eb, bike: #16a34a, swim: #0891b2,
strength: #9333ea, brick: #ea580c, rest/other: #6b7280
```
⚠️ These are stale relative to the current design tokens — see "Known gaps" below.
Current values are in `DESIGN.md`.

### Strava sync (`sync_strava_activities`)
- Freshness window: 1 hour (`STRAVA_SYNC_FRESHNESS`)
- Force-refetch: `force=True` bypasses cache
- Skips AI summaries during bulk import (`skip_summaries=True`) — generated lazily on first activity click
- Called on every `/calendar/events` request (calendar view) and dashboard load

---

## Routes reference

Full route tables (methods, paths, request/response shape) are in **ROUTES.md** —
open it only when working on routing or handler logic.

Quick orientation: three routers — `app/routers/setup.py`, `calendar.py`,
`dashboard.py`. Root `/` redirects to `/setup`. `inject_plan_state` middleware
(`main.py`) sets nav-gating template state on every request (see below).

---

## Frontend / templates

Full design system reference (CSS custom properties, fonts, typography scale,
component classes, theme toggling, animations, calendar JS behaviour) is in
**DESIGN.md** — open it only when touching templates, CSS, or frontend JS.

Backend-relevant facts worth keeping here even so:

- All CSS lives inline in `base.html`'s single `<style>` block — there are no
  separate CSS files.
- `inject_plan_state` middleware (`app/main.py`) injects into every template
  context: `has_plan` (bool, gates Calendar/Dashboard nav links), `days_to_race`
  (int | None), `race_name_short` (str | None), `athlete_initials` (str).
- Responsive breakpoint: 760px (hamburger nav / full-screen panels below it).

---

## Known gaps / incomplete items

- `PlannedSession.strava_activity_id` FK exists but is never populated (no matching logic)
- `PlannedSession.status` field is never updated from `"planned"` (no completion tracking)
- `Goal.target_time` collected in intake but not passed to Claude in prompts
- **Sport color drift:** `planner.py:SPORT_COLORS` (backend, drives FullCalendar event
  pills) uses old hex values; template sport dots use newer design-token values
  (see `DESIGN.md`). Pick one source of truth — recommend a shared constants module
  both Python and Jinja read from, rather than two hardcoded lists.
- `app/static/` is empty (mounted, must exist)
- ~~No tests of any kind~~ Unit tests exist in `tests/test_unit.py` (63 tests, Layer 1 only — pure functions and DB helpers, no Claude/Strava)
- No way to view/manage archived plans or edit goals after generation
- `weekly_reonadjust` has a typo in its function name (extra `o`)

---

## Testing rules

Unit tests live in `tests/test_unit.py`. A `PostToolUse` hook runs them automatically after every file edit, but also run them manually when finishing a task.

**After every code change:** run `python -m pytest tests/test_unit.py -q` and fix any failures before reporting the task done.

**When adding new code:** evaluate whether tests are needed and write them without being asked. Write tests if the new code is a pure function or DB helper with no Claude/Strava dependency. Skip if it requires mocking the agentic loop, MCP, or HTTP — those are Layer 2 and not currently covered.

**What belongs in `tests/test_unit.py`:**
- New pure functions in `claude_client.py`, `planner.py`, `knowledge.py`, `db.py`
- New small helpers in routers (e.g. a new `_parse_*` or `_build_*` function)
- Edge cases for existing functions when you discover an untested branch while working nearby

**What does not belong:**
- Tests that require Claude API calls, Strava MCP, or the full FastAPI app
- Tests for route handlers (Layer 2 — not currently in scope)

---

## Important code invariants to preserve

1. **Only one active TrainingPlan per athlete.** `generate_initial_plan` archives all existing active plans before creating the new one.
2. **MacroWeek → PlannedSession expansion is idempotent.** `_expand_week` deletes the week's sessions before inserting new ones.
3. **Strava token is not in Arete's DB.** It lives in `~/.config/strava-mcp/config.json`, managed by the MCP server.
4. **Cascading regeneration is bounded.** `_bounded_range_end` caps regeneration to 13 days so it fits within `MAX_TOKENS_ADJUSTMENT`.
5. **`clean_claude_message()` must be applied before any Claude response is shown to the user.** The raw response may contain `<GOAL_JSON>…</GOAL_JSON>` and `PLAN_CONFIRMED` markers.
6. **Prompt caching breakpoints.** The last tool in the tools list and the last tool_result in each loop iteration carry `cache_control: ephemeral`. Don't remove these — they significantly reduce API costs on multi-turn agentic calls.
7. **Don't switch Claude Code model or effort level mid-session.** It invalidates the cached prompt prefix (point 6) and forces a full, expensive re-read. Pick both at session start — see "Working on this repo with Claude Code" above.
