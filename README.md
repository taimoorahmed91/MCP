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

Phases 0 through 2 are complete for the fake-data MCP server.

The server runs over Streamable HTTP, validates a Bearer token from the
`Authorization` header, exposes two placeholder tools, and has been successfully
called from Claude through the public MCP connector.

The next major step is Phase 3: replace the hardcoded token fingerprint and fake
responses with Supabase-backed token lookup and real FitTrack data.

## Planned Phases

| Phase | Goal | Status |
| --- | --- | --- |
| 0 | Local Streamable HTTP MCP server with fake responses and token checking | Complete |
| 1 | Public HTTPS deployment with fake responses | Complete |
| 2 | Online testing with Claude using the public MCP connector | Complete |
| 3 | Supabase-backed token lookup and real FitTrack data | Not started |
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

For clients that specifically need stdio instead of HTTP, use:

```bash
uv run fittrack-mcp-stdio
```

The Phase 0 MCP tools are:

- `recent_workouts`
- `today_nutrition`

The token is not a tool argument. Every MCP request must include this HTTP
header:

```text
Authorization: Bearer <token>
```

Wrong or missing authorization headers return:

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

Use the local Phase 0 development token as an `Authorization: Bearer ...`
header while testing Phase 1. Keep that token outside Git.

The deployment entrypoint is [app.py](app.py), which exposes the MCP server as
an ASGI app for Vercel.

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
tool, send the Bearer token, and receive a tool response. The data is still
demo data until Phase 3 connects Supabase.

## Phase 3 Next Step

Phase 3 should replace the local hardcoded token fingerprint with a Supabase
lookup:

- read `Authorization: Bearer <token>` from each request;
- hash the token with SHA-256;
- look up the fingerprint in the FitTrack token table;
- reject missing, wrong, expired, or revoked tokens;
- use the resolved user ID to scope every FitTrack data query;
- replace placeholder tool responses with real Supabase data.

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
