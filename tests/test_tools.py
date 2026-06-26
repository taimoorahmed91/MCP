from fittrack_mcp.tools import get_recent_workouts, get_today_nutrition


TOKEN = "fittrack_phase0_dev_token"


def test_recent_workouts_requires_valid_token():
    response = get_recent_workouts(token="wrong-token")

    assert response == {
        "ok": False,
        "error": "authentication failed",
    }


def test_recent_workouts_returns_fake_data_for_known_token():
    response = get_recent_workouts(token=TOKEN, limit=2)

    assert response["ok"] is True
    assert response["user_id"] == "phase0-demo-user"
    assert response["source"] == "phase0_fake_data"
    assert len(response["workouts"]) == 2


def test_today_nutrition_uses_same_token_checkpoint():
    response = get_today_nutrition(token=TOKEN)

    assert response["ok"] is True
    assert response["user_id"] == "phase0-demo-user"
    assert response["calories"] == 2180
