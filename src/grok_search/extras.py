"""Pure allocation of web_search extra-source quotas between Tavily and Firecrawl."""


def allocate_extra_sources(
    extra_sources: int,
    *,
    tavily_key_present: bool,
    firecrawl_key_present: bool,
    tavily_enabled: bool = True,
    firecrawl_enabled: bool = True,
) -> tuple[int, int]:
    """Return ``(tavily_count, firecrawl_count)`` for ``web_search`` extras.

    Policy when both providers are usable:
    - N <= 0 → (0, 0)
    - N == 1 → all Tavily (so dual-provider never zeros Tavily for N >= 1)
    - N >= 2 → floor(70%) Firecrawl, remainder Tavily; if remainder would be 0,
      force at least one Tavily slot.
    """
    n = int(extra_sources or 0)
    if n <= 0:
        return 0, 0

    use_t = bool(tavily_key_present and tavily_enabled)
    use_f = bool(firecrawl_key_present and firecrawl_enabled)

    if use_t and use_f:
        if n == 1:
            return 1, 0
        firecrawl_count = (n * 7) // 10
        tavily_count = n - firecrawl_count
        if tavily_count == 0:
            tavily_count, firecrawl_count = 1, n - 1
        return tavily_count, firecrawl_count
    if use_f:
        return 0, n
    if use_t:
        return n, 0
    return 0, 0
