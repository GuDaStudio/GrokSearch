import io
import json

import httpx
import pytest

from grok_search import tavily_boundary_probe as probe


def _output_records(stdout: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stdout.getvalue().splitlines()[1:]]


async def _fail_if_requested(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected request to {request.url.host}")


@pytest.mark.asyncio
async def test_without_confirmation_sends_no_requests() -> None:
    stdout = io.StringIO()
    exit_code = await probe.async_main(
        [],
        environ={"TAVILY_API_KEY": "unused-key"},
        stdout=stdout,
        transport=httpx.MockTransport(_fail_if_requested),
    )

    assert exit_code == 0
    assert "would perform 9 basic Tavily Search operations" in stdout.getvalue()


@pytest.mark.asyncio
async def test_missing_key_sends_no_requests() -> None:
    stderr = io.StringIO()
    exit_code = await probe.async_main(
        ["--confirm-live"],
        environ={},
        stderr=stderr,
        transport=httpx.MockTransport(_fail_if_requested),
    )

    assert exit_code == 2
    assert "TAVILY_API_KEY is required" in stderr.getvalue()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.tavily.com",
        "https://user:password@api.tavily.com",
        "https://api.tavily.com?token=private",
    ],
)
async def test_unsafe_base_url_sends_no_requests(base_url: str) -> None:
    stderr = io.StringIO()
    exit_code = await probe.async_main(
        ["--base-url", base_url, "--confirm-live"],
        environ={"TAVILY_API_KEY": "unused-key"},
        stderr=stderr,
        transport=httpx.MockTransport(_fail_if_requested),
    )

    assert exit_code == 2
    assert "Configuration error" in stderr.getvalue()


def test_probe_matrix_has_exact_code_point_and_byte_counts() -> None:
    cases = probe.build_probe_cases()

    assert len(cases) == probe.EXPECTED_OPERATION_COUNT == 9
    assert {(case.label.split("-")[0], case.code_points) for case in cases} == {
        (family, length)
        for family in ("ascii", "cjk", "emoji")
        for length in probe.PROBE_LENGTHS
    }

    ascii_case = next(case for case in cases if case.label == "ascii-400")
    cjk_case = next(case for case in cases if case.label == "cjk-400")
    emoji_case = next(case for case in cases if case.label == "emoji-400")
    assert ascii_case.utf8_bytes == 400
    assert cjk_case.utf8_bytes > cjk_case.code_points
    assert emoji_case.utf8_bytes > emoji_case.code_points


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(200, json={"results": []}), "accepted"),
        (
            httpx.Response(
                400,
                json={"detail": {"error": "Query is too long. Max query length is 400 characters."}},
            ),
            "query_too_long",
        ),
        (httpx.Response(429, json={"detail": "quota"}), "auth_or_quota"),
        (httpx.Response(500, text="private response content"), "other_error"),
    ],
)
def test_response_classification(
    response: httpx.Response,
    expected: str,
) -> None:
    assert probe.classify_response(response) == expected


@pytest.mark.asyncio
async def test_confirmed_probe_is_bounded_and_output_is_private() -> None:
    fake_key = "test-secret-boundary-key"
    requests: list[httpx.Request] = []

    async def _handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        if len(body["query"]) == 401:
            return httpx.Response(
                400,
                json={
                    "detail": {
                        "error": "Query is too long. Max query length is 400 characters.",
                        "private": "private-response-marker",
                    }
                },
            )
        return httpx.Response(
            200,
            json={"results": [{"content": "private-result-marker"}]},
        )

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = await probe.async_main(
        ["--confirm-live"],
        environ={"TAVILY_API_KEY": fake_key},
        stdout=stdout,
        stderr=stderr,
        transport=httpx.MockTransport(_handle_request),
    )

    assert exit_code == 0
    assert len(requests) == probe.EXPECTED_OPERATION_COUNT == 9
    assert all(
        request.headers["Authorization"] == f"Bearer {fake_key}"
        for request in requests
    )
    assert all(request.url == "https://api.tavily.com/search" for request in requests)

    output = stdout.getvalue() + stderr.getvalue()
    assert fake_key not in output
    assert "private-response-marker" not in output
    assert "private-result-marker" not in output
    for case in probe.build_probe_cases():
        assert case.query not in output

    records = _output_records(stdout)
    assert len(records) == 9
    assert {record["classification"] for record in records} == {
        "accepted",
        "query_too_long",
    }
    assert all("query" not in record for record in records)


@pytest.mark.asyncio
async def test_transport_errors_are_private_and_return_nonzero() -> None:
    async def _fail_request(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private transport detail", request=request)

    stdout = io.StringIO()
    exit_code = await probe.async_main(
        ["--confirm-live"],
        environ={"TAVILY_API_KEY": "fake-key"},
        stdout=stdout,
        transport=httpx.MockTransport(_fail_request),
    )

    assert exit_code == 1
    assert "private transport detail" not in stdout.getvalue()
    assert all(
        record["classification"] == "other_error"
        and record["http_status"] is None
        for record in _output_records(stdout)
    )


@pytest.mark.asyncio
async def test_redirects_are_not_followed() -> None:
    requests: list[httpx.Request] = []

    async def _redirect_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(307, headers={"Location": "https://redirect.test/search"})

    stdout = io.StringIO()
    exit_code = await probe.async_main(
        ["--confirm-live"],
        environ={"TAVILY_API_KEY": "fake-key"},
        stdout=stdout,
        transport=httpx.MockTransport(_redirect_request),
    )

    assert exit_code == 0
    assert len(requests) == probe.EXPECTED_OPERATION_COUNT
    assert all(request.url.host == "api.tavily.com" for request in requests)
    assert all(
        record["classification"] == "other_error"
        for record in _output_records(stdout)
    )
