![这是图片](./images/title.png)
<div align="center">

<!-- # Grok Search MCP -->

[English](./docs/README_EN.md) | 简体中文

**通过 MCP 协议将 Grok 搜索能力集成到 Claude，显著增强文档检索与事实核查能力**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0.0+-green.svg)](https://github.com/jlowin/fastmcp)

</div>

---

## 概述

Grok Search MCP 是一个基于 [FastMCP](https://github.com/jlowin/fastmcp) 构建的 MCP（Model Context Protocol）服务器，通过转接第三方平台（如 Grok）的强大搜索能力，为 Claude、Claude Code 等 AI 模型提供实时网络搜索功能。

### 核心价值
- **突破知识截止限制**：让 Claude 访问最新的网络信息，不再受训练数据时间限制
- **增强事实核查**：实时搜索验证信息的准确性和时效性
- **结构化输出**：返回包含标题、链接、摘要的标准化 JSON，便于 AI 模型理解与引用
- **即插即用**：通过 MCP 协议无缝集成到 Claude Desktop、Claude Code 等客户端


**工作流程**：`Claude → MCP → Grok API → 搜索/抓取 → 结构化返回`

<details>
<summary><b>💡 更多选择Grok  search 的理由</b></summary>
与其他搜索方案对比：

| 特性 | Grok Search MCP | Google Custom Search API | Bing Search API | SerpAPI |
|------|----------------|-------------------------|-----------------|---------|
| **AI 优化结果** | ✅ 专为 AI 理解优化 | ❌ 通用搜索结果 | ❌ 通用搜索结果 | ❌ 通用搜索结果 |
| **内容摘要质量** | ✅ AI 生成高质量摘要 | ⚠️ 需二次处理 | ⚠️ 需二次处理 | ⚠️ 需二次处理 |
| **实时性** | ✅ 实时网络数据 | ✅ 实时 | ✅ 实时 | ✅ 实时 |
| **集成复杂度** | ✅ MCP 即插即用 | ⚠️ 需自行开发 | ⚠️ 需自行开发 | ⚠️ 需自行开发 |
| **返回格式** | ✅ AI 友好 JSON | ⚠️ 需格式化 | ⚠️ 需格式化 | ⚠️ 需格式化 |

## 功能特性

- ✅ OpenAI 兼容接口，环境变量配置
- ✅ 实时网络搜索 + 网页内容抓取
- ✅ 支持指定搜索平台（Twitter、Reddit、GitHub 等）
- ✅ 配置测试工具（连接测试 + API Key 脱敏）
- ✅ **多 Provider 支持（Grok / Tavily），通过 `update_config` 动态切换**
- ✅ **工具路由控制（一键禁用官方 WebSearch/WebFetch，强制使用 GrokSearch）**
- ✅ **自动时间注入（搜索时自动获取本地时间，确保时间相关查询的准确性）**
- ✅ 可扩展架构，支持添加其他搜索 Provider
</details>

## 安装教程
### Step 0.前期准备（若已经安装uv则跳过该步骤）

<details>

**Python 环境**：
- Python 3.10 或更高版本
- 已配置 Claude Code 或 Claude Desktop

**uv 工具**（推荐的 Python 包管理器）：

请确保您已成功安装 [uv 工具](https://docs.astral.sh/uv/getting-started/installation/)：

#### Windows 安装 uv
在 PowerShell 中运行以下命令：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**💡 重要提示** ：我们 **强烈推荐** Windows 用户在 WSL（Windows Subsystem for Linux）中运行本项目！

#### Linux/macOS 安装 uv

使用 curl 或 wget 下载并安装：

```bash
# 使用 curl
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 wget
wget -qO- https://astral.sh/uv/install.sh | sh
```

</details>


### Step 1. 安装 Grok Search MCP

使用 `claude mcp add-json` 一键安装并配置：
**注意：** 需要替换 **GROK_API_URL** 以及 **GROK_API_KEY** 这两个字段为你自己的站点以及密钥。支持 Grok 和 Tavily 两种 Provider，通过 `update_config` 工具切换。

```bash
claude mcp add-json grok-search --scope user '{
  "type": "stdio",
  "command": "uvx",
  "args": [
    "--from",
    "git+https://github.com/GuDaStudio/GrokSearch",
    "grok-search"
  ],
  "env": {
    "GROK_API_URL": "https://your-api-endpoint.com/v1",
    "GROK_API_KEY": "your-api-key-here"
  }
}'
```


### Step 2. 验证安装 & 检查MCP配置

```bash
claude mcp list
```

应能看到 `grok-search` 服务器已注册。

配置完成后，**强烈建议**在 Claude 对话中运行配置测试，以确保一切正常：

在 Claude 对话中输入：
```
请测试 Grok Search 的配置
```

或直接说：
```
显示 grok-search 配置信息
```

工具会自动执行以下检查：
- ✅ 验证环境变量是否正确加载
- ✅ 测试 API 连接（向 `/models` 端点发送请求）
- ✅ 显示响应时间和可用模型数量
- ✅ 识别并报告任何配置错误


如果看到 `❌ 连接失败` 或 `⚠️ 连接异常`，请检查：
- API URL 是否正确
- API Key 是否有效
- 网络连接是否正常

### Step 3. 配置系统提示词
为了更好的使用Grok Search 可以通过配置Claude Code或者类似的系统提示词来对整体Vibe Coding Cli进行优化，以Claude Code 为例可以编辑 ~/.claude/CLAUDE.md中追加下面内容，提供了两版使用详细版更能激活工具的能力：

**💡 提示**：现在可以使用 `toggle_builtin_tools` 工具一键禁用官方 WebSearch/WebFetch，强制路由到 GrokSearch！

#### 精简版提示词
```markdown
# Grok Search 提示词 精简版
## 激活与路由
**触发**：网络搜索/网页抓取/最新信息查询时自动激活
**替换**：尽可能使用 Grok-search的工具替换官方原生search以及fetch功能

## 工具矩阵

| Tool | Parameters | Output | Use Case |
|------|------------|--------|----------|
| `web_search` | `query`(必填), `platform`/`min_results`/`max_results`(可选) | `[{title,url,content}]` | 多源聚合/事实核查/最新资讯 |
| `web_fetch` | `url`(必填) | Structured Markdown | 完整内容获取/深度分析 |
| `get_config_info` | 无 | `{api_url,status,test}` | 连接诊断 |
| `update_config` | `field`(必填), `value`(必填) | `{status,old_value,new_value}` | 修改配置/切换Provider |
| `toggle_builtin_tools` | `action`(可选: on/off/status) | `{blocked,deny_list,file}` | 禁用/启用官方工具 |

## 执行策略
**查询构建**：广度用 `web_search`，深度用 `web_fetch`，特定平台设 `platform` 参数
**搜索执行**：优先摘要 → 关键 URL 补充完整内容 → 结果不足调整查询重试（禁止放弃）
**结果整合**：交叉验证 + **强制标注来源** `[标题](URL)` + 时间敏感信息注明日期

## 错误恢复

连接失败 → `get_config_info` 检查 | 无结果 → 放宽查询条件 | 超时 → 搜索替代源


## 核心约束

✅ 强制 GrokSearch 工具 + 输出必含来源引用 + 失败必重试 + 关键信息必验证
❌ 禁止无来源输出 + 禁止单次放弃 + 禁止未验证假设
```

#### 详细版提示词
<details>
<summary><b>💡 Grok Search Enhance 系统提示词（详细版）</b>（点击展开）</summary>

````markdown

  # Grok Search Enhance 系统提示词（详细版）

  ## 0. Module Activation
  **触发条件**：当需要执行以下操作时，自动激活本模块：
  - 网络搜索 / 信息检索 / 事实核查
  - 获取网页内容 / URL 解析 / 文档抓取
  - 查询最新信息 / 突破知识截止限制

  ## 1. Tool Routing Policy

  ### 强制替换规则
  | 需求场景 | ❌ 禁用 (Built-in) | ✅ 强制使用 (GrokSearch) |
  | :--- | :--- | :--- |
  | 网络搜索 | `WebSearch` | `mcp__grok-search__web_search` |
  | 网页抓取 | `WebFetch` | `mcp__grok-search__web_fetch` |
  | 配置诊断 | N/A | `mcp__grok-search__get_config_info` |

  ### 工具能力矩阵

| Tool | Parameters | Output | Use Case |
|------|------------|--------|----------|
| `web_search` | `query`(必填), `platform`/`min_results`/`max_results`(可选) | `[{title,url,content}]` | 多源聚合/事实核查/最新资讯 |
| `web_fetch` | `url`(必填) | Structured Markdown | 完整内容获取/深度分析 |
| `get_config_info` | 无 | `{api_url,status,test}` | 连接诊断 |
| `update_config` | `field`(必填), `value`(必填) | `{status,old_value,new_value}` | 修改配置/切换Provider |
| `toggle_builtin_tools` | `action`(可选: on/off/status) | `{blocked,deny_list,file}` | 禁用/启用官方工具 |


  ## 2. Search Workflow

  ### Phase 1: 查询构建 (Query Construction)
  1.  **意图识别**：分析用户需求，确定搜索类型：
      - **广度搜索**：多源信息聚合 → 使用 `web_search`
      - **深度获取**：单一 URL 完整内容 → 使用 `web_fetch`
  2.  **参数优化**：
      - 若需聚焦特定平台，设置 `platform` 参数
      - 根据需求复杂度调整 `min_results` / `max_results`

  ### Phase 2: 搜索执行 (Search Execution)
  1.  **首选策略**：优先使用 `web_search` 获取结构化摘要
  2.  **深度补充**：若摘要不足以回答问题，对关键 URL 调用 `web_fetch` 获取完整内容
  3.  **迭代检索**：若首轮结果不满足需求，**调整查询词**后重新搜索（禁止直接放弃）

  ### Phase 3: 结果整合 (Result Synthesis)
  1.  **信息验证**：交叉比对多源结果，识别矛盾信息
  2.  **时效标注**：对时间敏感信息，**必须**标注信息来源与时间
  3.  **引用规范**：输出中**强制包含**来源 URL，格式：`[标题](URL)`

  ## 3. Error Handling

  | 错误类型 | 诊断方法 | 恢复策略 |
  | :--- | :--- | :--- |
  | 连接失败 | 调用 `get_config_info` 检查配置 | 提示用户检查 API URL / Key |
  | 无搜索结果 | 检查 query 是否过于具体 | 放宽搜索词，移除限定条件 |
  | 网页抓取超时 | 检查 URL 可访问性 | 尝试搜索替代来源 |
  | 内容被截断 | 检查目标页面结构 | 分段抓取或提示用户直接访问 |

  ## 4. Anti-Patterns

  | ❌ 禁止行为 | ✅ 正确做法 |
  | :--- | :--- |
  | 搜索后不标注来源 | 输出**必须**包含 `[来源](URL)` 引用 |
  | 单次搜索失败即放弃 | 调整参数后至少重试 1 次 |
  | 假设网页内容而不抓取 | 对关键信息**必须**调用 `web_fetch` 验证 |
  | 忽略搜索结果的时效性 | 时间敏感信息**必须**标注日期 |

  ---
  模块说明：
  - 强制替换：明确禁用内置工具，强制路由到 GrokSearch
  - 三工具覆盖：web_search + web_fetch + get_config_info
  - 错误处理：包含配置诊断的恢复策略
  - 引用规范：强制标注来源，符合信息可追溯性要求
````

</details>

### 详细项目介绍

#### MCP 工具说明

本项目提供五个 MCP 工具：

##### `web_search` - 网络搜索

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | ✅ | - | 搜索查询语句 |
| `platform` | string | ❌ | `""` | 聚焦搜索平台（如 `"Twitter"`, `"GitHub, Reddit"`） |
| `min_results` | int | ❌ | `3` | 最少返回结果数 |
| `max_results` | int | ❌ | `10` | 最多返回结果数 |

**返回**：包含 `title`、`url`、`content` 的 JSON 数组


<details>
<summary><b>返回示例</b>（点击展开）</summary>

```json
[
  {
    "title": "Claude Code - Anthropic官方CLI工具",
    "url": "https://claude.com/claude-code",
    "description": "Anthropic推出的官方命令行工具，支持MCP协议集成，提供代码生成和项目管理功能"
  },
  {
    "title": "Model Context Protocol (MCP) 技术规范",
    "url": "https://modelcontextprotocol.io/docs",
    "description": "MCP协议官方文档，定义了AI模型与外部工具的标准化通信接口"
  },
  {
    ...
  }
]
```
</details>

##### `web_fetch` - 网页内容抓取

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `url` | string | ✅ | 目标网页 URL |

**功能**：获取完整网页内容并转换为结构化 Markdown，保留标题层级、列表、表格、代码块等元素

<details>
<summary><b>返回示例</b>（点击展开）</summary>

```markdown
---
source: https://modelcontextprotocol.io/docs/concepts/architecture
title: MCP 架构设计文档
fetched_at: 2024-01-15T10:30:00Z
---

# MCP 架构设计文档

## 目录
- [核心概念](#核心概念)
- [协议层次](#协议层次)
- [通信模式](#通信模式)

## 核心概念

Model Context Protocol (MCP) 是一个标准化的通信协议，用于连接 AI 模型与外部工具和数据源。
...

更多信息请访问 [官方文档](https://modelcontextprotocol.io)
```
</details>


##### `get_config_info` - 配置信息查询

**无需参数**。显示配置状态、测试 API 连接、返回响应时间和可用模型数量（API Key 自动脱敏）

<details>
<summary><b>返回示例</b>（点击展开）</summary>

```json
{
  "PROVIDER": "grok",
  "API_URL": "https://YOUR-API-URL/grok/v1",
  "API_KEY": "sk-a*****************xyz",
  "MODEL": "grok-4-fast",
  "DEBUG": false,
  "LOG_LEVEL": "INFO",
  "LOG_DIR": "/home/user/.config/grok-search/logs",
  "config_status": "✅ 配置完整",
  "connection_test": {
    "status": "✅ 连接成功",
    "message": "成功获取模型列表 (HTTP 200)，共 x 个模型",
    "response_time_ms": 234.56
  }
}
```

</details>

##### `update_config` - 配置修改

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `field` | string | ✅ | 配置字段名（如 `"PROVIDER"`, `"MODEL"`, `"API_KEY"`） |
| `value` | string | ✅ | 新的配置值 |

**支持的字段**：
- `PROVIDER`: 搜索提供者（`"grok"` 或 `"tavily"`）
- `API_URL`: API 端点 URL（Grok 专用）
- `API_KEY`: API 认证密钥
- `MODEL`: 模型 ID（如 `"grok-4-fast"`, `"grok-2-latest"`）
- `DEBUG`: 调试模式（`"true"` / `"false"`）
- `LOG_LEVEL`: 日志级别（`"DEBUG"` / `"INFO"` / `"WARNING"` / `"ERROR"`）
- `LOG_DIR`: 日志目录路径

**功能**：
- 修改配置并自动持久化到 `~/.config/grok-search/config.json`
- 支持切换 Provider（Grok / Tavily）
- 支持跨会话保持设置

<details>
<summary><b>返回示例</b>（点击展开）</summary>

```json
{
  "status": "✅ 成功",
  "field": "PROVIDER",
  "old_value": "grok",
  "new_value": "tavily",
  "config_file": "/home/user/.config/grok-search/config.json"
}
```

**使用示例**：

在 Claude 对话中输入：
```
切换到 Tavily 搜索
```

或直接说：
```
将模型改为 grok-2-latest
```

</details>

##### `toggle_builtin_tools` - 工具路由控制

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `action` | string | ❌ | `"status"` | 操作类型：`"on"`/`"enable"`(禁用官方工具)、`"off"`/`"disable"`(启用官方工具)、`"status"`/`"check"`(查看状态) |

**功能**：
- 控制项目级 `.claude/settings.json` 的 `permissions.deny` 配置
- 禁用/启用 Claude Code 官方的 `WebSearch` 和 `WebFetch` 工具
- 强制路由到 GrokSearch MCP 工具
- 自动定位项目根目录（查找 `.git`）
- 保留其他配置项

<details>
<summary><b>返回示例</b>（点击展开）</summary>

```json
{
  "blocked": true,
  "deny_list": ["WebFetch", "WebSearch"],
  "file": "/path/to/project/.claude/settings.json",
  "message": "官方工具已禁用"
}
```

**使用示例**：

```
# 禁用官方工具（推荐）
禁用官方的 search 和 fetch 工具

# 启用官方工具
启用官方的 search 和 fetch 工具

# 检查当前状态
显示官方工具的禁用状态
```

</details>

---

<details>
<summary><h2>项目架构</h2>（点击展开）</summary>

```
src/grok_search/
├── config.py          # 配置管理（环境变量 + 持久化）
├── server.py          # MCP 服务入口（注册工具）
├── logger.py          # 日志系统
├── utils.py           # 格式化工具
└── providers/
    ├── base.py        # SearchProvider 基类
    ├── grok.py        # Grok API 实现
    └── tavily.py      # Tavily API 实现
```

</details>

## 常见问题

**Q: 如何获取 Grok API 访问权限？**
A: 注册第三方平台 → 获取 API Endpoint 和 Key → 使用 `claude mcp add-json` 配置

**Q: 配置后如何验证？**
A: 在 Claude 对话中说"显示 grok-search 配置信息"，查看连接测试结果

## 许可证

本项目采用 [MIT License](LICENSE) 开源。

---

<div align="center">

**如果这个项目对您有帮助，请给个 ⭐ Star！**
[![Star History Chart](https://api.star-history.com/svg?repos=GuDaStudio/GrokSearch&type=date&legend=top-left)](https://www.star-history.com/#GuDaStudio/GrokSearch&type=date&legend=top-left)
</div>
