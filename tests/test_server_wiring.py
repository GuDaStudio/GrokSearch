"""Structural checks that shipped web_search uses the dual-split allocator."""

from pathlib import Path

import grok_search.server as server
from grok_search.extras import allocate_extra_sources


def test_server_exports_allocate_extra_sources():
    assert server.allocate_extra_sources is allocate_extra_sources


def test_web_search_source_uses_allocator_not_round_star_one():
    src = Path(server.__file__).read_text(encoding="utf-8")
    assert "allocate_extra_sources(" in src
    assert "round(extra_sources * 1)" not in src


def test_web_fetch_orders_tavily_before_firecrawl():
    src = Path(server.__file__).read_text(encoding="utf-8")
    tavily_pos = src.index("_call_tavily_extract")
    firecrawl_pos = src.index("_call_firecrawl_scrape")
    assert tavily_pos < firecrawl_pos


def test_web_map_uses_tavily_map():
    src = Path(server.__file__).read_text(encoding="utf-8")
    assert "async def web_map" in src
    assert "_call_tavily_map" in src
