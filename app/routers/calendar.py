import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import Session, select

from app.claude_client import generate_activity_summary, mcp_result_to_text
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
    structure = []
    if session_obj.structure:
        try:
            structure = json.loads(session_obj.structure)
        except (json.JSONDecodeError, TypeError):
            structure = []
    return templates.TemplateResponse(
        request, "_session_detail.html", {"session": session_obj, "structure": structure}
    )


@router.get("/calendar/activity/{activity_id}", response_class=HTMLResponse)
async def activity_detail(request: Request, activity_id: int, db: Session = Depends(get_session)):
    activity = db.get(StravaActivity, activity_id)
    if activity is None:
        return HTMLResponse("<p>Activity not found.</p>", status_code=404)

    changed = False

    # Lazy-fetch GPS and HR/pace streams on first view; cache in DB forever.
    if activity.gpx_data is None:
        try:
            result = await strava_mcp.call_tool(
                "get-activity-streams",
                {"id": activity.strava_id, "types": ["time", "latlng", "heartrate", "velocity_smooth"], "resolution": "low"},
            )
            stream = json.loads(mcp_result_to_text(result))
            data = stream.get("data", {})

            activity.gpx_data = json.dumps(data["latlng"]) if data.get("latlng") else "[]"

            if data.get("heartrate") and data.get("time"):
                activity.hr_data = json.dumps({"times": data["time"], "values": data["heartrate"]})

            if data.get("velocity_smooth") and data.get("time"):
                vel = data["velocity_smooth"]
                pace = [round(1000 / (v * 60), 2) if v and v > 0.5 else None for v in vel]
                activity.pace_data = json.dumps({"times": data["time"], "values": pace})

            changed = True
        except Exception as exc:
            print(f"[strava] stream fetch failed for strava_id={activity.strava_id}: {exc}")

    # Generate AI summary on first view if sync didn't already do it.
    if activity.ai_summary is None:
        try:
            activity.ai_summary = await generate_activity_summary(activity)
            changed = True
        except Exception as exc:
            print(f"[claude] on-demand summary failed for strava_id={activity.strava_id}: {exc}")

    if changed:
        db.add(activity)
        db.commit()
        db.refresh(activity)

    # Pre-serialise to JSON strings so the template can use | safe without tojson filter.
    gpx_coords_json = None
    if activity.gpx_data:
        coords = json.loads(activity.gpx_data)
        gpx_coords_json = json.dumps(coords) if coords else None

    hr_times_json = hr_values_json = None
    if activity.hr_data:
        s = json.loads(activity.hr_data)
        if s.get("values"):
            hr_times_json = json.dumps(s["times"])
            hr_values_json = json.dumps(s["values"])

    pace_times_json = pace_values_json = None
    if activity.pace_data:
        s = json.loads(activity.pace_data)
        if s.get("values"):
            pace_times_json = json.dumps(s["times"])
            pace_values_json = json.dumps(s["values"])

    return templates.TemplateResponse(
        request,
        "_activity_detail.html",
        {
            "activity": activity,
            "gpx_coords_json": gpx_coords_json,
            "hr_times_json": hr_times_json,
            "hr_values_json": hr_values_json,
            "pace_times_json": pace_times_json,
            "pace_values_json": pace_values_json,
        },
    )


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
