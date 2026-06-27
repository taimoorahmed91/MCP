"""HTTP Authorization enforcement for the Streamable HTTP MCP endpoint."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from .auth import AuthenticationError, extract_bearer_token
from .request_user import current_user
from .supabase_client import SupabaseFitTrackClient


ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]
AUTH_BYPASS_PATHS = {"/register"}


class AuthorizationHeaderMiddleware:
    """Require a valid Bearer token on every HTTP request."""

    def __init__(self, app: ASGIApp, fittrack_client: SupabaseFitTrackClient | None = None):
        self.app = app
        self.fittrack_client = fittrack_client

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope.get("path") in AUTH_BYPASS_PATHS:
            await self.app(scope, receive, send)
            return

        try:
            token = extract_bearer_token(_get_header(scope, "authorization"))
            client = self.fittrack_client or SupabaseFitTrackClient()
            user = await client.resolve_token(token)
        except (AuthenticationError, Exception):
            response = JSONResponse({"error": "authentication failed"}, status_code=401)
            await response(scope, receive, send)
            return

        context_token = current_user.set(user)
        try:
            await self.app(scope, receive, send)
        finally:
            current_user.reset(context_token)


def _get_header(scope: Scope, name: str) -> str | None:
    wanted = name.lower().encode("latin-1")
    for key, value in scope.get("headers", []):
        if key.lower() == wanted:
            return value.decode("latin-1")
    return None
