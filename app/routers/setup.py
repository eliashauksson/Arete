from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.claude_client import connect_strava, verify_strava_connection
from app.mcp_client import strava_mcp

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    return templates.TemplateResponse(request, "setup.html", {})


@router.post("/setup/connect-strava", response_class=HTMLResponse)
async def connect_strava_route():
    result = await connect_strava(strava_mcp)
    return result


@router.post("/setup/verify-connection", response_class=HTMLResponse)
async def verify_connection_route():
    result = await verify_strava_connection(strava_mcp)
    return result
