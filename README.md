![这是图片](./images/title.png)
<div align="center">

<!-- # Grok Search MCP -->

[English](./docs/README_EN.md) | 简体中文

**Grok-with-Tavily MCP，为 Claude Code 提供更完善的网络访问能力**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![FastMCP](https://img.shields.io/badge/FastMCP-2.0.0+-green.svg)](https://github.com/jlowin/fastmcp)

</div>

---

## 一、概述

Grok Search MCP 是一个基于 [FastMCP](https://github.com/jlowin/fastmcp) 构建的 MCP 服务器，采用**双引擎架构**：**Grok** 负责 AI 驱动的智能搜索，**Tavily** 负责高保真网页抓取与站点映射，各取所长为 Claude Code / Cherry Studio 等LLM Client提供完整的实时网络访问能力。

```
Claude ──MCP──► Grok Search Server
                  ├─ web_search      ───► Grok API（AI 搜索）
                  ├─ search_followup ───► Grok API（追问，复用会话上下文）
                  ├─ search_reflect  ───► Grok API（反思 → 补充搜索 → 交叉验证）
                  ├─ search_planning ───► 结构化规划脚手架（零 API 调用）
                  ├─ web_fetch       ───► Tavily Extract → Firecrawl Scrape（内容抓取，自动降级）
                  └─ web_map         ───► Tavily Map（站点映射）
```

> 💡 **推荐工具链**：对于复杂查询，建议按 `search_planning → web_search → search_followup → search_reflect` 的顺序组合使用，先规划再执行再验证。

### 功能特性

- **双引擎**：Grok 搜索 + Tavily 抓取/映射，互补协作
- **Firecrawl 托底**：Tavily 提取失败时自动降级到 Firecrawl Scrape，支持空内容自动重试
- **OpenAI 兼容接口**，支持任意 Grok 镜像站
- **自动时间注入**（检测时间相关查询，注入本地时间上下文）
- 一键禁用 Claude Code 官方 WebSearch/WebFetch，强制路由到本工具
- 智能重试（支持 Retry-After 头解析 + 指数退避）
- 父进程监控（Windows 下自动检测父进程退出，防止僵尸进程）

### 效果展示
我们以在`cherry studio`中配置本MCP为例，展示了`claude-opus-4.6`模型如何通过本项目实现外部知识搜集，降低幻觉率。
![](./images/wogrok.png)
如上图，**为公平实验，我们打开了claude模型内置的搜索工具**，然而opus 4.6仍然相信自己的内部常识，不查询FastAPI的官方文档，以获取最新示例。
![](./images/wgrok.png)
如上图，当打开`grok-search MCP`时，在相同的实验条件下，opus 4.6主动调用多次搜索，以**获取官方文档，回答更可靠。** 


## 二、安装

### 前置条件

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)（推荐的 Python 包管理器）
- Claude Code

<details>
<summary><b>安装 uv</b></summary>

```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

> Windows 用户**强烈推荐**在 WSL 中运行本项目。

</details>

### 一键安装
若之前安装过本项目，使用以下命令卸载旧版MCP。
```
claude mcp remove grok-search
```


将以下命令中的环境变量替换为你自己的值后执行。Grok 接口需为 OpenAI 兼容格式；Tavily 为可选配置，未配置时工具 `web_fetch` 和 `web_map` 不可用。

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

除此之外，你还可以在`env`字段中配置更多环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `GROK_API_URL` | ✅ | - | Grok API 地址（OpenAI 兼容格式） |
| `GROK_API_KEY` | ✅ | - | Grok API 密钥 |
| `GROK_MODEL` | ❌ | `grok-4-fast` | 默认模型（设置后优先于 `~/.config/grok-search/config.json`） |
| `TAVILY_API_KEY` | ❌ | - | Tavily API 密钥（用于 web_fetch / web_map） |
| `TAVILY_API_URL` | ❌ | `https://api.tavily.com` | Tavily API 地址 |
| `TAVILY_ENABLED` | ❌ | `true` | 是否启用 Tavily |
| `FIRECRAWL_API_KEY` | ❌ | - | Firecrawl API 密钥（Tavily 失败时托底） |
| `FIRECRAWL_API_URL` | ❌ | `https://api.firecrawl.dev/v2` | Firecrawl API 地址 |
| `GROK_DEBUG` | ❌ | `false` | 调试模式 |
| `GROK_LOG_LEVEL` | ❌ | `INFO` | 日志级别 |
| `GROK_LOG_DIR` | ❌ | `logs` | 日志目录 |
| `GROK_RETRY_MAX_ATTEMPTS` | ❌ | `3` | 最大重试次数 |
| `GROK_RETRY_MULTIPLIER` | ❌ | `1` | 重试退避乘数 |
| `GROK_RETRY_MAX_WAIT` | ❌ | `10` | 重试最大等待秒数 |
| `GROK_SESSION_TIMEOUT` | ❌ | `600` | 追问会话超时秒数（默认 10 分钟） |
| `GROK_MAX_SESSIONS` | ❌ | `20` | 最大并发会话数 |
| `GROK_MAX_SEARCHES` | ❌ | `50` | 单会话最大搜索次数 |


### 验证安装

```bash
claude mcp list
```

🍟 显示连接成功后，我们**十分推荐**在 Claude 对话中输入 
```
调用 grok-search toggle_builtin_tools，关闭Claude Code's built-in WebSearch and WebFetch tools
```
工具将自动修改**项目级** `.claude/settings.json` 的 `permissions.deny`，一键禁用 Claude Code 官方的 WebSearch 和 WebFetch，从而迫使claude code调用本项目实现搜索！



## 三、MCP 工具介绍

<details>
<summary>本项目提供十个 MCP 工具（展开查看）</summary>

### `web_search` — AI 网络搜索

通过 Grok API 执行 AI 驱动的网络搜索，返回 Grok 的回答正文。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | ✅ | - | 搜索查询语句 |
| `platform` | string | ❌ | `""` | 聚焦平台（如 `"Twitter"`, `"GitHub, Reddit"`） |
| `model` | string | ❌ | `null` | 按次指定 Grok 模型 ID |
| `extra_sources` | int | ❌ | `0` | 额外补充信源数量（Tavily/Firecrawl） |

返回值（`dict`）：

```json
{
  "session_id": "8236bf0b6a79",
  "conversation_id": "0fe631c32397",
  "content": "Grok 回答正文...",
  "sources_count": 3
}
```

| 字段 | 说明 |
|------|------|
| `session_id` | 本次查询的信源缓存 ID（用于 `get_sources`） |
| `conversation_id` | 会话 ID（用于 `search_followup` 追问） |
| `content` | Grok 回答正文（已自动剥离信源标记） |
| `sources_count` | 已缓存的信源数量 |

> **复杂查询建议**：对于多方面问题，建议拆分为多个聚焦的 `web_search` 调用，再用 `search_followup` 追问细节，或用 `search_reflect` 做深度研究。

### `search_followup` — 追问搜索 🆕

在已有搜索上下文中追问，保持对话连贯。需传入 `web_search` 返回的 `conversation_id`。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | ✅ | - | 追问内容 |
| `conversation_id` | string | ✅ | - | 上一次搜索返回的 `conversation_id` |
| `extra_sources` | int | ❌ | `0` | 额外补充信源 |

返回值与 `web_search` 相同。会话默认 10 分钟超时（可通过 `GROK_SESSION_TIMEOUT` 配置）。

### `search_reflect` — 反思增强搜索 🆕

搜索后自动反思遗漏 → 补充搜索 → 可选交叉验证。适用于需要高准确度的查询。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | ✅ | - | 搜索查询 |
| `context` | string | ❌ | `""` | 已知背景信息 |
| `max_reflections` | int | ❌ | `1` | 反思轮数（1-3，硬上限 3） |
| `cross_validate` | bool | ❌ | `false` | 启用交叉验证 |
| `extra_sources` | int | ❌ | `3` | 每轮补充信源数 |

返回值（`dict`）：

```json
{
  "session_id": "xxx",
  "conversation_id": "yyy",
  "content": "经反思增强的完整回答...",
  "reflection_log": [
    {"round": 1, "gap": "缺少最新数据", "supplementary_query": "..."}
  ],
  "validation": {"consistency": "high", "conflicts": [], "confidence": 0.92},
  "sources_count": 8,
  "search_rounds": 3
}
```

> `validation` 字段仅在 `cross_validate=true` 时返回。硬预算：反思≤3轮、单轮≤30s、总计≤120s。



### `get_sources` — 获取信源

通过 `session_id` 获取对应 `web_search` 的全部信源。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | ✅ | `web_search` 返回的 `session_id` |

返回值（`dict`）：

```json
{
  "session_id": "54e67e288b2b",
  "sources": [
    {
      "url": "https://realpython.com/async-io-python/",
      "provider": "tavily",
      "title": "Python's asyncio: A Hands-On Walkthrough",
      "description": "..."
    }
  ],
  "sources_count": 3
}
```

> 仅当 `web_search` 设置了 `extra_sources > 0` 时，`sources` 才会包含结构化来源。

### `web_fetch` — 网页内容抓取

通过 Tavily Extract API 获取完整网页内容，返回 Markdown 格式文本。Tavily 失败时自动降级到 Firecrawl Scrape 进行托底抓取。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | ✅ | 目标网页 URL |

返回值：`string`（Markdown 格式的网页内容）

### `web_map` — 站点结构映射

通过 Tavily Map API 遍历网站结构，发现 URL 并生成站点地图。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `url` | string | ✅ | - | 起始 URL |
| `instructions` | string | ❌ | `""` | 自然语言过滤指令 |
| `max_depth` | int | ❌ | `1` | 最大遍历深度（1-5） |
| `max_breadth` | int | ❌ | `20` | 每页最大跟踪链接数（1-500） |
| `limit` | int | ❌ | `50` | 总链接处理数上限（1-500） |
| `timeout` | int | ❌ | `150` | 超时秒数（10-150） |

返回值（`string`，JSON 格式）：

```json
{
  "base_url": "https://docs.python.org/3/library/",
  "results": [
    "https://docs.python.org/3/library",
    "https://docs.python.org/3/sqlite3.html",
    "..."
  ],
  "response_time": 0.14
}
```

### `get_config_info` — 配置诊断

无需参数。显示所有配置状态、测试 Grok API 连接、返回响应时间和可用模型列表（API Key 自动脱敏）。

### `switch_model` — 模型切换

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | ✅ | 模型 ID（如 `"grok-4-fast"`, `"grok-2-latest"`） |

切换后配置持久化到 `~/.config/grok-search/config.json`，跨会话保持。

### `toggle_builtin_tools` — 工具路由控制

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `action` | string | ❌ | `"status"` | `"on"` 禁用官方工具 / `"off"` 启用官方工具 / `"status"` 查看状态 |

修改项目级 `.claude/settings.json` 的 `permissions.deny`，一键禁用 Claude Code 官方的 WebSearch 和 WebFetch。

### `search_planning` — 搜索规划

结构化搜索规划脚手架，用于在执行复杂搜索前生成可执行计划。通过 6 个阶段引导 LLM 系统化思考：**意图分析 → 复杂度评估 → 查询分解 → 搜索策略 → 工具选择 → 执行顺序**。

> ⚠️ **注意**：该工具本身不发起任何搜索 API 调用，它只是一个结构化的思考框架。所有"智力劳动"由主模型（Claude）完成，工具仅负责记录和组装计划。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `phase` | string | ✅ | - | 阶段名称（见下方 6 阶段） |
| `thought` | string | ✅ | - | 当前阶段的思考过程 |
| `session_id` | string | ❌ | `""` | 规划会话 ID（首次调用自动生成） |
| `is_revision` | bool | ❌ | `false` | 是否修订已有阶段 |
| `revises_phase` | string | ❌ | `""` | 被修订的阶段名 |
| `confidence` | float | ❌ | `1.0` | 置信度 |
| `phase_data` | dict/list | ❌ | `null` | 结构化阶段产出 |

**6 个阶段**：

| 阶段 | 说明 | phase_data 示例 |
|------|------|-----------------|
| `intent_analysis` | 提炼核心问题、查询类型、时效性 | `{core_question, query_type, time_sensitivity, domain}` |
| `complexity_assessment` | 评估复杂度 1-3，决定后续需要哪些阶段 | `{level, estimated_sub_queries, justification}` |
| `query_decomposition` | 拆分为子查询（含依赖关系） | `[{id, goal, tool_hint, boundary, depends_on}]` |
| `search_strategy` | 搜索词 + 策略 | `{approach, search_terms, fallback_plan}` |
| `tool_selection` | 每个子查询用什么工具 | `[{sub_query_id, tool, reason}]` |
| `execution_order` | 并行/串行执行顺序 | `{parallel, sequential, estimated_rounds}` |

返回值（`dict`）：

```json
{
  "session_id": "a1b2c3d4e5f6",
  "completed_phases": ["intent_analysis", "complexity_assessment"],
  "complexity_level": 2,
  "plan_complete": false,
  "phases_remaining": ["query_decomposition", "search_strategy", "tool_selection", "execution_order"]
}
```

当 `plan_complete: true` 时，返回 `executable_plan` 包含完整的可执行计划。

</details>

### 推荐工具链流程

对于复杂查询，建议组合使用以下工具链：

```
┌─────────────────────┐
│ 1. search_planning  │  规划：6 阶段结构化思考（零 API 调用）
│    ↓ 输出执行计划   │  → 子查询列表 + 搜索策略 + 执行顺序
├─────────────────────┤
│ 2. web_search       │  执行：按计划逐一搜索各子查询
│    ↓ 返回 conv_id   │  → 获取初步答案 + session_id + conversation_id
├─────────────────────┤
│ 3. search_followup  │  追问：复用会话上下文，深入细节
│    ↓ 同一会话       │  → 获取补充信息（如单科成绩、具体数据等）
├─────────────────────┤
│ 4. search_reflect   │  验证：自动反思遗漏 → 补充搜索 → 交叉验证
│    ↓ 最终回答       │  → 高置信度的完整答案
├─────────────────────┤
│ 5. get_sources      │  溯源：获取每一步的信源详情（URL + 标题）
└─────────────────────┘
```

> 简单查询直接使用 `web_search` 即可，无需走完整流程。

## 四、常见问题

<details>
<summary>
Q: 必须同时配置 Grok 和 Tavily 吗？
</summary>
A: Grok（`GROK_API_URL` + `GROK_API_KEY`）为必填，提供核心搜索能力。Tavily 和 Firecrawl 均为可选：配置 Tavily 后 `web_fetch` 优先使用 Tavily Extract，失败时降级到 Firecrawl Scrape；两者均未配置时 `web_fetch` 将返回配置错误提示。`web_map` 依赖 Tavily。
</details>

<details>
<summary>
Q: Grok API 地址需要什么格式？
</summary>
A: 需要 OpenAI 兼容格式的 API 地址（支持 `/chat/completions` 和 `/models` 端点）。如使用官方 Grok，需通过兼容 OpenAI 格式的镜像站访问。
</details>

<details>
<summary>
Q: 如何验证配置？
</summary>
A: 在 Claude 对话中说"显示 grok-search 配置信息"，将自动测试 API 连接并显示结果。
</details>

<details>
<summary>
Q: 信源分离（source separation）不工作？
</summary>
A: <code>web_search</code> 内部使用 <code>split_answer_and_sources</code> 将回答正文和信源列表分开。该机制依赖模型输出特定格式（如 <code>sources([...])</code> 函数调用、<code>## Sources</code> 标题分隔等）。<br><br>
如果使用第三方 OpenAI 兼容 API（非 Grok 官方 <code>api.x.ai</code>），模型通常不会输出结构化信源标记，因此 <code>content</code> 字段可能包含信源混合内容。<br><br>
<strong>推荐方案</strong>：配置 <code>extra_sources > 0</code>，通过 Tavily/Firecrawl 独立获取结构化信源，不依赖 Grok 原生信源分离。信源数据通过 <code>get_sources</code> 工具获取，包含完整的 URL、标题和描述。
</details>

<details>
<summary>
Q: search_planning 会消耗 API 额度吗？
</summary>
A: 不会。<code>search_planning</code> 是纯内存状态机，所有"思考"由主模型（Claude）完成，工具仅负责记录和组装计划，全程零 API 调用。
</details>

## 许可证

[MIT License](LICENSE)

---

<div align="center">

**如果这个项目对您有帮助，请给个 Star！**

[![Star History Chart](https://api.star-history.com/svg?repos=GuDaStudio/GrokSearch&type=date&legend=top-left)](https://www.star-history.com/#GuDaStudio/GrokSearch&type=date&legend=top-left)
</div>
