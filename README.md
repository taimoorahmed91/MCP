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

Phase 0 is implemented as a local Python MCP server over Streamable HTTP, with
fake data and hardcoded token validation.

## Planned Phases

| Phase | Goal | Status |
| --- | --- | --- |
| 0 | Local Streamable HTTP MCP server with fake responses and token checking | Implemented |
| 1 | Public deployment with fake responses | Ready to deploy |
| 2 | Online testing with MCP Inspector and a real assistant | Not started |
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

## Phase 0 Development Token

Use this local-only token when testing Phase 0:

```text
fittrack_phase0_dev_token
```

The code stores only this token's SHA-256 fingerprint:

```text
8d7290a9091a2b494e899f7e3ae5281a75eb243b05dcb619917049ad82fe2345
```

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

Both tools require the `token` argument. Wrong or missing tokens return:

```json
{
  "ok": false,
  "error": "authentication failed"
}
```

## Deploying Phase 1

Phase 1 deploys the same fake-data MCP server to a public HTTPS URL.

Deploy with Vercel:

```bash
vercel
```

After deployment, the MCP endpoint should be:

```text
https://<your-vercel-project>.vercel.app/mcp
```

Use the same Phase 0 development token while testing Phase 1:

```text
fittrack_phase0_dev_token
```

The deployment entrypoint is [app.py](app.py), which exposes the MCP server as
an ASGI app for Vercel.

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
