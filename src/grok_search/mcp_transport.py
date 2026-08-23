"""Additive FastMCP HTTP transport settings.

stdio remains the default. HTTP binds loopback only by default and fail-closes
unless GROK_SEARCH_MCP_TOKEN is set. This token is never taken from
GUDA_API_KEY / GROK_API_KEY / TAVILY_API_KEY / FIRECRAWL_API_KEY.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Mapping

from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

Transport = Literal["stdio", "http"]

DEFAULT_TRANSPORT: Transport = "stdio"
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8800
DEFAULT_HTTP_PATH = "/mcp"

_ENV_TRANSPORT = "GROK_SEARCH_MCP_TRANSPORT"
_ENV_HOST = "GROK_SEARCH_MCP_HOST"
_ENV_PORT = "GROK_SEARCH_MCP_PORT"
_ENV_PATH = "GROK_SEARCH_MCP_PATH"
_ENV_TOKEN = "GROK_SEARCH_MCP_TOKEN"

class McpHttpConfigError(ValueError):
    """Raised when HTTP MCP is requested with an invalid or missing setup."""


@dataclass(frozen=True)
class McpHttpBind:
    host: str
    port: int
    path: str


def _env(environ: Mapping[str, str] | None, name: str, default: str | None = None) -> str | None:
    source = os.environ if environ is None else environ
    if name not in source:
        return default
    value = source[name]
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def resolve_transport(environ: Mapping[str, str] | None = None) -> Transport:
    raw = _env(environ, _ENV_TRANSPORT, DEFAULT_TRANSPORT)
    value = (raw or DEFAULT_TRANSPORT).lower()
    if value not in ("stdio", "http"):
        raise McpHttpConfigError(
            f"{_ENV_TRANSPORT} must be 'stdio' or 'http', got {raw!r}"
        )
    return value  # type: ignore[return-value]


def resolve_http_bind(environ: Mapping[str, str] | None = None) -> McpHttpBind:
    host = _env(environ, _ENV_HOST, DEFAULT_HTTP_HOST) or DEFAULT_HTTP_HOST
    port_raw = _env(environ, _ENV_PORT, str(DEFAULT_HTTP_PORT)) or str(DEFAULT_HTTP_PORT)
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise McpHttpConfigError(
            f"{_ENV_PORT} must be an integer, got {port_raw!r}"
        ) from exc
    if not (1 <= port <= 65535):
        raise McpHttpConfigError(f"{_ENV_PORT} out of range: {port}")

    path = _env(environ, _ENV_PATH, DEFAULT_HTTP_PATH) or DEFAULT_HTTP_PATH
    if not path.startswith("/"):
        path = f"/{path}"
    return McpHttpBind(host=host, port=port, path=path)


def require_http_token(environ: Mapping[str, str] | None = None) -> str:
    """Return the inbound HTTP bearer. Fail closed; never fall back to other keys."""
    token = _env(environ, _ENV_TOKEN, None)
    if not token:
        raise McpHttpConfigError(
            f"{_ENV_TOKEN} is required when {_ENV_TRANSPORT}=http "
            "(fail closed). Do not reuse GUDA_API_KEY, GROK_API_KEY, "
            "TAVILY_API_KEY, or FIRECRAWL_API_KEY."
        )
    return token


def build_static_token_verifier(token: str) -> StaticTokenVerifier:
    return StaticTokenVerifier(
        tokens={
            token: {
                "client_id": "grok-search-http",
                "scopes": ["mcp"],
            }
        }
    )


def apply_http_auth(mcp, token: str) -> StaticTokenVerifier:
    verifier = build_static_token_verifier(token)
    mcp.auth = verifier
    return verifier


@dataclass(frozen=True)
class McpRunSettings:
    transport: Transport
    host: str | None = None
    port: int | None = None
    path: str | None = None
    token: str | None = None


def resolve_run_settings(environ: Mapping[str, str] | None = None) -> McpRunSettings:
    transport = resolve_transport(environ)
    if transport == "stdio":
        return McpRunSettings(transport="stdio")
    bind = resolve_http_bind(environ)
    token = require_http_token(environ)
    return McpRunSettings(
        transport="http",
        host=bind.host,
        port=bind.port,
        path=bind.path,
        token=token,
    )


def run_mcp(mcp, settings: McpRunSettings | None = None, environ: Mapping[str, str] | None = None) -> None:
    """Start FastMCP with stdio (default) or authenticated HTTP."""
    resolved = settings if settings is not None else resolve_run_settings(environ)
    if resolved.transport == "stdio":
        mcp.run(transport="stdio", show_banner=False)
        return

    assert resolved.token is not None
    assert resolved.host is not None
    assert resolved.port is not None
    assert resolved.path is not None
    apply_http_auth(mcp, resolved.token)
    mcp.run(
        transport="http",
        show_banner=False,
        host=resolved.host,
        port=resolved.port,
        path=resolved.path,
    )
