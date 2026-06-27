"""Fake Phase 0 FitTrack tools."""

from __future__ import annotations

from typing import Any

from .request_user import current_user
from .supabase_client import SupabaseFitTrackClient


async def get_authenticated_user_full_name(
    fittrack_client: SupabaseFitTrackClient | None = None,
) -> str:
    """Return the authenticated FitTrack user's full name."""

    user = current_user.get()
    if user is None:
        raise RuntimeError("authentication failed")

    client = fittrack_client or SupabaseFitTrackClient()
    return await client.get_profile_full_name(user.user_id)


def get_recent_workouts(*, user_id: str = "phase0-demo-user", limit: int = 5) -> dict[str, Any]:
    """Return fixed workout data to prove the request path works."""

    workouts = [
        {
            "date": "2026-06-24",
            "type": "strength",
            "summary": "Upper body session, 48 minutes, moderate intensity.",
        },
        {
            "date": "2026-06-22",
            "type": "run",
            "summary": "Easy outdoor run, 5.2 km, steady pace.",
        },
        {
            "date": "2026-06-20",
            "type": "mobility",
            "summary": "Recovery mobility flow, 25 minutes.",
        },
    ]

    return {
        "ok": True,
        "user_id": user_id,
        "workouts": workouts[: max(0, limit)],
        "source": "phase0_fake_data",
    }


def get_today_nutrition(*, user_id: str = "phase0-demo-user") -> dict[str, Any]:
    """Return fixed nutrition data to prove a second tool uses the checkpoint."""

    return {
        "ok": True,
        "user_id": user_id,
        "date": "2026-06-26",
        "calories": 2180,
        "protein_grams": 142,
        "carbs_grams": 236,
        "fat_grams": 71,
        "source": "phase0_fake_data",
    }
