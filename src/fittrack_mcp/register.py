"""Compatibility response for MCP clients that call /register."""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4


def build_registration_response(request_body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a dynamic-client-registration-shaped response.

    The server still authenticates tool calls with the FitTrack Bearer token.
    This response exists only so MCP clients that probe `/register` can complete
    their setup flow without failing schema validation.
    """

    request_body = request_body or {}
    redirect_uris = request_body.get("redirect_uris")
    if not isinstance(redirect_uris, list) or not redirect_uris:
        redirect_uris = ["http://localhost:6274/oauth/callback"]

    response = {
        "client_id": f"fittrack-mcp-{uuid4()}",
        "client_id_issued_at": int(time.time()),
        "redirect_uris": redirect_uris,
        "token_endpoint_auth_method": request_body.get("token_endpoint_auth_method") or "none",
        "grant_types": request_body.get("grant_types") or ["authorization_code", "refresh_token"],
        "response_types": request_body.get("response_types") or ["code"],
    }

    if isinstance(request_body.get("scope"), str):
        response["scope"] = request_body["scope"]

    if isinstance(request_body.get("client_name"), str):
        response["client_name"] = request_body["client_name"]

    return response
