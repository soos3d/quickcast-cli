"""HTML page rendering routes."""

import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["pages"])

# Configure templates
templates_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_path)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page (public)."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main viewer page."""
    # Template expects feed context; empty defaults until detector injects real feeds
    # (Phase 2 will pass detector state via Depends).
    context = {
        "request": request,
        "feeds": {},
        "active_feed_id": None,
        "active_feed_name": "No feed",
        "active_feed_source": "",
        "model": "",
    }
    return templates.TemplateResponse("viewer.html", context)


@router.get("/recordings.html", response_class=HTMLResponse)
async def recordings_page(request: Request):
    """Render the recordings page."""
    return templates.TemplateResponse("recordings.html", {"request": request})
