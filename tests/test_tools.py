import anyio

from fittrack_mcp.auth import AuthenticatedUser
from fittrack_mcp.request_user import current_user
from fittrack_mcp.tools import (
    get_authenticated_user_full_name,
    get_authenticated_user_meals,
    get_recent_workouts,
    get_today_nutrition,
)


class FakeFitTrackClient:
    async def get_profile_full_name(self, user_id):
        assert user_id == "user-123"
        return "Taimoor Ahmed"

    async def get_meals(self, user_id, *, meal_date, calories=None):
        assert user_id == "user-123"
        assert meal_date == "2026-01-03"
        assert calories == 580
        return [{"date": meal_date, "time": "12:55", "food": "Fried Eggs", "calories": 580}]


def test_recent_workouts_returns_fake_data():
    response = get_recent_workouts(limit=2)

    assert response["ok"] is True
    assert response["user_id"] == "phase0-demo-user"
    assert response["source"] == "phase0_fake_data"
    assert len(response["workouts"]) == 2


def test_today_nutrition_returns_fake_data():
    response = get_today_nutrition()

    assert response["ok"] is True
    assert response["user_id"] == "phase0-demo-user"
    assert response["calories"] == 2180


def test_get_authenticated_user_full_name_uses_current_user():
    async def lookup():
        context_token = current_user.set(AuthenticatedUser(user_id="user-123"))
        try:
            assert await get_authenticated_user_full_name(FakeFitTrackClient()) == "Taimoor Ahmed"
        finally:
            current_user.reset(context_token)

    anyio.run(lookup)


def test_get_authenticated_user_meals_uses_current_user():
    async def lookup():
        context_token = current_user.set(AuthenticatedUser(user_id="user-123"))
        try:
            meals = await get_authenticated_user_meals(
                date="2026-01-03",
                calories=580,
                fittrack_client=FakeFitTrackClient(),
            )
        finally:
            current_user.reset(context_token)

        assert meals == [{"date": "2026-01-03", "time": "12:55", "food": "Fried Eggs", "calories": 580}]

    anyio.run(lookup)
