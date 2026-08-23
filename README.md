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
                  ├─ web_search  ───► Grok API（AI 搜索）
                  │                    + optional extras: Tavily Search + Firecrawl Search
                  ├─ web_fetch   ───► Tavily Extract → Firecrawl Scrape（内容抓取，自动降级）
                  └─ web_map     ───► Tavily Map（站点映射）
```

### 功能特性

- **双引擎**：Grok 搜索 + Tavily 抓取/映射，互补协作
- **web_search extras**：`extra_sources>0` 时在 Tavily Search 与 Firecrawl Search 之间按比例分配（`GUDA_API_KEY` 同时派生两者时 **不会** 把全部配额给 Firecrawl）；`extra_sources=0`（默认）仅 Grok
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

#### GuDa 用户（推荐）

GuDa 用户只需配置 `GUDA_API_KEY` 即可享受完整服务，所有 API 地址自动派生：

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
    "GUDA_API_KEY": "your-guda-api-key",
    "GUDA_BASE_URL": "https://search.karldigi.dev"
  }
}'
```

#### 自定义配置

如需使用自己的 API 端点，可分别配置各服务：

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

<details> <summary>如果遇到 SSL / 证书验证错误</summary>

在部分企业网络或代理环境中，可能会出现类似错误：

certificate verify failed
self signed certificate in certificate chain

可以在 uvx 参数中添加 --native-tls，使其使用系统证书库：

claude mcp add-json grok-search --scope user '{
  "type": "stdio",
  "command": "uvx",
  "args": [
    "--native-tls",
    "--from",
    "git+https://github.com/karlorz/GrokSearch@grok-with-tavily",
    "grok-search"
  ],
  "env": {
    "GUDA_API_KEY": "your-guda-api-key"
  }
}'
</details> ```

除此之外，你还可以在`env`字段中配置更多环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `GUDA_API_KEY` | ❌ | - | GuDa API 密钥（配置后自动派生所有服务的 URL 和 Key） |
| `GUDA_BASE_URL` | ❌ | `https://code.guda.studio` | GuDa 服务基础地址 |
| `GROK_API_URL` | ❌ | `{GUDA_BASE_URL}/grok/v1` | Grok API 地址（OpenAI 兼容格式），显式设置时覆盖 GuDa 派生值 |
| `GROK_API_KEY` | ❌ | `{GUDA_API_KEY}` | Grok API 密钥，显式设置时覆盖 GuDa 派生值 |
| `GROK_MODEL` | ❌ | `grok-4.20-beta` | 默认模型（设置后优先于 `~/.config/grok-search/config.json`） |
| `TAVILY_API_KEY` | ❌ | `{GUDA_API_KEY}` | Tavily API 密钥（用于 web_search extras / web_fetch / web_map） |
| `TAVILY_API_URL` | ❌ | `{GUDA_BASE_URL}/tavily` | Tavily API 地址 |
| `TAVILY_ENABLED` | ❌ | `true` | 是否启用 Tavily（search extras / extract / map） |
| `FIRECRAWL_API_KEY` | ❌ | `{GUDA_API_KEY}` | Firecrawl API 密钥（Tavily 失败时托底） |
| `FIRECRAWL_API_URL` | ❌ | `{GUDA_BASE_URL}/firecrawl` | Firecrawl API 地址 |
| `FIRECRAWL_ENABLED` | ❌ | `true` | 是否启用 Firecrawl（search extras / scrape 托底） |
| `GROK_DEBUG` | ❌ | `false` | 调试模式 |
| `GROK_LOG_LEVEL` | ❌ | `INFO` | 日志级别 |
| `GROK_LOG_DIR` | ❌ | `logs` | 日志目录 |
| `GROK_RETRY_MAX_ATTEMPTS` | ❌ | `3` | 最大重试次数 |
| `GROK_RETRY_MULTIPLIER` | ❌ | `1` | 重试退避乘数 |
| `GROK_RETRY_MAX_WAIT` | ❌ | `10` | 重试最大等待秒数 |
| `GROK_SEARCH_MCP_TRANSPORT` | ❌ | `stdio` | MCP 传输：`stdio`（默认）或 `http`（附加 loopback） |
| `GROK_SEARCH_MCP_HOST` | ❌ | `127.0.0.1` | HTTP 绑定地址；默认 loopback，不会默认 `0.0.0.0` |
| `GROK_SEARCH_MCP_PORT` | ❌ | `8800` | HTTP 端口（避开 80/8080/6080） |
| `GROK_SEARCH_MCP_PATH` | ❌ | `/mcp` | HTTP MCP 路径 |
| `GROK_SEARCH_MCP_TOKEN` | HTTP 必填 | - | 入站 Bearer。仅 HTTP 使用；缺失则 fail-closed。不要复用 `GUDA_API_KEY` / Grok / Tavily / Firecrawl 密钥 |

> **注意**：配置了 `GUDA_API_KEY` 后，`GROK_API_URL`/`GROK_API_KEY`/`TAVILY_*`/`FIRECRAWL_*` 均为可选，系统自动从 `GUDA_BASE_URL` 派生。显式设置的独立变量优先级更高。

### 可选 HTTP MCP（stdio 仍是默认）

默认仍走 FastMCP `stdio`。需要本机 HTTP 时：

```bash
export GROK_SEARCH_MCP_TOKEN="$(openssl rand -hex 32)"
GROK_SEARCH_MCP_TRANSPORT=http \
  GROK_SEARCH_MCP_TOKEN="$GROK_SEARCH_MCP_TOKEN" \
  uv run grok-search
```

服务监听 `http://127.0.0.1:8800/mcp`，校验 `Authorization: Bearer <GROK_SEARCH_MCP_TOKEN>`；缺头或错 token 返回 401。stdio 不使用该 token。

仓库内 `cursor-plugin/` 是本地 Cursor 插件示例（`type: "http"`，`variables.GROK_SEARCH_MCP_TOKEN` 必填，`mcpServers` 指向 `./mcp.json`），不是 marketplace。详见 `cursor-plugin/README.md`。

### web_search extras 分配（`extra_sources`）

| `extra_sources` | 双方均启用 | 说明 |
|-----------------|------------|------|
| `0`（默认） | — | 仅 Grok |
| `1` | Tavily=1, Firecrawl=0 | 单条 extras 优先 Tavily |
| `≥2` | 约 30% Tavily / 70% Firecrawl | 双方均启用时 **Tavily 份额不为 0** |

关闭一侧：`TAVILY_ENABLED=false` → extras 全给 Firecrawl；`FIRECRAWL_ENABLED=false` → extras 全给 Tavily。

#### Tavily 查询长度保护

- `web_search` 的完整查询仍会发送给 Grok；分配到 Firecrawl 时，Firecrawl 也会收到完整查询。
- 只有 Tavily Search 请求在发送边界被限制为前 **400 个 Python Unicode 码点**，避免 Tavily 返回 `Query is too long` 的终止性 HTTP 400。
- 建议调用方传入简洁、类似搜索引擎的查询。系统不会自动把长查询拆成多个 Tavily 搜索，因为每个子查询都会增加 API credits 消耗和延迟。
- 长度截断日志只记录截断前后的长度，不记录查询内容。

仓库提供一个默认不联网的边界探针：

```bash
# 仅显示目标主机和预计成本，不发送请求
uv run grok-search-tavily-probe

# 先通过安全的环境配置提供 TAVILY_API_KEY，不要把真实密钥粘贴到命令历史
# 明确确认后才执行：ASCII/CJK/emoji × 399/400/401，共 9 次 basic Search
uv run grok-search-tavily-probe --confirm-live

# GuDa 兼容网关（先安全设置对应 bearer；不要写入命令历史或日志）
uv run grok-search-tavily-probe \
  --base-url https://your-gateway.example/tavily --confirm-live
```

探针只输出测试标签、Python 码点数、UTF-8 字节数、HTTP 状态和归一化分类；不会输出密钥、查询、响应正文、错误详情或搜索结果。直接执行 live 模式会消耗 9 次 basic Search credits。


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
<summary>本项目提供八个 MCP 工具（展开查看）</summary>

### `web_search` — AI 网络搜索

通过 Grok API 执行 AI 驱动的网络搜索，默认仅返回 Grok 的回答正文，并返回 `session_id` 以便后续获取信源。

`web_search` 输出不展开信源，仅返回 `sources_count`；信源会按 `session_id` 缓存在服务端，可用 `get_sources` 拉取。

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | ✅ | - | 搜索查询语句；保持简洁。Tavily extras 最多接收前 400 个 Python Unicode 码点，Grok/Firecrawl 保留完整查询 |
| `platform` | string | ❌ | `""` | 聚焦平台（如 `"Twitter"`, `"GitHub, Reddit"`） |
| `model` | string | ❌ | `null` | 按次指定 Grok 模型 ID |
| `extra_sources` | int | ❌ | `0` | 额外补充信源数量（Tavily/Firecrawl，可为 0 关闭） |

自动检测查询中的时间相关关键词（如"最新""今天""recent"等），注入本地时间上下文以提升时效性搜索的准确度。

返回值（结构化字典）：
- `session_id`: 本次查询的会话 ID
- `content`: Grok 回答正文（已自动剥离信源）
- `sources_count`: 已缓存的信源数量

### `get_sources` — 获取信源

通过 `session_id` 获取对应 `web_search` 的全部信源。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `session_id` | string | ✅ | `web_search` 返回的 `session_id` |

返回值（结构化字典）：
- `session_id`
- `sources_count`
- `sources`: 信源列表（每项包含 `url`，可能包含 `title`/`description`/`provider`）

### `web_fetch` — 网页内容抓取

通过 Tavily Extract API 获取完整网页内容，返回 Markdown 格式。Tavily 失败时自动降级到 Firecrawl Scrape 进行托底抓取。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | ✅ | 目标网页 URL |

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

结构化搜索规划脚手架（分阶段、多轮），用于在执行复杂搜索前先生成可执行的搜索计划。
</details>

## 四、常见问题

<details>
<summary>
Q: 必须同时配置 Grok 和 Tavily 吗？
</summary>
A: 配置 `GUDA_API_KEY` 即可获得完整的 Grok + Tavily + Firecrawl 服务。如不使用 GuDa，Grok（`GROK_API_URL` + `GROK_API_KEY`）为必填，提供核心搜索能力。Tavily 和 Firecrawl 均为可选：配置 Tavily 后 `web_fetch` 优先使用 Tavily Extract，失败时降级到 Firecrawl Scrape；两者均未配置时 `web_fetch` 将返回配置错误提示。`web_map` 依赖 Tavily。
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

## 许可证

[MIT License](LICENSE)

---

<div align="center">

**如果这个项目对您有帮助，请给个 Star！**

[![Star History Chart](https://api.star-history.com/svg?repos=GuDaStudio/GrokSearch&type=date&legend=top-left)](https://www.star-history.com/#GuDaStudio/GrokSearch&type=date&legend=top-left)
</div>
