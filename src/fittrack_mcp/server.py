"""MCP entry points for the FitTrack server."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from .http_auth import AuthorizationHeaderMiddleware
from .tools import get_authenticated_user_full_name, get_recent_workouts, get_today_nutrition


SERVER_NAME = "FitTrack MCP Server"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEPLOYED_HOST = "0.0.0.0"
MCP_PATH = "/mcp"
REGISTER_PATH = "/register"


def build_server(*, deployed: bool = False):
    """Build the MCP server.

    Importing MCP lazily keeps the core auth and tool behavior testable even
    before the dependency has been installed in a fresh checkout.
    """

    try:
        from mcp.server.fastmcp import FastMCP
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The 'mcp' package is not installed. Run 'uv sync --extra dev' "
            "or install the project dependencies before starting the server."
        ) from exc

    mcp = FastMCP(
        SERVER_NAME,
        host=DEPLOYED_HOST if deployed else DEFAULT_HOST,
        port=DEFAULT_PORT,
        streamable_http_path=MCP_PATH,
        stateless_http=deployed,
    )

    @mcp.tool()
    async def get_user() -> str:
        """Returns the full name of the authenticated FitTrack user. No inputs required."""

        return await get_authenticated_user_full_name()

    @mcp.tool()
    def recent_workouts(limit: int = 5) -> dict:
        """Get recent FitTrack workouts for the token's user.

        Phase 0 returns fake data.
        """

        return get_recent_workouts(limit=limit)

    @mcp.tool()
    def today_nutrition() -> dict:
        """Get today's FitTrack nutrition summary for the token's user.

        Phase 0 returns fake data.
        """

        return get_today_nutrition()

    return mcp


def build_asgi_app():
    """Build the ASGI app used by HTTPS hosting providers."""

    return with_cors(VercelMCPApp())


def build_local_asgi_app():
    """Build the local ASGI app with the same header authentication."""

    return with_cors(build_http_app(deployed=False))


def with_cors(app):
    """Allow browser-based MCP clients such as MCP Inspector."""

    return CORSMiddleware(
        app,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
        allow_headers=["*"],
        expose_headers=["*"],
    )


def build_http_app(*, deployed: bool):
    """Build the public HTTP app with registration outside Bearer auth."""

    mcp_app = build_server(deployed=deployed).streamable_http_app()
    protected_mcp_app = AuthorizationHeaderMiddleware(mcp_app)

    return Starlette(
        routes=[
            Route(
                REGISTER_PATH,
                endpoint=register,
                methods=["POST", "OPTIONS"],
            ),
            Mount("/", app=protected_mcp_app),
        ]
    )


class VercelMCPApp:
    """ASGI app that starts FastMCP's session manager per serverless request."""

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            response = Response(status_code=404)
            await response(scope, receive, send)
            return

        if scope.get("path") == REGISTER_PATH:
            await register_request(scope, receive, send)
            return

        mcp = build_server(deployed=True)
        mcp_app = mcp.streamable_http_app()
        protected_app = AuthorizationHeaderMiddleware(mcp_app)

        async with mcp.session_manager.run():
            await protected_app(scope, receive, send)


def add_register_route(app):
    """Add the MCP connector registration handshake endpoint."""

    app.routes.append(
        Route(
            REGISTER_PATH,
            endpoint=register,
            methods=["POST", "OPTIONS"],
        )
    )


async def register(request):
    """Allow connector registration without a user Bearer token."""

    if request.method == "OPTIONS":
        return Response(status_code=200)

    return JSONResponse({"ok": True}, status_code=200)


async def register_request(scope, receive, send):
    """ASGI-compatible registration handler for deployed app fallbacks."""

    if scope.get("method") == "OPTIONS":
        response = Response(status_code=200)
    else:
        response = JSONResponse({"ok": True}, status_code=200)

    await response(scope, receive, send)


def main() -> None:
    """Run the local MCP server over Streamable HTTP."""

    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise RuntimeError("The 'uvicorn' package is required to run the HTTP server.") from exc

    uvicorn.run(build_local_asgi_app(), host=DEFAULT_HOST, port=DEFAULT_PORT)


def main_stdio() -> None:
    """Run the local MCP server over stdio."""

    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
