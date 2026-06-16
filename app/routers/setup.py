from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.claude_client import connect_strava, verify_strava_connection
from app.db import get_or_create_athlete, get_session
from app.mcp_client import strava_mcp
from app.models import Athlete, Goal, PlannedSession, TrainingPlan
from app.planner import generate_initial_plan, refine_plan

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

    return RedirectResponse(url="/setup/refine", status_code=303)


@router.get("/setup/refine", response_class=HTMLResponse)
async def refine_page(request: Request, db: Session = Depends(get_session)):
    athlete = db.exec(select(Athlete)).first()
    if athlete is None:
        return RedirectResponse("/setup", status_code=303)
    plan = db.exec(
        select(TrainingPlan)
        .where(TrainingPlan.athlete_id == athlete.id)
        .where(TrainingPlan.status == "active")
    ).first()
    if plan is None:
        return RedirectResponse("/setup", status_code=303)
    sessions = db.exec(
        select(PlannedSession).where(PlannedSession.plan_id == plan.id).order_by(PlannedSession.date)
    ).all()
    return templates.TemplateResponse(request, "refine.html", {"sessions": sessions})


@router.post("/setup/refine/chat", response_class=HTMLResponse)
async def refine_chat(
    request: Request,
    instruction: str = Form(...),
    db: Session = Depends(get_session),
):
    athlete = db.exec(select(Athlete)).first()
    plan = None
    if athlete:
        plan = db.exec(
            select(TrainingPlan)
            .where(TrainingPlan.athlete_id == athlete.id)
            .where(TrainingPlan.status == "active")
        ).first()
    if plan is None:
        return HTMLResponse("<p>No active plan found. <a href='/setup'>Go to setup</a>.</p>")

    error = None
    sessions = []
    try:
        sessions = await refine_plan(strava_mcp, db, plan, instruction)
        # re-query to get the full sorted list including past sessions
        sessions = db.exec(
            select(PlannedSession).where(PlannedSession.plan_id == plan.id).order_by(PlannedSession.date)
        ).all()
    except Exception as exc:
        error = str(exc)
        sessions = db.exec(
            select(PlannedSession).where(PlannedSession.plan_id == plan.id).order_by(PlannedSession.date)
        ).all()

    return templates.TemplateResponse(
        request,
        "_refine_response.html",
        {"instruction": instruction, "sessions": sessions, "error": error},
    )
