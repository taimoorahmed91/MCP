"""Small Supabase REST client for Phase 3 token and profile lookups."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from .auth import AuthenticatedUser, AuthenticationError, fingerprint_token


class SupabaseConfigError(RuntimeError):
    """Raised when required Supabase environment variables are missing."""


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    service_role_key: str


def get_supabase_settings() -> SupabaseSettings:
    url = os.environ.get("SUPABASE_URL")
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not service_role_key:
        raise SupabaseConfigError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    return SupabaseSettings(
        url=url.rstrip("/"),
        service_role_key=service_role_key,
    )


class SupabaseFitTrackClient:
    def __init__(self, settings: SupabaseSettings | None = None):
        self.settings = settings or get_supabase_settings()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "apikey": self.settings.service_role_key,
            "Authorization": f"Bearer {self.settings.service_role_key}",
        }

    async def resolve_token(self, token: str) -> AuthenticatedUser:
        token_hash = fingerprint_token(token)
        now = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient(base_url=self.settings.url, headers=self.headers) as client:
            response = await client.get(
                "/rest/v1/fittrack_api_tokens",
                params={
                    "select": "user_id",
                    "token_hash": f"eq.{token_hash}",
                    "expires_at": f"gt.{now}",
                    "limit": "1",
                },
            )
            response.raise_for_status()

        rows = response.json()
        if not rows:
            raise AuthenticationError("authentication failed")

        return AuthenticatedUser(user_id=rows[0]["user_id"])

    async def get_profile_full_name(self, user_id: str) -> str:
        async with httpx.AsyncClient(base_url=self.settings.url, headers=self.headers) as client:
            response = await client.get(
                "/rest/v1/profiles",
                params={
                    "select": "full_name",
                    "id": f"eq.{user_id}",
                    "limit": "1",
                },
            )
            response.raise_for_status()

        rows = response.json()
        if not rows:
            raise LookupError("profile not found")

        return rows[0]["full_name"]
