import logging
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.db import create_db_and_tables, engine, migrate_db
from app.mcp_client import strava_mcp
from app.models import Athlete, Goal, TrainingPlan
from app.routers import calendar, dashboard, setup

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    migrate_db()
    try:
        await strava_mcp.start()
    except Exception:
        logger.exception("Failed to start the Strava MCP server subprocess")
    yield
    await strava_mcp.stop()


app = FastAPI(title="Arete", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(setup.router)
app.include_router(dashboard.router)
app.include_router(calendar.router)


@app.middleware("http")
async def inject_plan_state(request: Request, call_next):
    with Session(engine) as db:
        athlete = db.exec(select(Athlete)).first()
        has_plan = False
        days_to_race = None
        race_name_short = None
        athlete_initials = "A"

        if athlete:
            plan = db.exec(
                select(TrainingPlan)
                .where(TrainingPlan.athlete_id == athlete.id)
                .where(TrainingPlan.status == "active")
            ).first()
            has_plan = plan is not None

            if has_plan and plan:
                goal = db.get(Goal, plan.goal_id)
                if goal and goal.race_date:
                    days_to_race = (goal.race_date - date.today()).days
                    race_name_short = (goal.race_name or "Race")[:14].upper()

            if athlete.display_name:
                parts = athlete.display_name.split()
                first = parts[0][0] if parts else "A"
                last = parts[-1][0] if len(parts) > 1 else ""
                athlete_initials = (first + last).upper()

    request.state.has_plan = has_plan
    request.state.days_to_race = days_to_race
    request.state.race_name_short = race_name_short
    request.state.athlete_initials = athlete_initials
    return await call_next(request)


@app.get("/")
async def root():
    return RedirectResponse(url="/setup")
