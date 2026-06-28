import anyio
import httpx
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from fittrack_mcp.auth import AuthenticatedUser
from fittrack_mcp.http_auth import AuthorizationHeaderMiddleware
from fittrack_mcp.server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEBUG_AUTH_PATH,
    DEPLOYED_HOST,
    MCP_PATH,
    REGISTER_PATH,
    build_asgi_app,
    build_http_app,
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
    assert server.settings.json_response is True


def test_asgi_app_builds_for_deployment():
    app = build_asgi_app()

    assert app is not None


def test_local_asgi_app_uses_authorization_middleware():
    app = build_http_app(deployed=False)

    assert [route.path for route in app.routes] == [REGISTER_PATH, ""]
    assert isinstance(app.routes[1].app, AuthorizationHeaderMiddleware)


def test_asgi_app_allows_browser_preflight_for_mcp_headers():
    async def request_preflight():
        transport = httpx.ASGITransport(app=build_asgi_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.options(
                MCP_PATH,
                headers={
                    "Origin": "http://localhost:6274",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization,content-type,accept",
                },
            )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"
        assert "authorization" in response.headers["access-control-allow-headers"].lower()

    anyio.run(request_preflight)


def test_tools_do_not_expose_token_parameter():
    async def check_tools():
        tools = await build_server().list_tools()
        input_schemas = {tool.name: tool.inputSchema for tool in tools}
        descriptions = {tool.name: tool.description for tool in tools}

        assert set(input_schemas) == {"get_user", "get_meals", "get_sleep"}
        assert input_schemas["get_user"]["properties"] == {}
        assert descriptions["get_user"] == "Returns the full name of the authenticated FitTrack user. No inputs required."
        assert "date" in input_schemas["get_meals"]["properties"]
        assert "calories_min" in input_schemas["get_meals"]["properties"]
        assert "calories_max" in input_schemas["get_meals"]["properties"]
        assert "calories" not in input_schemas["get_meals"]["properties"]
        assert "date" in input_schemas["get_sleep"]["properties"]
        assert "hours_min" in input_schemas["get_sleep"]["properties"]
        assert "hours_max" in input_schemas["get_sleep"]["properties"]
        assert "token" not in input_schemas["get_sleep"]["properties"]

    anyio.run(check_tools)


def test_authorization_middleware_allows_get_without_authorization_header():
    async def inner_app(scope, receive, send):
        response = JSONResponse({"ok": True, "method": scope["method"]})
        await response(scope, receive, send)

    async def request_without_header():
        transport = httpx.ASGITransport(app=AuthorizationHeaderMiddleware(inner_app))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(MCP_PATH)

        assert response.status_code == 200
        assert response.json() == {"ok": True, "method": "GET"}

    anyio.run(request_without_header)


def test_authorization_middleware_skips_register_path():
    async def inner_app(scope, receive, send):
        response = JSONResponse({"ok": True, "path": scope["path"]})
        await response(scope, receive, send)

    async def request_register_without_header():
        transport = httpx.ASGITransport(app=AuthorizationHeaderMiddleware(inner_app))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(REGISTER_PATH)

        assert response.status_code == 200
        assert response.json() == {"ok": True, "path": REGISTER_PATH}

    anyio.run(request_register_without_header)


def test_asgi_app_register_returns_200_without_authorization_header():
    async def request_register_without_header():
        transport = httpx.ASGITransport(app=build_asgi_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(REGISTER_PATH)

        assert response.status_code == 200
        payload = response.json()
        assert isinstance(payload["client_id"], str)
        assert isinstance(payload["redirect_uris"], list)
        assert "scope" not in payload

    anyio.run(request_register_without_header)


def test_asgi_app_register_echoes_redirect_uris():
    async def request_register_without_header():
        transport = httpx.ASGITransport(app=build_asgi_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                REGISTER_PATH,
                json={"redirect_uris": ["http://localhost:6274/oauth/callback"]},
            )

        assert response.status_code == 200
        assert response.json()["redirect_uris"] == ["http://localhost:6274/oauth/callback"]

    anyio.run(request_register_without_header)


def test_asgi_app_initialize_returns_json_response_without_authorization_header():
    async def initialize():
        transport = httpx.ASGITransport(app=build_asgi_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                MCP_PATH,
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0.0.0"},
                    },
                },
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert response.json()["id"] == 1

    anyio.run(initialize)


def test_debug_auth_reports_missing_authorization_header():
    async def request_debug_auth():
        transport = httpx.ASGITransport(app=build_asgi_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get(DEBUG_AUTH_PATH)

        assert response.status_code == 200
        assert response.json()["stage"] == "authorization_header"

    anyio.run(request_debug_auth)


def test_asgi_app_rejects_tool_call_without_authorization_header():
    async def request_without_header():
        transport = httpx.ASGITransport(app=build_asgi_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                MCP_PATH,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "get_user", "arguments": {}},
                },
            )

        assert response.status_code == 200
        assert response.json() == {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32001,
                "message": "authentication failed",
            },
        }

    anyio.run(request_without_header)


def test_asgi_app_rejects_tool_call_with_wrong_authorization_header():
    async def request_with_wrong_header():
        transport = httpx.ASGITransport(app=build_asgi_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                MCP_PATH,
                headers={"Authorization": "Bearer wrong-token"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "get_user", "arguments": {}},
                },
            )

        assert response.status_code == 200
        assert response.json()["error"]["message"] == "authentication failed"

    anyio.run(request_with_wrong_header)


def test_asgi_app_allows_valid_authorization_header():
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
