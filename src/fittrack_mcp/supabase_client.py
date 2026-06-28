"""Small Supabase REST client for Phase 3 token and profile lookups."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from .auth import AuthenticatedUser, AuthenticationError, fingerprint_token


class SupabaseConfigError(RuntimeError):
    """Raised when required Supabase environment variables are missing."""


class TokenLookupError(AuthenticationError):
    """Raised when the provided token does not resolve to a valid user."""


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
            raise TokenLookupError("authentication failed")

        return AuthenticatedUser(user_id=rows[0]["user_id"])

    async def debug_token_hash_lookup(self, token_hash: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(base_url=self.settings.url, headers=self.headers) as client:
            response = await client.get(
                "/rest/v1/fittrack_api_tokens",
                params={
                    "select": "user_id,expires_at",
                    "token_hash": f"eq.{token_hash}",
                    "limit": "1",
                },
            )
            response.raise_for_status()

        return response.json()

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

    async def get_meals(
        self,
        user_id: str,
        *,
        meal_date: str,
        calories_min: int | None = None,
        calories_max: int | None = None,
    ) -> list[dict[str, Any]]:
        params = [
            ("select", "id,date,time,food,calories"),
            ("user_id", f"eq.{user_id}"),
            ("date", f"eq.{meal_date}"),
            ("order", "time.asc"),
        ]

        if calories_min is None and calories_max is None:
            params.append(("calories", "gt.0"))
        if calories_min is not None:
            params.append(("calories", f"gte.{calories_min}"))
        if calories_max is not None:
            params.append(("calories", f"lte.{calories_max}"))

        async with httpx.AsyncClient(base_url=self.settings.url, headers=self.headers) as client:
            response = await client.get(
                "/rest/v1/fittrack_meals",
                params=params,
            )
            response.raise_for_status()

        return response.json()

    async def get_sleep_routine(
        self,
        user_id: str,
        *,
        sleep_date: str,
        hours_min: float | None = None,
        hours_max: float | None = None,
    ) -> list[dict[str, Any]]:
        params = [
            ("select", "id,date,hours,notes"),
            ("user_id", f"eq.{user_id}"),
            ("date", f"eq.{sleep_date}"),
            ("order", "date.desc"),
        ]

        if hours_min is None and hours_max is None:
            params.append(("hours", "gt.0"))
        if hours_min is not None:
            params.append(("hours", f"gte.{hours_min:g}"))
        if hours_max is not None:
            params.append(("hours", f"lte.{hours_max:g}"))

        async with httpx.AsyncClient(base_url=self.settings.url, headers=self.headers) as client:
            response = await client.get(
                "/rest/v1/fittrack_sleep",
                params=params,
            )
            response.raise_for_status()

        return response.json()
