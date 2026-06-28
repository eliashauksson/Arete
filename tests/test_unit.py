"""
Layer-1 unit tests: pure functions and DB helpers.
Nothing here calls Claude or Strava.
"""
import json
import pytest
from datetime import date, datetime, timedelta

from sqlmodel import Session, SQLModel, create_engine


# ── In-memory DB fixture ──────────────────────────────────────────────────────

@pytest.fixture(name="db")
def db_fixture():
    from app import models  # noqa: registers all SQLModel table metadata
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ── extract_json ──────────────────────────────────────────────────────────────

from app.claude_client import extract_json


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_markdown_json_block():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_markdown_plain_block():
    assert extract_json('```\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_embedded_in_text():
    # Fallback: finds the first { … } pair when JSON is buried in prose
    assert extract_json('Here it is: {"a": 1} done.') == {"a": 1}


def test_extract_json_nested():
    data = {"weeks": [{"n": 1, "sports": ["run", "bike"]}]}
    assert extract_json(json.dumps(data)) == data


def test_extract_json_invalid_raises():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        extract_json("not json at all")


def test_extract_json_empty_raises():
    with pytest.raises((json.JSONDecodeError, ValueError)):
        extract_json("")


def test_extract_json_array_returns_list():
    # Claude occasionally returns a bare array instead of an object.
    # extract_json passes it through — callers must guard with isinstance or .get().
    result = extract_json('[{"date": "2026-07-01"}]')
    assert isinstance(result, list)
    assert result[0]["date"] == "2026-07-01"


# ── extract_goal_json ─────────────────────────────────────────────────────────

from app.claude_client import extract_goal_json


def test_extract_goal_json_valid():
    payload = {"goals": [{"race_name": "Marathon"}], "weekly_hours": 8.0}
    text = f"<GOAL_JSON>\n{json.dumps(payload)}\n</GOAL_JSON>\nPLAN_CONFIRMED"
    assert extract_goal_json(text) == payload


def test_extract_goal_json_no_tags_returns_none():
    assert extract_goal_json("Just some chat text") is None


def test_extract_goal_json_invalid_json_in_tags_returns_none():
    assert extract_goal_json("<GOAL_JSON>not valid json</GOAL_JSON>") is None


def test_extract_goal_json_handles_whitespace_around_json():
    payload = {"goals": [], "weekly_hours": 5.0}
    text = f"<GOAL_JSON>   {json.dumps(payload)}   </GOAL_JSON>"
    assert extract_goal_json(text) == payload


def test_extract_goal_json_multiline_json():
    payload = {"goals": [{"race_name": "Tri", "race_date": "2027-06-01"}]}
    text = "<GOAL_JSON>\n" + json.dumps(payload, indent=2) + "\n</GOAL_JSON>"
    assert extract_goal_json(text) == payload


def test_extract_goal_json_empty_tags_returns_none():
    assert extract_goal_json("<GOAL_JSON></GOAL_JSON>") is None


# ── clean_claude_message ──────────────────────────────────────────────────────

from app.claude_client import clean_claude_message


def test_clean_strips_goal_json_block():
    text = "Great news!\n<GOAL_JSON>{\"a\":1}</GOAL_JSON>\nPLAN_CONFIRMED"
    result = clean_claude_message(text)
    assert "<GOAL_JSON>" not in result
    assert "PLAN_CONFIRMED" not in result
    assert "Great news!" in result


def test_clean_strips_plan_confirmed():
    result = clean_claude_message("Here is your plan. PLAN_CONFIRMED")
    assert "PLAN_CONFIRMED" not in result
    assert "Here is your plan." in result


def test_clean_no_markers_unchanged():
    text = "Just a normal response."
    assert clean_claude_message(text) == text


def test_clean_preserves_text_around_goal_json():
    text = "Before.\n<GOAL_JSON>{\"x\":1}</GOAL_JSON>\nAfter."
    result = clean_claude_message(text)
    assert "Before." in result
    assert "After." in result
    assert "<GOAL_JSON>" not in result


def test_clean_strips_surrounding_whitespace():
    assert clean_claude_message("  Hello.  ") == "Hello."


def test_clean_multiline_goal_json_block():
    text = "Start.\n<GOAL_JSON>\n{\n  \"a\": 1\n}\n</GOAL_JSON>\nEnd."
    result = clean_claude_message(text)
    assert "<GOAL_JSON>" not in result
    assert "Start." in result
    assert "End." in result


def test_clean_goal_json_with_no_surrounding_whitespace():
    # Block touching adjacent text with no spaces — regex should still strip cleanly
    result = clean_claude_message("Great!<GOAL_JSON>{\"a\":1}</GOAL_JSON>Let's go.")
    assert "<GOAL_JSON>" not in result
    assert "Great!" in result
    assert "Let's go." in result


def test_clean_multiple_goal_json_blocks():
    # re.sub with DOTALL strips all occurrences
    text = "<GOAL_JSON>{\"a\":1}</GOAL_JSON>middle<GOAL_JSON>{\"b\":2}</GOAL_JSON>"
    result = clean_claude_message(text)
    assert "<GOAL_JSON>" not in result
    assert "middle" in result


# ── load_knowledge ────────────────────────────────────────────────────────────

from app.knowledge import load_knowledge


def test_load_knowledge_empty_list_returns_core_only():
    result = load_knowledge([])
    assert len(result) > 100  # core file has real content


def test_load_knowledge_unknown_sport_same_as_empty():
    assert load_knowledge(["unicycling"]) == load_knowledge([])


def test_load_knowledge_known_sport_adds_content():
    core_only = load_knowledge([])
    assert len(load_knowledge(["run"])) > len(core_only)
    assert len(load_knowledge(["bike"])) > len(core_only)
    assert len(load_knowledge(["swim"])) > len(core_only)
    assert len(load_knowledge(["trail_run"])) > len(core_only)


def test_load_knowledge_trail_alias_matches_trail_run():
    assert load_knowledge(["trail"]) == load_knowledge(["trail_run"])


def test_load_knowledge_triathlon_keyword():
    core_only = load_knowledge([])
    result = load_knowledge(["triathlon"])
    assert len(result) > len(core_only)


def test_load_knowledge_run_bike_swim_combo_uses_triathlon_file():
    # The multisport combo ["run","bike","swim"] should load the same
    # triathlon.md as the ["triathlon"] keyword, not three separate files.
    assert load_knowledge(["run", "bike", "swim"]) == load_knowledge(["triathlon"])


def test_load_knowledge_case_insensitive():
    assert load_knowledge(["run"]) == load_knowledge(["RUN"])
    assert load_knowledge(["Run"]) == load_knowledge(["run"])


# ── build_activity_summary ────────────────────────────────────────────────────

from app.planner import build_activity_summary
from app.models import StravaActivity


def _activity(strava_id: int, sport: str, dt: datetime, distance: float = 10_000.0, moving_time: int = 3600) -> StravaActivity:
    return StravaActivity(
        athlete_id=1, strava_id=strava_id, name=f"Act {strava_id}",
        sport_type=sport, start_date=dt,
        distance=distance, moving_time=moving_time,
        elapsed_time=moving_time, total_elevation_gain=100.0,
    )


def test_build_activity_summary_empty():
    assert build_activity_summary([]) == "No activities on record."


def test_build_activity_summary_single_activity():
    a = _activity(1, "run", datetime(2026, 1, 15), distance=10_000, moving_time=3600)
    result = build_activity_summary([a])
    assert "2026-01" in result
    assert "run" in result
    assert "10km" in result
    assert "1.0h" in result


def test_build_activity_summary_aggregates_same_month():
    a1 = _activity(1, "run", datetime(2026, 1, 5), distance=10_000, moving_time=3600)
    a2 = _activity(2, "run", datetime(2026, 1, 20), distance=10_000, moving_time=3600)
    result = build_activity_summary([a1, a2])
    assert "2×run" in result
    assert "20km" in result
    assert "2.0h" in result


def test_build_activity_summary_multiple_months_sorted():
    a1 = _activity(1, "run", datetime(2026, 3, 1))
    a2 = _activity(2, "run", datetime(2026, 1, 1))
    lines = build_activity_summary([a1, a2]).strip().split("\n")
    assert lines[0].startswith("2026-01")
    assert lines[1].startswith("2026-03")


def test_build_activity_summary_multiple_sports_same_month():
    a1 = _activity(1, "run", datetime(2026, 1, 1))
    a2 = _activity(2, "bike", datetime(2026, 1, 2))
    result = build_activity_summary([a1, a2])
    assert "run" in result
    assert "bike" in result


def test_build_activity_summary_zero_distance_does_not_crash():
    a = _activity(1, "swim", datetime(2026, 1, 1), distance=0, moving_time=1800)
    result = build_activity_summary([a])
    assert "2026-01" in result
    assert "0km" in result


def test_build_activity_summary_sport_type_lowercased():
    # StravaActivity.sport_type may come back from Strava with mixed case
    a = _activity(1, "Run", datetime(2026, 1, 1))
    result = build_activity_summary([a])
    assert "run" in result


def test_build_activity_summary_none_sport_type_falls_back_to_other():
    a = _activity(1, "run", datetime(2026, 1, 1))
    a.sport_type = None  # defensive guard in code: `(a.sport_type or "other")`
    result = build_activity_summary([a])
    assert "other" in result


def test_build_activity_summary_none_distance_and_moving_time():
    a = _activity(1, "run", datetime(2026, 1, 1))
    a.distance = None    # `(a.distance or 0)` guard
    a.moving_time = None  # `(a.moving_time or 0)` guard
    result = build_activity_summary([a])
    assert "0km" in result
    assert "0.0h" in result


# ── _session_to_dict ──────────────────────────────────────────────────────────

from app.planner import _session_to_dict
from app.models import PlannedSession


def test_session_to_dict_includes_expected_fields():
    s = PlannedSession(
        plan_id=1, date=date(2026, 7, 1), sport_type="run",
        title="Easy Run", description="30 min easy",
        hr_zone=2, structure='[{"type":"main","duration_min":30}]',
        planned_duration_min=30, planned_load=50.0,
    )
    d = _session_to_dict(s)
    assert d["date"] == "2026-07-01"
    assert d["sport_type"] == "run"
    assert d["title"] == "Easy Run"
    assert d["description"] == "30 min easy"
    assert d["planned_duration_min"] == 30
    assert d["planned_load"] == 50.0


def test_session_to_dict_excludes_hr_zone_and_structure():
    # These are intentionally omitted so Claude regenerates them fresh
    # rather than copying null values from the existing plan.
    s = PlannedSession(
        plan_id=1, date=date(2026, 7, 1), sport_type="run",
        title="Run", hr_zone=3, structure='[{"type":"main","duration_min":30}]',
    )
    d = _session_to_dict(s)
    assert "hr_zone" not in d
    assert "structure" not in d


def test_session_to_dict_handles_none_fields():
    s = PlannedSession(plan_id=1, date=date(2026, 7, 1), sport_type="rest", title="Rest")
    d = _session_to_dict(s)
    assert d["description"] is None
    assert d["planned_duration_min"] is None
    assert d["planned_load"] is None


# ── _bounded_range_end ────────────────────────────────────────────────────────

from app.planner import _bounded_range_end, ADJUSTMENT_WINDOW_DAYS
from app.models import TrainingPlan


def test_bounded_range_end_no_sessions_returns_window(db):
    plan = TrainingPlan(athlete_id=1, goal_id=1, status="active")
    db.add(plan); db.commit(); db.refresh(plan)
    cutoff = date(2026, 7, 1)
    assert _bounded_range_end(db, plan, cutoff) == cutoff + timedelta(days=ADJUSTMENT_WINDOW_DAYS)


def test_bounded_range_end_last_session_within_window(db):
    plan = TrainingPlan(athlete_id=1, goal_id=1, status="active")
    db.add(plan); db.commit(); db.refresh(plan)
    cutoff = date(2026, 7, 1)
    s = PlannedSession(plan_id=plan.id, date=cutoff + timedelta(days=5), sport_type="run", title="Run")
    db.add(s); db.commit()
    assert _bounded_range_end(db, plan, cutoff) == cutoff + timedelta(days=5)


def test_bounded_range_end_last_session_beyond_window(db):
    plan = TrainingPlan(athlete_id=1, goal_id=1, status="active")
    db.add(plan); db.commit(); db.refresh(plan)
    cutoff = date(2026, 7, 1)
    s = PlannedSession(plan_id=plan.id, date=cutoff + timedelta(days=30), sport_type="run", title="Run")
    db.add(s); db.commit()
    assert _bounded_range_end(db, plan, cutoff) == cutoff + timedelta(days=ADJUSTMENT_WINDOW_DAYS)


def test_bounded_range_end_picks_latest_of_multiple_sessions(db):
    plan = TrainingPlan(athlete_id=1, goal_id=1, status="active")
    db.add(plan); db.commit(); db.refresh(plan)
    cutoff = date(2026, 7, 1)
    for offset in [3, 7, 5]:
        db.add(PlannedSession(plan_id=plan.id, date=cutoff + timedelta(days=offset), sport_type="run", title="Run"))
    db.commit()
    # last session is 7 days out (within window), should return that date
    assert _bounded_range_end(db, plan, cutoff) == cutoff + timedelta(days=7)


# ── get_or_create_athlete ─────────────────────────────────────────────────────

from app.db import get_or_create_athlete
from app.models import Athlete
from sqlmodel import select


def test_get_or_create_athlete_creates_when_none(db):
    athlete = get_or_create_athlete(db)
    assert athlete.id is not None


def test_get_or_create_athlete_returns_same_on_second_call(db):
    a1 = get_or_create_athlete(db)
    a2 = get_or_create_athlete(db)
    assert a1.id == a2.id


def test_get_or_create_athlete_only_one_row(db):
    get_or_create_athlete(db)
    get_or_create_athlete(db)
    assert len(db.exec(select(Athlete)).all()) == 1


# ── _parse_fc_date ────────────────────────────────────────────────────────────

from app.routers.calendar import _parse_fc_date


def test_parse_fc_date_plain_iso():
    assert _parse_fc_date("2026-06-28") == date(2026, 6, 28)


def test_parse_fc_date_with_trailing_z():
    assert _parse_fc_date("2026-06-28T00:00:00Z") == date(2026, 6, 28)


def test_parse_fc_date_with_time_no_z():
    assert _parse_fc_date("2026-06-28T00:00:00") == date(2026, 6, 28)


def test_parse_fc_date_end_of_month():
    assert _parse_fc_date("2026-01-31T23:59:59Z") == date(2026, 1, 31)


# ── _week_start ───────────────────────────────────────────────────────────────

from app.routers.dashboard import _week_start


def test_week_start_monday_unchanged():
    d = date(2026, 6, 22)  # Monday
    assert _week_start(d) == d


def test_week_start_wednesday_returns_monday():
    assert _week_start(date(2026, 6, 24)) == date(2026, 6, 22)


def test_week_start_sunday_returns_monday():
    assert _week_start(date(2026, 6, 28)) == date(2026, 6, 22)


def test_week_start_crosses_month_boundary():
    # Wednesday July 1 → Monday June 29
    assert _week_start(date(2026, 7, 1)) == date(2026, 6, 29)


def test_week_start_crosses_year_boundary():
    # Thursday Jan 1 2026 → Monday Dec 29 2025
    assert _week_start(date(2026, 1, 1)) == date(2025, 12, 29)


# ── _active_conversation ──────────────────────────────────────────────────────

from app.routers.setup import _active_conversation
from app.models import SetupConversation


def test_active_conversation_none_when_empty(db):
    assert _active_conversation(db, 1) is None


def test_active_conversation_returns_chatting(db):
    conv = SetupConversation(athlete_id=1, status="chatting")
    db.add(conv); db.commit()
    result = _active_conversation(db, 1)
    assert result is not None
    assert result.id == conv.id


def test_active_conversation_ignores_done(db):
    conv = SetupConversation(athlete_id=1, status="done")
    db.add(conv); db.commit()
    assert _active_conversation(db, 1) is None


def test_active_conversation_returns_most_recent(db):
    conv1 = SetupConversation(athlete_id=1, status="chatting", created_at=datetime(2026, 1, 1))
    conv2 = SetupConversation(athlete_id=1, status="chatting", created_at=datetime(2026, 1, 2))
    db.add(conv1); db.add(conv2); db.commit()
    assert _active_conversation(db, 1).id == conv2.id


def test_active_conversation_ignores_other_athlete(db):
    conv = SetupConversation(athlete_id=2, status="chatting")
    db.add(conv); db.commit()
    assert _active_conversation(db, 1) is None


def test_active_conversation_mixed_statuses(db):
    done = SetupConversation(athlete_id=1, status="done", created_at=datetime(2026, 1, 2))
    chatting = SetupConversation(athlete_id=1, status="chatting", created_at=datetime(2026, 1, 1))
    db.add(done); db.add(chatting); db.commit()
    result = _active_conversation(db, 1)
    assert result.id == chatting.id
