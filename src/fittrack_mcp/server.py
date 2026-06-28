"""MCP entry points for the FitTrack server."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
import httpx
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from .http_auth import AuthorizationHeaderMiddleware
from .auth import AuthenticationError, extract_bearer_token, fingerprint_token
from .register import build_registration_response
from .supabase_client import SupabaseConfigError, SupabaseFitTrackClient, TokenLookupError
from .tools import (
    get_authenticated_user_full_name,
    get_authenticated_user_meals,
    get_authenticated_user_sleep_routine,
)


SERVER_NAME = "FitTrack MCP Server"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEPLOYED_HOST = "0.0.0.0"
MCP_PATH = "/mcp"
REGISTER_PATH = "/register"
DEBUG_AUTH_PATH = "/debug-auth"


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
        json_response=deployed,
    )

    @mcp.tool()
    async def get_user() -> str:
        """Returns the full name of the authenticated FitTrack user. No inputs required."""

        return await get_authenticated_user_full_name()

    @mcp.tool()
    async def get_meals(
        date: str | None = None,
        calories_min: int | None = None,
        calories_max: int | None = None,
    ) -> list[dict]:
        """Returns meals for the authenticated FitTrack user. Optional inputs: date as YYYY-MM-DD, calories_min, and calories_max. If date is omitted, today's date is used. If no calorie range is provided, only meals with calories greater than zero are returned."""

        return await get_authenticated_user_meals(
            date=date,
            calories_min=calories_min,
            calories_max=calories_max,
        )

    @mcp.tool()
    async def get_sleep(
        date: str | None = None,
        hours_min: float | None = None,
        hours_max: float | None = None,
    ) -> list[dict]:
        """Returns sleep entries for the authenticated FitTrack user. Optional inputs: date as YYYY-MM-DD, hours_min, and hours_max. If date is omitted, today's date is used. If no sleep-hours range is provided, only entries with hours greater than zero are returned."""

        return await get_authenticated_user_sleep_routine(
            date=date,
            hours_min=hours_min,
            hours_max=hours_max,
        )

    return mcp


def build_asgi_app():
    """Build the ASGI app used by HTTPS hosting providers."""

    return with_cors(VercelMCPApp())


def build_local_asgi_app():
    """Build the local ASGI app with the same header authentication."""

    return with_cors(RequestScopedMCPApp(deployed=True))


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
        app = RequestScopedMCPApp(deployed=True)
        await app(scope, receive, send)


class RequestScopedMCPApp:
    """ASGI app that starts FastMCP's session manager around each request."""

    def __init__(self, *, deployed: bool):
        self.deployed = deployed

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            response = Response(status_code=404)
            await response(scope, receive, send)
            return

        if scope.get("path") == REGISTER_PATH:
            await register_request(scope, receive, send)
            return

        if scope.get("path") == DEBUG_AUTH_PATH:
            await debug_auth_request(scope, receive, send)
            return

        mcp = build_server(deployed=self.deployed)
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

    try:
        request_body = await request.json()
    except Exception:
        request_body = {}

    return JSONResponse(build_registration_response(request_body), status_code=200)


async def register_request(scope, receive, send):
    """ASGI-compatible registration handler for deployed app fallbacks."""

    if scope.get("method") == "OPTIONS":
        response = Response(status_code=200)
    else:
        response = JSONResponse(build_registration_response(), status_code=200)

    await response(scope, receive, send)


async def debug_auth_request(scope, receive, send):
    """Return safe diagnostics for the current Authorization header."""

    try:
        authorization = _get_header(scope, "authorization")
        token = extract_bearer_token(authorization)
    except AuthenticationError:
        response = JSONResponse(
            {
                "ok": False,
                "stage": "authorization_header",
                "message": "Missing or invalid Authorization: Bearer header.",
            },
            status_code=200,
        )
        await response(scope, receive, send)
        return

    try:
        client = SupabaseFitTrackClient()
    except SupabaseConfigError:
        response = JSONResponse(
            {
                "ok": False,
                "stage": "environment",
                "message": "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing.",
            },
            status_code=200,
        )
        await response(scope, receive, send)
        return

    try:
        user = await client.resolve_token(token)
    except TokenLookupError:
        rows = await _safe_debug_rows(client, token)
        if rows:
            message = "Token hash exists, but no unexpired token row matched."
            expires_at = rows[0].get("expires_at")
        else:
            message = "Token hash was not found in fittrack_api_tokens."
            expires_at = None

        response = JSONResponse(
            {
                "ok": False,
                "stage": "token_lookup",
                "message": message,
                "expires_at": expires_at,
            },
            status_code=200,
        )
        await response(scope, receive, send)
        return
    except httpx.HTTPStatusError as exc:
        response = JSONResponse(
            {
                "ok": False,
                "stage": "supabase_http",
                "status_code": exc.response.status_code,
                "message": "Supabase rejected the request.",
            },
            status_code=200,
        )
        await response(scope, receive, send)
        return
    except httpx.RequestError:
        response = JSONResponse(
            {
                "ok": False,
                "stage": "supabase_network",
                "message": "Could not reach Supabase.",
            },
            status_code=200,
        )
        await response(scope, receive, send)
        return

    response = JSONResponse(
        {
            "ok": True,
            "stage": "authenticated",
            "user_id": user.user_id,
        },
        status_code=200,
    )
    await response(scope, receive, send)


async def _safe_debug_rows(client: SupabaseFitTrackClient, token: str):
    try:
        return await client.debug_token_hash_lookup(fingerprint_token(token))
    except Exception:
        return []


def _get_header(scope, name: str) -> str | None:
    wanted = name.lower().encode("latin-1")
    for key, value in scope.get("headers", []):
        if key.lower() == wanted:
            return value.decode("latin-1")
    return None


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
