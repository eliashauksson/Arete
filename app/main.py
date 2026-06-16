import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.db import create_db_and_tables, engine, migrate_db
from app.mcp_client import strava_mcp
from app.models import Athlete, TrainingPlan
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
        if athlete:
            plan = db.exec(
                select(TrainingPlan)
                .where(TrainingPlan.athlete_id == athlete.id)
                .where(TrainingPlan.status == "active")
            ).first()
            has_plan = plan is not None
    request.state.has_plan = has_plan
    return await call_next(request)


@app.get("/")
async def root():
    return RedirectResponse(url="/setup")
