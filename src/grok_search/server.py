import sys
from pathlib import Path

# 支持直接运行：添加 src 目录到 Python 路径
src_dir = Path(__file__).parent.parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from mcp.server.fastmcp import FastMCP, Context
from typing import Annotated, Optional
from pydantic import Field

# 尝试使用绝对导入（支持 mcp run）
try:
    from grok_search.providers.grok import GrokSearchProvider
    from grok_search.logger import log_info
    from grok_search.config import config
    from grok_search.sources import SourcesCache, merge_sources, new_session_id, split_answer_and_sources
    from grok_search.conversation import conversation_manager
    from grok_search.reflect import ReflectEngine
    from grok_search.planning import (
        engine as planning_engine,
    )
except ImportError:
    from .providers.grok import GrokSearchProvider
    from .logger import log_info
    from .config import config
    from .sources import SourcesCache, merge_sources, new_session_id, split_answer_and_sources
    from .conversation import conversation_manager
    from .reflect import ReflectEngine
    from .planning import (
        engine as planning_engine,
    )

import asyncio

mcp = FastMCP("grok-search")

_SOURCES_CACHE = SourcesCache(max_size=256)
_AVAILABLE_MODELS_CACHE: dict[tuple[str, str], list[str]] = {}
_AVAILABLE_MODELS_LOCK = asyncio.Lock()


async def _fetch_available_models(api_url: str, api_key: str) -> list[str]:
    import httpx

    models_url = f"{api_url.rstrip('/')}/models"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            models_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

    models: list[str] = []
    for item in (data or {}).get("data", []) or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            models.append(item["id"])
    return models


async def _get_available_models_cached(api_url: str, api_key: str) -> list[str]:
    key = (api_url, api_key)
    async with _AVAILABLE_MODELS_LOCK:
        if key in _AVAILABLE_MODELS_CACHE:
            return _AVAILABLE_MODELS_CACHE[key]

    try:
        models = await _fetch_available_models(api_url, api_key)
    except Exception:
        models = []

    async with _AVAILABLE_MODELS_LOCK:
        _AVAILABLE_MODELS_CACHE[key] = models
    return models


def _extra_results_to_sources(
    tavily_results: list[dict] | None,
    firecrawl_results: list[dict] | None,
) -> list[dict]:
    sources: list[dict] = []
    seen: set[str] = set()

    if firecrawl_results:
        for r in firecrawl_results:
            url = (r.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            item: dict = {"url": url, "provider": "firecrawl"}
            title = (r.get("title") or "").strip()
            if title:
                item["title"] = title
            desc = (r.get("description") or "").strip()
            if desc:
                item["description"] = desc
            sources.append(item)

    if tavily_results:
        for r in tavily_results:
            url = (r.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            item: dict = {"url": url, "provider": "tavily"}
            title = (r.get("title") or "").strip()
            if title:
                item["title"] = title
            content = (r.get("content") or "").strip()
            if content:
                item["description"] = content
            sources.append(item)

    return sources


@mcp.tool(
    name="web_search",
    description="""
    AI-powered web search via Grok API. Returns a single answer for a single query.

    Returns: session_id (for get_sources), conversation_id (for search_followup), content, sources_count.

    💡 **For complex multi-aspect topics**, use the recommended pipeline:
      1. Start with **search_planning** to generate a structured search plan (zero API cost)
      2. Execute each sub-query with **web_search**
      3. Use **search_followup** to drill into details within the same conversation context
      4. Use **search_reflect** for queries needing reflection, verification, or cross-validation
      5. Use **get_sources** to retrieve source details for any session_id

    For simple single-aspect lookups, just call web_search directly.
    """,
    meta={"version": "4.0.0", "author": "guda.studio"},
)
async def web_search(
    query: Annotated[str, "Clear, self-contained natural-language search query."],
    platform: Annotated[str, "Target platform to focus on (e.g., 'Twitter', 'GitHub', 'Reddit'). Leave empty for general web search."] = "",
    model: Annotated[str, "Optional model ID for this request only. This value is used ONLY when user explicitly provided."] = "",
    extra_sources: Annotated[int, "Number of additional reference results from Tavily/Firecrawl. Set 0 to disable. Default 0."] = 0,
) -> dict:
    return await _execute_search(query=query, platform=platform, model=model, extra_sources=extra_sources)


async def _execute_search(
    query: str,
    platform: str = "",
    model: str = "",
    extra_sources: int = 0,
    history: list[dict] | None = None,
    conversation_id: str = "",
) -> dict:
    """Core search logic shared by web_search, search_followup, and search_reflect."""
    session_id = new_session_id()
    try:
        api_url = config.grok_api_url
        api_key = config.grok_api_key
    except ValueError as e:
        await _SOURCES_CACHE.set(session_id, [])
        return {"error": "config_error", "message": f"配置错误: {str(e)}", "session_id": session_id, "conversation_id": "", "content": "", "sources_count": 0}

    effective_model = config.grok_model
    model_validation_warning = ""
    if model:
        available = await _get_available_models_cached(api_url, api_key)
        if available and model not in available:
            if config.strict_model_validation:
                await _SOURCES_CACHE.set(session_id, [])
                return {"error": "invalid_model", "message": f"无效模型: {model}", "session_id": session_id, "conversation_id": "", "content": "", "sources_count": 0}
            model_validation_warning = f"模型 {model} 不在 /models 列表中，已按非严格模式继续请求。"
        effective_model = model

    grok_provider = GrokSearchProvider(api_url, api_key, effective_model)

    # Conversation management
    conv_session = None
    if conversation_id:
        conv_session = await conversation_manager.get(conversation_id)
    if conv_session is None:
        conv_session = await conversation_manager.get_or_create()
        conversation_id = conv_session.session_id

    conv_session.add_user_message(query)

    # 计算额外信源配额
    has_tavily = bool(config.tavily_api_key)
    has_firecrawl = bool(config.firecrawl_api_key)
    firecrawl_count = 0
    tavily_count = 0
    if extra_sources > 0:
        if has_firecrawl and has_tavily:
            firecrawl_count = extra_sources // 2
            tavily_count = extra_sources - firecrawl_count
        elif has_firecrawl:
            firecrawl_count = extra_sources
        elif has_tavily:
            tavily_count = extra_sources

    # 并行执行搜索任务
    async def _safe_grok() -> str | Exception:
        try:
            return await grok_provider.search(query, platform, history=history)
        except Exception as e:
            return e

    async def _safe_tavily() -> list[dict] | None:
        try:
            if tavily_count:
                return await _call_tavily_search(query, tavily_count)
        except Exception:
            return None

    async def _safe_firecrawl() -> list[dict] | None:
        try:
            if firecrawl_count:
                return await _call_firecrawl_search(query, firecrawl_count)
        except Exception:
            return None

    coros: list = [_safe_grok()]
    if tavily_count > 0:
        coros.append(_safe_tavily())
    if firecrawl_count > 0:
        coros.append(_safe_firecrawl())

    gathered = await asyncio.gather(*coros)

    grok_result_or_error = gathered[0]
    if isinstance(grok_result_or_error, Exception):
        await _SOURCES_CACHE.set(session_id, [])
        return {
            "error": "search_error",
            "message": f"Grok 搜索失败: {str(grok_result_or_error)}",
            "session_id": session_id,
            "conversation_id": conversation_id,
            "content": "",
            "sources_count": 0,
        }

    grok_result: str = grok_result_or_error or ""
    tavily_results: list[dict] | None = None
    firecrawl_results: list[dict] | None = None
    idx = 1
    if tavily_count > 0:
        tavily_results = gathered[idx]
        idx += 1
    if firecrawl_count > 0:
        firecrawl_results = gathered[idx]

    answer, grok_sources = split_answer_and_sources(grok_result)
    extra = _extra_results_to_sources(tavily_results, firecrawl_results)
    all_sources = merge_sources(grok_sources, extra)

    conv_session.add_assistant_message(answer)

    await _SOURCES_CACHE.set(session_id, all_sources)
    result = {
        "session_id": session_id,
        "conversation_id": conversation_id,
        "content": answer,
        "sources_count": len(all_sources),
    }
    if model_validation_warning:
        result["warning"] = model_validation_warning
    return result


@mcp.tool(
    name="search_followup",
    description="""
    Ask a follow-up question in an existing search conversation context.
    Requires a conversation_id from a previous web_search or search_followup result.

    Use this when you need more details, want comparison, or want to ask about specific points from a previous answer.
    For a completely new topic, use web_search instead.
    """,
    meta={"version": "1.0.0", "author": "guda.studio"},
)
async def search_followup(
    query: Annotated[str, "Follow-up question to ask in the existing conversation context."],
    conversation_id: Annotated[str, "Conversation ID from a previous web_search or search_followup result."],
    extra_sources: Annotated[int, "Number of additional reference results from Tavily/Firecrawl. Default 0."] = 0,
) -> dict:
    # Get existing conversation for history
    conv_session = await conversation_manager.get(conversation_id)
    if conv_session is None:
        return {"error": "session_expired", "message": "会话已过期或不存在，请使用 web_search 开始新搜索。", "session_id": "", "conversation_id": conversation_id, "content": "", "sources_count": 0}

    history = conv_session.get_history()

    return await _execute_search(
        query=query,
        extra_sources=extra_sources,
        history=history,
        conversation_id=conversation_id,
    )


@mcp.tool(
    name="search_reflect",
    description="""
    Reflection-enhanced web search for important queries where accuracy matters.

    Performs an initial search, then reflects on the answer to identify gaps,
    automatically performs supplementary searches, and optionally cross-validates
    information across multiple sources.

    Use this instead of web_search when:
    - The question requires high accuracy
    - You need comprehensive coverage of a topic
    - Cross-validation of facts is important

    Can be used standalone or as the final verification step in the pipeline:
    search_planning → web_search → search_followup → **search_reflect**

    For simple lookups, use web_search instead (faster, cheaper).
    """,
    meta={"version": "1.0.0", "author": "guda.studio"},
)
async def search_reflect(
    query: Annotated[str, "Search query to research with reflection."],
    context: Annotated[str, "Optional background information or previous findings to consider."] = "",
    max_reflections: Annotated[int, "Number of reflection rounds (1-3). Higher = more thorough but slower."] = 1,
    cross_validate: Annotated[bool, "If true, cross-validates facts across search rounds for consistency."] = False,
    extra_sources: Annotated[int, "Number of Tavily/Firecrawl sources per search round. Default 3."] = 3,
) -> dict:
    try:
        api_url = config.grok_api_url
        api_key = config.grok_api_key
    except ValueError as e:
        return {"error": "config_error", "message": f"配置错误: {str(e)}", "session_id": "", "conversation_id": "", "content": "", "sources_count": 0}

    grok_provider = GrokSearchProvider(api_url, api_key, config.grok_model)
    engine = ReflectEngine(grok_provider, conversation_manager)

    # Create a search executor that uses _execute_search (with conversation_id reuse)
    async def executor(q: str, es: int, history: list[dict] | None, conv_id: str) -> dict:
        return await _execute_search(query=q, extra_sources=es, history=history, conversation_id=conv_id)

    return await engine.run(
        query=query,
        context=context,
        max_reflections=max_reflections,
        cross_validate=cross_validate,
        extra_sources=extra_sources,
        execute_search=executor,
    )


@mcp.tool(
    name="get_sources",
    description="""
    When you feel confused or curious about the search response content, use the session_id returned by web_search to invoke the this tool to obtain the corresponding list of information sources.
    Retrieve all cached sources for a previous web_search call.
    Provide the session_id returned by web_search to get the full source list.
    """,
    meta={"version": "1.0.0", "author": "guda.studio"},
)
async def get_sources(
    session_id: Annotated[str, "Session ID from previous web_search call."]
) -> dict:
    sources = await _SOURCES_CACHE.get(session_id)
    if sources is None:
        return {
            "session_id": session_id,
            "sources": [],
            "sources_count": 0,
            "error": "session_id_not_found_or_expired",
        }
    return {"session_id": session_id, "sources": sources, "sources_count": len(sources)}


async def _call_tavily_extract(url: str) -> str | None:
    import httpx
    api_url = config.tavily_api_url
    api_key = config.tavily_api_key
    if not api_key:
        return None
    endpoint = f"{api_url.rstrip('/')}/extract"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"urls": [url], "format": "markdown"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                content = data["results"][0].get("raw_content", "")
                return content if content and content.strip() else None
            return None
    except Exception:
        return None


async def _call_tavily_search(query: str, max_results: int = 6) -> list[dict] | None:
    import httpx
    api_key = config.tavily_api_key
    if not api_key:
        return None
    endpoint = f"{config.tavily_api_url.rstrip('/')}/search"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
        "include_raw_content": False,
        "include_answer": False,
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            return [
                {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", ""), "score": r.get("score", 0)}
                for r in results
            ] if results else None
    except Exception:
        return None


async def _call_firecrawl_search(query: str, limit: int = 14) -> list[dict] | None:
    import httpx
    api_key = config.firecrawl_api_key
    if not api_key:
        return None
    endpoint = f"{config.firecrawl_api_url.rstrip('/')}/search"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"query": query, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            results = data.get("data", {}).get("web", [])
            return [
                {"title": r.get("title", ""), "url": r.get("url", ""), "description": r.get("description", "")}
                for r in results
            ] if results else None
    except Exception:
        return None


async def _call_firecrawl_scrape(url: str, ctx=None) -> str | None:
    import httpx
    api_url = config.firecrawl_api_url
    api_key = config.firecrawl_api_key
    if not api_key:
        return None
    endpoint = f"{api_url.rstrip('/')}/scrape"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    max_retries = config.retry_max_attempts
    for attempt in range(max_retries):
        body = {
            "url": url,
            "formats": ["markdown"],
            "timeout": 60000,
            "waitFor": (attempt + 1) * 1500,
        }
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(endpoint, headers=headers, json=body)
                response.raise_for_status()
                data = response.json()
                markdown = data.get("data", {}).get("markdown", "")
                if markdown and markdown.strip():
                    return markdown
                await log_info(ctx, f"Firecrawl: markdown为空, 重试 {attempt + 1}/{max_retries}", config.debug_enabled)
        except Exception as e:
            await log_info(ctx, f"Firecrawl error: {e}", config.debug_enabled)
            return None
    return None


@mcp.tool(
    name="web_fetch",
    description="""
    Fetches and extracts complete content from a URL, returning it as a structured Markdown document.

    **Key Features:**
        - **Full Content Extraction:** Retrieves and parses all meaningful content (text, images, links, tables, code blocks).
        - **Markdown Conversion:** Converts HTML structure to well-formatted Markdown with preserved hierarchy.
        - **Content Fidelity:** Maintains 100% content fidelity without summarization or modification.

    **Edge Cases & Best Practices:**
        - Ensure URL is complete and accessible (not behind authentication or paywalls).
        - May not capture dynamically loaded content requiring JavaScript execution.
        - Large pages may take longer to process; consider timeout implications.
    """,
    meta={"version": "1.3.0", "author": "guda.studio"},
)
async def web_fetch(
    url: Annotated[str, "Valid HTTP/HTTPS web address pointing to the target page. Must be complete and accessible."],
    ctx: Context = None
) -> str:
    await log_info(ctx, f"Begin Fetch: {url}", config.debug_enabled)

    result = await _call_tavily_extract(url)
    if result:
        await log_info(ctx, "Fetch Finished (Tavily)!", config.debug_enabled)
        return result

    await log_info(ctx, "Tavily unavailable or failed, trying Firecrawl...", config.debug_enabled)
    result = await _call_firecrawl_scrape(url, ctx)
    if result:
        await log_info(ctx, "Fetch Finished (Firecrawl)!", config.debug_enabled)
        return result

    await log_info(ctx, "Fetch Failed!", config.debug_enabled)
    if not config.tavily_api_key and not config.firecrawl_api_key:
        return "配置错误: TAVILY_API_KEY 和 FIRECRAWL_API_KEY 均未配置"
    return "提取失败: 所有提取服务均未能获取内容"


async def _call_tavily_map(url: str, instructions: str = None, max_depth: int = 1,
                           max_breadth: int = 20, limit: int = 50, timeout: int = 150) -> str:
    import httpx
    import json
    api_url = config.tavily_api_url
    api_key = config.tavily_api_key
    if not api_key:
        return "配置错误: TAVILY_API_KEY 未配置，请设置环境变量 TAVILY_API_KEY"
    endpoint = f"{api_url.rstrip('/')}/map"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"url": url, "max_depth": max_depth, "max_breadth": max_breadth, "limit": limit, "timeout": timeout}
    if instructions:
        body["instructions"] = instructions
    try:
        async with httpx.AsyncClient(timeout=float(timeout + 10)) as client:
            response = await client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            return json.dumps({
                "base_url": data.get("base_url", ""),
                "results": data.get("results", []),
                "response_time": data.get("response_time", 0)
            }, ensure_ascii=False, indent=2)
    except httpx.TimeoutException:
        return f"映射超时: 请求超过{timeout}秒"
    except httpx.HTTPStatusError as e:
        return f"HTTP错误: {e.response.status_code} - {e.response.text[:200]}"
    except Exception as e:
        return f"映射错误: {str(e)}"


@mcp.tool(
    name="web_map",
    description="""
    Maps a website's structure by traversing it like a graph, discovering URLs and generating a comprehensive site map.

    **Key Features:**
        - **Graph Traversal:** Explores website structure starting from root URL.
        - **Depth & Breadth Control:** Configure traversal limits to balance coverage and performance.
        - **Instruction Filtering:** Use natural language to focus crawler on specific content types.

    **Edge Cases & Best Practices:**
        - Start with low max_depth (1-2) for initial exploration, increase if needed.
        - Use instructions to filter for specific content (e.g., "only documentation pages").
        - Large sites may hit timeout limits; adjust timeout and limit parameters accordingly.
    """,
    meta={"version": "1.3.0", "author": "guda.studio"},
)
async def web_map(
    url: Annotated[str, "Root URL to begin the mapping (e.g., 'https://docs.example.com')."],
    instructions: Annotated[str, "Natural language instructions for the crawler to filter or focus on specific content."] = "",
    max_depth: Annotated[int, "Maximum depth of mapping from the base URL (1-5)."] = 1,
    max_breadth: Annotated[int, "Maximum number of links to follow per page (1-500)."] = 20,
    limit: Annotated[int, "Total number of links to process before stopping (1-500)."] = 50,
    timeout: Annotated[int, "Maximum time in seconds for the operation (10-150)."] = 150
) -> str:
    result = await _call_tavily_map(url, instructions, max_depth, max_breadth, limit, timeout)
    return result


@mcp.tool(
    name="get_config_info",
    description="""
    Returns current Grok Search MCP server configuration and tests API connectivity.

    **Key Features:**
        - **Configuration Check:** Verifies environment variables and current settings.
        - **Connection Test:** Sends request to /models endpoint to validate API access.
        - **Model Discovery:** Lists all available models from the API.

    **Edge Cases & Best Practices:**
        - Use this tool first when debugging connection or configuration issues.
        - API keys are automatically masked for security in the response.
        - Connection test timeout is 10 seconds; network issues may cause delays.
    """,
    meta={"version": "1.3.0", "author": "guda.studio"},
)
async def get_config_info() -> str:
    import json
    import httpx

    config_info = config.get_config_info()

    # 添加连接测试
    test_result = {
        "status": "未测试",
        "message": "",
        "response_time_ms": 0
    }

    try:
        api_url = config.grok_api_url
        api_key = config.grok_api_key

        # 构建 /models 端点 URL
        models_url = f"{api_url.rstrip('/')}/models"

        # 发送测试请求
        import time
        start_time = time.time()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                models_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )

            response_time = (time.time() - start_time) * 1000  # 转换为毫秒

            if response.status_code == 200:
                test_result["status"] = "✅ 连接成功"
                test_result["message"] = f"成功获取模型列表 (HTTP {response.status_code})"
                test_result["response_time_ms"] = round(response_time, 2)

                # 尝试解析返回的模型列表
                try:
                    models_data = response.json()
                    if "data" in models_data and isinstance(models_data["data"], list):
                        model_count = len(models_data["data"])
                        test_result["message"] += f"，共 {model_count} 个模型"

                        # 提取所有模型的 ID/名称
                        model_names = []
                        for model in models_data["data"]:
                            if isinstance(model, dict) and "id" in model:
                                model_names.append(model["id"])

                        if model_names:
                            test_result["available_models"] = model_names
                except:
                    pass
            else:
                test_result["status"] = "⚠️ 连接异常"
                test_result["message"] = f"HTTP {response.status_code}: {response.text[:100]}"
                test_result["response_time_ms"] = round(response_time, 2)

    except httpx.TimeoutException:
        test_result["status"] = "❌ 连接超时"
        test_result["message"] = "请求超时（10秒），请检查网络连接或 API URL"
    except httpx.RequestError as e:
        test_result["status"] = "❌ 连接失败"
        test_result["message"] = f"网络错误: {str(e)}"
    except ValueError as e:
        test_result["status"] = "❌ 配置错误"
        test_result["message"] = str(e)
    except Exception as e:
        test_result["status"] = "❌ 测试失败"
        test_result["message"] = f"未知错误: {str(e)}"

    config_info["connection_test"] = test_result

    return json.dumps(config_info, ensure_ascii=False, indent=2)


@mcp.tool(
    name="switch_model",
    description="""
    Switches the default Grok model used for search and fetch operations, persisting the setting.

    **Key Features:**
        - **Model Selection:** Change the AI model for web search and content fetching.
        - **Persistent Storage:** Model preference saved to ~/.config/grok-search/config.json.
        - **Immediate Effect:** New model used for all subsequent operations.

    **Edge Cases & Best Practices:**
        - Use get_config_info to verify available models before switching.
        - Invalid model IDs may cause API errors in subsequent requests.
        - Model changes persist across sessions until explicitly changed again.
    """,
    meta={"version": "1.3.0", "author": "guda.studio"},
)
async def switch_model(
    model: Annotated[str, "Model ID to switch to (e.g., 'grok-4-fast', 'grok-2-latest', 'grok-vision-beta')."]
) -> str:
    import json

    try:
        previous_model = config.grok_model
        config.set_model(model)
        current_model = config.grok_model

        result = {
            "status": "✅ 成功",
            "previous_model": previous_model,
            "current_model": current_model,
            "message": f"模型已从 {previous_model} 切换到 {current_model}",
            "config_file": str(config.config_file)
        }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except ValueError as e:
        result = {
            "status": "❌ 失败",
            "message": f"切换模型失败: {str(e)}"
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        result = {
            "status": "❌ 失败",
            "message": f"未知错误: {str(e)}"
        }
        return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(
    name="toggle_builtin_tools",
    description="""
    Toggle Claude Code's built-in WebSearch and WebFetch tools on/off.

    **Key Features:**
        - **Tool Control:** Enable or disable Claude Code's native web tools.
        - **Project Scope:** Changes apply to current project's .claude/settings.json.
        - **Status Check:** Query current state without making changes.

    **Edge Cases & Best Practices:**
        - Use "on" to block built-in tools when preferring this MCP server's implementation.
        - Use "off" to restore Claude Code's native tools.
        - Use "status" to check current configuration without modification.
    """,
    meta={"version": "1.3.0", "author": "guda.studio"},
)
async def toggle_builtin_tools(
    action: Annotated[str, "Action to perform: 'on' (block built-in), 'off' (allow built-in), or 'status' (check current state)."] = "status"
) -> str:
    import json

    # Locate project root
    root = Path.cwd()
    while root != root.parent and not (root / ".git").exists():
        root = root.parent

    settings_path = root / ".claude" / "settings.json"
    tools = ["WebFetch", "WebSearch"]

    # Load or initialize
    if settings_path.exists():
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    else:
        settings = {"permissions": {"deny": []}}

    deny = settings.setdefault("permissions", {}).setdefault("deny", [])
    blocked = all(t in deny for t in tools)

    # Execute action
    if action in ["on", "enable"]:
        for t in tools:
            if t not in deny:
                deny.append(t)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        msg = "官方工具已禁用"
        blocked = True
    elif action in ["off", "disable"]:
        deny[:] = [t for t in deny if t not in tools]
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        msg = "官方工具已启用"
        blocked = False
    else:
        msg = f"官方工具当前{'已禁用' if blocked else '已启用'}"

    return json.dumps({
        "blocked": blocked,
        "deny_list": deny,
        "file": str(settings_path),
        "message": msg
    }, ensure_ascii=False, indent=2)


@mcp.tool(
    name="search_planning",
    description="""
    A structured thinking scaffold for planning web searches BEFORE execution. Produces no side effects — only organizes your reasoning into a reusable plan.

    **WHEN TO USE**: Before any search requiring 2+ tool calls, or when the query is ambiguous/multi-faceted. Skip for single obvious lookups.

    **HOW**: Call once per phase, filling only that phase's structured field. The server tracks your session and signals when the plan is complete.

    ## Phases (call in order, one per invocation)

    ### 1. `intent_analysis` → fill `intent`
    Distill the user's real question. Classify type and time sensitivity. Surface ambiguities and flawed premises. Identify `unverified_terms` — external classifications/rankings/taxonomies (e.g., "CCF-A", "Fortune 500") whose contents you cannot reliably enumerate from memory.

    ### 2. `complexity_assessment` → fill `complexity`
    Rate 1-3. This controls how many phases are required:
    - **Level 1** (1-2 searches): phases 1-3 only → then execute
    - **Level 2** (3-5 searches): phases 1-5
    - **Level 3** (6+ searches): all 6 phases

    ### 3. `query_decomposition` → fill `sub_queries`
    Split into non-overlapping sub-queries along ONE decomposition axis (e.g., by venue type OR by technique — never both). Each `boundary` must state mutual exclusion with sibling sub-queries. Use `depends_on` for sequential dependencies.
    **Prerequisite rule**: If Phase 1 identified `unverified_terms`, create a prerequisite sub-query to verify each term's current contents FIRST. Other sub-queries must `depends_on` it — do NOT hardcode assumed values from training data.

    ### 4. `search_strategy` → fill `strategy`
    Design concise search terms (max 8 words each). One term serves one sub-query. Choose approach:
    - `broad_first`: round 1 wide scan → round 2+ narrow based on findings (exploratory)
    - `narrow_first`: precise first, expand if needed (analytical)
    - `targeted`: known-item retrieval (factual)

    ### 5. `tool_selection` → fill `tool_plan`
    Map each sub-query to optimal tool:
    - **web_search**(query, platform?, extra_sources?): general retrieval
    - **search_followup**(query, conversation_id): drill into details in same conversation
    - **search_reflect**(query, context?, cross_validate?): high-accuracy with reflection & validation
    - **web_fetch**(url): extract full markdown from known URL
    - **web_map**(url, instructions?, max_depth?): discover site structure

    ### 6. `execution_order` → fill `execution_order`
    Group independent sub-queries into parallel batches. Sequence dependent ones.

    ## Anti-patterns (AVOID)
    - ❌ `codebase RAG retrieval augmented generation 2024 2025 paper` (9 words, synonym stacking)
      ✅ `codebase RAG papers 2024` (4 words, concise)
    - ❌ purpose: "sq1+sq2" (merged scope defeats decomposition)
      ✅ purpose: "sq2" (one term, one goal)
    - ❌ Decompose by venue (sq1=SE, sq2=AI) AND by technique (sq3=indexing, sq4=repo-level) — creates overlapping matrix
      ✅ Pick ONE axis: by venue (sq1=SE, sq2=AI, sq3=IR) OR by technique (sq1=RAG systems, sq2=indexing, sq3=retrieval)
    - ❌ All terms round 1 with broad_first (no depth)
      ✅ Round 1: broad terms → Round 2: refined by Round 1 findings
    - ❌ Level 3 for simple "what is X?" → Level 1 suffices
    - ❌ Skipping intent_analysis → always start here

    ## Session & Revision
    First call: leave `session_id` empty → server returns one. Pass it back in subsequent calls.
    To revise: set `is_revision=true` + `revises_phase` to overwrite a previous phase.
    Plan auto-completes when all required phases (per complexity level) are filled.
    """,
    meta={"version": "1.0.0", "author": "guda.studio"},
)
async def search_planning(
    phase: Annotated[str, "Current phase: intent_analysis | complexity_assessment | query_decomposition | search_strategy | tool_selection | execution_order"],
    thought: Annotated[str, "Your reasoning for this phase — explain WHY, not just WHAT"],
    next_phase_needed: Annotated[bool, "true to continue planning, false when done or plan auto-completes"],
    intent_json: Annotated[str, "JSON string matching IntentOutput schema"] = "",
    complexity_json: Annotated[str, "JSON string matching ComplexityOutput schema"] = "",
    sub_queries_json: Annotated[str, "JSON array of SubQuery objects"] = "",
    strategy_json: Annotated[str, "JSON string matching StrategyOutput schema"] = "",
    tool_plan_json: Annotated[str, "JSON array of ToolPlanItem objects"] = "",
    execution_order_json: Annotated[str, "JSON string matching ExecutionOrderOutput schema"] = "",
    session_id: Annotated[str, "Session ID from previous call. Empty for new session."] = "",
    is_revision: Annotated[bool, "true to revise a previously completed phase"] = False,
    revises_phase: Annotated[str, "Phase name to revise (required if is_revision=true)"] = "",
    confidence: Annotated[float, "Confidence in this phase's output (0.0-1.0)"] = 1.0,
) -> str:
    import json
    
    def _parse_json(jstr):
        if not jstr or not jstr.strip():
            return None
        try:
            return json.loads(jstr)
        except Exception:
            return None

    phase_data_map = {
        "intent_analysis": _parse_json(intent_json),
        "complexity_assessment": _parse_json(complexity_json),
        "query_decomposition": _parse_json(sub_queries_json),
        "search_strategy": _parse_json(strategy_json),
        "tool_selection": _parse_json(tool_plan_json),
        "execution_order": _parse_json(execution_order_json),
    }

    target = revises_phase if is_revision and revises_phase else phase
    phase_data = phase_data_map.get(target)

    result = planning_engine.process_phase(
        phase=phase,
        thought=thought,
        session_id=session_id,
        is_revision=is_revision,
        revises_phase=revises_phase,
        confidence=confidence,
        phase_data=phase_data,
    )

    return json.dumps(result, ensure_ascii=False, indent=2)


def main():
    import signal
    import os
    import threading

    # 信号处理（仅主线程）
    if threading.current_thread() is threading.main_thread():
        def handle_shutdown(signum, frame):
            os._exit(0)
        signal.signal(signal.SIGINT, handle_shutdown)
        if sys.platform != 'win32':
            signal.signal(signal.SIGTERM, handle_shutdown)

    # Windows 父进程监控
    if sys.platform == 'win32':
        import time
        import ctypes
        parent_pid = os.getppid()

        def is_parent_alive(pid):
            """Windows 下检查进程是否存活"""
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            result = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            return result and exit_code.value == STILL_ACTIVE

        def monitor_parent():
            while True:
                if not is_parent_alive(parent_pid):
                    os._exit(0)
                time.sleep(2)

        threading.Thread(target=monitor_parent, daemon=True).start()

    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        pass
    finally:
        os._exit(0)


if __name__ == "__main__":
    main()
