import httpx
from typing import List
from .base import BaseSearchProvider, SearchResult
from ..config import config
from tavily import TavilyClient
from ..logger import log_info


class TavilyProvider(BaseSearchProvider):
    SEARCH_URL = "https://api.tavily.com/search"
    EXTRACT_URL = "https://api.tavily.com/extract"

    def __init__(self, api_key: str):
        super().__init__("https://api.tavily.com", api_key)

    def get_provider_name(self) -> str:
        return "Tavily"

    async def search(self, query: str, platform: str = "", min_results: int = 3, max_results: int = 10, ctx=None) -> str:
        tavily_client = TavilyClient(api_key=self.api_key)
        response = tavily_client.search(query=query, search_depth="advanced")
        return str(response['results'])

    async def fetch(self, url: str, ctx=None) -> str:
        tavily_client = TavilyClient(api_key=self.api_key)
        log_info(ctx, f"Tavily fetch url: {url}", config.debug_enabled)
        response = tavily_client.extract(url)
        log_info(ctx, f"Tavily fetch response: {response}", config.debug_enabled)
        return response['results'][0]['raw_content']
