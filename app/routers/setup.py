from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.claude_client import connect_strava, verify_strava_connection
from app.db import get_or_create_athlete, get_session
from app.mcp_client import strava_mcp
from app.models import Athlete, Goal
from app.planner import generate_initial_plan

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, db: Session = Depends(get_session)):
    athlete = db.exec(select(Athlete)).first()
    goal = None
    if athlete is not None:
        goal = db.exec(
            select(Goal).where(Goal.athlete_id == athlete.id).order_by(Goal.created_at.desc())
        ).first()
    return templates.TemplateResponse(request, "setup.html", {"goal": goal, "error": None})


@router.post("/setup/connect-strava", response_class=HTMLResponse)
async def connect_strava_route():
    result = await connect_strava(strava_mcp)
    return result


@router.post("/setup/verify-connection", response_class=HTMLResponse)
async def verify_connection_route():
    result = await verify_strava_connection(strava_mcp)
    return result


@router.post("/setup/generate-plan")
async def generate_plan_route(
    request: Request,
    race_name: str = Form(""),
    race_date: Optional[str] = Form(None),
    race_distance: str = Form(""),
    weekly_hours: Optional[float] = Form(None),
    notes: str = Form(""),
    db: Session = Depends(get_session),
):
    athlete = get_or_create_athlete(db)
    goal = Goal(
        athlete_id=athlete.id,
        race_name=race_name or None,
        race_date=date.fromisoformat(race_date) if race_date else None,
        race_distance=race_distance or None,
        weekly_hours=weekly_hours,
        notes=notes or None,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)

    try:
        await generate_initial_plan(strava_mcp, db, athlete, goal)
    except Exception as exc:
        return templates.TemplateResponse(
            request,
            "setup.html",
            {"goal": goal, "error": f"Plan generation failed: {exc}"},
        )

    return RedirectResponse(url="/calendar", status_code=303)
