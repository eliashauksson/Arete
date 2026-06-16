import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.db import create_db_and_tables
from app.mcp_client import strava_mcp
from app.routers import calendar, dashboard, setup

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
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


@app.get("/")
async def root():
    return RedirectResponse(url="/setup")
