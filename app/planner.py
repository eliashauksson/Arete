import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import delete as sqla_delete
from sqlmodel import Session, select

from app.claude_client import (
    expand_macro_week as _claude_expand_week,
    generate_activity_summary,
    generate_macro_plan as _claude_macro_plan,
    get_cached_athlete_context,
    run_agentic_json,
)
from app.mcp_client import StravaMCPClient
from app.models import Athlete, Goal, MacroPlan, MacroWeek, PlannedSession, StravaActivity, TrainingPlan

MAX_TOKENS_ADJUSTMENT = 4096
MAX_TOKENS_PLAN_GENERATION = 8192
STRAVA_SYNC_FRESHNESS = timedelta(hours=1)
ADJUSTMENT_WINDOW_DAYS = 13  # bounds regeneration to ~2 weeks so it always fits MAX_TOKENS_ADJUSTMENT

SPORT_COLORS = {
    "run": "#2563eb",
    "bike": "#16a34a",
    "swim": "#0891b2",
    "strength": "#9333ea",
    "brick": "#ea580c",
    "rest": "#6b7280",
    "other": "#6b7280",
}

PLAN_SYSTEM_PROMPT = (
    "You are an expert endurance training coach. You design safe, progressive "
    "training plans tailored to the athlete's current fitness, goal, and "
    "available time. You have access to tools that can read the athlete's "
    "real Strava data (profile, recent activities, heart rate zones) — use "
    "them to ground the plan in their actual fitness, but if Strava isn't "
    "connected or a tool fails, proceed sensibly using only the information "
    "you have. Always reply with ONLY the JSON object requested — no "
    "markdown formatting, no commentary before or after it."
)

SESSION_SCHEMA_NOTE = (
    "Respond with ONLY this JSON shape: "
    '{"sessions": [{'
    '"date": "YYYY-MM-DD", '
    '"sport_type": one of run/bike/swim/strength/brick/rest/other, '
    '"title": max 6 words, '
    '"description": 2-3 sentences (what to do, target pace/HR zone, why this session matters for the goal; null for rest days), '
    '"hr_zone": integer 1-5 for the primary target HR zone, or null for rest/strength, '
    '"structure": array of {\"type\": string, \"duration_min\": integer, \"note\": string (optional)} '
    'e.g. [{"type":"warmup","duration_min":10},{"type":"main","duration_min":30,"note":"zone 2 easy pace"},{"type":"cooldown","duration_min":5}] — '
    'null for rest days, '
    '"planned_duration_min": integer minutes (0 for rest), '
    '"planned_load": 0-150 relative stress (0 for rest)'
    "}]}. "
    'Include every calendar day in the range. '
    'For rest days set sport_type="rest" and description/hr_zone/structure=null, planned_duration_min=0, planned_load=0.'
)

ACTIVITY_SCHEMA_NOTE = (
    'Respond with ONLY JSON of the shape: {"activities": [{"strava_id": integer, '
    '"name": string, "sport_type": string, "start_date": "YYYY-MM-DD", '
    '"distance": meters as number, "moving_time": seconds as integer, '
    '"elapsed_time": seconds as integer, "total_elevation_gain": meters as number, '
    '"average_heartrate": number or null, "relative_effort": number or null}, ...]}. '
    "If there are no activities in range, return an empty list."
)


def _bounded_range_end(db: Session, plan: TrainingPlan, cutoff: date) -> date:
    """Caps a regeneration window to ADJUSTMENT_WINDOW_DAYS so the output always
    fits MAX_TOKENS_ADJUSTMENT, even when adjusting a session early in the plan."""
    last_date = db.exec(
        select(PlannedSession.date)
        .where(PlannedSession.plan_id == plan.id)
        .order_by(PlannedSession.date.desc())
    ).first()
    window_end = cutoff + timedelta(days=ADJUSTMENT_WINDOW_DAYS)
    return min(last_date, window_end) if last_date else window_end


def _session_to_dict(s: PlannedSession) -> dict:
    # hr_zone and structure are always freshly generated, so omit them from the
    # existing-plan context — showing null values causes Claude to preserve them.
    return {
        "date": s.date.isoformat(),
        "sport_type": s.sport_type,
        "title": s.title,
        "description": s.description,
        "planned_duration_min": s.planned_duration_min,
        "planned_load": s.planned_load,
    }


async def regenerate_sessions_from(
    mcp: StravaMCPClient,
    db: Session,
    plan: TrainingPlan,
    goal: Goal,
    cutoff_date: date,
    context_prompt: str,
    max_tokens: int,
    range_end: Optional[date] = None,
) -> list[PlannedSession]:
    """Replaces every PlannedSession in `plan` between `cutoff_date` and `end`
    (inclusive) with a freshly Claude-generated set, never touching sessions
    outside that range."""
    if range_end is not None:
        end = range_end
    else:
        last_date = db.exec(
            select(PlannedSession.date)
            .where(PlannedSession.plan_id == plan.id)
            .where(PlannedSession.date >= cutoff_date)
            .order_by(PlannedSession.date.desc())
        ).first()
        end = last_date or cutoff_date

    existing = db.exec(
        select(PlannedSession)
        .where(PlannedSession.plan_id == plan.id)
        .where(PlannedSession.date >= cutoff_date)
        .where(PlannedSession.date <= end)
        .order_by(PlannedSession.date)
    ).all()

    prompt = (
        f"{context_prompt}\n\n"
        f"Goal: {goal.race_name or 'general fitness'} "
        f"({goal.race_distance or 'distance not specified'}), "
        f"race date {goal.race_date.isoformat() if goal.race_date else 'not set'}, "
        f"target time {goal.target_time or 'not set'}. "
        f"Athlete has about {goal.weekly_hours or 'an unspecified number of'} "
        f"hours/week available. Notes: {goal.notes or 'none'}.\n\n"
        f"Sessions currently planned from {cutoff_date.isoformat()} to "
        f"{end.isoformat()} (to be replaced):\n"
        f"{json.dumps([_session_to_dict(s) for s in existing])}\n\n"
        f"Generate the replacement plan for every day from {cutoff_date.isoformat()} "
        f"through {end.isoformat()} inclusive. {SESSION_SCHEMA_NOTE}"
    )

    data = await run_agentic_json(
        mcp, prompt, system=PLAN_SYSTEM_PROMPT, effort="medium", max_tokens=max_tokens
    )
    sessions_data = data.get("sessions", [])

    db.exec(
        sqla_delete(PlannedSession)
        .where(PlannedSession.plan_id == plan.id)
        .where(PlannedSession.date >= cutoff_date)
        .where(PlannedSession.date <= end)
    )
    db.flush()

    new_sessions = []
    for item in sessions_data:
        try:
            session_date = date.fromisoformat(item["date"])
        except (KeyError, ValueError):
            continue
        raw_structure = item.get("structure")
        session = PlannedSession(
            plan_id=plan.id,
            date=session_date,
            sport_type=item.get("sport_type") or "other",
            title=item.get("title") or "Session",
            description=item.get("description"),
            hr_zone=item.get("hr_zone"),
            structure=json.dumps(raw_structure) if raw_structure else None,
            planned_duration_min=item.get("planned_duration_min"),
            planned_load=item.get("planned_load"),
        )
        db.add(session)
        new_sessions.append(session)
    db.commit()
    for s in new_sessions:
        db.refresh(s)
    return new_sessions


def _store_macro_plan(
    db: Session,
    training_plan: TrainingPlan,
    athlete,
    weeks_data: list[dict],
    season_start: date,
    season_end: date,
) -> MacroPlan:
    macro_plan = MacroPlan(
        training_plan_id=training_plan.id,
        athlete_id=athlete.id,
        season_start=season_start,
        season_end=season_end,
    )
    db.add(macro_plan)
    db.commit()
    db.refresh(macro_plan)

    for w in weeks_data:
        raw_start = w.get("start_date")
        try:
            w_start = date.fromisoformat(raw_start) if raw_start else season_start + timedelta(weeks=w.get("week_number", 1) - 1)
        except ValueError:
            w_start = season_start + timedelta(weeks=w.get("week_number", 1) - 1)
        # Normalise to the Monday of that week
        w_start = w_start - timedelta(days=w_start.weekday())

        db.add(MacroWeek(
            macro_plan_id=macro_plan.id,
            week_number=w.get("week_number", 1),
            start_date=w_start,
            phase=w.get("phase", "base"),
            sport_focus=w.get("sport_focus"),
            hours_run=float(w.get("hours_run") or 0),
            hours_bike=float(w.get("hours_bike") or 0),
            hours_swim=float(w.get("hours_swim") or 0),
            hours_strength=float(w.get("hours_strength") or 0),
            theme=w.get("theme", ""),
            is_expanded=False,
        ))
    db.commit()
    return macro_plan


async def _expand_week(
    db: Session,
    plan: TrainingPlan,
    goal: Goal,
    macro_week: MacroWeek,
) -> list[PlannedSession]:
    """Expand one MacroWeek into 7 PlannedSession records using a lightweight Haiku call."""
    goal_context = (
        f"Goal: {goal.race_name or 'general fitness'}"
        + (f" ({goal.race_distance})" if goal.race_distance else "")
        + f", race date {goal.race_date.isoformat() if goal.race_date else 'TBD'}. "
        + f"Available {goal.weekly_hours or '?'}h/week."
    )
    if goal.notes:
        goal_context += f" Notes: {goal.notes}."

    # Previous week's sessions for continuity
    prev_sessions_db = db.exec(
        select(PlannedSession)
        .where(PlannedSession.plan_id == plan.id)
        .where(PlannedSession.date >= macro_week.start_date - timedelta(days=7))
        .where(PlannedSession.date < macro_week.start_date)
        .order_by(PlannedSession.date)
    ).all()
    prev_sessions = [
        {"date": s.date.isoformat(), "sport_type": s.sport_type, "planned_duration_min": s.planned_duration_min}
        for s in prev_sessions_db
    ]

    week_dict = {
        "week_number": macro_week.week_number,
        "start_date": macro_week.start_date.isoformat(),
        "phase": macro_week.phase,
        "theme": macro_week.theme,
        "sport_focus": macro_week.sport_focus,
        "hours_run": macro_week.hours_run,
        "hours_bike": macro_week.hours_bike,
        "hours_swim": macro_week.hours_swim,
        "hours_strength": macro_week.hours_strength,
    }
    data = await _claude_expand_week(week_dict, goal_context, prev_sessions)
    sessions_data = data.get("sessions", [])

    week_end = macro_week.start_date + timedelta(days=6)
    db.exec(
        sqla_delete(PlannedSession)
        .where(PlannedSession.plan_id == plan.id)
        .where(PlannedSession.date >= macro_week.start_date)
        .where(PlannedSession.date <= week_end)
    )
    db.flush()

    new_sessions = []
    for item in sessions_data:
        try:
            session_date = date.fromisoformat(item["date"])
        except (KeyError, ValueError):
            continue
        raw_structure = item.get("structure")
        session = PlannedSession(
            plan_id=plan.id,
            date=session_date,
            sport_type=item.get("sport_type") or "other",
            title=item.get("title") or "Session",
            description=item.get("description"),
            hr_zone=item.get("hr_zone"),
            structure=json.dumps(raw_structure) if raw_structure else None,
            planned_duration_min=item.get("planned_duration_min"),
            planned_load=item.get("planned_load"),
        )
        db.add(session)
        new_sessions.append(session)

    macro_week.is_expanded = True
    db.add(macro_week)
    db.commit()
    for s in new_sessions:
        db.refresh(s)
    print(f"[planner] expanded week {macro_week.week_number} → {len(new_sessions)} sessions")
    return new_sessions


async def maybe_auto_expand(db: Session, plan: TrainingPlan, goal: Goal) -> bool:
    """Expand the next unexpanded week when fewer than 14 detailed future days remain.
    Returns True if an expansion was performed."""
    today = date.today()

    future_count = len(db.exec(
        select(PlannedSession)
        .where(PlannedSession.plan_id == plan.id)
        .where(PlannedSession.date >= today)
    ).all())

    if future_count >= 14:
        return False

    macro_plan = db.exec(
        select(MacroPlan).where(MacroPlan.training_plan_id == plan.id)
    ).first()
    if macro_plan is None:
        return False

    this_monday = today - timedelta(days=today.weekday())
    next_week = db.exec(
        select(MacroWeek)
        .where(MacroWeek.macro_plan_id == macro_plan.id)
        .where(MacroWeek.is_expanded == False)
        .where(MacroWeek.start_date >= this_monday)
        .order_by(MacroWeek.start_date)
    ).first()

    if next_week is None:
        return False

    print(f"[planner] auto-expanding week {next_week.week_number} ({future_count} detailed days remain)")
    await _expand_week(db, plan, goal, next_week)
    return True


async def generate_initial_plan(mcp: StravaMCPClient, db: Session, athlete, goal: Goal) -> TrainingPlan:
    # Archive any existing active plans
    for p in db.exec(
        select(TrainingPlan)
        .where(TrainingPlan.athlete_id == athlete.id)
        .where(TrainingPlan.status == "active")
    ).all():
        p.status = "archived"
        db.add(p)
    db.commit()

    plan = TrainingPlan(athlete_id=athlete.id, goal_id=goal.id, status="active")
    db.add(plan)
    db.commit()
    db.refresh(plan)

    today = date.today()
    season_start = today - timedelta(days=today.weekday())  # Monday of current week

    # ── Strava history sync (12 months → compact summary) ─────────────────────
    history_summary: Optional[str] = None
    try:
        history = await sync_strava_activities(
            mcp, db, athlete.id,
            today - timedelta(days=365), today - timedelta(days=1),
            force=True, max_tokens=8192, skip_summaries=True,
        )
        if history:
            history_summary = build_activity_summary(history)
            print(f"[planner] synced {len(history)} activities for history context")
    except Exception as exc:
        print(f"[planner] history sync failed: {exc}")

    # ── Resolve season end from goal data ──────────────────────────────────────
    goal_data: dict = {}
    if goal.goals_json:
        try:
            goal_data = json.loads(goal.goals_json)
        except json.JSONDecodeError:
            pass
    if not goal_data.get("goals") and (goal.race_name or goal.race_date):
        goal_data["goals"] = [{
            "race_name": goal.race_name,
            "race_date": goal.race_date.isoformat() if goal.race_date else None,
            "race_distance": goal.race_distance,
            "priority": "A",
        }]
    if goal.weekly_hours and "weekly_hours" not in goal_data:
        goal_data["weekly_hours"] = goal.weekly_hours
    if goal.sport_types and "sport_types" not in goal_data:
        try:
            goal_data["sport_types"] = json.loads(goal.sport_types)
        except (json.JSONDecodeError, TypeError):
            pass
    if goal.notes and "notes" not in goal_data:
        goal_data["notes"] = goal.notes

    goals_list = goal_data.get("goals", [])
    a_race = next((g for g in goals_list if g.get("priority") == "A"), None)
    last_race = goals_list[-1] if goals_list else None
    season_end_raw = (a_race or last_race or {}).get("race_date")
    try:
        season_end = date.fromisoformat(season_end_raw) if season_end_raw else today + timedelta(days=90)
    except ValueError:
        season_end = today + timedelta(days=90)
    if season_end <= season_start:
        season_end = season_start + timedelta(days=90)

    # ── Athlete profile (for macro context) ───────────────────────────────────
    athlete_context: Optional[str] = None
    try:
        athlete_context = await get_cached_athlete_context(mcp)
    except Exception as exc:
        print(f"[planner] athlete context failed: {exc}")

    # ── Layer 1: Generate full-season macro plan ───────────────────────────────
    macro_data = await _claude_macro_plan(
        goal_data, season_start, season_end, history_summary, athlete_context
    )
    weeks_data = macro_data.get("weeks", [])
    print(f"[planner] macro plan: {len(weeks_data)} weeks, {season_start} → {season_end}")
    _store_macro_plan(db, plan, athlete, weeks_data, season_start, season_end)

    # ── Layer 2: Expand first 3 weeks into detailed sessions ──────────────────
    macro_plan = db.exec(select(MacroPlan).where(MacroPlan.training_plan_id == plan.id)).first()
    if macro_plan:
        first_three = db.exec(
            select(MacroWeek)
            .where(MacroWeek.macro_plan_id == macro_plan.id)
            .order_by(MacroWeek.start_date)
        ).all()[:3]
        for week in first_three:
            try:
                await _expand_week(db, plan, goal, week)
            except Exception as exc:
                print(f"[planner] week {week.week_number} expansion failed: {exc}")

    return plan


async def adjust_session(mcp: StravaMCPClient, db: Session, session: PlannedSession, instruction: str) -> None:
    plan = db.get(TrainingPlan, session.plan_id)
    goal = db.get(Goal, plan.goal_id)
    context_prompt = (
        f'The athlete wants to adjust their plan starting from the session on '
        f'{session.date.isoformat()} ("{session.title}"). Their instruction: '
        f'"{instruction}". Update that session and rebalance any later '
        f"sessions in the plan as needed to sensibly account for the change."
    )
    range_end = _bounded_range_end(db, plan, session.date)
    await regenerate_sessions_from(
        mcp, db, plan, goal, session.date, context_prompt, MAX_TOKENS_ADJUSTMENT, range_end=range_end
    )


async def weekly_reonadjust(mcp: StravaMCPClient, db: Session, plan: TrainingPlan) -> None:
    goal = db.get(Goal, plan.goal_id)
    today = date.today()
    week_start = today - timedelta(days=7)
    week_end = today - timedelta(days=1)

    planned = db.exec(
        select(PlannedSession)
        .where(PlannedSession.plan_id == plan.id)
        .where(PlannedSession.date >= week_start)
        .where(PlannedSession.date <= week_end)
    ).all()
    planned_load_sum = sum(s.planned_load or 0 for s in planned)

    actuals = await sync_strava_activities(mcp, db, plan.athlete_id, week_start, week_end, force=True)
    actual_load_sum = sum(activity_load(a) for a in actuals)

    context_prompt = (
        f"Here is how last week ({week_start.isoformat()} to {week_end.isoformat()}) "
        f"went: planned total load {planned_load_sum:.0f} across {len(planned)} "
        f"sessions, actual total load {actual_load_sum:.0f} across {len(actuals)} "
        f"real Strava activities. Rebalance the remaining plan starting today "
        f"({today.isoformat()}) to account for how training actually went (back "
        f"off if they under-trained or seem fatigued, progress normally if "
        f"compliance was good)."
    )
    range_end = _bounded_range_end(db, plan, today)
    await regenerate_sessions_from(
        mcp, db, plan, goal, today, context_prompt, MAX_TOKENS_ADJUSTMENT, range_end=range_end
    )


def build_activity_summary(activities: list[StravaActivity]) -> str:
    """Compact month-by-sport summary for Claude's planning context."""
    if not activities:
        return "No activities on record."
    by_month: dict = defaultdict(lambda: defaultdict(lambda: {"n": 0, "km": 0.0, "h": 0.0}))
    for a in activities:
        key = a.start_date.strftime("%Y-%m")
        sport = (a.sport_type or "other").lower()
        by_month[key][sport]["n"] += 1
        by_month[key][sport]["km"] += (a.distance or 0) / 1000
        by_month[key][sport]["h"] += (a.moving_time or 0) / 3600
    lines = []
    for month in sorted(by_month.keys()):
        parts = [
            f"{s['n']}×{sport} {s['km']:.0f}km {s['h']:.1f}h"
            for sport, s in sorted(by_month[month].items())
        ]
        lines.append(f"{month}: {', '.join(parts)}")
    return "\n".join(lines)


async def sync_strava_activities(
    mcp: StravaMCPClient,
    db: Session,
    athlete_id: int,
    start: date,
    end: date,
    force: bool = False,
    max_tokens: int = 2048,
    skip_summaries: bool = False,
) -> list[StravaActivity]:
    if start > end:
        return []

    athlete = db.get(Athlete, athlete_id)
    now = datetime.utcnow()
    is_fresh = (
        not force
        and athlete is not None
        and athlete.last_strava_sync is not None
        and now - athlete.last_strava_sync < STRAVA_SYNC_FRESHNESS
    )

    if not is_fresh:
        print(f"[strava-sync] fetching live (force={force}, athlete_id={athlete_id})")
        prompt = (
            f"Fetch ALL of my Strava activities between {start.isoformat()} and "
            f"{end.isoformat()} inclusive. If there are many activities, paginate "
            f"(per_page=200, page=1, page=2, …) until you have retrieved all of them. "
            f"{ACTIVITY_SCHEMA_NOTE}"
        )
        data = await run_agentic_json(mcp, prompt, effort="low", max_tokens=max_tokens)

        to_summarise: list[StravaActivity] = []
        for item in data.get("activities", []):
            try:
                strava_id = int(item["strava_id"])
            except (KeyError, TypeError, ValueError):
                continue
            existing = db.exec(select(StravaActivity).where(StravaActivity.strava_id == strava_id)).first()
            is_new = existing is None
            if existing is None:
                existing = StravaActivity(
                    athlete_id=athlete_id,
                    strava_id=strava_id,
                    name="",
                    sport_type="other",
                    start_date=datetime.utcnow(),
                    distance=0,
                    moving_time=0,
                    elapsed_time=0,
                    total_elevation_gain=0,
                )
            existing.name = item.get("name") or existing.name
            existing.sport_type = item.get("sport_type") or existing.sport_type
            if item.get("start_date"):
                existing.start_date = datetime.fromisoformat(item["start_date"])
            existing.distance = float(item.get("distance") or 0)
            existing.moving_time = int(item.get("moving_time") or 0)
            existing.elapsed_time = int(item.get("elapsed_time") or 0)
            existing.total_elevation_gain = float(item.get("total_elevation_gain") or 0)
            existing.average_heartrate = item.get("average_heartrate")
            existing.relative_effort = item.get("relative_effort")
            existing.raw_json = json.dumps(item)
            db.add(existing)
            if is_new:
                to_summarise.append(existing)

        if athlete is not None:
            athlete.last_strava_sync = now
            db.add(athlete)
        db.commit()

        # Generate AI coaching summaries for newly synced activities.
        # Skipped for bulk historical imports — generated lazily on first view instead.
        if not skip_summaries:
            for act in to_summarise:
                db.refresh(act)
                try:
                    act.ai_summary = await generate_activity_summary(act)
                    db.add(act)
                except Exception as exc:
                    print(f"[claude] summary failed for strava_id={act.strava_id}: {exc}")
            if to_summarise:
                db.commit()
    else:
        print(f"[strava-sync] using cache, synced {now - athlete.last_strava_sync} ago")

    range_start = datetime.combine(start, datetime.min.time())
    range_end = datetime.combine(end + timedelta(days=1), datetime.min.time())
    return db.exec(
        select(StravaActivity)
        .where(StravaActivity.athlete_id == athlete_id)
        .where(StravaActivity.start_date >= range_start)
        .where(StravaActivity.start_date < range_end)
        .order_by(StravaActivity.start_date)
    ).all()


async def refine_plan(
    mcp: StravaMCPClient,
    db: Session,
    plan: TrainingPlan,
    instruction: str,
) -> list[PlannedSession]:
    """Apply a freeform chat instruction to the future portion of a plan."""
    goal = db.get(Goal, plan.goal_id)
    today = date.today()

    all_sessions = db.exec(
        select(PlannedSession).where(PlannedSession.plan_id == plan.id).order_by(PlannedSession.date)
    ).all()
    future = [s for s in all_sessions if s.date >= today]
    if not future:
        return []

    start, end = future[0].date, future[-1].date
    context_prompt = (
        f"Here is the current training plan ({start.isoformat()} – {end.isoformat()}):\n"
        f"{json.dumps([_session_to_dict(s) for s in future])}\n\n"
        f'The athlete says: "{instruction}"\n\n'
        f"Regenerate all sessions honouring this preference, with full coaching detail per the required schema."
    )
    return await regenerate_sessions_from(
        mcp, db, plan, goal, start, context_prompt, MAX_TOKENS_PLAN_GENERATION, range_end=end
    )


def activity_load(activity: StravaActivity) -> float:
    if activity.relative_effort is not None:
        return activity.relative_effort
    return activity.moving_time / 60
