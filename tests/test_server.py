from fittrack_mcp.server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEPLOYED_HOST,
    MCP_PATH,
    build_asgi_app,
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
