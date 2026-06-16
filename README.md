# Arete

A local, single-user, AI-powered endurance training planner.

Stack: FastAPI, Jinja2 + HTMX, SQLite (SQLModel), FullCalendar.js, Leaflet.js, Chart.js,
and the Anthropic Python SDK.

## How it works

Arete does **not** talk to the Strava REST API or implement Strava OAuth
itself. Instead, it runs the community [`strava-mcp`](https://github.com/r-huijts/strava-mcp)
server as a local subprocess (over stdio) and bridges it into Claude using
the Anthropic SDK's MCP client helpers. When Arete needs Strava data, Claude
calls the MCP tools directly — Arete's own code never touches Strava's API
or stores Strava tokens.

Claude responses are extracted via a manual agentic loop (`app/claude_client.py`).
The setup intake uses a direct (non-tool) Claude call with the full conversation
history; plan generation and activity analysis go through the full MCP-enabled
agentic loop with prompt caching.

## Pages

- **`/setup`** — conversational AI intake coach. Claude asks 1–2 questions at a
  time to gather your A/B/C race goals, sport mix (run/bike/swim/strength/tri),
  weekly availability, and blocked days. It silently fetches your Strava profile
  after the first message and weaves it in naturally. After 8–10 exchanges it
  summarises everything and asks for confirmation, then generates a structured
  plan saved to SQLite. The full conversation is stored so you can close the
  browser and pick up where you left off.
- **`/calendar`** — FullCalendar view of planned sessions (colour-coded by
  sport) with real Strava activities overlaid. Click a planned session for
  details and a free-text adjustment field — Claude regenerates everything
  from that date forward. Click a Strava activity to see a detail panel with
  a Leaflet map of the GPS route, Chart.js HR and pace graphs, and a 2–3
  sentence AI coaching summary.
- **`/dashboard`** — Chart.js bar chart of planned vs. actual training load
  per week, weekly compliance %, and a **Re-adjust** button that sends last
  week's numbers to Claude and rebalances the upcoming plan.

## Prerequisites

- Python 3.10+
- [Node.js](https://nodejs.org/) (tested with v20) — needed to run the
  Strava MCP server via `npx`
- An [Anthropic API key](https://console.anthropic.com/settings/keys) with
  a funded account (API usage is billed separately from Claude.ai subscriptions)
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
   - Make sure billing is set up (**Settings → Billing**)

3. **Create a Strava API application:**
   - Go to [strava.com/settings/api](https://www.strava.com/settings/api)
   - Application Name: `Arete` (anything works)
   - Category: Training
   - Website: `http://localhost`
   - **Authorization Callback Domain: `localhost`** — bare word, no `http://`,
     no port. The Strava MCP server's OAuth helper catches the redirect.
   - Copy the **Client ID** and **Client Secret**.

4. **Configure environment variables:**

   ```bash
   cp .env.example .env
   ```

   Edit `.env`:

   ```
   ANTHROPIC_API_KEY=sk-ant-...
   STRAVA_CLIENT_ID=...
   STRAVA_CLIENT_SECRET=...
   ```

5. **Run the app:**

   ```bash
   .venv/bin/uvicorn app.main:app --reload --port 8000
   ```

   Arete spawns the Strava MCP server (`npx -y @r-huijts/strava-mcp-server`)
   automatically on startup.

6. **Connect Strava:**

   Open [http://localhost:8000/setup](http://localhost:8000/setup) and use
   the **Connect Strava** / **Test connection** links to authorise via
   Strava's browser OAuth flow.

7. **Run the intake chat:**

   Chat with the AI coach on `/setup`. It will ask about your goals, check
   your Strava history, and generate a plan when you confirm. Then visit
   `/calendar` to see your sessions.

## Project structure

```
app/
├── main.py              FastAPI app; lifespan starts/stops the Strava MCP subprocess
├── config.py            Settings (env vars)
├── db.py                SQLModel engine + session + get_or_create_athlete
├── models.py            Athlete, Goal, TrainingPlan, PlannedSession,
│                        StravaActivity, SetupConversation
├── mcp_client.py        Spawns and manages the Strava MCP server over stdio
├── claude_client.py     Agentic loop (MCP tools + prompt caching), setup intake
│                        chat, activity summary, goal JSON extraction
├── planner.py           Plan generation & cascading regeneration
├── routers/
│   ├── setup.py         /setup (intake chat), /setup/chat, /setup/generate,
│   │                    /setup/reset, /setup/refine, /setup/connect-strava
│   ├── calendar.py      /calendar, /calendar/events, /calendar/session/{id},
│   │                    /calendar/activity/{id}, /calendar/session/{id}/adjust
│   └── dashboard.py     /dashboard, /dashboard/chart-data, /dashboard/re-adjust
├── templates/           Jinja2 templates (FullCalendar, Leaflet, Chart.js via CDN)
└── static/              Static assets
```

## Notes

- Single local user — no login system. Strava connection state lives in the
  MCP server's config (`~/.config/strava-mcp/config.json`), not in Arete's DB.
- The SQLite database (`arete.db`) is created and migrated automatically on
  first run and is gitignored.
- GPS/HR/pace streams are fetched from Strava on first activity click and
  cached in the DB permanently — subsequent clicks are instant.
- "Load" is a relative training-stress number Claude assigns when planning;
  actual load uses Strava's relative effort score when available, falling back
  to moving time.
- Generating a plan archives any previously active plan — there is only ever
  one active `TrainingPlan` per athlete.
