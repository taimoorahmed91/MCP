import anyio

from fittrack_mcp.auth import AuthenticatedUser
from fittrack_mcp.request_user import current_user
from fittrack_mcp.tools import (
    get_authenticated_user_full_name,
    get_authenticated_user_meals,
    get_authenticated_user_sleep_routine,
)


class FakeFitTrackClient:
    async def get_profile_full_name(self, user_id):
        assert user_id == "user-123"
        return "Taimoor Ahmed"

    async def get_meals(self, user_id, *, meal_date, calories_min=None, calories_max=None):
        assert user_id == "user-123"
        assert meal_date == "2026-01-03"
        assert calories_min == 500
        assert calories_max == 700
        return [{"date": meal_date, "time": "12:55", "food": "Fried Eggs", "calories": 580}]

    async def get_sleep_routine(self, user_id, *, sleep_date, hours_min=None, hours_max=None):
        assert user_id == "user-123"
        assert sleep_date == "2026-02-23"
        assert hours_min == 7.5
        assert hours_max == 8.5
        return [{"date": sleep_date, "hours": 8, "notes": None}]


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
                calories_min=500,
                calories_max=700,
                fittrack_client=FakeFitTrackClient(),
            )
        finally:
            current_user.reset(context_token)

        assert meals == [{"date": "2026-01-03", "time": "12:55", "food": "Fried Eggs", "calories": 580}]

    anyio.run(lookup)


def test_get_authenticated_user_sleep_routine_uses_current_user():
    async def lookup():
        context_token = current_user.set(AuthenticatedUser(user_id="user-123"))
        try:
            sleep_entries = await get_authenticated_user_sleep_routine(
                date="2026-02-23",
                hours_min=7.5,
                hours_max=8.5,
                fittrack_client=FakeFitTrackClient(),
            )
        finally:
            current_user.reset(context_token)

        assert sleep_entries == [{"date": "2026-02-23", "hours": 8, "notes": None}]

    anyio.run(lookup)
