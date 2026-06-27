"""Token authentication for the FitTrack MCP server."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


class AuthenticationError(Exception):
    """Raised when a request does not carry a valid token."""


@dataclass(frozen=True)
class AuthenticatedUser:
    """The user identity resolved from a valid token."""

    user_id: str


def fingerprint_token(token: str) -> str:
    """Return the one-way fingerprint used to compare tokens."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def extract_bearer_token(header_value: str | None) -> str:
    """Validate an HTTP Authorization header carrying a Bearer token."""

    prefix = "Bearer "
    if not header_value or not header_value.startswith(prefix):
        raise AuthenticationError("authentication failed")

    token = header_value[len(prefix) :].strip()
    if not token:
        raise AuthenticationError("authentication failed")

    return token
