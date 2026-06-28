import json
import re
from datetime import date as _date, timedelta
from typing import Any, Optional

import anthropic

from app.config import settings
from app.knowledge import load_knowledge
from app.mcp_client import StravaMCPClient

_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
_athlete_context_cache: Optional[str] = None


async def cached_tools(mcp: StravaMCPClient) -> list[dict]:
    """Builds the Claude tool list from the live MCP tools, with a cache_control
    breakpoint on the last one. Tools render first in the API's prompt prefix, so
    this caches the whole (~5k-token) tools array across loop iterations and
    separate calls, as long as the MCP server's tool list doesn't change."""
    tools = [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema} for t in await mcp.list_tools()]
    if tools:
        tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral", "ttl": "1h"}}
    return tools


async def get_cached_athlete_context(mcp: StravaMCPClient) -> Optional[str]:
    """Fetches athlete profile + HR zones from Strava once per process and caches the
    summary text. The result is injected as a cache_control-marked block into planning
    calls so Anthropic's server can cache it across API turns."""
    global _athlete_context_cache
    if _athlete_context_cache is not None:
        return _athlete_context_cache
    tools = await cached_tools(mcp)
    prompt = (
        "Use the Strava tools to fetch the athlete's profile and heart rate zones. "
        "Write a concise 3-5 sentence summary: who they are, their sport background, "
        "current fitness level, and any notable training context (HR zones, recent "
        "activity volume). Plain text only."
    )
    try:
        text, _ = await _agentic_loop(
            mcp,
            [{"role": "user", "content": prompt}],
            tools,
            system=None,
            effort="low",
            max_tokens=384,
            max_iterations=4,
        )
        _athlete_context_cache = text.strip() or None
    except Exception as exc:
        print(f"[claude] athlete context fetch failed: {exc}")
    return _athlete_context_cache


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


async def _agentic_loop(
    mcp: StravaMCPClient,
    messages: list[dict],
    tools: list[dict],
    system: Optional[str],
    effort: str,
    max_tokens: int,
    max_iterations: int = 8,
) -> tuple[str, list[dict]]:
    extra: dict = (
        {"system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral", "ttl": "1h"}}]}
        if system
        else {}
    )
    for _ in range(max_iterations):
        response = await _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            output_config={"effort": effort},
            tools=tools,
            messages=messages,
            **extra,
        )
        usage = response.usage
        print(
            f"[claude] model=claude-sonnet-4-6 effort={effort} "
            f"input_tokens={usage.input_tokens} output_tokens={usage.output_tokens} "
            f"cache_read={usage.cache_read_input_tokens or 0} "
            f"cache_creation={usage.cache_creation_input_tokens or 0}"
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text")
            return text, messages

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = await mcp.call_tool(block.name, block.input)
                result_parts = [getattr(item, "text", None) for item in result.content]
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "\n".join(p for p in result_parts if p) or "(no content)",
                        "is_error": bool(getattr(result, "isError", False)),
                    }
                )
        # Cache the accumulated conversation history by marking the last tool result.
        # On the next loop iteration, everything up to this point is a cache hit.
        if tool_results:
            tool_results[-1] = {**tool_results[-1], "cache_control": {"type": "ephemeral", "ttl": "1h"}}
        messages.append({"role": "user", "content": tool_results})
    raise RuntimeError("Exceeded max tool-use iterations without a final answer from Claude")


async def run_agentic_text(
    mcp: StravaMCPClient, prompt: str, system: Optional[str] = None, effort: str = "low"
) -> str:
    tools = await cached_tools(mcp)
    text, _ = await _agentic_loop(
        mcp, [{"role": "user", "content": prompt}], tools, system, effort, max_tokens=1024
    )
    return text or "Claude did not return a text response."


async def run_agentic_json(
    mcp: StravaMCPClient,
    prompt: str,
    system: Optional[str] = None,
    effort: str = "medium",
    max_tokens: int = 2048,
) -> dict:
    tools = await cached_tools(mcp)

    # When a system prompt is present (planning calls), prepend a cached athlete
    # context block so Anthropic's server can cache it across iterations.
    if system:
        athlete_ctx = await get_cached_athlete_context(mcp)
        if athlete_ctx:
            first_content = [
                {"type": "text", "text": f"Athlete summary:\n{athlete_ctx}", "cache_control": {"type": "ephemeral", "ttl": "1h"}},
                {"type": "text", "text": prompt},
            ]
        else:
            first_content = prompt
    else:
        first_content = prompt

    messages = [{"role": "user", "content": first_content}]
    text, messages = await _agentic_loop(mcp, messages, tools, system, effort, max_tokens=max_tokens)
    try:
        return extract_json(text)
    except (json.JSONDecodeError, ValueError):
        messages.append(
            {
                "role": "user",
                "content": (
                    "That was not valid JSON. Respond again with ONLY the JSON "
                    "object — no markdown formatting, no commentary, nothing else."
                ),
            }
        )
        text, _ = await _agentic_loop(mcp, messages, tools, system, effort, max_tokens=max_tokens)
        return extract_json(text)


async def generate_activity_summary(activity) -> str:
    """Lightweight Claude call (no MCP) to produce a 2-3 sentence coaching summary
    from an activity's aggregate stats."""
    client = _client
    parts = [f"{activity.sport_type.title()} — {activity.name}"]
    if activity.moving_time:
        parts.append(f"{activity.moving_time // 60} min")
    if activity.distance:
        parts.append(f"{activity.distance / 1000:.1f} km")
    if activity.average_heartrate:
        parts.append(f"avg HR {int(activity.average_heartrate)} bpm")
    if activity.total_elevation_gain:
        parts.append(f"{int(activity.total_elevation_gain)} m gain")
    if activity.relative_effort:
        parts.append(f"effort score {int(activity.relative_effort)}")
    prompt = (
        ", ".join(parts) + ". "
        "Write a 2-3 sentence coaching summary: effort level, pacing quality, "
        "and one notable observation about this workout. Plain text only, no markdown."
    )
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


_SETUP_GREETING = "Hi! I'm your Arete training coach. What are you currently training for — a specific race, general fitness, or something else?"

_SETUP_SYSTEM = """You are an intake coach for Arete, a personalised AI training app. Gather training information through warm, natural conversation.

RULES:
- Ask 1-2 questions per turn only. Be concise (2-4 sentences per reply).
- Never repeat the opening greeting — it has already been shown to the user.
- If Strava data is provided, weave it in naturally: "I can see you've been running around X km/week — is that typical?"

EXTRACT across the conversation:
- Race goals: name, date, distance, priority (A = peak race, B = target, C = tune-up). Can be multiple races.
- Sport mix: run / bike / swim / strength / triathlon
- Weekly training hours and preferred training days
- Blocked/unavailable days
- Current fitness level, recent training, injuries, constraints

FLOW: gather info for ~8-10 exchanges, then summarise everything and ask "Does this look right?"

ON USER CONFIRMATION output this EXACTLY (valid JSON, no deviations):
<GOAL_JSON>
{"goals":[{"race_name":"...","race_date":"YYYY-MM-DD","race_distance":"...","priority":"A","sport_type":"run"}],"sport_types":["run"],"weekly_hours":8.0,"blocked_days":[],"notes":"..."}
</GOAL_JSON>
PLAN_CONFIRMED"""


async def setup_chat_response(messages: list[dict], strava_context: Optional[str] = None) -> str:
    """Single Claude call (no tools) for the conversational setup intake."""
    client = _client
    system = _SETUP_SYSTEM
    if strava_context:
        system += f"\n\nAthlete's Strava snapshot (reference naturally, don't quote verbatim):\n{strava_context}"
    # Prepend the greeting as a prior assistant turn so Claude knows the
    # conversation already opened with it and won't repeat it.
    ctx = [{"role": "assistant", "content": _SETUP_GREETING}] + messages
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
        messages=ctx,
    )
    usage = response.usage
    print(
        f"[claude-setup] input={usage.input_tokens} output={usage.output_tokens} "
        f"cache_read={usage.cache_read_input_tokens or 0}"
    )
    return response.content[0].text.strip()


def extract_goal_json(text: str) -> Optional[dict]:
    """Parse the <GOAL_JSON>…</GOAL_JSON> block Claude emits on confirmation."""
    m = re.search(r"<GOAL_JSON>(.*?)</GOAL_JSON>", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            return None
    return None


def clean_claude_message(text: str) -> str:
    """Strip internal markers before showing text to the user."""
    text = re.sub(r"<GOAL_JSON>.*?</GOAL_JSON>", "", text, flags=re.DOTALL)
    text = text.replace("PLAN_CONFIRMED", "")
    return text.strip()


async def generate_macro_plan(
    goal_data: dict,
    season_start: _date,
    season_end: _date,
    history_summary: Optional[str] = None,
    athlete_context: Optional[str] = None,
) -> dict:
    """One Claude call (no MCP) to produce a full-season macro plan as compact JSON."""
    client = _client
    num_weeks = max(1, ((season_end - season_start).days // 7) + 1)

    goals = goal_data.get("goals", [])
    weekly_hours = goal_data.get("weekly_hours") or 8
    sport_types = goal_data.get("sport_types") or ["run"]
    blocked_days = goal_data.get("blocked_days") or []
    notes = goal_data.get("notes") or ""

    parts: list[str] = [
        f"Season: {season_start.isoformat()} → {season_end.isoformat()} ({num_weeks} weeks). "
        f"Week 1 starts {season_start.isoformat()}.",
        f"Available: {weekly_hours}h/week. Sports: {', '.join(sport_types)}. "
        f"Blocked days: {', '.join(blocked_days) or 'none'}.",
    ]
    if goals:
        race_lines = [
            f"  {g.get('priority','?')}: {g.get('race_name')} "
            f"({g.get('race_distance','?')}) on {g.get('race_date','TBD')}"
            for g in goals
        ]
        parts.append("Races:\n" + "\n".join(race_lines))
    if notes:
        parts.append(f"Notes: {notes}")
    if athlete_context:
        parts.append(f"Athlete profile: {athlete_context}")
    if history_summary:
        parts.append(f"12-month training history (use for periodisation):\n{history_summary}")

    schema = (
        '{"weeks":[{"week_number":1,"start_date":"YYYY-MM-DD",'
        '"phase":"base|build|specific|taper|race|recovery",'
        '"sport_focus":"run|bike|swim|strength|mixed",'
        '"hours_run":0.0,"hours_bike":0.0,"hours_swim":0.0,"hours_strength":0.0,'
        '"theme":"one concise line"}]}'
    )
    parts.append(
        f"Design a complete, properly periodised macro plan for ALL {num_weeks} weeks "
        "(base → build → specific → taper → race → recovery as appropriate). "
        f"Respond ONLY with this JSON shape — no markdown, no commentary:\n{schema}"
    )

    kb_text = load_knowledge(sport_types)
    system_text = (
        f"{kb_text}\n\n"
        "---\n\n"
        "You are an expert endurance coach. Use the training science guidelines above "
        "when designing the plan. Respond only with the JSON object — no markdown, no commentary."
    )
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=[{
            "type": "text",
            "text": system_text,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }],
        messages=[{"role": "user", "content": "\n\n".join(parts)}],
    )
    usage = response.usage
    print(
        f"[claude-macro] input={usage.input_tokens} output={usage.output_tokens} "
        f"cache_read={usage.cache_read_input_tokens or 0}"
    )
    return extract_json(response.content[0].text)


async def expand_macro_week(
    week: dict,
    goal_context: str,
    prev_sessions: list[dict],
    sport_types: Optional[list[str]] = None,
) -> dict:
    """Lightweight Haiku call to expand one MacroWeek into 7 PlannedSession records."""
    client = _client

    start = _date.fromisoformat(week["start_date"])
    days = [(start + timedelta(days=i)) for i in range(7)]
    day_list = ", ".join(f"{d.strftime('%a')} {d.isoformat()}" for d in days)

    load_parts = []
    if week.get("hours_run"):   load_parts.append(f"run {week['hours_run']}h")
    if week.get("hours_bike"):  load_parts.append(f"bike {week['hours_bike']}h")
    if week.get("hours_swim"):  load_parts.append(f"swim {week['hours_swim']}h")
    if week.get("hours_strength"): load_parts.append(f"strength {week['hours_strength']}h")
    load_str = ", ".join(load_parts) or "rest week"

    prev_ctx = ""
    if prev_sessions:
        compact = [
            {"date": s["date"], "type": s["sport_type"], "min": s.get("planned_duration_min")}
            for s in prev_sessions
        ]
        prev_ctx = f"\nPrevious week (for continuity): {json.dumps(compact)}"

    schema = (
        'Return ONLY: {"sessions":[{"date":"YYYY-MM-DD",'
        '"sport_type":"run|bike|swim|strength|brick|rest|other",'
        '"title":"max 6 words",'
        '"description":"2 sentences or null for rest",'
        '"hr_zone":1-5|null,'
        '"structure":[{"type":"warmup|main|interval|threshold|cooldown|recovery","duration_min":int}]|null,'
        '"planned_duration_min":int,"planned_load":0-150}]}'
    )

    prompt = (
        f"Week {week['week_number']} · Phase: {week['phase']} · Theme: {week['theme']}\n"
        f"Load targets: {load_str}\n"
        f"{goal_context}"
        f"{prev_ctx}\n\n"
        f"Dates: {day_list}\n"
        f"Generate exactly 7 sessions in date order. Rest days: sport_type=rest, description=null, structure=null, planned_duration_min=0, planned_load=0.\n"
        f"{schema}"
    )

    kb_text = load_knowledge(sport_types or ["run"])
    system_text = (
        f"{kb_text}\n\n"
        "---\n\n"
        "You are an expert endurance coach. Use the training science guidelines above "
        "when designing sessions. Respond only with the JSON object — no markdown, no commentary."
    )
    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
        messages=[{"role": "user", "content": prompt}],
    )
    usage = response.usage
    print(f"[claude-expand-week] input={usage.input_tokens} output={usage.output_tokens}")
    return extract_json(response.content[0].text)


async def verify_strava_connection(mcp: StravaMCPClient) -> str:
    """Round-trips through Claude + the Strava MCP tools to prove the bridge works."""
    return await run_agentic_text(
        mcp,
        "Check whether my Strava account is connected. If it is, tell me my name "
        "and give a one-sentence summary of my profile. If it is not connected, "
        "say so plainly and tell me how to connect it.",
    )


async def connect_strava(mcp: StravaMCPClient) -> str:
    """Asks Claude to use whichever tool connects/authorizes the Strava account."""
    return await run_agentic_text(
        mcp,
        "Connect my Strava account using the appropriate tool. After calling it, "
        "tell me plainly what just happened and what I need to do next (for "
        "example, check my browser to authorize).",
    )
