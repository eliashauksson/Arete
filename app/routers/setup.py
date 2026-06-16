import json
from datetime import date as date_cls

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.claude_client import (
    clean_claude_message,
    connect_strava,
    extract_goal_json,
    get_cached_athlete_context,
    setup_chat_response,
    verify_strava_connection,
)
from app.db import get_or_create_athlete, get_session
from app.mcp_client import strava_mcp
from app.models import Athlete, Goal, PlannedSession, SetupConversation, TrainingPlan
from app.planner import generate_initial_plan, refine_plan

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _active_conversation(db: Session, athlete_id: int) -> SetupConversation | None:
    return db.exec(
        select(SetupConversation)
        .where(SetupConversation.athlete_id == athlete_id)
        .where(SetupConversation.status == "chatting")
        .order_by(SetupConversation.created_at.desc())
    ).first()


# ── Main chat page ─────────────────────────────────────────────────────────────

@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, db: Session = Depends(get_session)):
    athlete = db.exec(select(Athlete)).first()
    messages: list[dict] = []
    conv_id: int | None = None

    if athlete:
        conv = _active_conversation(db, athlete.id)
        if conv:
            raw = json.loads(conv.messages)
            # Strip internal markers so the history renders cleanly
            from app.claude_client import clean_claude_message
            messages = [
                {"role": m["role"], "content": clean_claude_message(m["content"]) if m["role"] == "assistant" else m["content"]}
                for m in raw
            ]
            conv_id = conv.id

    return templates.TemplateResponse(
        request, "setup.html", {"messages": messages, "conv_id": conv_id}
    )


@router.post("/setup/reset", response_class=HTMLResponse)
async def setup_reset(db: Session = Depends(get_session)):
    """Mark the current conversation done so the user starts fresh."""
    athlete = db.exec(select(Athlete)).first()
    if athlete:
        conv = _active_conversation(db, athlete.id)
        if conv:
            conv.status = "done"
            db.add(conv)
            db.commit()
    return RedirectResponse("/setup", status_code=303)


# ── Conversation turn ──────────────────────────────────────────────────────────

@router.post("/setup/chat", response_class=HTMLResponse)
async def setup_chat(
    request: Request,
    message: str = Form(...),
    db: Session = Depends(get_session),
):
    athlete = get_or_create_athlete(db)

    conv = _active_conversation(db, athlete.id)
    if conv is None:
        conv = SetupConversation(athlete_id=athlete.id)
        db.add(conv)
        db.commit()
        db.refresh(conv)

    messages: list[dict] = json.loads(conv.messages)

    # Fetch Strava context silently on the first user turn
    if conv.strava_context is None and len(messages) == 0:
        try:
            conv.strava_context = await get_cached_athlete_context(strava_mcp)
        except Exception as exc:
            print(f"[setup-intake] Strava context failed: {exc}")

    messages.append({"role": "user", "content": message})

    try:
        raw_response = await setup_chat_response(messages, conv.strava_context)
    except Exception as exc:
        raw_response = f"Sorry, something went wrong. Please try again. ({exc})"

    plan_confirmed = "PLAN_CONFIRMED" in raw_response
    if plan_confirmed:
        goal_data = extract_goal_json(raw_response)
        if goal_data:
            conv.goal_json = json.dumps(goal_data)

    display_text = clean_claude_message(raw_response)

    # Store raw response (with JSON markers) so future turns have full context
    messages.append({"role": "assistant", "content": raw_response})
    conv.messages = json.dumps(messages)
    db.add(conv)
    db.commit()

    return templates.TemplateResponse(
        request,
        "_chat_bubble.html",
        {
            "user_message": message,
            "claude_message": display_text,
            "plan_confirmed": plan_confirmed and conv.goal_json is not None,
        },
    )


# ── Plan generation ────────────────────────────────────────────────────────────

@router.post("/setup/generate", response_class=HTMLResponse)
async def setup_generate(request: Request, db: Session = Depends(get_session)):
    athlete = db.exec(select(Athlete)).first()
    if athlete is None:
        return HTMLResponse("<p>No athlete record found.</p>", status_code=404)

    conv = _active_conversation(db, athlete.id)
    if conv is None or conv.goal_json is None:
        return HTMLResponse(
            "<p>No confirmed plan data found — please finish the intake conversation first.</p>",
            status_code=400,
        )

    try:
        goal_data: dict = json.loads(conv.goal_json)
    except json.JSONDecodeError:
        return HTMLResponse("<p>Goal data is malformed. Please restart the conversation.</p>", status_code=400)

    # Primary goal: first A-priority race, or the first race if none marked A
    goals_list: list[dict] = goal_data.get("goals", [])
    primary = next((g for g in goals_list if g.get("priority") == "A"), None) or (goals_list[0] if goals_list else {})

    raw_date = primary.get("race_date")
    goal = Goal(
        athlete_id=athlete.id,
        race_name=primary.get("race_name") or "Training Plan",
        race_date=date_cls.fromisoformat(raw_date) if raw_date else None,
        race_distance=primary.get("race_distance"),
        weekly_hours=goal_data.get("weekly_hours"),
        notes=goal_data.get("notes"),
        sport_types=json.dumps(goal_data.get("sport_types", [])),
        goals_json=conv.goal_json,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)

    error = None
    try:
        await generate_initial_plan(strava_mcp, db, athlete, goal)
    except Exception as exc:
        error = str(exc)

    conv.status = "done"
    db.add(conv)
    db.commit()

    if error:
        return templates.TemplateResponse(request, "_plan_generated.html", {"error": error})

    # Success: tell HTMX to navigate to the calendar.
    resp = Response(content="", media_type="text/html")
    resp.headers["HX-Redirect"] = "/calendar"
    return resp


# ── Refine (post-generation chat adjustment) ───────────────────────────────────

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
        return HTMLResponse("<p>No active plan. <a href='/setup'>Go to setup</a>.</p>")

    error = None
    sessions = []
    try:
        sessions = await refine_plan(strava_mcp, db, plan, instruction)
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


# ── Strava integration (kept for direct use from setup page) ───────────────────

@router.post("/setup/connect-strava", response_class=HTMLResponse)
async def connect_strava_route():
    result = await connect_strava(strava_mcp)
    return result


@router.post("/setup/verify-connection", response_class=HTMLResponse)
async def verify_connection_route():
    result = await verify_strava_connection(strava_mcp)
    return result
