"""
Routes package.
"""

from .auth import router as auth_router
from .stores import router as stores_router
from .logs import router as logs_router
from .sync import router as sync_router

__all__ = [
    "auth_router",
    "stores_router",
    "logs_router",
    "sync_router",
]
