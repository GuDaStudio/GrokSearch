# Local Cursor plugin (HTTP MCP)

In-repo example matching `cursor/plugins` `third_party/github`: `type: "http"` plus a required `GROK_SEARCH_MCP_TOKEN` variable. Not a marketplace listing.

stdio stays the default Grok Search transport. This plugin only talks to a server you start yourself on loopback.

## 1. Start the HTTP MCP on loopback

Generate a dedicated bearer (not your GuDa / Grok / Tavily / Firecrawl key):

```bash
export GROK_SEARCH_MCP_TOKEN="$(openssl rand -hex 32)"
GROK_SEARCH_MCP_TRANSPORT=http \
  GROK_SEARCH_MCP_HOST=127.0.0.1 \
  GROK_SEARCH_MCP_PORT=8800 \
  GROK_SEARCH_MCP_PATH=/mcp \
  GROK_SEARCH_MCP_TOKEN="$GROK_SEARCH_MCP_TOKEN" \
  uv run grok-search
```

The process binds `http://127.0.0.1:8800/mcp` and fail-closes if `GROK_SEARCH_MCP_TOKEN` is missing. It never defaults to `0.0.0.0`.

Grok/Tavily/Firecrawl credentials are still the existing `GUDA_API_KEY` or `GROK_*` / `TAVILY_*` / `FIRECRAWL_*` env vars. They are not the inbound MCP bearer.

## 2. Point Cursor at this folder

Load `cursor-plugin/` as a local plugin (do not publish to the marketplace). Set `GROK_SEARCH_MCP_TOKEN` to the same value used when starting the server.

`plugin.json` requires `variables.GROK_SEARCH_MCP_TOKEN` and points `mcpServers` at `./mcp.json`:

```json
{
  "mcpServers": {
    "grok-search": {
      "type": "http",
      "url": "http://127.0.0.1:8800/mcp",
      "headers": {
        "Authorization": "Bearer ${GROK_SEARCH_MCP_TOKEN}"
      }
    }
  }
}
```

Missing or wrong `Authorization` header returns HTTP 401.
