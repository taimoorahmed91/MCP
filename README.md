# FitTrack MCP Server

This project contains a Model Context Protocol (MCP) server for FitTrack.
The server will let an AI assistant, such as Claude, answer questions about a
user's FitTrack data after the user provides a short-lived personal access
token generated inside the FitTrack app.

The detailed build plan lives in [plan.txt](plan.txt).

## Purpose

The MCP server is a separate service from the FitTrack web app. It will:

- receive requests from an MCP-compatible AI assistant;
- validate the user's FitTrack access token on every request;
- resolve that token to exactly one FitTrack user;
- read only that user's data from Supabase;
- expose safe, focused tools for fitness questions and logging.

The FitTrack web app is not called directly by this server. Both the web app
and this server read from the same Supabase database.

## Current Status

Phases 0 through 2 are complete, and Phase 3 Sub-step A is implemented.

The server runs over Streamable HTTP, validates a Bearer token from the
`Authorization` header, and has been successfully called from Claude through
the public MCP connector.

The current Phase 3A code resolves real app-generated tokens through Supabase
and adds a `get_user` tool that returns the authenticated user's `full_name`
from the `profiles` table. The workout and nutrition tools still return
placeholder data.

## Planned Phases

| Phase | Goal | Status |
| --- | --- | --- |
| 0 | Local Streamable HTTP MCP server with fake responses and token checking | Complete |
| 1 | Public HTTPS deployment with fake responses | Complete |
| 2 | Online testing with Claude using the public MCP connector | Complete |
| 3A | Supabase-backed token lookup and `get_user` profile lookup | Implemented |
| 3B | Replace placeholder workout/nutrition responses with real FitTrack data | Not started |
| 4 | Safety review for expiry, revocation, isolation, and rate limits | Not started |
| 5 | Everyday Claude usage | Not started |

## Phase 0 Scope

Phase 0 creates the smallest useful server:

- Python project setup;
- local Streamable HTTP MCP server entry point;
- one shared token-checking checkpoint;
- one known hardcoded token fingerprint;
- fake tools such as recent workouts or today's nutrition;
- clear rejection when the token is missing or invalid.

Phase 0 should not include Supabase, hosting, real user data, Google login, or
production secrets.

## Running Locally

Install dependencies:

```bash
uv sync --extra dev
```

This project requires Python 3.10 or newer.

Run tests:

```bash
uv run pytest
```

Start the local MCP server over Streamable HTTP:

```bash
uv run fittrack-mcp
```

Keep that command running while an MCP client connects.

The local MCP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

The connector registration handshake endpoint is:

```text
http://127.0.0.1:8000/register
```

`POST /register` is intentionally allowed without a Bearer token. Tool calls
and other MCP requests still require `Authorization: Bearer <token>`.

On Vercel, `/register` is routed to a standalone function at
[api/register.py](api/register.py) so it cannot be intercepted by the MCP Bearer
token middleware.

For clients that specifically need stdio instead of HTTP, use:

```bash
uv run fittrack-mcp-stdio
```

The MCP tools are:

- `get_user`
- `recent_workouts`
- `today_nutrition`

The token is not a tool argument. MCP tool-call requests must include this HTTP
header:

```text
Authorization: Bearer <token>
```

Wrong or missing authorization headers on tool calls return:

```json
{
  "error": "authentication failed"
}
```

## Phase 1 Deployment

Phase 1 deploys the same fake-data MCP server to a public HTTPS URL.

Deploy with Vercel:

```bash
vercel
```

After deployment, the MCP endpoint should be:

```text
https://<your-vercel-project>.vercel.app/mcp
```

Use a real app-generated FitTrack token as an `Authorization: Bearer ...`
header once the Supabase environment variables are configured.

The deployment entrypoint is [app.py](app.py), which exposes the MCP server as
an ASGI app for Vercel.

For Vercel, the deployed ASGI app explicitly starts FastMCP's Streamable HTTP
session manager around each serverless request. This avoids `POST /mcp` crashes
when the platform does not run Starlette lifespan startup before invoking the
function.

## Claude Code Setup

This server uses custom Bearer-token authentication, not OAuth. Add it to Claude
Code with the token header configured up front:

```bash
claude mcp add --transport http fittrack https://<your-vercel-project>.vercel.app/mcp \
  --header "Authorization: Bearer <real-app-generated-token>"
```

If the FitTrack token expires, remove and re-add the server with a fresh token,
or configure Claude Code with a `headersHelper` that prints:

```json
{"Authorization": "Bearer <real-app-generated-token>"}
```

Do not rely on `/mcp` OAuth authentication for this server. `/register` is
allowed for connector compatibility, but it is not a full OAuth dynamic client
registration flow.

## MCP Inspector

Use these MCP Inspector settings:

- Transport Type: `Streamable HTTP`
- URL: `https://<your-vercel-project>.vercel.app/mcp`
- Connection Type: `Direct`
- Custom header name: `Authorization`
- Custom header value: `Bearer <real-app-generated-token>`

The Vercel ASGI app includes CORS support so browser-based direct connections
can send the `Authorization` header.

## Environment Variables

These Phase 3A variables have been added in Vercel:

| Variable | Vercel status | Value |
| --- | --- | --- |
| `SUPABASE_URL` | Added | `https://nywsjgxlnilmcztnvidc.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Added | Stored only in Vercel, not committed |

The service role key must only be stored in the deployment environment. Do not
commit it to Git.

## Phase 2 Claude Test

Claude has successfully connected to the public MCP server and used the
`recent_workouts` tool from a plain-language request:

```text
get my recent workout
```

The response returned the expected Phase 0 placeholder workouts:

- 2026-06-24 strength workout;
- 2026-06-22 easy run;
- 2026-06-20 mobility session.

This confirms the connector can load the server, discover the tools, choose a
tool, send the Bearer token, and receive a tool response.

## Phase 3A

Phase 3A replaces the local hardcoded token fingerprint with a Supabase lookup:

- read `Authorization: Bearer <token>` from each request;
- hash the token with SHA-256;
- look up the fingerprint in `fittrack_api_tokens.token_hash`;
- require `fittrack_api_tokens.expires_at` to be later than the current time;
- reject missing, wrong, expired, or revoked tokens;
- use the resolved `user_id` to query `profiles.id`;
- return `profiles.full_name` from the `get_user` tool.

The `get_user` tool has no inputs and is described to clients as:

```text
Returns the full name of the authenticated FitTrack user. No inputs required.
```

## Phase 3B Next Step

Phase 3B should replace the placeholder workout and nutrition responses with
real Supabase data, scoped to the `user_id` resolved from the Bearer token.

## Security Principles

- The token is the identity.
- The assistant never gets to claim which user it is acting for.
- Every request is authenticated independently.
- Token checking happens in one shared place.
- Real tokens should never be stored directly, only their one-way fingerprints.
- Once Supabase is connected, every data query must be scoped to the user
  resolved from the token.

## Notes

The intended implementation language is Python, using the standard MCP toolkit.
Hosting is expected to start with Vercel, with Railway or Render as fallback
options if the server shape fits those platforms better.
