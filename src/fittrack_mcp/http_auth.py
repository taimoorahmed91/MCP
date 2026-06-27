"""HTTP Authorization enforcement for the Streamable HTTP MCP endpoint."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from starlette.responses import JSONResponse
from starlette.types import Message, Receive, Scope, Send

from .auth import AuthenticationError, extract_bearer_token
from .request_user import current_user
from .supabase_client import SupabaseFitTrackClient


ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]
AUTH_BYPASS_PATHS = {"/register"}


class AuthorizationHeaderMiddleware:
    """Require a valid Bearer token on MCP tool-call requests."""

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

        if scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        body, receive = await _buffer_request_body(receive)
        if not _is_tool_call(body):
            await self.app(scope, receive, send)
            return

        try:
            token = extract_bearer_token(_get_header(scope, "authorization"))
            client = self.fittrack_client or SupabaseFitTrackClient()
            user = await client.resolve_token(token)
        except (AuthenticationError, Exception):
            response = JSONResponse(_authentication_failed_jsonrpc(body), status_code=200)
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


async def _buffer_request_body(receive: Receive) -> tuple[bytes, Receive]:
    messages: list[Message] = []
    body_parts: list[bytes] = []

    while True:
        message = await receive()
        messages.append(message)
        if message["type"] != "http.request":
            break

        body_parts.append(message.get("body", b""))
        if not message.get("more_body", False):
            break

    async def replay_receive() -> Message:
        if messages:
            return messages.pop(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    return b"".join(body_parts), replay_receive


def _is_tool_call(body: bytes) -> bool:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return False

    if isinstance(payload, list):
        return any(_message_is_tool_call(item) for item in payload)

    return _message_is_tool_call(payload)


def _message_is_tool_call(message: object) -> bool:
    return isinstance(message, dict) and message.get("method") == "tools/call"


def _authentication_failed_jsonrpc(body: bytes) -> dict:
    request_id = None
    try:
        payload = json.loads(body)
        if isinstance(payload, dict):
            request_id = payload.get("id")
        elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
            request_id = payload[0].get("id")
    except json.JSONDecodeError:
        pass

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": -32001,
            "message": "authentication failed",
        },
    }
