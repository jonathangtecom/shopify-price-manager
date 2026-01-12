"""
Authentication module.
"""

from app.auth.password import hash_password, verify_password
from app.auth.session import SessionManager, SESSION_COOKIE_NAME

__all__ = [
    "hash_password",
    "verify_password",
    "SessionManager",
    "SESSION_COOKIE_NAME",
]
