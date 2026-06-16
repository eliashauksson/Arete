import json
from datetime import date, datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from app.claude_client import run_agentic_json
from app.mcp_client import StravaMCPClient
from app.models import Athlete, Goal, PlannedSession, StravaActivity, TrainingPlan

MAX_TOKENS_ADJUSTMENT = 1000
MAX_TOKENS_PLAN_GENERATION = 2000
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
    'Respond with ONLY JSON of the shape: {"sessions": [{"date": "YYYY-MM-DD", '
    '"sport_type": one of "run"/"bike"/"swim"/"strength"/"brick"/"rest"/"other", '
    '"title": short string (max 6 words), "description": max 15 words, '
    '"planned_duration_min": integer minutes, "planned_load": number '
    "(your own relative training-stress estimate, roughly 0-150 where an easy "
    "30 min run is ~30 and a hard 90 min long run is ~120)}, ...]}. Be concise — "
    "every word costs tokens. "
    'Include every day in the requested range, using sport_type "rest" for '
    "rest days (with planned_duration_min 0 and planned_load 0)."
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

    for s in existing:
        db.delete(s)
    db.flush()

    new_sessions = []
    for item in sessions_data:
        try:
            session_date = date.fromisoformat(item["date"])
        except (KeyError, ValueError):
            continue
        session = PlannedSession(
            plan_id=plan.id,
            date=session_date,
            sport_type=item.get("sport_type") or "other",
            title=item.get("title") or "Session",
            description=item.get("description"),
            planned_duration_min=item.get("planned_duration_min"),
            planned_load=item.get("planned_load"),
        )
        db.add(session)
        new_sessions.append(session)
    db.commit()
    for s in new_sessions:
        db.refresh(s)
    return new_sessions


async def generate_initial_plan(mcp: StravaMCPClient, db: Session, athlete, goal: Goal) -> TrainingPlan:
    existing_active = db.exec(
        select(TrainingPlan)
        .where(TrainingPlan.athlete_id == athlete.id)
        .where(TrainingPlan.status == "active")
    ).all()
    for p in existing_active:
        p.status = "archived"
        db.add(p)
    db.commit()

    plan = TrainingPlan(athlete_id=athlete.id, goal_id=goal.id, status="active")
    db.add(plan)
    db.commit()
    db.refresh(plan)

    start = date.today()
    end = start + timedelta(days=27)
    context_prompt = (
        "Before designing the plan, use the Strava tools to fetch the athlete's "
        "profile, recent activities (last several weeks), and heart rate zones "
        "so the plan reflects their real current fitness. Then design a "
        "progressive 4-week training plan."
    )
    await regenerate_sessions_from(
        mcp, db, plan, goal, start, context_prompt, MAX_TOKENS_PLAN_GENERATION, range_end=end
    )
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


async def sync_strava_activities(
    mcp: StravaMCPClient,
    db: Session,
    athlete_id: int,
    start: date,
    end: date,
    force: bool = False,
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
            f"Fetch my Strava activities between {start.isoformat()} and "
            f"{end.isoformat()} inclusive. {ACTIVITY_SCHEMA_NOTE}"
        )
        data = await run_agentic_json(mcp, prompt, effort="low")

        for item in data.get("activities", []):
            try:
                strava_id = int(item["strava_id"])
            except (KeyError, TypeError, ValueError):
                continue
            existing = db.exec(select(StravaActivity).where(StravaActivity.strava_id == strava_id)).first()
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

        if athlete is not None:
            athlete.last_strava_sync = now
            db.add(athlete)
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
        f"Adjust the plan to honour their preference. Keep unchanged sessions as-is."
    )
    return await regenerate_sessions_from(
        mcp, db, plan, goal, start, context_prompt, MAX_TOKENS_PLAN_GENERATION, range_end=end
    )


def activity_load(activity: StravaActivity) -> float:
    if activity.relative_effort is not None:
        return activity.relative_effort
    return activity.moving_time / 60
