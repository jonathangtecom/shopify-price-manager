"""
Authentication routes - login/logout.
"""

import time
from collections import defaultdict
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import settings
from ..dependencies import get_session_manager, check_auth
from ..auth import verify_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Brute force protection: track failed login attempts by IP
failed_attempts = defaultdict(list)
LOCKOUT_THRESHOLD = 5  # Lock after 5 failed attempts
LOCKOUT_DURATION = 300  # 5 minutes in seconds
ATTEMPT_WINDOW = 60  # Track attempts in last 60 seconds


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
    """Handle login form submission with brute force protection."""
    session_manager = get_session_manager()
    client_ip = request.client.host
    current_time = time.time()
    
    # Clean up old attempts
    failed_attempts[client_ip] = [
        attempt_time for attempt_time in failed_attempts[client_ip]
        if current_time - attempt_time < LOCKOUT_DURATION
    ]
    
    # Check if IP is locked out
    if len(failed_attempts[client_ip]) >= LOCKOUT_THRESHOLD:
        time_since_first = current_time - failed_attempts[client_ip][0]
        if time_since_first < LOCKOUT_DURATION:
            remaining = int(LOCKOUT_DURATION - time_since_first)
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": f"Too many failed attempts. Try again in {remaining} seconds."},
                status_code=429
            )
        else:
            # Lockout expired, reset
            failed_attempts[client_ip] = []
    
    # Verify password against hash from settings
    if settings.admin_password_hash and verify_password(password, settings.admin_password_hash):
        # Successful login - clear failed attempts
        failed_attempts[client_ip] = []
        response = RedirectResponse(url="/stores", status_code=303)
        session_manager.create_session(response)
        return response
    
    # Failed login - record attempt
    failed_attempts[client_ip].append(current_time)
    
    # Add small delay to slow down brute force (increases with each attempt)
    delay = min(len(failed_attempts[client_ip]) * 0.5, 3)
    time.sleep(delay)
    
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
