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
                  ├─ web_search      ---> Grok API (AI Search)
                  ├─ search_followup ---> Grok API (Follow-up, reuses conversation context)
                  ├─ search_reflect  ---> Grok API (Reflect → Supplement → Cross-validate)
                  ├─ search_planning ---> Structured planning scaffold (zero API calls)
                  ├─ web_fetch       ---> Tavily Extract → Firecrawl Scrape (Content Extraction)
                  └─ web_map         ---> Tavily Map (Site Mapping)
```

> 💡 **Recommended Pipeline**: For complex queries, use `search_planning → web_search → search_followup → search_reflect` in sequence — plan first, execute, then verify.

### Features

- **Dual Engine**: Grok search + Tavily extraction/mapping, complementary collaboration
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

```bash
claude mcp add-json grok-search --scope user '{
  "type": "stdio",
  "command": "uvx",
  "args": [
    "--from",
    "git+https://github.com/GuDaStudio/GrokSearch@grok-with-tavily",
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
| `GROK_API_URL` | Yes | - | Grok API endpoint (OpenAI-compatible format) |
| `GROK_API_KEY` | Yes | - | Grok API key |
| `GROK_MODEL` | No | `grok-4-fast` | Default model (takes precedence over `~/.config/grok-search/config.json` when set) |
| `TAVILY_API_KEY` | No | - | Tavily API key (for web_fetch / web_map) |
| `TAVILY_API_URL` | No | `https://api.tavily.com` | Tavily API endpoint |
| `TAVILY_ENABLED` | No | `true` | Enable Tavily |
| `GROK_DEBUG` | No | `false` | Debug mode |
| `GROK_LOG_LEVEL` | No | `INFO` | Log level |
| `GROK_LOG_DIR` | No | `logs` | Log directory |
| `GROK_RETRY_MAX_ATTEMPTS` | No | `3` | Max retry attempts |
| `GROK_RETRY_MULTIPLIER` | No | `1` | Retry backoff multiplier |
| `GROK_RETRY_MAX_WAIT` | No | `10` | Max retry wait in seconds |
| `FIRECRAWL_API_KEY` | No | - | Firecrawl API key (fallback when Tavily fails) |
| `FIRECRAWL_API_URL` | No | `https://api.firecrawl.dev/v2` | Firecrawl API endpoint |
| `GROK_SESSION_TIMEOUT` | No | `600` | Follow-up session timeout in seconds (default 10 min) |
| `GROK_MAX_SESSIONS` | No | `20` | Max concurrent sessions |
| `GROK_MAX_SEARCHES` | No | `50` | Max searches per session |


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
<summary>This project provides ten MCP tools (click to expand)</summary>

### `web_search` — AI Web Search

Executes AI-driven web search via Grok API. Returns Grok's answer, a `session_id` for retrieving sources, and a `conversation_id` for follow-up.

💡 **For complex multi-aspect topics**, break into focused sub-queries:
1. Identify distinct aspects of the question
2. Call `web_search` separately for each aspect
3. Use `search_followup` to ask follow-up questions in the same context
4. Use `search_reflect` for important queries needing reflection & verification

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Clear, self-contained search query |
| `platform` | string | No | `""` | Focus platform (e.g., `"Twitter"`, `"GitHub, Reddit"`) |
| `model` | string | No | `null` | Per-request Grok model ID |
| `extra_sources` | int | No | `0` | Extra sources via Tavily/Firecrawl (0 disables) |

Return value (structured dict):
- `session_id`: for `get_sources`
- `conversation_id`: for `search_followup`
- `content`: answer text
- `sources_count`: cached sources count

### `search_followup` — Conversational Follow-up

Ask a follow-up question in an existing search conversation context. Requires a `conversation_id` from a previous `web_search` or `search_followup` result.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Follow-up question |
| `conversation_id` | string | Yes | - | From previous `web_search`/`search_followup` |
| `extra_sources` | int | No | `0` | Extra sources via Tavily/Firecrawl |

Return: same structure as `web_search`. Returns `{"error": "session_expired", ...}` if session expired.

### `search_reflect` — Reflection-Enhanced Search

Performs an initial search, then reflects on the answer to identify gaps, automatically performs supplementary searches, and optionally cross-validates information.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | Yes | - | Search query |
| `context` | string | No | `""` | Background information |
| `max_reflections` | int | No | `1` | Reflection rounds (1-3, hard limit) |
| `cross_validate` | bool | No | `false` | Cross-validate facts across rounds |
| `extra_sources` | int | No | `3` | Tavily/Firecrawl sources per round (max 10) |

Hard budget constraints: max 3 reflections, 60s per search, 30s per reflect/validate, 120s total.

Return value:
- `session_id`, `conversation_id`, `content`, `sources_count`, `search_rounds`
- `reflection_log`: list of `{round, gap, supplementary_query}`
- `round_sessions`: list of `{round, query, session_id}` for source traceability
- `validation` (if `cross_validate=true`): `{consistency, conflicts, confidence}`

### `get_sources` — Retrieve Sources

Retrieves the full cached source list for a previous search call.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `session_id` | string | Yes | `session_id` from `web_search`/`search_reflect` |

For `search_reflect`, use `round_sessions` to retrieve sources for each search round individually.

Return value:
- `session_id`, `sources_count`
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

A structured multi-phase planning scaffold to generate an executable search plan before running complex searches. Guides the LLM through 6 phases: **Intent Analysis → Complexity Assessment → Query Decomposition → Search Strategy → Tool Selection → Execution Order**.

> ⚠️ **Note**: This tool makes **zero API calls**. It is purely a structured thinking framework — the LLM (Claude) does all the reasoning, the tool only records and assembles the plan.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `phase` | string | Yes | - | Phase name (see 6 phases below) |
| `thought` | string | Yes | - | Reasoning for current phase |
| `session_id` | string | No | `""` | Planning session ID (auto-generated on first call) |
| `is_revision` | bool | No | `false` | Whether revising an existing phase |
| `revises_phase` | string | No | `""` | Name of phase being revised |
| `confidence` | float | No | `1.0` | Confidence score |
| `phase_data` | dict/list | No | `null` | Structured phase output |

**6 Phases**:

| Phase | Purpose | phase_data Example |
|-------|---------|-------------------|
| `intent_analysis` | Distill core question, query type, time sensitivity | `{core_question, query_type, time_sensitivity, domain}` |
| `complexity_assessment` | Rate complexity 1-3, determines required phases | `{level, estimated_sub_queries, justification}` |
| `query_decomposition` | Split into sub-queries with dependencies | `[{id, goal, tool_hint, boundary, depends_on}]` |
| `search_strategy` | Search terms + approach | `{approach, search_terms, fallback_plan}` |
| `tool_selection` | Assign tool per sub-query | `[{sub_query_id, tool, reason}]` |
| `execution_order` | Parallel/sequential ordering | `{parallel, sequential, estimated_rounds}` |

Return value:

```json
{
  "session_id": "a1b2c3d4e5f6",
  "completed_phases": ["intent_analysis", "complexity_assessment"],
  "complexity_level": 2,
  "plan_complete": false,
  "phases_remaining": ["query_decomposition", "search_strategy", "tool_selection", "execution_order"]
}
```

When `plan_complete: true`, returns `executable_plan` with the full plan.

</details>

### Recommended Pipeline

For complex queries, combine the tools in this pipeline:

```
┌─────────────────────┐
│ 1. search_planning  │  Plan: 6-phase structured thinking (zero API calls)
│    ↓ outputs plan   │  → sub-query list + search strategy + execution order
├─────────────────────┤
│ 2. web_search       │  Execute: search each sub-query per plan
│    ↓ returns IDs    │  → initial answers + session_id + conversation_id
├─────────────────────┤
│ 3. search_followup  │  Drill down: reuse conversation context for details
│    ↓ same session   │  → supplementary info (scores, specifics, etc.)
├─────────────────────┤
│ 4. search_reflect   │  Verify: auto-reflect → supplement → cross-validate
│    ↓ final answer   │  → high-confidence complete answer
├─────────────────────┤
│ 5. get_sources      │  Trace: retrieve source details for each step
└─────────────────────┘
```

> For simple queries, just use `web_search` directly — no need for the full pipeline.

## 4. FAQ

<details>
<summary>
Q: Must I configure both Grok and Tavily?
</summary>
A: Grok (`GROK_API_URL` + `GROK_API_KEY`) is required and provides the core search capability. Tavily is optional — without it, `web_fetch` and `web_map` will return configuration error messages.
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

<details>
<summary>
Q: Source separation not working?
</summary>
A: <code>web_search</code> internally uses <code>split_answer_and_sources</code> to separate the answer text from source citations. This depends on the model outputting specific formats (e.g., <code>sources([...])</code> function calls, <code>## Sources</code> heading separators).<br><br>
When using third-party OpenAI-compatible APIs (not official Grok at <code>api.x.ai</code>), the model typically doesn't output structured source markers, so the <code>content</code> field may contain mixed content.<br><br>
<strong>Recommended</strong>: Set <code>extra_sources > 0</code> to independently fetch structured sources via Tavily/Firecrawl. Retrieve source details (URL, title, description) using the <code>get_sources</code> tool.
</details>

<details>
<summary>
Q: Does search_planning consume API quota?
</summary>
A: No. <code>search_planning</code> is a pure in-memory state machine. The LLM (Claude) does all reasoning; the tool only records and assembles the plan. Zero API calls throughout.
</details>

## License

[MIT License](LICENSE)

---

<div align="center">

**If this project helps you, please give it a Star!**

[![Star History Chart](https://api.star-history.com/svg?repos=GuDaStudio/GrokSearch&type=date&legend=top-left)](https://www.star-history.com/#GuDaStudio/GrokSearch&type=date&legend=top-left)
</div>
