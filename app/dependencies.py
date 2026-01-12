"""
FastAPI dependency injection.
Simple setup - just database and session management.
"""

from typing import Optional
from fastapi import Request, HTTPException

from .config import settings
from .db import SQLiteDatabase
from .auth import SessionManager


# Global instances (initialized on startup)
_db: Optional[SQLiteDatabase] = None
_session_manager: Optional[SessionManager] = None


async def init_dependencies():
    """Initialize global dependencies. Called on app startup."""
    global _db, _session_manager
    
    _db = SQLiteDatabase(settings.database_path)
    await _db.initialize()
    
    _session_manager = SessionManager(settings.session_secret)


async def close_dependencies():
    """Close global dependencies. Called on app shutdown."""
    global _db
    if _db:
        await _db.close()


def get_db() -> SQLiteDatabase:
    """Get the database instance."""
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


def get_session_manager() -> SessionManager:
    """Get the session manager instance."""
    if _session_manager is None:
        raise RuntimeError("Session manager not initialized")
    return _session_manager


async def require_auth(request: Request):
    """
    Dependency that requires authentication.
    Redirects to login if not authenticated.
    """
    session_manager = get_session_manager()
    
    if not session_manager.is_authenticated(request):
        if request.url.path.startswith("/api/"):
            raise HTTPException(status_code=401, detail="Not authenticated")
        raise HTTPException(status_code=307, headers={"Location": "/login"})


def check_auth(request: Request) -> bool:
    """Check if user is authenticated (without raising exception)."""
    session_manager = get_session_manager()
    return session_manager.is_authenticated(request)
