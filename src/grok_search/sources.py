import ast
import copy
import json
import re
import uuid
from collections import OrderedDict
from typing import Any

import asyncio

from .providers.contracts import NormalizedSource, merge_normalized_sources
from .utils import extract_unique_urls


_MD_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_SOURCES_HEADING_PATTERN = re.compile(
    r"(?im)^"
    r"(?:#{1,6}\s*)?"
    r"(?:\*\*|__)?\s*"
    r"(sources?|references?|citations?|信源|参考资料|参考|引用|来源列表|来源)"
    r"\s*(?:\*\*|__)?"
    r"(?:\s*[（(][^)\n]*[)）])?"
    r"\s*[:：]?\s*$"
)
_SOURCES_FUNCTION_PATTERN = re.compile(
    r"(?im)(^|\n)\s*(sources|source|citations|citation|references|reference|citation_card|source_cards|source_card)\s*\("
)


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


class SourcesCache:
    def __init__(self, max_size: int = 256):
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._cache: OrderedDict[str, list[dict]] = OrderedDict()

    async def set(self, session_id: str, sources: list[dict]) -> None:
        async with self._lock:
            self._cache[session_id] = copy.deepcopy(sources)
            self._cache.move_to_end(session_id)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    async def get(self, session_id: str) -> list[dict] | None:
        async with self._lock:
            sources = self._cache.get(session_id)
            if sources is None:
                return None
            self._cache.move_to_end(session_id)
            return copy.deepcopy(sources)


def merge_sources(
    *source_lists: list[dict | NormalizedSource] | tuple[NormalizedSource, ...],
) -> list[dict]:
    normalized_sources: list[NormalizedSource] = []
    for sources in source_lists:
        for item in sources or []:
            source = (
                item
                if isinstance(item, NormalizedSource)
                else NormalizedSource.from_mapping(item)
                if isinstance(item, dict)
                else None
            )
            if source is not None:
                normalized_sources.append(source)
    return [source.to_dict() for source in merge_normalized_sources(normalized_sources)]


def split_answer_and_sources(text: str) -> tuple[str, list[dict]]:
    raw = (text or "").strip()
    if not raw:
        return "", []

    split = _split_function_call_sources(raw)
    if split:
        return split

    split = _split_heading_sources(raw)
    if split:
        return split

    split = _split_details_block_sources(raw)
    if split:
        return split

    split = _split_tail_link_block(raw)
    if split:
        return split

    return raw, _extract_sources_from_text(raw)


def _split_function_call_sources(text: str) -> tuple[str, list[dict]] | None:
    matches = list(_SOURCES_FUNCTION_PATTERN.finditer(text))
    if not matches:
        return None

    for m in reversed(matches):
        open_paren_idx = m.end() - 1
        extracted = _extract_balanced_call_at_end(text, open_paren_idx)
        if not extracted:
            continue

        close_paren_idx, args_text = extracted
        sources = _parse_sources_payload(args_text)
        if not sources:
            continue

        answer = text[: m.start()].rstrip()
        return answer, sources

    return None


def _extract_balanced_call_at_end(text: str, open_paren_idx: int) -> tuple[int, str] | None:
    if open_paren_idx < 0 or open_paren_idx >= len(text) or text[open_paren_idx] != "(":
        return None

    depth = 1
    in_string: str | None = None
    escape = False

    for idx in range(open_paren_idx + 1, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == in_string:
                in_string = None
            continue

        if ch in ("'", '"'):
            in_string = ch
            continue

        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                if text[idx + 1 :].strip():
                    return None
                args_text = text[open_paren_idx + 1 : idx]
                return idx, args_text

    return None


def _split_heading_sources(text: str) -> tuple[str, list[dict]] | None:
    matches = list(_SOURCES_HEADING_PATTERN.finditer(text))
    if not matches:
        return None

    for m in reversed(matches):
        start = m.start()
        sources_text = text[start:]
        sources = _extract_sources_from_text(sources_text)
        if not sources:
            continue
        answer = text[:start].rstrip()
        return answer, sources
    return None


def _split_tail_link_block(text: str) -> tuple[str, list[dict]] | None:
    lines = text.splitlines()
    if not lines:
        return None

    idx = len(lines) - 1
    while idx >= 0 and not lines[idx].strip():
        idx -= 1
    if idx < 0:
        return None

    tail_end = idx
    link_like_count = 0
    while idx >= 0:
        line = lines[idx].strip()
        if not line:
            idx -= 1
            continue
        if not _is_link_only_line(line):
            break
        link_like_count += 1
        idx -= 1

    tail_start = idx + 1
    if link_like_count < 2:
        return None

    block_text = "\n".join(lines[tail_start : tail_end + 1])
    sources = _extract_sources_from_text(block_text)
    if not sources:
        return None

    answer = "\n".join(lines[:tail_start]).rstrip()
    return answer, sources


def _split_details_block_sources(text: str) -> tuple[str, list[dict]] | None:
    lower = text.lower()
    close_idx = lower.rfind("</details>")
    if close_idx == -1:
        return None
    tail = text[close_idx + len("</details>") :].strip()
    if tail:
        return None

    open_idx = lower.rfind("<details", 0, close_idx)
    if open_idx == -1:
        return None

    block_text = text[open_idx : close_idx + len("</details>")]
    sources = _extract_sources_from_text(block_text)
    if len(sources) < 2:
        return None

    answer = text[:open_idx].rstrip()
    return answer, sources


def _is_link_only_line(line: str) -> bool:
    stripped = re.sub(r"^\s*(?:[-*]|\d+\.)\s*", "", line).strip()
    if not stripped:
        return False
    if stripped.startswith(("http://", "https://")):
        return True
    if _MD_LINK_PATTERN.search(stripped):
        return True
    return False


def _parse_sources_payload(payload: str) -> list[dict]:
    payload = (payload or "").strip().rstrip(";")
    if not payload:
        return []

    data: Any = None
    try:
        data = json.loads(payload)
    except Exception:
        try:
            data = ast.literal_eval(payload)
        except Exception:
            data = None

    if data is None:
        return _extract_sources_from_text(payload)

    if isinstance(data, dict):
        for key in ("sources", "citations", "references", "urls"):
            if key in data:
                return _normalize_sources(data[key])
        return _normalize_sources(data)

    return _normalize_sources(data)


def _normalize_sources(data: Any) -> list[dict]:
    items: list[Any]
    if isinstance(data, (list, tuple)):
        items = list(data)
    elif isinstance(data, dict):
        items = [data]
    else:
        items = [data]

    normalized: list[dict] = []
    seen: set[str] = set()

    for item in items:
        if isinstance(item, str):
            for url in extract_unique_urls(item):
                source = NormalizedSource.from_mapping({"url": url})
                if source is not None and source.url not in seen:
                    seen.add(source.url)
                    normalized.append(source.to_dict())
            continue

        if isinstance(item, (list, tuple)) and len(item) >= 2:
            title, url = item[0], item[1]
            source = NormalizedSource.from_mapping({"url": url, "title": title})
            if source is not None and source.url not in seen:
                seen.add(source.url)
                normalized.append(source.to_dict())
            continue

        if isinstance(item, dict):
            source = NormalizedSource.from_mapping(item)
            if source is None or source.url in seen:
                continue
            seen.add(source.url)
            normalized.append(source.to_dict())
            continue

    return normalized


def _extract_sources_from_text(text: str) -> list[dict]:
    raw = text or ""
    if "http://" not in raw and "https://" not in raw:
        return []

    titles_by_url: dict[str, str] = {}

    for title, href in _MD_LINK_PATTERN.findall(raw):
        title = (title or "").strip()
        markdown_urls = extract_unique_urls(href or "")
        if markdown_urls and title and markdown_urls[0] not in titles_by_url:
            titles_by_url[markdown_urls[0]] = title

    candidates: list[dict] = []
    for url in extract_unique_urls(raw):
        source = {"url": url}
        title = titles_by_url.get(url)
        if title:
            source["title"] = title
        candidates.append(source)

    return _normalize_sources(candidates)
