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

This is the current build phase: project scaffolding, the data models, and
a working Claude ↔ Strava-MCP connection. Plan generation and the real
dashboard/calendar UI (HTMX, FullCalendar, Chart.js) are not built yet —
`/dashboard` and `/calendar` are placeholder pages for now.

## Pages

- **`/setup`** — connect Strava (via the MCP server's own browser-based
  OAuth flow) and verify that Claude can reach your Strava data.
- **`/dashboard`** — planned vs. actual training load (placeholder).
- **`/calendar`** — planned sessions and Strava activities overlaid
  (placeholder).

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

## Project structure

```
app/
├── main.py            FastAPI app; lifespan starts/stops the Strava MCP subprocess
├── config.py           Settings (env vars)
├── db.py                SQLModel engine + session
├── models.py             Athlete, Goal, TrainingPlan, PlannedSession, StravaActivity
├── mcp_client.py          Spawns and manages the Strava MCP server over stdio
├── claude_client.py        Bridges the live MCP tools into Claude via the tool runner
├── routers/
│   ├── setup.py             /setup, /setup/connect-strava, /setup/verify-connection
│   ├── dashboard.py          /dashboard (placeholder)
│   └── calendar.py           /calendar (placeholder)
├── templates/             Jinja2 templates
└── static/                  Static assets (placeholder)
```

## Notes

- This is built for a single local user — there's no login system. Strava
  connection state lives in the MCP server's own config file
  (`~/.config/strava-mcp/config.json`), not in Arete's database.
- The SQLite database (`arete.db`) is created automatically on first run
  and is gitignored.
