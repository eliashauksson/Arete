# Arete

A local, single-user, AI-powered endurance training planner.

Stack: FastAPI, Jinja2 + HTMX, SQLite (SQLModel), FullCalendar.js, Chart.js,
and the Anthropic Python SDK.

## How it works

Arete does **not** talk to the Strava REST API or implement Strava OAuth
itself. Instead, it runs the community [`strava-mcp`](https://github.com/r-huijts/strava-mcp)
server as a local subprocess (over stdio) and bridges it into Claude using
the Anthropic SDK's MCP client helpers + tool runner. When you ask Arete to
check your Strava connection, build a plan, or look at your activities,
Claude calls the Strava MCP server's tools directly — Arete's own code never
touches Strava's API or stores Strava tokens.

Claude's responses are extracted as structured JSON via a manual agentic
loop (`app/claude_client.py`) — it calls the Strava MCP tools itself when
Claude asks for them, rather than relying on the SDK's tool runner, so
results can be reliably parsed into the plan/activity records Arete stores.

## Pages

- **`/setup`** — connect Strava (via the MCP server's own browser-based
  OAuth flow), verify that Claude can reach your Strava data, and fill in a
  goal (race, date, distance, weekly hours, notes). Submitting the goal form
  has Claude fetch your real profile, recent activities, and HR zones via
  the Strava MCP tools and generate a 4-week training plan, saved to SQLite
  and then shown on `/calendar`. Takes 10–30 seconds — it's a real
  multi-step Claude + Strava round trip, not instant.
- **`/calendar`** — a FullCalendar view of your planned sessions
  (color-coded by sport: run/bike/swim/strength/brick/rest/other) with real
  Strava activities overlaid (faded/dashed). Click a planned session to see
  its details and type a free-text adjustment (e.g. "I'm injured, swap this
  week for rest") — Claude regenerates everything from that date forward,
  never touching sessions already in the past.
- **`/dashboard`** — a Chart.js bar chart of planned vs. actual training
  load per week, a weekly compliance percentage list, and a **Re-adjust**
  button that sends last week's planned-vs-actual numbers to Claude and
  rebalances the upcoming plan accordingly.

## Prerequisites

- Python 3.10+
- [Node.js](https://nodejs.org/) (tested with v20) — needed to run the
  Strava MCP server via `npx`
- An [Anthropic API key](https://console.anthropic.com/settings/keys) with
  a funded account (API usage is billed separately from any Claude.ai
  subscription)
- A [Strava API application](https://www.strava.com/settings/api)

## Setup

1. **Clone and create a virtualenv:**

   ```bash
   git clone <this-repo-url>
   cd Arete
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

2. **Get an Anthropic API key:**
   - Sign in at [console.anthropic.com](https://console.anthropic.com)
   - Go to **API Keys** → **Create Key**
   - Make sure the account has billing set up (**Settings → Billing**) —
     requests will fail with a billing error otherwise

3. **Create a Strava API application:**
   - Go to [strava.com/settings/api](https://www.strava.com/settings/api)
     (log in first)
   - Application Name: `Arete` (anything works)
   - Category: Training
   - Website: `http://localhost`
   - **Authorization Callback Domain: `localhost`** — just the bare word, no
     `http://`, no port. The Strava MCP server's OAuth helper listens on a
     local port to catch the redirect, so this must be `localhost`.
   - Copy the **Client ID** and **Client Secret** shown after creating it.

4. **Configure environment variables:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and fill in:

   ```
   ANTHROPIC_API_KEY=sk-ant-...
   STRAVA_CLIENT_ID=...
   STRAVA_CLIENT_SECRET=...
   ```

5. **Run the app:**

   ```bash
   .venv/bin/uvicorn app.main:app --reload --port 8000
   ```

   On startup, Arete spawns the Strava MCP server (`npx -y
   @r-huijts/strava-mcp-server`) automatically — no separate process to
   manage.

6. **Connect Strava:**

   Open [http://localhost:8000/setup](http://localhost:8000/setup) in a
   real browser (not curl — this step needs to open a browser window for
   Strava's consent screen) and click **Connect Strava**. Authorize the app,
   then use **Test Claude + Strava connection** to confirm Claude can pull
   your real Strava data.

7. **Generate a training plan:**

   On the same `/setup` page, fill in the goal form (race name, race date,
   distance, weekly hours available, optional notes) and click **Generate
   training plan**. This takes 10–30 seconds, then redirects you to
   `/calendar` with a real 4-week plan. From there:
   - Click any planned session to see details or type an adjustment
     instruction for Claude to act on.
   - Visit `/dashboard` to see planned-vs-actual load and weekly
     compliance, and use **Re-adjust** to have Claude rebalance the
     upcoming plan based on how last week actually went.

## Project structure

```
app/
├── main.py            FastAPI app; lifespan starts/stops the Strava MCP subprocess
├── config.py           Settings (env vars)
├── db.py                SQLModel engine + session + get_or_create_athlete
├── models.py             Athlete, Goal, TrainingPlan, PlannedSession, StravaActivity
├── mcp_client.py          Spawns and manages the Strava MCP server over stdio
├── claude_client.py        Manual agentic loop bridging the live MCP tools into Claude,
│                            with structured-JSON extraction (run_agentic_text/_json)
├── planner.py              Plan generation & cascading regeneration: generate_initial_plan,
│                            adjust_session, weekly_reonadjust, sync_strava_activities
├── routers/
│   ├── setup.py             /setup, /setup/connect-strava, /setup/verify-connection,
│   │                        /setup/generate-plan
│   ├── calendar.py           /calendar, /calendar/events, /calendar/session/{id},
│   │                         /calendar/session/{id}/adjust
│   └── dashboard.py          /dashboard, /dashboard/chart-data, /dashboard/re-adjust
├── templates/             Jinja2 templates (incl. FullCalendar + Chart.js via CDN)
└── static/                  Static assets (placeholder)
```

## Notes

- This is built for a single local user — there's no login system. Strava
  connection state lives in the MCP server's own config file
  (`~/.config/strava-mcp/config.json`), not in Arete's database.
- The SQLite database (`arete.db`) is created automatically on first run
  and is gitignored.
- "Load" is a relative training-stress number, not an official Strava
  metric: Claude assigns it when planning sessions, and actual load uses
  Strava's relative effort/suffer score when available, falling back to
  minutes of moving time otherwise.
- Generating a plan archives any previously active plan for the athlete —
  there's only ever one active `TrainingPlan` at a time.
- `/calendar` and `/dashboard` re-fetch and cache Strava activities (via
  Claude + the MCP tools) into the local `StravaActivity` table on every
  load, so each visit can trigger a real (and billed) Claude API call.
