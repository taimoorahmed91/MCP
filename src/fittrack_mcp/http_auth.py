"""HTTP Authorization enforcement for the Streamable HTTP MCP endpoint."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable

import httpx

from starlette.responses import JSONResponse
from starlette.types import Message, Receive, Scope, Send

from .auth import AuthenticationError, extract_bearer_token, fingerprint_token
from .request_user import current_user
from .supabase_client import SupabaseConfigError, SupabaseFitTrackClient, TokenLookupError


ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]
AUTH_BYPASS_PATHS = {"/register"}
logger = logging.getLogger(__name__)


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
            authorization_header = _get_header(scope, "authorization")
            token = extract_bearer_token(authorization_header)
            client = self.fittrack_client or SupabaseFitTrackClient()
            user = await client.resolve_token(token)
        except TokenLookupError:
            logger.warning("fittrack auth failed: no unexpired token row matched")
            await _log_token_hash_row_state(token, client)
            response = JSONResponse(_authentication_failed_jsonrpc(body), status_code=200)
            await response(scope, receive, send)
            return
        except SupabaseConfigError:
            logger.exception("fittrack auth failed: Supabase environment is not configured")
            response = JSONResponse(_authentication_failed_jsonrpc(body), status_code=200)
            await response(scope, receive, send)
            return
        except httpx.HTTPStatusError as exc:
            logger.exception("fittrack auth failed: Supabase returned HTTP %s", exc.response.status_code)
            response = JSONResponse(_authentication_failed_jsonrpc(body), status_code=200)
            await response(scope, receive, send)
            return
        except httpx.RequestError:
            logger.exception("fittrack auth failed: Supabase request failed")
            response = JSONResponse(_authentication_failed_jsonrpc(body), status_code=200)
            await response(scope, receive, send)
            return
        except AuthenticationError:
            logger.warning("fittrack auth failed: missing or invalid Authorization Bearer header")
            response = JSONResponse(_authentication_failed_jsonrpc(body), status_code=200)
            await response(scope, receive, send)
            return
        except Exception:
            logger.exception("fittrack auth failed: unexpected error")
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


async def _log_token_hash_row_state(token: str, client: SupabaseFitTrackClient) -> None:
    try:
        rows = await client.debug_token_hash_lookup(fingerprint_token(token))
    except Exception:
        logger.exception("fittrack auth debug: failed to query token row by hash")
        return

    if not rows:
        logger.warning("fittrack auth debug: token hash does not exist in fittrack_api_tokens")
        return

    logger.warning(
        "fittrack auth debug: token hash exists but is expired or not valid; expires_at=%s",
        rows[0].get("expires_at"),
    )
