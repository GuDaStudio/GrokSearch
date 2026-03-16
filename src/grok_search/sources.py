import ast
import json
import re
import uuid
from collections import OrderedDict
from typing import Any

import asyncio

from .config import config
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
_THINK_BLOCK_PATTERN = re.compile(r"(?is)<think>.*?</think>")
_LEADING_POLICY_PATTERNS = [
    re.compile(r"(?is)^\s*\**\s*i cannot comply\b.*"),
    re.compile(r"(?is)^\s*\**\s*i do not accept\b.*"),
    re.compile(r"(?is)^\s*\**\s*refusal\s*[:：].*"),
    re.compile(r"(?is)^\s*\**\s*refuse to\b.*"),
    re.compile(r"(?is)^\s*\**\s*rejected?\b.*"),
    re.compile(r"(?is)^\s*\**\s*拒绝执行\b.*"),
    re.compile(r"(?is)^\s*\**\s*无法遵循\b.*"),
]
_POLICY_META_KEYWORDS = (
    "cannot comply",
    "refuse",
    "refusal",
    "override my core",
    "core behavior",
    "custom rules",
    "用户提供的自定义",
    "覆盖我的核心",
    "核心行为",
    "拒绝执行",
    "无法遵循",
)
_POLICY_CONTEXT_KEYWORDS = (
    "jailbreak",
    "prompt injection",
    "system instructions",
    "system prompt",
    "user-injected",
    "注入",
    "越狱",
    "系统指令",
    "系统提示",
    "自定义“system”",
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
            self._cache[session_id] = sources
            self._cache.move_to_end(session_id)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    async def get(self, session_id: str) -> list[dict] | None:
        async with self._lock:
            sources = self._cache.get(session_id)
            if sources is None:
                return None
            self._cache.move_to_end(session_id)
            return sources


def merge_sources(*source_lists: list[dict]) -> list[dict]:
    seen: set[str] = set()
    merged: list[dict] = []
    for sources in source_lists:
        for item in sources or []:
            url = (item or {}).get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            url = url.strip()
            if url in seen:
                continue
            seen.add(url)
            merged.append(item)
    return merged


def split_answer_and_sources(text: str) -> tuple[str, list[dict]]:
    raw = (text or "").strip()
    if not raw:
        return "", []

    if config.output_cleanup_enabled:
        cleaned = sanitize_answer_text(raw)
        if cleaned:
            raw = cleaned

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

    return raw, []


def sanitize_answer_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""

    cleaned = _THINK_BLOCK_PATTERN.sub("", raw).strip()
    paragraphs = _split_paragraphs(cleaned)
    filtered = [paragraph for paragraph in paragraphs if not _looks_like_policy_block(paragraph)]
    if filtered:
        return "\n\n".join(filtered).strip()
    return cleaned


def _split_paragraphs(text: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def _looks_like_policy_block(text: str) -> bool:
    normalized = _normalize_policy_text(text)
    if not normalized:
        return False

    if any(pattern.match(normalized) for pattern in _LEADING_POLICY_PATTERNS):
        return True

    return any(keyword in normalized for keyword in _POLICY_META_KEYWORDS) and any(
        keyword in normalized for keyword in _POLICY_CONTEXT_KEYWORDS
    )


def _normalize_policy_text(text: str) -> str:
    normalized = re.sub(r"[>*_`#-]+", " ", text or "")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().lower()


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
                if url not in seen:
                    seen.add(url)
                    normalized.append({"url": url})
            continue

        if isinstance(item, (list, tuple)) and len(item) >= 2:
            title, url = item[0], item[1]
            if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in seen:
                seen.add(url)
                out: dict = {"url": url}
                if isinstance(title, str) and title.strip():
                    out["title"] = title.strip()
                normalized.append(out)
            continue

        if isinstance(item, dict):
            url = item.get("url") or item.get("href") or item.get("link")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            if url in seen:
                continue
            seen.add(url)
            out: dict = {"url": url}
            title = item.get("title") or item.get("name") or item.get("label")
            if isinstance(title, str) and title.strip():
                out["title"] = title.strip()
            desc = item.get("description") or item.get("snippet") or item.get("content")
            if isinstance(desc, str) and desc.strip():
                out["description"] = desc.strip()
            normalized.append(out)
            continue

    return normalized


def _extract_sources_from_text(text: str) -> list[dict]:
    sources: list[dict] = []
    seen: set[str] = set()

    for title, url in _MD_LINK_PATTERN.findall(text or ""):
        url = (url or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        title = (title or "").strip()
        if title:
            sources.append({"title": title, "url": url})
        else:
            sources.append({"url": url})

    for url in extract_unique_urls(text or ""):
        if url in seen:
            continue
        seen.add(url)
        sources.append({"url": url})

    return sources
