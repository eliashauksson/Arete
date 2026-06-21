# ROUTES.md — Arete full route reference

> Open this only when working on routing or handler logic. It's split out of
> CLAUDE.md so routine non-routing sessions don't load it every turn.

---

## `/setup` router

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

---

## `/calendar` router

| Method | Path | What it does |
|---|---|---|
| GET | `/calendar` | Full calendar page. Triggers `maybe_auto_expand` before rendering. |
| GET | `/calendar/events` | FullCalendar events API. Returns planned sessions + macro week banners (unexpanded) + race day markers + Strava activities as JSON. |
| GET | `/calendar/session/{id}` | Session detail HTMX partial (side panel). |
| GET | `/calendar/activity/{id}` | Activity detail HTMX partial. Fetches GPS/HR/pace streams lazily; generates AI summary if missing. |
| POST | `/calendar/week/{macro_week_id}/expand` | Expands a MacroWeek on demand. Returns JSON `{ok, sessions_count}`. |
| POST | `/calendar/session/{id}/adjust` | Adjusts session + following sessions via Claude. Body: `{"instruction": "..."}`. Returns JSON `{ok}`. |

---

## `/dashboard` router

| Method | Path | What it does |
|---|---|---|
| GET | `/dashboard` | Dashboard page with stat cards, Chart.js bar chart, weekly table. |
| POST | `/dashboard/re-adjust` | Calls `weekly_reonadjust`, redirects to `/dashboard`. |

---

## `/` (main.py)

- `GET /` → redirects to `/setup`
- HTTP middleware `inject_plan_state` → sets `request.state.has_plan` (used by base.html nav to gate Calendar/Dashboard links)
