import json
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.claude_client import generate_activity_summary, mcp_result_to_text
from app.db import get_session
from app.mcp_client import strava_mcp
from app.models import Athlete, Goal, MacroPlan, MacroWeek, PlannedSession, StravaActivity, TrainingPlan
from app.planner import SPORT_COLORS, _expand_week, adjust_session, maybe_auto_expand, sync_strava_activities

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _parse_fc_date(value: str) -> date:
    """FullCalendar sends ISO datetime strings (possibly with a trailing Z)."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


@router.get("/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request, db: Session = Depends(get_session)):
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
    goal = db.get(Goal, plan.goal_id)
    if goal:
        try:
            await maybe_auto_expand(db, plan, goal)
        except Exception as exc:
            print(f"[calendar] auto-expand failed: {exc}")

    # Phase tag and week strip data (DB only, no Strava call)
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    phase_tag = None
    week_theme = ""
    week_total_sessions = 0
    week_planned_load = 0

    macro_plan = db.exec(select(MacroPlan).where(MacroPlan.training_plan_id == plan.id)).first()
    if macro_plan:
        current_week = db.exec(
            select(MacroWeek)
            .where(MacroWeek.macro_plan_id == macro_plan.id)
            .where(MacroWeek.start_date <= today)
            .order_by(MacroWeek.start_date.desc())
        ).first()
        if current_week:
            total_weeks = db.exec(
                select(func.count(MacroWeek.id)).where(MacroWeek.macro_plan_id == macro_plan.id)
            ).one()
            phase_tag = f"{current_week.phase.title()} Phase — Week {current_week.week_number} / {total_weeks}"
            week_theme = current_week.theme

    week_end = this_monday + timedelta(days=6)
    week_sessions = db.exec(
        select(PlannedSession)
        .where(PlannedSession.plan_id == plan.id)
        .where(PlannedSession.date >= this_monday)
        .where(PlannedSession.date <= week_end)
        .where(PlannedSession.sport_type != "rest")
    ).all()
    week_total_sessions = len(week_sessions)
    week_planned_load = round(sum(s.planned_load or 0 for s in week_sessions))

    import calendar as _cal
    month_label = today.strftime("%B %Y")

    return templates.TemplateResponse(request, "calendar.html", {
        "phase_tag": phase_tag,
        "month_label": month_label,
        "week_theme": week_theme,
        "week_total_sessions": week_total_sessions,
        "week_planned_load": week_planned_load,
    })


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
                "classNames": ["planned", f"sport-{s.sport_type}"],
                "extendedProps": {"sessionId": s.id, "kind": "planned"},
            }
        )

    # ── Macro week summary events for unexpanded future weeks ─────────────────
    if active_plan:
        macro_plan = db.exec(
            select(MacroPlan).where(MacroPlan.training_plan_id == active_plan.id)
        ).first()
        if macro_plan:
            today = date.today()
            # Overlap condition: week_start < end_date AND week_start >= start_date-6
            overlap_start = start_date - timedelta(days=6)
            unexpanded = db.exec(
                select(MacroWeek)
                .where(MacroWeek.macro_plan_id == macro_plan.id)
                .where(MacroWeek.is_expanded == False)
                .where(MacroWeek.start_date >= overlap_start)
                .where(MacroWeek.start_date < end_date)
                .where(MacroWeek.start_date >= today)
                .order_by(MacroWeek.start_date)
            ).all()
            for week in unexpanded:
                load_parts = []
                if week.hours_run:     load_parts.append(f"{week.hours_run:.0f}h run")
                if week.hours_bike:    load_parts.append(f"{week.hours_bike:.0f}h bike")
                if week.hours_swim:    load_parts.append(f"{week.hours_swim:.0f}h swim")
                if week.hours_strength: load_parts.append(f"{week.hours_strength:.0f}h str")
                load_str = " · ".join(load_parts) or "rest"
                events.append({
                    "id": f"macro-{week.id}",
                    "title": f"W{week.week_number} {week.phase.title()} — {load_str}",
                    "start": week.start_date.isoformat(),
                    "end": (week.start_date + timedelta(days=7)).isoformat(),
                    "allDay": True,
                    "classNames": ["macro-week", f"macro-{week.phase}"],
                    "extendedProps": {
                        "weekId": week.id,
                        "weekNum": week.week_number,
                        "kind": "macro",
                        "phase": week.phase,
                        "theme": week.theme,
                        "hoursRun": week.hours_run,
                        "hoursBike": week.hours_bike,
                        "hoursSwim": week.hours_swim,
                        "hoursStrength": week.hours_strength,
                    },
                })

    # ── Race events ───────────────────────────────────────────────────────────
    if active_plan:
        goal = db.get(Goal, active_plan.goal_id)
        if goal:
            races = []
            if goal.goals_json:
                try:
                    gdata = json.loads(goal.goals_json)
                    races = gdata.get("goals", [])
                except (json.JSONDecodeError, TypeError):
                    pass
            if not races and goal.race_name and goal.race_date:
                races = [{"race_name": goal.race_name, "race_date": goal.race_date.isoformat(), "race_distance": goal.race_distance, "priority": "A"}]
            for race in races:
                raw_rdate = race.get("race_date")
                if not raw_rdate:
                    continue
                try:
                    rdate = date.fromisoformat(str(raw_rdate))
                except (ValueError, TypeError):
                    continue
                if rdate < start_date or rdate >= end_date:
                    continue
                priority = (race.get("priority") or "A").upper()
                name = race.get("race_name") or "Race"
                distance = race.get("race_distance") or ""
                events.append({
                    "id": f"race-{name}-{rdate.isoformat()}",
                    "title": f"🏁 {name}",
                    "start": rdate.isoformat(),
                    "allDay": True,
                    "color": "#E6A817",
                    "classNames": ["race", f"race-{priority.lower()}"],
                    "extendedProps": {
                        "kind": "race",
                        "raceName": name,
                        "raceDate": rdate.isoformat(),
                        "raceDistance": distance,
                        "racePriority": priority,
                    },
                })

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


@router.post("/calendar/week/{macro_week_id}/expand")
async def expand_week_route(macro_week_id: int, db: Session = Depends(get_session)):
    """Expand a MacroWeek into daily PlannedSession records on user request."""
    macro_week = db.get(MacroWeek, macro_week_id)
    if macro_week is None:
        return JSONResponse({"ok": False, "error": "Week not found"}, status_code=404)
    if macro_week.is_expanded:
        return {"ok": True, "already_expanded": True}
    macro_plan = db.get(MacroPlan, macro_week.macro_plan_id)
    if macro_plan is None:
        return JSONResponse({"ok": False, "error": "Macro plan not found"}, status_code=404)
    plan = db.get(TrainingPlan, macro_plan.training_plan_id)
    goal = db.get(Goal, plan.goal_id)
    try:
        sessions = await _expand_week(db, plan, goal, macro_week)
        return {"ok": True, "sessions_count": len(sessions)}
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)


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
