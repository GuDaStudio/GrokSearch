from grok_search.extras import allocate_extra_sources


def test_zero_extras():
    assert allocate_extra_sources(0, tavily_key_present=True, firecrawl_key_present=True) == (0, 0)


def test_both_n1_prefers_tavily():
    assert allocate_extra_sources(1, tavily_key_present=True, firecrawl_key_present=True) == (1, 0)


def test_both_n2():
    assert allocate_extra_sources(2, tavily_key_present=True, firecrawl_key_present=True) == (1, 1)


def test_both_n3():
    assert allocate_extra_sources(3, tavily_key_present=True, firecrawl_key_present=True) == (1, 2)


def test_both_n5_split():
    assert allocate_extra_sources(5, tavily_key_present=True, firecrawl_key_present=True) == (2, 3)


def test_both_n10():
    assert allocate_extra_sources(10, tavily_key_present=True, firecrawl_key_present=True) == (3, 7)


def test_firecrawl_only():
    assert allocate_extra_sources(4, tavily_key_present=False, firecrawl_key_present=True) == (0, 4)


def test_tavily_only():
    assert allocate_extra_sources(4, tavily_key_present=True, firecrawl_key_present=False) == (4, 0)


def test_tavily_disabled_flag():
    assert allocate_extra_sources(
        5, tavily_key_present=True, firecrawl_key_present=True, tavily_enabled=False
    ) == (0, 5)


def test_firecrawl_disabled_flag():
    assert allocate_extra_sources(
        5, tavily_key_present=True, firecrawl_key_present=True, firecrawl_enabled=False
    ) == (5, 0)


def test_both_disabled():
    assert allocate_extra_sources(
        5,
        tavily_key_present=True,
        firecrawl_key_present=True,
        tavily_enabled=False,
        firecrawl_enabled=False,
    ) == (0, 0)


def test_negative_clamped():
    assert allocate_extra_sources(-1, tavily_key_present=True, firecrawl_key_present=True) == (0, 0)
