import json
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import get_session
from app.mcp_client import strava_mcp
from app.models import Athlete, PlannedSession, TrainingPlan
from app.planner import activity_load, sync_strava_activities, weekly_reonadjust

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _get_active_plan(db: Session) -> Optional[TrainingPlan]:
    athlete = db.exec(select(Athlete)).first()
    if athlete is None:
        return None
    return db.exec(
        select(TrainingPlan)
        .where(TrainingPlan.athlete_id == athlete.id)
        .where(TrainingPlan.status == "active")
    ).first()


async def _weekly_breakdown(db: Session) -> list[dict]:
    plan = _get_active_plan(db)
    if plan is None:
        return []

    sessions = db.exec(
        select(PlannedSession).where(PlannedSession.plan_id == plan.id).order_by(PlannedSession.date)
    ).all()
    if not sessions:
        return []

    range_start = sessions[0].date
    chart_end = sessions[-1].date
    fetch_end = min(chart_end, date.today())

    activities = []
    if fetch_end >= range_start:
        try:
            activities = await sync_strava_activities(strava_mcp, db, plan.athlete_id, range_start, fetch_end)
        except Exception:
            activities = []

    planned_by_week: dict = defaultdict(float)
    for s in sessions:
        planned_by_week[_week_start(s.date)] += s.planned_load or 0

    actual_by_week: dict = defaultdict(float)
    for a in activities:
        actual_by_week[_week_start(a.start_date.date())] += activity_load(a)

    weeks = []
    cursor = _week_start(range_start)
    final = _week_start(chart_end)
    while cursor <= final:
        planned = planned_by_week.get(cursor, 0)
        actual = actual_by_week.get(cursor, 0)
        compliance = round(actual / planned * 100) if planned > 0 else None
        weeks.append(
            {
                "week_start": cursor.isoformat(),
                "planned_load": round(planned, 1),
                "actual_load": round(actual, 1),
                "compliance": compliance,
            }
        )
        cursor += timedelta(days=7)
    return weeks


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_session)):
    if _get_active_plan(db) is None:
        return RedirectResponse("/setup", status_code=303)
    weeks = await _weekly_breakdown(db)
    return templates.TemplateResponse(
        request, "dashboard.html", {"weeks": weeks, "weeks_json": json.dumps(weeks)}
    )


@router.post("/dashboard/re-adjust")
async def dashboard_re_adjust(db: Session = Depends(get_session)):
    plan = _get_active_plan(db)
    if plan is not None:
        await weekly_reonadjust(strava_mcp, db, plan)
    return RedirectResponse(url="/dashboard", status_code=303)
