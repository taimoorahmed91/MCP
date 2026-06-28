import anyio
import httpx

from fittrack_mcp.auth import AuthenticationError, fingerprint_token
from fittrack_mcp.supabase_client import SupabaseConfigError, SupabaseFitTrackClient, SupabaseSettings, get_supabase_settings


def test_get_supabase_settings_reads_required_environment(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    settings = get_supabase_settings()

    assert settings.url == "https://example.supabase.co"
    assert settings.service_role_key == "service-key"


def test_get_supabase_settings_requires_environment(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    try:
        get_supabase_settings()
    except SupabaseConfigError as exc:
        assert "SUPABASE_URL" in str(exc)
    else:
        raise AssertionError("Expected SupabaseConfigError")


def test_resolve_token_queries_hash_and_expiry(monkeypatch):
    requests = []
    token = "real-token"
    expected_hash = fingerprint_token(token)

    async def handler(request):
        requests.append(request)
        assert request.url.path == "/rest/v1/fittrack_api_tokens"
        assert request.url.params["select"] == "user_id"
        assert request.url.params["token_hash"] == f"eq.{expected_hash}"
        assert request.url.params["expires_at"].startswith("gt.")
        assert request.headers["apikey"] == "service-key"
        assert request.headers["authorization"] == "Bearer service-key"
        return httpx.Response(200, json=[{"user_id": "user-123"}])

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_async_client(transport=transport, **kwargs))

    async def resolve():
        client = SupabaseFitTrackClient(SupabaseSettings(url="https://example.supabase.co", service_role_key="service-key"))
        user = await client.resolve_token(token)
        assert user.user_id == "user-123"

    anyio.run(resolve)
    assert len(requests) == 1


def test_resolve_token_rejects_missing_row(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_async_client(transport=transport, **kwargs))

    async def resolve():
        client = SupabaseFitTrackClient(SupabaseSettings(url="https://example.supabase.co", service_role_key="service-key"))
        try:
            await client.resolve_token("bad-token")
        except AuthenticationError as exc:
            assert str(exc) == "authentication failed"
        else:
            raise AssertionError("Expected AuthenticationError")

    anyio.run(resolve)


def test_get_profile_full_name_queries_profiles(monkeypatch):
    async def handler(request):
        assert request.url.path == "/rest/v1/profiles"
        assert request.url.params["select"] == "full_name"
        assert request.url.params["id"] == "eq.user-123"
        return httpx.Response(200, json=[{"full_name": "Taimoor Ahmed"}])

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_async_client(transport=transport, **kwargs))

    async def lookup():
        client = SupabaseFitTrackClient(SupabaseSettings(url="https://example.supabase.co", service_role_key="service-key"))
        assert await client.get_profile_full_name("user-123") == "Taimoor Ahmed"

    anyio.run(lookup)


def test_get_meals_defaults_to_nonzero_calories(monkeypatch):
    async def handler(request):
        assert request.url.path == "/rest/v1/fittrack_meals"
        assert request.url.params["select"] == "id,date,time,food,calories"
        assert request.url.params["user_id"] == "eq.user-123"
        assert request.url.params["date"] == "eq.2026-01-03"
        assert request.url.params.get_list("calories") == ["gt.0"]
        assert request.url.params["order"] == "time.asc"
        return httpx.Response(200, json=[{"food": "Fried Eggs", "calories": 580}])

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_async_client(transport=transport, **kwargs))

    async def lookup():
        client = SupabaseFitTrackClient(SupabaseSettings(url="https://example.supabase.co", service_role_key="service-key"))
        rows = await client.get_meals("user-123", meal_date="2026-01-03")
        assert rows == [{"food": "Fried Eggs", "calories": 580}]

    anyio.run(lookup)


def test_get_meals_filters_calorie_range_when_provided(monkeypatch):
    async def handler(request):
        assert request.url.params.get_list("calories") == ["gte.500", "lte.700"]
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_async_client(transport=transport, **kwargs))

    async def lookup():
        client = SupabaseFitTrackClient(SupabaseSettings(url="https://example.supabase.co", service_role_key="service-key"))
        assert await client.get_meals("user-123", meal_date="2026-01-03", calories_min=500, calories_max=700) == []

    anyio.run(lookup)


def test_get_sleep_routine_defaults_to_nonzero_hours(monkeypatch):
    async def handler(request):
        assert request.url.path == "/rest/v1/fittrack_sleep_routine"
        assert request.url.params["select"] == "id,date,hours,notes"
        assert request.url.params["user_id"] == "eq.user-123"
        assert request.url.params["date"] == "eq.2026-02-23"
        assert request.url.params.get_list("hours") == ["gt.0"]
        assert request.url.params["order"] == "date.desc"
        return httpx.Response(200, json=[{"date": "2026-02-23", "hours": 8, "notes": None}])

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_async_client(transport=transport, **kwargs))

    async def lookup():
        client = SupabaseFitTrackClient(SupabaseSettings(url="https://example.supabase.co", service_role_key="service-key"))
        rows = await client.get_sleep_routine("user-123", sleep_date="2026-02-23")
        assert rows == [{"date": "2026-02-23", "hours": 8, "notes": None}]

    anyio.run(lookup)


def test_get_sleep_routine_filters_hour_range_when_provided(monkeypatch):
    async def handler(request):
        assert request.url.params.get_list("hours") == ["gte.7.5", "lte.8.5"]
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_async_client(transport=transport, **kwargs))

    async def lookup():
        client = SupabaseFitTrackClient(SupabaseSettings(url="https://example.supabase.co", service_role_key="service-key"))
        assert await client.get_sleep_routine("user-123", sleep_date="2026-02-23", hours_min=7.5, hours_max=8.5) == []

    anyio.run(lookup)
