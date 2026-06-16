import json
from typing import Any, Optional

import anthropic

from app.config import settings
from app.mcp_client import StravaMCPClient

_client: Optional[anthropic.AsyncAnthropic] = None
_athlete_context_cache: Optional[str] = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


def mcp_tool_to_claude_tool(t: Any) -> dict:
    return {
        "name": t.name,
        "description": t.description or "",
        "input_schema": t.inputSchema,
    }


async def cached_tools(mcp: StravaMCPClient) -> list[dict]:
    """Builds the Claude tool list from the live MCP tools, with a cache_control
    breakpoint on the last one. Tools render first in the API's prompt prefix, so
    this caches the whole (~5k-token) tools array across loop iterations and
    separate calls, as long as the MCP server's tool list doesn't change."""
    tools = [mcp_tool_to_claude_tool(t) for t in await mcp.list_tools()]
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


def mcp_result_to_text(result: Any) -> str:
    parts = [getattr(item, "text", None) for item in result.content]
    text = "\n".join(p for p in parts if p)
    return text or "(no content)"


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
    client = get_client()
    extra: dict = (
        {"system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral", "ttl": "1h"}}]}
        if system
        else {}
    )
    for _ in range(max_iterations):
        response = await client.messages.create(
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
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": mcp_result_to_text(result),
                        "is_error": bool(getattr(result, "isError", False)),
                    }
                )
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
    client = get_client()
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
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


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
