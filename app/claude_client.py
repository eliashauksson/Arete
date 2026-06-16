from typing import Optional

import anthropic
from anthropic.lib.tools.mcp import async_mcp_tool

from app.config import settings
from app.mcp_client import StravaMCPClient

_client: Optional[anthropic.AsyncAnthropic] = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def ask_claude_with_strava_tools(mcp: StravaMCPClient, prompt: str) -> str:
    """Runs one prompt through Claude with the live Strava MCP tools attached."""
    tools = await mcp.list_tools()
    runner = get_client().beta.messages.tool_runner(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
        tools=[async_mcp_tool(t, mcp.session) for t in tools],
    )

    final_text = ""
    async for message in runner:
        for block in message.content:
            if block.type == "text":
                final_text = block.text
    return final_text or "Claude did not return a text response."


async def verify_strava_connection(mcp: StravaMCPClient) -> str:
    """Round-trips through Claude + the Strava MCP tools to prove the bridge works."""
    return await ask_claude_with_strava_tools(
        mcp,
        "Check whether my Strava account is connected. If it is, tell me my name "
        "and give a one-sentence summary of my profile. If it is not connected, "
        "say so plainly and tell me how to connect it.",
    )


async def connect_strava(mcp: StravaMCPClient) -> str:
    """Asks Claude to use whichever tool connects/authorizes the Strava account."""
    return await ask_claude_with_strava_tools(
        mcp,
        "Connect my Strava account using the appropriate tool. After calling it, "
        "tell me plainly what just happened and what I need to do next (for "
        "example, check my browser to authorize).",
    )
