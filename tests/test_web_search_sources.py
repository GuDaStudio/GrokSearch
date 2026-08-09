import pytest

import grok_search.server as server
from grok_search.providers.contracts import NormalizedSource, SearchOutput


@pytest.mark.asyncio
async def test_web_search_merges_structured_fallback_and_extra_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeGrokProvider:
        def __init__(self, api_url: str, api_key: str, model: str) -> None:
            pass

        async def search(self, query: str, platform: str) -> SearchOutput:
            return SearchOutput(
                content=(
                    "Answer body\n\n"
                    "## Sources\n"
                    "- [Fallback A](https://example.test/a)\n"
                    "- [Fallback C](https://example.test/c)"
                ),
                sources=(
                    NormalizedSource(
                        url="https://example.test/a",
                        title="Structured A",
                        provider="grok",
                    ),
                    NormalizedSource(
                        url="https://example.test/b",
                        provider="grok",
                    ),
                ),
            )

    async def _fake_tavily(query: str, max_results: int) -> list[dict]:
        return [
            {
                "url": "https://example.test/d",
                "title": "Tavily D",
                "content": "D description",
            }
        ]

    async def _fake_firecrawl(query: str, limit: int) -> list[dict]:
        return [
            {
                "url": "https://example.test/b",
                "title": "Firecrawl B",
                "description": "B description",
            }
        ]

    monkeypatch.setenv("GROK_API_URL", "https://grok.test/v1")
    monkeypatch.setenv("GROK_API_KEY", "test-grok-key")
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    monkeypatch.setenv("FIRECRAWL_API_KEY", "test-firecrawl-key")
    monkeypatch.setattr(server, "GrokSearchProvider", _FakeGrokProvider)
    monkeypatch.setattr(server, "_call_tavily_search", _fake_tavily)
    monkeypatch.setattr(server, "_call_firecrawl_search", _fake_firecrawl)

    search_response = await server.web_search("query", extra_sources=2)
    source_response = await server.get_sources(search_response["session_id"])

    assert set(search_response) == {"session_id", "content", "sources_count"}
    assert search_response["content"] == "Answer body"
    assert search_response["sources_count"] == 4
    assert source_response == {
        "session_id": search_response["session_id"],
        "sources": [
            {
                "url": "https://example.test/a",
                "title": "Structured A",
                "provider": "grok",
            },
            {
                "url": "https://example.test/b",
                "provider": "grok",
                "title": "Firecrawl B",
                "description": "B description",
            },
            {"url": "https://example.test/c", "title": "Fallback C"},
            {
                "url": "https://example.test/d",
                "provider": "tavily",
                "title": "Tavily D",
                "description": "D description",
            },
        ],
        "sources_count": 4,
    }
