"""HTTP Authorization enforcement for the Streamable HTTP MCP endpoint."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from .auth import AuthenticationError, authenticate_authorization_header


ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


class AuthorizationHeaderMiddleware:
    """Require a valid Bearer token on every HTTP request."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            authenticate_authorization_header(_get_header(scope, "authorization"))
        except AuthenticationError:
            response = JSONResponse({"error": "authentication failed"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def _get_header(scope: Scope, name: str) -> str | None:
    wanted = name.lower().encode("latin-1")
    for key, value in scope.get("headers", []):
        if key.lower() == wanted:
            return value.decode("latin-1")
    return None
