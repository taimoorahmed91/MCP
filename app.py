"""Vercel ASGI entrypoint for the FitTrack MCP server."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fittrack_mcp.server import build_asgi_app  # noqa: E402


app = build_asgi_app()
