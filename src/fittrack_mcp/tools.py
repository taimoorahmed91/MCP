"""Fake Phase 0 FitTrack tools behind the shared authentication checkpoint."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from .auth import AuthenticationError, authenticate_token


F = TypeVar("F", bound=Callable[..., dict[str, Any]])


def authenticated_tool(handler: F) -> Callable[..., dict[str, Any]]:
    """Wrap a tool so token validation happens in one shared place."""

    def wrapped(*, token: str | None = None, **kwargs: Any) -> dict[str, Any]:
        try:
            user = authenticate_token(token)
        except AuthenticationError as exc:
            return {
                "ok": False,
                "error": str(exc),
            }

        return handler(user_id=user.user_id, **kwargs)

    return wrapped


@authenticated_tool
def get_recent_workouts(*, user_id: str, limit: int = 5) -> dict[str, Any]:
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


@authenticated_tool
def get_today_nutrition(*, user_id: str) -> dict[str, Any]:
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
