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
`Authorization` header, and has been successfully called from Claude Desktop
through `mcp-remote`.

The current Phase 3A code resolves real app-generated tokens through Supabase
and adds a `get_user` tool that returns the authenticated user's `full_name`
from the `profiles` table. Phase 3B has started with a real `get_meals` tool
backed by the `fittrack_meals` table and a real `sleep_routine` tool backed by
the `fittrack_sleep_routine` table. The workout and nutrition tools still
return placeholder data.

## Planned Phases

| Phase | Goal | Status |
| --- | --- | --- |
| 0 | Local Streamable HTTP MCP server with fake responses and token checking | Complete |
| 1 | Public HTTPS deployment with fake responses | Complete |
| 2 | Online testing with Claude using the public MCP connector | Complete |
| 3A | Supabase-backed token lookup and `get_user` profile lookup | Implemented |
| 3B | Replace placeholder workout/nutrition responses with real FitTrack data | Started with real `get_meals` and `sleep_routine` |
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
- `get_meals`
- `sleep_routine`
- `recent_workouts`
- `today_nutrition`

The token is not a tool argument. MCP tool-call requests must include this HTTP
header:

```text
Authorization: Bearer <token>
```

Wrong or missing authorization headers on tool calls return a JSON-RPC error:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32001,
    "message": "authentication failed"
  }
}
```

The server deliberately avoids returning HTTP `401` for MCP tool-call auth
failures because some MCP clients interpret `401` as a signal to start an OAuth
flow. FitTrack MCP uses the custom `Authorization: Bearer <token>` header
instead.

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

Deployed mode also uses JSON responses for MCP POST requests. This is friendlier
for Vercel and browser-based tools such as MCP Inspector than holding each POST
open as an event stream.

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

## Claude Desktop Setup

Claude Desktop connects to remote MCP servers through a local stdio bridge. For
this project, the bridge is `mcp-remote`.

The working Claude Desktop configuration is:

```json
{
  "mcpServers": {
    "fittrack": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote@latest",
        "https://mcp-khaki-two.vercel.app/mcp",
        "--transport",
        "http-only",
        "--header",
        "Authorization:${FITTRACK_AUTH_HEADER}",
        "--debug"
      ],
      "env": {
        "FITTRACK_AUTH_HEADER": "Bearer <real-app-generated-token>"
      }
    }
  }
}
```

Replace `<real-app-generated-token>` with the same FitTrack token that works in
MCP Inspector or `/debug-auth`.

Important details:

- use `mcp-remote@latest` so Claude Desktop always runs the current bridge;
- use `--transport http-only` so `mcp-remote` stays on Streamable HTTP;
- pass the token as an environment variable so the required space in
  `Bearer <token>` is preserved;
- keep the header argument as `Authorization:${FITTRACK_AUTH_HEADER}`;
- keep `--debug` enabled while diagnosing Claude Desktop connection issues.

After editing Claude Desktop's config file, fully quit and reopen Claude
Desktop. A normal window close is not always enough for Claude to reload MCP
configuration.

On macOS, Claude Desktop logs can be watched with:

```bash
tail -n 80 -F ~/Library/Logs/Claude/mcp*.log
```

`mcp-remote` debug logs are written under:

```text
~/.mcp-auth/
```

To find the newest debug log:

```bash
ls -lt ~/.mcp-auth/*debug.log | head
```

To read the newest debug log:

```bash
tail -n 120 ~/.mcp-auth/*debug.log
```

If Claude Desktop keeps using stale auth state, clear the local bridge cache and
restart Claude Desktop:

```bash
rm -rf ~/.mcp-auth
```

Do this only when you are ready to reconnect the MCP server and re-create the
local `mcp-remote` state.

## Vercel Hosting Notes

The current deployment is hosted on Vercel at:

```text
https://mcp-khaki-two.vercel.app/mcp
```

Vercel can run this project well enough for the current Claude Desktop setup,
but there is an important platform caveat.

Streamable HTTP includes a long-lived `GET /mcp` request for server-sent events.
Claude Desktop, through `mcp-remote`, may keep that request open in the
background. Vercel's Python serverless runtime eventually kills long-running
requests. In Vercel logs this appears as:

```text
Vercel Runtime Timeout Error: Task timed out after 300 seconds
requestMethod: GET
requestPath: /mcp
responseStatusCode: 200
```

This timeout means Vercel killed the open stream. It does not automatically mean
the Bearer token is wrong or that Supabase failed.

The current mitigation is the Claude Desktop config above:

- `mcp-remote@latest`
- `--transport http-only`
- token passed through `FITTRACK_AUTH_HEADER`
- `--debug` enabled

If this becomes unreliable in daily use, move the same app to a host that is
designed for long-lived HTTP connections, such as Railway, Render, Fly.io, Cloud
Run, or a small VPS.

## MCP Inspector

Use these MCP Inspector settings:

- Transport Type: `Streamable HTTP`
- URL: `https://<your-vercel-project>.vercel.app/mcp`
- Connection Type: `Direct`
- Custom header name: `Authorization`
- Custom header value: `Bearer <real-app-generated-token>`

The Vercel ASGI app includes CORS support so browser-based direct connections
can send the `Authorization` header.

Inspector is useful for proving that the server, Bearer token, Supabase lookup,
and tool schemas work. Claude Desktop is the more important end-to-end test
because it adds the `mcp-remote` bridge and a persistent background connection.

## Auth Debugging

If `get_user` returns `MCP error -32001: authentication failed`, test the same
Bearer token against:

```text
https://<your-vercel-project>.vercel.app/debug-auth
```

Send the same header:

```text
Authorization: Bearer <real-app-generated-token>
```

The response does not expose the token or service role key. It reports which
stage failed: missing header, missing Supabase environment variables, Supabase
HTTP/network error, token hash not found, expired token row, or authenticated
user ID.

A successful debug response looks like:

```json
{
  "ok": true,
  "stage": "authenticated",
  "user_id": "cf439197-c0cf-487d-936f-fe289a68bb41"
}
```

If `/debug-auth` succeeds but Claude Desktop fails, look at the Claude Desktop
and `mcp-remote` logs before changing server code. That usually means the issue
is in the client bridge, cached auth state, or hosting connection behavior.

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

Phase 3B has started with `get_meals` and `sleep_routine`.

The `get_meals` tool reads from `fittrack_meals`, scoped to the `user_id`
resolved from the Bearer token. It accepts optional inputs:

- `date`: `YYYY-MM-DD`; defaults to today's date when omitted.
- `calories_min`: positive integer lower bound.
- `calories_max`: positive integer upper bound.

When no calorie range is provided, it defaults to `calories > 0`.

It returns meal rows with:

- `id`
- `date`
- `time`
- `food`
- `calories`

Claude Desktop has successfully called `get_meals` through the deployed Vercel
MCP server and returned real meals for June 27:

| Time | Food | Calories |
| --- | --- | --- |
| 09:20 | 200g banana, 150ml milk, 2 tsp sugar | 240 |
| 12:06 | 2 scoops whey | 292 |
| 12:45 | 3 boiled eggs, 4 toast, 2 tsp mayo | 570 |
| 19:40 | 300g chicken breast, 120g roti, 50g yogurt | 695 |

Total returned calories: `1,797`.

## Sleep Routine Tool

The `sleep_routine` tool reads from `fittrack_sleep_routine`, scoped to the
`user_id` resolved from the Bearer token. It accepts optional inputs:

- `date`: `YYYY-MM-DD`; defaults to today's date when omitted.
- `hours_min`: positive number lower bound, allowing decimals such as `7.5`.
- `hours_max`: positive number upper bound, allowing decimals such as `8.5`.

When no sleep-hours range is provided, it defaults to `hours > 0`.

It returns sleep routine rows with:

- `id`
- `date`
- `hours`
- `notes`

The tool is described to clients as:

```text
Returns sleep routine entries for the authenticated FitTrack user. Optional inputs: date as YYYY-MM-DD, hours_min, and hours_max. If date is omitted, today's date is used. If no sleep-hours range is provided, only entries with hours greater than zero are returned.
```

Remaining Phase 3B work: replace the placeholder workout and nutrition tools
with real Supabase-backed queries.

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
