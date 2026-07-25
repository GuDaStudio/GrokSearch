"""Safely probe Tavily Search query-length boundaries.

The probe is deliberately opt-in and privacy-preserving: it never prints the
credential, generated queries, response bodies, error details, or results.
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
import os
import sys
from collections.abc import Mapping, Sequence
from typing import TextIO
from urllib.parse import urlparse

import httpx

from .constants import TAVILY_MAX_QUERY_CHARS


DEFAULT_BASE_URL = "https://api.tavily.com"
PROBE_LENGTHS = (
    TAVILY_MAX_QUERY_CHARS - 1,
    TAVILY_MAX_QUERY_CHARS,
    TAVILY_MAX_QUERY_CHARS + 1,
)
PROBE_FAMILIES = (
    ("ascii", "tavily boundary ", "a"),
    ("cjk", "边界 ", "界"),
    ("emoji", "emoji ", "😀"),
)
EXPECTED_OPERATION_COUNT = len(PROBE_LENGTHS) * len(PROBE_FAMILIES)


@dataclass(frozen=True)
class ProbeCase:
    label: str
    query: str

    @property
    def code_points(self) -> int:
        return len(self.query)

    @property
    def utf8_bytes(self) -> int:
        return len(self.query.encode("utf-8"))


@dataclass(frozen=True)
class ProbeResult:
    case: str
    code_points: int
    utf8_bytes: int
    http_status: int | None
    classification: str

    def public_dict(self) -> dict[str, str | int | None]:
        return {
            "case": self.case,
            "code_points": self.code_points,
            "utf8_bytes": self.utf8_bytes,
            "http_status": self.http_status,
            "classification": self.classification,
        }


def build_probe_cases() -> tuple[ProbeCase, ...]:
    cases: list[ProbeCase] = []
    for family, prefix, padding in PROBE_FAMILIES:
        for length in PROBE_LENGTHS:
            query = prefix + padding * (length - len(prefix))
            if len(query) != length:
                raise AssertionError(f"failed to construct {family}-{length}")
            cases.append(ProbeCase(label=f"{family}-{length}", query=query))
    return tuple(cases)


def classify_response(response: httpx.Response) -> str:
    if 200 <= response.status_code < 300:
        return "accepted"
    if response.status_code == 400:
        detail = response.content[:4096].decode("utf-8", errors="ignore").lower()
        if "query" in detail and (
            "too long" in detail or "max query length" in detail
        ):
            return "query_too_long"
    if response.status_code in {401, 403, 429, 432, 433}:
        return "auth_or_quota"
    return "other_error"


def validate_base_url(base_url: str) -> tuple[str, str]:
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("base URL must be an absolute HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain credentials, query, or fragment")
    endpoint = f"{base_url.rstrip('/')}/search"
    return endpoint, parsed.hostname


async def run_probe(
    *,
    api_key: str,
    base_url: str,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[ProbeResult, ...]:
    endpoint, _ = validate_base_url(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    results: list[ProbeResult] = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        follow_redirects=False,
        transport=transport,
    ) as client:
        for case in build_probe_cases():
            body = {
                "query": case.query,
                "max_results": 1,
                "search_depth": "basic",
                "include_raw_content": False,
                "include_answer": False,
            }
            try:
                response = await client.post(endpoint, headers=headers, json=body)
            except httpx.HTTPError:
                results.append(
                    ProbeResult(
                        case=case.label,
                        code_points=case.code_points,
                        utf8_bytes=case.utf8_bytes,
                        http_status=None,
                        classification="other_error",
                    )
                )
                continue

            results.append(
                ProbeResult(
                    case=case.label,
                    code_points=case.code_points,
                    utf8_bytes=case.utf8_bytes,
                    http_status=response.status_code,
                    classification=classify_response(response),
                )
            )

    return tuple(results)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe Tavily's limit-1/limit/limit+1 query boundary "
            f"around {TAVILY_MAX_QUERY_CHARS} characters without logging content."
        )
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Tavily-compatible API base URL; defaults to the direct Tavily API.",
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Acknowledge that the probe performs nine basic Search operations.",
    )
    return parser


async def async_main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    args = build_parser().parse_args(argv)
    env = os.environ if environ is None else environ
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr

    try:
        _, hostname = validate_base_url(args.base_url)
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=err)
        return 2

    if not args.confirm_live:
        print(
            f"Dry run only. Target host: {hostname}. This run would perform "
            f"{EXPECTED_OPERATION_COUNT} basic Tavily Search operations.",
            file=out,
        )
        return 0

    api_key = env.get("TAVILY_API_KEY", "")
    if not api_key:
        print("Configuration error: TAVILY_API_KEY is required.", file=err)
        return 2

    print(
        f"Target host: {hostname}. Performing {EXPECTED_OPERATION_COUNT} "
        "basic Tavily Search operations.",
        file=out,
    )
    results = await run_probe(
        api_key=api_key,
        base_url=args.base_url,
        transport=transport,
    )
    for result in results:
        print(json.dumps(result.public_dict(), sort_keys=True), file=out)

    return 1 if any(result.http_status is None for result in results) else 0


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(async_main(argv))
