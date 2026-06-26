from fittrack_mcp.tools import get_recent_workouts, get_today_nutrition


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
