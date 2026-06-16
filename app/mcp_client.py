import os
from contextlib import AsyncExitStack
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings


class StravaMCPClient:
    def __init__(self) -> None:
        self._stack: Optional[AsyncExitStack] = None
        self.session: Optional[ClientSession] = None

    async def start(self) -> None:
        self._stack = AsyncExitStack()
        server_params = StdioServerParameters(
            command="npx",
            args=["-y", "@r-huijts/strava-mcp-server"],
            env={
                **os.environ,
                "STRAVA_CLIENT_ID": settings.strava_client_id,
                "STRAVA_CLIENT_SECRET": settings.strava_client_secret,
                "ROUTE_EXPORT_PATH": settings.strava_route_export_path,
            },
        )
        read, write = await self._stack.enter_async_context(stdio_client(server_params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

    async def stop(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self.session = None
        self._stack = None

    async def list_tools(self) -> list[Any]:
        assert self.session is not None, "Strava MCP session not started"
        result = await self.session.list_tools()
        return result.tools

    async def call_tool(self, name: str, arguments: Optional[dict] = None) -> Any:
        assert self.session is not None, "Strava MCP session not started"
        return await self.session.call_tool(name, arguments or {})


strava_mcp = StravaMCPClient()
