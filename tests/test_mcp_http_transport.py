"""HTTP MCP transport: stdio default, fail-closed token, bind, Bearer 401."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from starlette.testclient import TestClient

from grok_search.mcp_transport import (
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PATH,
    DEFAULT_HTTP_PORT,
    McpHttpConfigError,
    apply_http_auth,
    require_http_token,
    resolve_http_bind,
    resolve_run_settings,
    resolve_transport,
)
from grok_search.server import mcp

PLUGIN_DIR = Path(__file__).resolve().parents[1] / "cursor-plugin"

pytestmark = pytest.mark.filterwarnings(
    "ignore:Using `httpx` with `starlette.testclient` is deprecated"
)


def test_default_transport_is_stdio():
    assert resolve_transport({}) == "stdio"


def test_explicit_stdio_does_not_require_token():
    settings = resolve_run_settings(
        {
            "GROK_SEARCH_MCP_TRANSPORT": "stdio",
            "GROK_SEARCH_MCP_TOKEN": "unused-for-stdio",
        }
    )
    assert settings.transport == "stdio"
    assert settings.token is None
    assert settings.host is None


def test_http_without_token_fails_closed():
    with pytest.raises(McpHttpConfigError, match="GROK_SEARCH_MCP_TOKEN"):
        require_http_token({"GROK_SEARCH_MCP_TRANSPORT": "http"})


def test_http_without_token_does_not_fall_back_to_foreign_keys():
    environ = {
        "GROK_SEARCH_MCP_TRANSPORT": "http",
        "GUDA_API_KEY": "guda-should-not-work",
        "GROK_API_KEY": "grok-should-not-work",
        "TAVILY_API_KEY": "tavily-should-not-work",
        "FIRECRAWL_API_KEY": "firecrawl-should-not-work",
    }
    with pytest.raises(McpHttpConfigError, match="GROK_SEARCH_MCP_TOKEN"):
        resolve_run_settings(environ)


def test_http_empty_token_fails_closed():
    with pytest.raises(McpHttpConfigError, match="GROK_SEARCH_MCP_TOKEN"):
        resolve_run_settings(
            {
                "GROK_SEARCH_MCP_TRANSPORT": "http",
                "GROK_SEARCH_MCP_TOKEN": "   ",
            }
        )


def test_http_bind_defaults():
    bind = resolve_http_bind({})
    assert bind.host == DEFAULT_HTTP_HOST == "127.0.0.1"
    assert bind.port == DEFAULT_HTTP_PORT == 8800
    assert bind.path == DEFAULT_HTTP_PATH == "/mcp"
    assert bind.host != "0.0.0.0"
    assert bind.port not in {80, 8080, 6080}


def test_http_bind_custom_host_port_path():
    bind = resolve_http_bind(
        {
            "GROK_SEARCH_MCP_HOST": "127.0.0.1",
            "GROK_SEARCH_MCP_PORT": "8801",
            "GROK_SEARCH_MCP_PATH": "mcp-v2",
        }
    )
    assert bind.host == "127.0.0.1"
    assert bind.port == 8801
    assert bind.path == "/mcp-v2"


def test_http_run_settings_include_token_and_bind():
    settings = resolve_run_settings(
        {
            "GROK_SEARCH_MCP_TRANSPORT": "http",
            "GROK_SEARCH_MCP_TOKEN": "loopback-test-token",
            "GROK_SEARCH_MCP_PORT": "8800",
        }
    )
    assert settings.transport == "http"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8800
    assert settings.path == "/mcp"
    assert settings.token == "loopback-test-token"


def test_invalid_transport_rejected():
    with pytest.raises(McpHttpConfigError, match="stdio"):
        resolve_transport({"GROK_SEARCH_MCP_TRANSPORT": "sse"})


def test_cursor_plugin_is_local_type_http_example():
    plugin = json.loads((PLUGIN_DIR / ".cursor-plugin" / "plugin.json").read_text())
    mcp_cfg = json.loads((PLUGIN_DIR / "mcp.json").read_text())
    assert plugin["mcpServers"] == "./mcp.json"
    assert plugin["variables"]["required"] == ["GROK_SEARCH_MCP_TOKEN"]
    server = mcp_cfg["mcpServers"]["grok-search"]
    assert server["type"] == "http"
    assert server["url"] == "http://127.0.0.1:8800/mcp"
    assert server["headers"]["Authorization"] == "Bearer ${GROK_SEARCH_MCP_TOKEN}"
    dumped = json.dumps(plugin) + json.dumps(mcp_cfg)
    assert "gsk_" not in dumped
    assert "sk-" not in dumped
    assert "marketplace" not in dumped.lower()


def _mcp_app(token: str):
    previous = getattr(mcp, "auth", None)
    apply_http_auth(mcp, token)
    app = mcp.http_app(path="/mcp", transport="http")
    return app, previous


MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "MCP-Protocol-Version": "2025-03-26",
}

INITIALIZE_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "grok-search-tests", "version": "0.1.0"},
    },
}

TOOLS_LIST_BODY = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {},
}


def _decode_mcp_response(response: httpx.Response) -> dict:
    ctype = response.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        data_lines = [
            line[5:].strip()
            for line in response.text.splitlines()
            if line.startswith("data:")
        ]
        assert data_lines, response.text
        return json.loads(data_lines[-1])
    return response.json()


def test_http_initialize_and_list_tools_with_bearer():
    token = "unit-http-mcp-token"
    app, previous = _mcp_app(token)
    try:
        with TestClient(app) as client:
            init = client.post(
                "/mcp",
                json=INITIALIZE_BODY,
                headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"},
            )
            assert init.status_code == 200, init.text
            init_payload = _decode_mcp_response(init)
            assert init_payload.get("result", {}).get("serverInfo", {}).get("name") == "grok-search"
            session = init.headers.get("mcp-session-id")
            headers = {**MCP_HEADERS, "Authorization": f"Bearer {token}"}
            if session:
                headers["Mcp-Session-Id"] = session
            listed = client.post("/mcp", json=TOOLS_LIST_BODY, headers=headers)
            assert listed.status_code == 200, listed.text
            tools_payload = _decode_mcp_response(listed)
            names = {t["name"] for t in tools_payload["result"]["tools"]}
            assert "web_search" in names
            assert "get_sources" in names
    finally:
        mcp.auth = previous


def test_http_initialize_without_bearer_is_401():
    token = "unit-http-mcp-token"
    app, previous = _mcp_app(token)
    try:
        with TestClient(app) as client:
            missing = client.post("/mcp", json=INITIALIZE_BODY, headers=MCP_HEADERS)
            assert missing.status_code == 401
            wrong = client.post(
                "/mcp",
                json=INITIALIZE_BODY,
                headers={**MCP_HEADERS, "Authorization": "Bearer wrong-token"},
            )
            assert wrong.status_code == 401
    finally:
        mcp.auth = previous
