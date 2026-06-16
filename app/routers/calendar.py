from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.mcp_client import strava_mcp
from app.models import Athlete, PlannedSession, StravaActivity, TrainingPlan
from app.planner import SPORT_COLORS, adjust_session, sync_strava_activities

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _parse_fc_date(value: str) -> date:
    """FullCalendar sends ISO datetime strings (possibly with a trailing Z)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request):
    return templates.TemplateResponse(request, "calendar.html", {})


@router.get("/calendar/events")
async def calendar_events(start: str, end: str, db: Session = Depends(get_session)):
    start_date = _parse_fc_date(start)
    end_date = _parse_fc_date(end)  # FullCalendar's `end` is exclusive

    athlete = db.exec(select(Athlete)).first()
    active_plan = None
    if athlete:
        active_plan = db.exec(
            select(TrainingPlan)
            .where(TrainingPlan.athlete_id == athlete.id)
            .where(TrainingPlan.status == "active")
        ).first()

    planned = []
    if active_plan:
        planned = db.exec(
            select(PlannedSession)
            .where(PlannedSession.plan_id == active_plan.id)
            .where(PlannedSession.date >= start_date)
            .where(PlannedSession.date < end_date)
            .order_by(PlannedSession.date)
        ).all()

    events = []
    for s in planned:
        color = SPORT_COLORS.get(s.sport_type, SPORT_COLORS["other"])
        events.append(
            {
                "id": f"planned-{s.id}",
                "title": s.title,
                "start": s.date.isoformat(),
                "allDay": True,
                "color": color,
                "classNames": ["planned"],
                "extendedProps": {"sessionId": s.id, "kind": "planned"},
            }
        )

    athlete = db.exec(select(Athlete)).first()
    if athlete is not None and end_date > start_date:
        try:
            activities = await sync_strava_activities(
                strava_mcp, db, athlete.id, start_date, end_date - timedelta(days=1)
            )
        except Exception:
            range_start = datetime.combine(start_date, datetime.min.time())
            range_end = datetime.combine(end_date, datetime.min.time())
            activities = db.exec(
                select(StravaActivity)
                .where(StravaActivity.athlete_id == athlete.id)
                .where(StravaActivity.start_date >= range_start)
                .where(StravaActivity.start_date < range_end)
            ).all()
        for a in activities:
            sport_key = (a.sport_type or "other").lower()
            color = SPORT_COLORS.get(sport_key, SPORT_COLORS["other"])
            events.append(
                {
                    "id": f"actual-{a.id}",
                    "title": f"✓ {a.name}",
                    "start": a.start_date.date().isoformat(),
                    "allDay": True,
                    "color": color,
                    "classNames": ["actual"],
                    "extendedProps": {"activityId": a.id, "kind": "actual"},
                }
            )

    return events


@router.get("/calendar/session/{session_id}", response_class=HTMLResponse)
async def session_detail(request: Request, session_id: int, db: Session = Depends(get_session)):
    session_obj = db.get(PlannedSession, session_id)
    if session_obj is None:
        return HTMLResponse("<p>Session not found.</p>", status_code=404)
    return templates.TemplateResponse(request, "_session_detail.html", {"session": session_obj})


class AdjustRequest(BaseModel):
    instruction: str


@router.post("/calendar/session/{session_id}/adjust")
async def adjust_session_route(session_id: int, body: AdjustRequest, db: Session = Depends(get_session)):
    session_obj = db.get(PlannedSession, session_id)
    if session_obj is None:
        return JSONResponse({"ok": False, "error": "Session not found"}, status_code=404)
    try:
        await adjust_session(strava_mcp, db, session_obj, body.instruction)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)
    return {"ok": True}
