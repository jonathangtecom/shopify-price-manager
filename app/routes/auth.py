"""
Authentication routes - login/logout.
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import settings
from ..dependencies import get_session_manager, check_auth
from ..auth import verify_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Show login page."""
    if check_auth(request):
        return RedirectResponse(url="/stores", status_code=303)
    
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": error}
    )


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    """Handle login form submission."""
    session_manager = get_session_manager()
    
    # Verify password against hash from settings
    if settings.admin_password_hash and verify_password(password, settings.admin_password_hash):
        response = RedirectResponse(url="/stores", status_code=303)
        session_manager.create_session(response)
        return response
    
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Invalid password"},
        status_code=401
    )


@router.post("/logout")
async def logout(request: Request):
    """Handle logout."""
    session_manager = get_session_manager()
    response = RedirectResponse(url="/login", status_code=303)
    session_manager.clear_session(response)
    return response


@router.get("/logout")
async def logout_get(request: Request):
    """Handle logout via GET."""
    return await logout(request)
