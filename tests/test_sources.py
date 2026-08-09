import pytest

from grok_search.providers.contracts import NormalizedSource
from grok_search.sources import SourcesCache, merge_sources, split_answer_and_sources


def test_merge_sources_is_stable_and_enriches_exact_duplicates() -> None:
    first = {"url": " https://example.test/a ", "title": ""}

    merged = merge_sources(
        [first, {"url": "https://example.test/b", "provider": "grok"}],
        [
            {
                "url": "https://example.test/a",
                "title": "Source A",
                "description": "A description",
                "provider": "grok",
            },
            {
                "url": "https://example.test/b",
                "description": "B description",
                "provider": "firecrawl",
            },
        ],
        [{"url": "ftp://example.test/ignored"}, {"url": "not-a-url"}],
    )

    assert merged == [
        {
            "url": "https://example.test/a",
            "title": "Source A",
            "description": "A description",
            "provider": "grok",
        },
        {
            "url": "https://example.test/b",
            "provider": "grok",
            "description": "B description",
        },
    ]
    assert first == {"url": " https://example.test/a ", "title": ""}


def test_merge_sources_uses_shared_metadata_aliases() -> None:
    assert merge_sources(
        [
            {
                "href": "https://example.test/aliased",
                "name": "Aliased title",
                "snippet": "Aliased description",
            }
        ]
    ) == [
        {
            "url": "https://example.test/aliased",
            "title": "Aliased title",
            "description": "Aliased description",
        }
    ]


def test_normalized_source_enforces_absolute_http_url_and_clean_metadata() -> None:
    source = NormalizedSource(
        url=" https://example.test/source ",
        title=" Source title ",
        provider=" grok ",
    )

    assert source.to_dict() == {
        "url": "https://example.test/source",
        "title": "Source title",
        "provider": "grok",
    }
    with pytest.raises(ValueError, match="absolute HTTP"):
        NormalizedSource(url="ftp://example.test/source")


@pytest.mark.asyncio
async def test_sources_cache_stores_and_returns_defensive_snapshots() -> None:
    cache = SourcesCache()
    supplied = [{"url": "https://example.test/a", "title": "Original"}]

    await cache.set("session", supplied)
    supplied[0]["title"] = "Changed outside cache"
    supplied.append({"url": "https://example.test/b"})

    first_read = await cache.get("session")
    assert first_read == [{"url": "https://example.test/a", "title": "Original"}]

    assert first_read is not None
    first_read[0]["title"] = "Changed returned value"
    second_read = await cache.get("session")

    assert second_read == [{"url": "https://example.test/a", "title": "Original"}]


def test_split_answer_recovers_inline_urls_without_rewriting_the_answer() -> None:
    answer_text = (
        "Start with https://example.test/bare, then read "
        "[Labeled source](https://example.test/labeled). "
        "The first URL appears again as "
        "[Bare source title](https://example.test/bare)."
    )

    answer, sources = split_answer_and_sources(answer_text)

    assert answer == answer_text
    assert sources == [
        {"url": "https://example.test/bare", "title": "Bare source title"},
        {"url": "https://example.test/labeled", "title": "Labeled source"},
    ]


def test_split_answer_recovers_single_inline_markdown_link() -> None:
    answer_text = "The result is documented by [Source A](https://example.test/a)."

    answer, sources = split_answer_and_sources(answer_text)

    assert answer == answer_text
    assert sources == [
        {"url": "https://example.test/a", "title": "Source A"},
    ]


def test_split_answer_normalizes_inline_urls_through_shared_source_contract() -> None:
    answer_text = (
        "Read [Punctuated source](https://example.test/a,), "
        "but ignore malformed https://,."
    )

    answer, sources = split_answer_and_sources(answer_text)

    assert answer == answer_text
    assert sources == [
        {"url": "https://example.test/a", "title": "Punctuated source"},
    ]
