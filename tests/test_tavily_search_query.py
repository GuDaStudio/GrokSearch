import json
import logging
from typing import get_args, get_type_hints

import httpx
import pytest

import grok_search.server as server
from grok_search.providers.contracts import SearchOutput


TAVILY_QUERY_LIMIT = server.TAVILY_MAX_QUERY_CHARS


@pytest.fixture
def posted_json(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    requests: list[dict] = []
    real_async_client = httpx.AsyncClient

    async def _record_request(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(_record_request)

    def _recording_client(*args, **kwargs) -> httpx.AsyncClient:
        return real_async_client(*args, transport=transport, **kwargs)

    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    monkeypatch.setattr(httpx, "AsyncClient", _recording_client)
    return requests


def test_tavily_query_limit_matches_api_contract() -> None:
    assert TAVILY_QUERY_LIMIT == 400


def test_web_search_query_guidance_explains_provider_specific_limit() -> None:
    query_annotation = get_type_hints(server.web_search, include_extras=True)["query"]
    guidance = get_args(query_annotation)[1]

    assert "Keep it concise" in guidance
    assert f"first {TAVILY_QUERY_LIMIT}" in guidance
    assert "Grok and Firecrawl retain the full query" in guidance


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected_query"),
    [
        pytest.param("short query", "short query", id="short-unchanged"),
        pytest.param(
            "x" * TAVILY_QUERY_LIMIT,
            "x" * TAVILY_QUERY_LIMIT,
            id="exactly-400-unchanged",
        ),
        pytest.param(
            "x" * (TAVILY_QUERY_LIMIT + 1),
            "x" * TAVILY_QUERY_LIMIT,
            id="over-400-clamped",
        ),
        pytest.param(
            "界" * (TAVILY_QUERY_LIMIT + 1),
            "界" * TAVILY_QUERY_LIMIT,
            id="unicode-clamped-by-character",
        ),
    ],
)
async def test_tavily_search_serializes_query_within_character_limit(
    posted_json: list[dict],
    query: str,
    expected_query: str,
) -> None:
    await server._call_tavily_search(query)

    assert len(posted_json) == 1
    assert posted_json[0]["query"] == expected_query
    assert len(posted_json[0]["query"]) <= TAVILY_QUERY_LIMIT


@pytest.mark.asyncio
async def test_tavily_search_logs_lengths_without_query_content(
    posted_json: list[dict],
    caplog: pytest.LogCaptureFixture,
) -> None:
    query = "private-query-content-" + ("x" * TAVILY_QUERY_LIMIT)

    with caplog.at_level(logging.WARNING, logger="grok_search"):
        await server._call_tavily_search(query)

    assert len(posted_json) == 1
    assert [record.getMessage() for record in caplog.records] == [
        f"Tavily search query truncated from {len(query)} "
        f"to {TAVILY_QUERY_LIMIT} characters"
    ]
    assert query not in caplog.text


@pytest.mark.asyncio
async def test_web_search_keeps_full_query_for_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, str] = {}
    query = "full-query-" + ("x" * TAVILY_QUERY_LIMIT)

    class _RecordingGrokProvider:
        def __init__(self, api_url: str, api_key: str, model: str) -> None:
            pass

        async def search(self, received_query: str, platform: str) -> SearchOutput:
            calls["grok"] = received_query
            return SearchOutput(content="answer")

    async def _record_tavily(received_query: str, max_results: int):
        calls["tavily_helper"] = received_query
        return None

    async def _record_firecrawl(received_query: str, limit: int):
        calls["firecrawl"] = received_query
        return None

    monkeypatch.setenv("GROK_API_URL", "https://grok.test/v1")
    monkeypatch.setenv("GROK_API_KEY", "test-grok-key")
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-firecrawl-key")
    monkeypatch.setattr(server, "GrokSearchProvider", _RecordingGrokProvider)
    monkeypatch.setattr(server, "_call_tavily_search", _record_tavily)
    monkeypatch.setattr(server, "_call_firecrawl_search", _record_firecrawl)

    await server.web_search(query, extra_sources=2)

    assert calls == {
        "grok": query,
        "tavily_helper": query,
        "firecrawl": query,
    }
