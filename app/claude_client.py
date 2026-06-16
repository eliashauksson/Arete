import json
from typing import Any, Optional

import anthropic

from app.config import settings
from app.mcp_client import StravaMCPClient

_client: Optional[anthropic.AsyncAnthropic] = None


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
    extra: dict = {"system": system} if system else {}
    for _ in range(max_iterations):
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            output_config={"effort": effort},
            tools=tools,
            messages=messages,
            **extra,
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
    tools = [mcp_tool_to_claude_tool(t) for t in await mcp.list_tools()]
    text, _ = await _agentic_loop(
        mcp, [{"role": "user", "content": prompt}], tools, system, effort, max_tokens=1024
    )
    return text or "Claude did not return a text response."


async def run_agentic_json(
    mcp: StravaMCPClient, prompt: str, system: Optional[str] = None, effort: str = "medium"
) -> dict:
    tools = [mcp_tool_to_claude_tool(t) for t in await mcp.list_tools()]
    messages = [{"role": "user", "content": prompt}]
    text, messages = await _agentic_loop(mcp, messages, tools, system, effort, max_tokens=4096)
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
        text, _ = await _agentic_loop(mcp, messages, tools, system, effort, max_tokens=4096)
        return extract_json(text)


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
