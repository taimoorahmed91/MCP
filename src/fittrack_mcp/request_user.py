"""Per-request authenticated user context."""

from __future__ import annotations

from contextvars import ContextVar

from .auth import AuthenticatedUser


current_user: ContextVar[AuthenticatedUser | None] = ContextVar("current_user", default=None)
