from abc import ABC, abstractmethod
from typing import Dict, List


class SearchResult:
    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        source: str = "",
        published_date: str = "",
    ):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.source = source
        self.published_date = published_date

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "published_date": self.published_date,
        }


class BaseSearchProvider(ABC):
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        pass
    
    @abstractmethod
    async def fetch(self, url: str, ctx=None) -> str:
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        pass
