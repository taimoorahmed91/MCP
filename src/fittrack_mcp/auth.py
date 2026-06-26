"""Token authentication for the Phase 0 server."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone


KNOWN_TOKEN_FINGERPRINT = (
    "8d7290a9091a2b494e899f7e3ae5281a75eb243b05dcb619917049ad82fe2345"
)


class AuthenticationError(Exception):
    """Raised when a request does not carry a valid token."""


@dataclass(frozen=True)
class AuthenticatedUser:
    """The user identity resolved from a valid token."""

    user_id: str


def fingerprint_token(token: str) -> str:
    """Return the one-way fingerprint used to compare tokens."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_token_expired(now: datetime | None = None) -> bool:
    """Phase 0 expiry hook.

    The real server will check the database token expiry here. For Phase 0 the
    shape is present, but the known local token is treated as not expired.
    """

    _ = now or datetime.now(timezone.utc)
    return False


def authenticate_token(token: str | None) -> AuthenticatedUser:
    """Validate a token and return the resolved user.

    Phase 0 uses one hardcoded token fingerprint. Later phases will keep this
    function's role but swap its source of truth to Supabase.
    """

    if not token:
        raise AuthenticationError("authentication failed")

    incoming_fingerprint = fingerprint_token(token)
    if not hmac.compare_digest(incoming_fingerprint, KNOWN_TOKEN_FINGERPRINT):
        raise AuthenticationError("authentication failed")

    if is_token_expired():
        raise AuthenticationError("authentication failed")

    return AuthenticatedUser(user_id="phase0-demo-user")


def authenticate_authorization_header(header_value: str | None) -> AuthenticatedUser:
    """Validate an HTTP Authorization header carrying a Bearer token."""

    prefix = "Bearer "
    if not header_value or not header_value.startswith(prefix):
        raise AuthenticationError("authentication failed")

    token = header_value[len(prefix) :].strip()
    return authenticate_token(token)
