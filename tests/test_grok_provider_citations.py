import json

import pytest

from grok_search.providers.grok import GrokSearchProvider


class _StreamingResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    async def aiter_lines(self):
        for line in self._lines:
            yield line


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}"


def _provider() -> GrokSearchProvider:
    return GrokSearchProvider("https://grok.test/v1", "test-key")


@pytest.mark.asyncio
async def test_v2_stream_preserves_nested_annotations_and_search_sources() -> None:
    response = _StreamingResponse(
        [
            _sse({"choices": [{"delta": {"content": "Answer "}}]}),
            _sse(
                {
                    "choices": [
                        {
                            "delta": {
                                "content": None,
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "url_citation": {
                                            "url": "https://example.test/a",
                                            "title": "",
                                            "start_index": 0,
                                            "end_index": 6,
                                        },
                                    }
                                ],
                            }
                        }
                    ],
                    "search_sources": [
                        {
                            "type": "web",
                            "url": "https://example.test/a",
                            "title": "Source A",
                        },
                        {
                            "type": "web",
                            "url": "https://example.test/b",
                            "title": "Source B",
                            "description": "B description",
                        },
                    ],
                }
            ),
            _sse({"choices": [{"delta": {"content": "body"}}]}),
            "data: [DONE]",
        ]
    )

    result = await _provider()._parse_streaming_response(response)

    assert result.content == "Answer body"
    assert [source.to_dict() for source in result.sources] == [
        {
            "url": "https://example.test/a",
            "title": "Source A",
            "provider": "grok",
        },
        {
            "url": "https://example.test/b",
            "title": "Source B",
            "description": "B description",
            "provider": "grok",
        },
    ]


@pytest.mark.asyncio
async def test_v3_stream_preserves_flat_metadata_only_final_annotation() -> None:
    response = _StreamingResponse(
        [
            _sse({"choices": [{"delta": {"content": "V3 answer"}}]}),
            _sse(
                {
                    "choices": [
                        {
                            "delta": {
                                "content": None,
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "url": "https://example.test/v3",
                                        "title": "V3 source",
                                        "start_index": 0,
                                        "end_index": 2,
                                    }
                                ],
                            }
                        }
                    ]
                }
            ),
            "data:[DONE]",
        ]
    )

    result = await _provider()._parse_streaming_response(response)

    assert result.content == "V3 answer"
    assert [source.to_dict() for source in result.sources] == [
        {
            "url": "https://example.test/v3",
            "title": "V3 source",
            "provider": "grok",
        }
    ]


@pytest.mark.asyncio
async def test_plain_json_preserves_message_annotations() -> None:
    response = _StreamingResponse(
        [
            json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "Plain answer",
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "url": "https://example.test/plain",
                                        "title": "Plain source",
                                    }
                                ],
                            }
                        }
                    ]
                }
            )
        ]
    )

    result = await _provider()._parse_streaming_response(response)

    assert result.content == "Plain answer"
    assert [source.to_dict() for source in result.sources] == [
        {
            "url": "https://example.test/plain",
            "title": "Plain source",
            "provider": "grok",
        }
    ]


@pytest.mark.asyncio
async def test_malformed_events_do_not_discard_valid_content_or_sources() -> None:
    response = _StreamingResponse(
        [
            _sse(
                {
                    "choices": [
                        {
                            "delta": {
                                "content": "before",
                                "annotations": [
                                    {
                                        "type": "url_citation",
                                        "url": "https://example.test/valid",
                                    }
                                ],
                            }
                        }
                    ]
                }
            ),
            "data: {not-json",
            _sse({"choices": [None, {"delta": {"content": "ignored"}}]}),
            _sse({"choices": [{"delta": {"content": " after"}}]}),
        ]
    )

    result = await _provider()._parse_streaming_response(response)

    assert result.content == "before after"
    assert [source.to_dict() for source in result.sources] == [
        {"url": "https://example.test/valid", "provider": "grok"}
    ]
