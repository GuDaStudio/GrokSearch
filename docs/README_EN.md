![Image](../images/title.png)
<div align="center">

<!-- # Grok Search MCP -->

English | [简体中文](../README.md)

**Grok-with-Tavily MCP, providing enhanced web access for Claude Code**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![FastMCP](https://img.shields.io/badge/FastMCP-2.0.0+-green.svg)](https://github.com/jlowin/fastmcp)

</div>

---

## 1. Overview

Grok Search MCP is an MCP server built on [FastMCP](https://github.com/jlowin/fastmcp), featuring a **dual-engine architecture**: **Grok** handles AI-driven intelligent search, while **Tavily** handles high-fidelity web content extraction and site mapping. Together they provide complete real-time web access for LLM clients such as Claude Code and Cherry Studio.

```
Claude --MCP--> Grok Search Server
                  ├─ web_search  ---> Grok API (AI Search)
                  │                    + optional extras: Tavily Search + Firecrawl Search
                  ├─ web_fetch   ---> Tavily Extract → Firecrawl Scrape (auto-fallback)
                  └─ web_map     ---> Tavily Map (Site Mapping)
```

### Features

- **Dual Engine**: Grok search + Tavily extraction/mapping, complementary collaboration
- **web_search extras**: when `extra_sources>0`, quota is split between Tavily Search and Firecrawl Search (with `GUDA_API_KEY`, Tavily is **not** zeroed); default `extra_sources=0` is Grok-only
- **OpenAI-compatible interface**, supports any Grok mirror endpoint
- **Automatic time injection** (detects time-related queries, injects local time context)
- One-click disable Claude Code's built-in WebSearch/WebFetch, force routing to this tool
- Smart retry (Retry-After header parsing + exponential backoff)
- Parent process monitoring (auto-detects parent process exit on Windows, prevents zombie processes)

### Demo

Using `cherry studio` with this MCP configured, here's how `claude-opus-4.6` leverages this project for external knowledge retrieval, reducing hallucination rates.

![](../images/wogrok.png)
As shown above, **for a fair experiment, we enabled Claude's built-in search tools**, yet Opus 4.6 still relied on its internal knowledge without consulting FastAPI's official documentation for the latest examples.

![](../images/wgrok.png)
As shown above, with `grok-search MCP` enabled under the same experimental conditions, Opus 4.6 proactively made multiple search calls to **retrieve official documentation, producing more reliable answers.**


## 2. Installation

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended Python package manager)
- Claude Code

<details>
<summary><b>Install uv</b></summary>

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

> Windows users are **strongly recommended** to run this project in WSL.

</details>

### One-Click Install

If you have previously installed this project, remove the old MCP first:
```
claude mcp remove grok-search
```

Replace the environment variables in the following command with your own values. The Grok endpoint must be OpenAI-compatible; Tavily is optional — `web_fetch` and `web_map` will be unavailable without it.

#### GuDa Users (Recommended)

GuDa users only need to set `GUDA_API_KEY` to access all services — API URLs are automatically derived:

```bash
claude mcp add-json grok-search --scope user '{
  "type": "stdio",
  "command": "uvx",
  "args": [
    "--from",
    "git+https://github.com/karlorz/GrokSearch@grok-with-tavily",
    "grok-search"
  ],
  "env": {
    "GUDA_API_KEY": "your-guda-api-key"
  }
}'
```

#### Custom Configuration

To use your own API endpoints, configure each service separately:

```bash
claude mcp add-json grok-search --scope user '{
  "type": "stdio",
  "command": "uvx",
  "args": [
    "--from",
    "git+https://github.com/karlorz/GrokSearch@grok-with-tavily",
    "grok-search"
  ],
  "env": {
    "GROK_API_URL": "https://your-api-endpoint.com/v1",
    "GROK_API_KEY": "your-grok-api-key",
    "TAVILY_API_KEY": "tvly-your-tavily-key",
    "TAVILY_API_URL": "https://api.tavily.com"
  }
}'
```

You can also configure additional environment variables in the `env` field:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GUDA_API_KEY` | No | - | GuDa API key (auto-derives all service URLs and keys when set) |
| `GUDA_BASE_URL` | No | `https://code.guda.studio` | GuDa service base URL |
| `GROK_API_URL` | No | `{GUDA_BASE_URL}/grok/v1` | Grok API endpoint (OpenAI-compatible), overrides GuDa-derived value |
| `GROK_API_KEY` | No | `{GUDA_API_KEY}` | Grok API key, overrides GuDa-derived value |
| `GROK_MODEL` | No | `grok-4.20-beta` | Default model (takes precedence over `~/.config/grok-search/config.json` when set) |
| `TAVILY_API_KEY` | No | `{GUDA_API_KEY}` | Tavily API key (for web_search extras / web_fetch / web_map) |
| `TAVILY_API_URL` | No | `{GUDA_BASE_URL}/tavily` | Tavily API endpoint |
| `TAVILY_ENABLED` | No | `true` | Enable Tavily (search extras / extract / map) |
| `FIRECRAWL_API_KEY` | No | `{GUDA_API_KEY}` | Firecrawl API key (fallback when Tavily fails) |
| `FIRECRAWL_API_URL` | No | `{GUDA_BASE_URL}/firecrawl` | Firecrawl API endpoint |
| `FIRECRAWL_ENABLED` | No | `true` | Enable Firecrawl (search extras / scrape fallback) |
| `GROK_DEBUG` | No | `false` | Debug mode |
| `GROK_LOG_LEVEL` | No | `INFO` | Log level |
| `GROK_LOG_DIR` | No | `logs` | Log directory |
| `GROK_RETRY_MAX_ATTEMPTS` | No | `3` | Max retry attempts |
| `GROK_RETRY_MULTIPLIER` | No | `1` | Retry backoff multiplier |
| `GROK_RETRY_MAX_WAIT` | No | `10` | Max retry wait in seconds |
| `GROK_SEARCH_MCP_TRANSPORT` | No | `stdio` | MCP transport: `stdio` (default) or additive `http` |
| `GROK_SEARCH_MCP_HOST` | No | `127.0.0.1` | HTTP bind address; loopback default, never `0.0.0.0` unless you set it |
| `GROK_SEARCH_MCP_PORT` | No | `8800` | HTTP port (not 80/8080/6080) |
| `GROK_SEARCH_MCP_PATH` | No | `/mcp` | HTTP MCP path |
| `GROK_SEARCH_MCP_TOKEN` | Required for HTTP | - | Inbound Bearer. HTTP only; missing token fail-closes. Do not reuse `GUDA_API_KEY` / Grok / Tavily / Firecrawl keys |

> **Note**: When `GUDA_API_KEY` is set, all `GROK_API_URL`/`GROK_API_KEY`/`TAVILY_*`/`FIRECRAWL_*` variables become optional as they are auto-derived from `GUDA_BASE_URL`. Explicitly set variables take higher priority.

### Optional HTTP MCP (stdio stays default)

The server still defaults to FastMCP `stdio`. For local HTTP:

```bash
export GROK_SEARCH_MCP_TOKEN="$(openssl rand -hex 32)"
GROK_SEARCH_MCP_TRANSPORT=http \
  GROK_SEARCH_MCP_TOKEN="$GROK_SEARCH_MCP_TOKEN" \
  uv run grok-search
```

It binds `http://127.0.0.1:8800/mcp` and checks `Authorization: Bearer <GROK_SEARCH_MCP_TOKEN>`. Missing or wrong header returns 401. stdio does not use this token.

`cursor-plugin/` is an in-repo local Cursor plugin example (`type: "http"`, required `variables.GROK_SEARCH_MCP_TOKEN`, `"mcpServers": "./mcp.json"`). It is not a marketplace listing. See `cursor-plugin/README.md`.

### web_search extras allocation (`extra_sources`)

| `extra_sources` | Both enabled | Notes |
|-----------------|--------------|-------|
| `0` (default) | — | Grok only |
| `1` | Tavily=1, Firecrawl=0 | Single extra prefers Tavily |
| `≥2` | ~30% Tavily / ~70% Firecrawl | **Tavily share is never zero** when both are on |

Disable one side: `TAVILY_ENABLED=false` → all extras to Firecrawl; `FIRECRAWL_ENABLED=false` → all extras to Tavily.

**This fork install pin:** `git+https://github.com/karlorz/GrokSearch@grok-with-tavily`

#### Tavily query-length guard

- Grok always receives the full `web_search` query. Firecrawl also receives the full query when it is allocated an extra-source share.
- Only the Tavily Search request is capped at the provider boundary, using the first **400 Python Unicode code points**, to prevent a terminal `Query is too long` HTTP 400.
- Callers should still submit concise, search-engine-style queries. GrokSearch does not automatically fan one long query into multiple Tavily searches because every subquery adds API-credit usage and latency.
- Truncation warnings contain original and final lengths only, never query content.

The repository includes a boundary probe that is offline by default:

```bash
# Reports the target host and bounded cost; sends no request
uv run grok-search-tavily-probe

# Provide TAVILY_API_KEY through a secure environment first; do not paste a live key into shell history
# Explicit live confirmation: ASCII/CJK/emoji × 399/400/401 = 9 basic Searches
uv run grok-search-tavily-probe --confirm-live

# GuDa-compatible gateway (set its bearer securely; do not log it)
uv run grok-search-tavily-probe \
  --base-url https://your-gateway.example/tavily --confirm-live
```

The probe outputs only the case label, Python code-point count, UTF-8 byte count, HTTP status, and normalized classification. It never outputs credentials, generated queries, response bodies, raw error details, or search results. Live mode consumes nine basic Search operations.


### Verify Installation

```bash
claude mcp list
```

After confirming a successful connection, we **highly recommend** typing the following in a Claude conversation:
```
Call grok-search toggle_builtin_tools to disable Claude Code's built-in WebSearch and WebFetch tools
```
This will automatically modify the **project-level** `.claude/settings.json` `permissions.deny`, disabling Claude Code's built-in WebSearch and WebFetch, forcing Claude Code to use this project for searches!



## 3. MCP Tools

<details>
<summary>This project provides eight MCP tools (click to expand)</summary>

### `web_search` — AI Web Search

Executes AI-driven web search via Grok API. By default it returns only Grok's answer and a `session_id` for retrieving sources later.

`web_search` does not expand sources in the response; it only returns `sources_count`. Sources are cached server-side by `session_id` and can be fetched with `get_sources`.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Keep concise. Tavily extras receive at most the first 400 Python Unicode code points; Grok and Firecrawl retain the full query |
| `platform` | string | No | `""` | Focus platform (e.g., `"Twitter"`, `"GitHub, Reddit"`) |
| `model` | string | No | `null` | Per-request Grok model ID |
| `extra_sources` | int | No | `0` | Extra sources via Tavily/Firecrawl (0 disables) |

Automatically detects time-related keywords in queries (e.g., "latest", "today", "recent"), injecting local time context to improve accuracy for time-sensitive searches.

Return value (structured dict):
- `session_id`: search session ID
- `content`: answer only (sources removed)
- `sources_count`: cached sources count

### `get_sources` — Retrieve Sources

Retrieves the full cached source list for a previous `web_search` call.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | `session_id` returned by `web_search` |

Return value (structured dict):
- `session_id`
- `sources_count`
- `sources`: source list (each item includes `url`, may include `title`/`description`/`provider`)

### `web_fetch` — Web Content Extraction

Extracts complete web content via Tavily Extract API, returning Markdown format.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | Target webpage URL |

### `web_map` — Site Structure Mapping

Traverses website structure via Tavily Map API, discovering URLs and generating a site map.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | Yes | - | Starting URL |
| `instructions` | string | No | `""` | Natural language filtering instructions |
| `max_depth` | int | No | `1` | Max traversal depth (1-5) |
| `max_breadth` | int | No | `20` | Max links to follow per page (1-500) |
| `limit` | int | No | `50` | Total link processing limit (1-500) |
| `timeout` | int | No | `150` | Timeout in seconds (10-150) |

### `get_config_info` — Configuration Diagnostics

No parameters required. Displays all configuration status, tests Grok API connection, returns response time and available model list (API keys auto-masked).

### `switch_model` — Model Switching

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Model ID (e.g., `"grok-4-fast"`, `"grok-2-latest"`) |

Settings persist to `~/.config/grok-search/config.json` across sessions.

### `toggle_builtin_tools` — Tool Routing Control

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | string | No | `"status"` | `"on"` disable built-in tools / `"off"` enable built-in tools / `"status"` check status |

Modifies project-level `.claude/settings.json` `permissions.deny` to disable Claude Code's built-in WebSearch and WebFetch.

### `search_planning` — Search Planning

A structured multi-phase planning scaffold to generate an executable search plan before running complex searches.
</details>

## 4. FAQ

<details>
<summary>
Q: Must I configure both Grok and Tavily?
</summary>
A: Set `GUDA_API_KEY` to get full Grok + Tavily + Firecrawl service. Without GuDa, Grok (`GROK_API_URL` + `GROK_API_KEY`) is required and provides the core search capability. Tavily is optional — without it, `web_fetch` and `web_map` will return configuration error messages.
</details>

<details>
<summary>
Q: What format does the Grok API URL need?
</summary>
A: An OpenAI-compatible API endpoint (supporting `/chat/completions` and `/models` endpoints). If using official Grok, access it through an OpenAI-compatible mirror.
</details>

<details>
<summary>
Q: How to verify configuration?
</summary>
A: Say "Show grok-search configuration info" in a Claude conversation to automatically test the API connection and display results.
</details>

## License

[MIT License](LICENSE)

---

<div align="center">

**If this project helps you, please give it a Star!**

[![Star History Chart](https://api.star-history.com/svg?repos=GuDaStudio/GrokSearch&type=date&legend=top-left)](https://www.star-history.com/#GuDaStudio/GrokSearch&type=date&legend=top-left)
</div>
