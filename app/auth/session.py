"""
Cookie-based session management.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, Response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


# Session duration: 24 hours
SESSION_MAX_AGE = 24 * 60 * 60  # seconds
SESSION_COOKIE_NAME = "session"


class SessionManager:
    """Manages signed cookie-based sessions."""

    def __init__(self, secret_key: str):
        """
        Initialize session manager.
        
        Args:
            secret_key: Secret key for signing cookies
        """
        self._serializer = URLSafeTimedSerializer(secret_key)

    def create_session(self, response: Response, user_id: str = "admin") -> None:
        """
        Create a new session and set the cookie.
        
        Args:
            response: FastAPI response object
            user_id: User identifier to store in session
        """
        # Create session data
        session_data = {
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Sign and encode
        token = self._serializer.dumps(session_data)

        # Set cookie
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            max_age=SESSION_MAX_AGE,
            httponly=True,  # Not accessible via JavaScript
            samesite="lax",  # CSRF protection
            secure=False,  # Set to True in production with HTTPS
        )

    def get_session(self, request: Request) -> Optional[dict]:
        """
        Get session data from request cookie.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Session data dict or None if invalid/expired
        """
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if not token:
            return None

        try:
            # Verify signature and check expiration
            session_data = self._serializer.loads(
                token, max_age=SESSION_MAX_AGE
            )
            return session_data
        except (BadSignature, SignatureExpired):
            return None

    def clear_session(self, response: Response) -> None:
        """
        Clear the session cookie.
        
        Args:
            response: FastAPI response object
        """
        response.delete_cookie(
            key=SESSION_COOKIE_NAME,
            httponly=True,
            samesite="lax",
        )

    def is_authenticated(self, request: Request) -> bool:
        """
        Check if the request has a valid session.
        
        Args:
            request: FastAPI request object
            
        Returns:
            True if authenticated, False otherwise
        """
        return self.get_session(request) is not None
