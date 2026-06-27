import anyio
import httpx
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from fittrack_mcp.auth import AuthenticatedUser
from fittrack_mcp.http_auth import AuthorizationHeaderMiddleware
from fittrack_mcp.server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEPLOYED_HOST,
    MCP_PATH,
    build_asgi_app,
    build_local_asgi_app,
    build_server,
)


def test_server_defaults_to_local_streamable_http_settings():
    server = build_server()

    assert server.settings.host == DEFAULT_HOST
    assert server.settings.port == DEFAULT_PORT
    assert server.settings.streamable_http_path == MCP_PATH


def test_deployed_server_uses_stateless_http():
    server = build_server(deployed=True)

    assert server.settings.host == DEPLOYED_HOST
    assert server.settings.streamable_http_path == MCP_PATH
    assert server.settings.stateless_http is True


def test_asgi_app_builds_for_deployment():
    app = build_asgi_app()

    assert app is not None


def test_local_asgi_app_uses_authorization_middleware():
    app = build_local_asgi_app()

    assert isinstance(app, AuthorizationHeaderMiddleware)


def test_tools_do_not_expose_token_parameter():
    async def check_tools():
        tools = await build_server().list_tools()
        input_schemas = {tool.name: tool.inputSchema for tool in tools}
        descriptions = {tool.name: tool.description for tool in tools}

        assert input_schemas["get_user"]["properties"] == {}
        assert descriptions["get_user"] == "Returns the full name of the authenticated FitTrack user. No inputs required."
        assert "token" not in input_schemas["recent_workouts"]["properties"]
        assert "token" not in input_schemas["today_nutrition"]["properties"]

    anyio.run(check_tools)


def test_asgi_app_rejects_missing_authorization_header():
    async def request_without_header():
        transport = httpx.ASGITransport(app=build_asgi_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(MCP_PATH)

        assert response.status_code == 401
        assert response.json() == {"error": "authentication failed"}

    anyio.run(request_without_header)


def test_authorization_middleware_skips_register_path():
    async def inner_app(scope, receive, send):
        response = JSONResponse({"ok": True, "path": scope["path"]})
        await response(scope, receive, send)

    async def request_register_without_header():
        transport = httpx.ASGITransport(app=AuthorizationHeaderMiddleware(inner_app))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post("/register")

        assert response.status_code == 200
        assert response.json() == {"ok": True, "path": "/register"}

    anyio.run(request_register_without_header)


def test_asgi_app_rejects_wrong_authorization_header():
    async def request_with_wrong_header():
        transport = httpx.ASGITransport(app=build_asgi_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(MCP_PATH, headers={"Authorization": "Bearer wrong-token"})

        assert response.status_code == 401
        assert response.json() == {"error": "authentication failed"}

    anyio.run(request_with_wrong_header)


def test_asgi_app_allows_valid_authorization_header(monkeypatch):
    class FakeFitTrackClient:
        async def resolve_token(self, token):
            assert token == "unit-test-token"
            return AuthenticatedUser(user_id="user-123")

    app = AuthorizationHeaderMiddleware(
        build_server(deployed=True).streamable_http_app(),
        fittrack_client=FakeFitTrackClient(),
    )

    with TestClient(app) as client:
        response = client.get(MCP_PATH, headers={"Authorization": "Bearer unit-test-token"})

    assert response.status_code == 406
    assert "Client must accept text/event-stream" in response.text
