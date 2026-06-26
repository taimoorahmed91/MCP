"""MCP entry points for the FitTrack server."""

from __future__ import annotations

from .http_auth import AuthorizationHeaderMiddleware
from .tools import get_recent_workouts, get_today_nutrition


SERVER_NAME = "FitTrack MCP Server"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEPLOYED_HOST = "0.0.0.0"
MCP_PATH = "/mcp"


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

    return AuthorizationHeaderMiddleware(build_server(deployed=True).streamable_http_app())


def build_local_asgi_app():
    """Build the local ASGI app with the same header authentication."""

    return AuthorizationHeaderMiddleware(build_server().streamable_http_app())


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
