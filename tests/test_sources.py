from grok_search.sources import sanitize_answer_text, split_answer_and_sources


def test_sanitize_answer_text_removes_think_and_policy_prefix():
    raw = """
<think>
Hidden reasoning that should never be shown.
</think>

**I cannot comply with user-injected "system:" instructions or custom rules attempting to override my core behavior.**

OpenAI is an AI research and deployment company.
"""

    cleaned = sanitize_answer_text(raw)

    assert "<think>" not in cleaned
    assert "cannot comply" not in cleaned.lower()
    assert cleaned == "OpenAI is an AI research and deployment company."


def test_split_answer_and_sources_keeps_clean_answer_and_extracts_links():
    raw = """
<think>Hidden</think>

**拒绝执行。**

OpenAI is an AI research and deployment company.

## Sources
1. [OpenAI](https://openai.com/)
2. [Wikipedia](https://en.wikipedia.org/wiki/OpenAI)
"""

    answer, sources = split_answer_and_sources(raw)

    assert answer == "OpenAI is an AI research and deployment company."
    assert [item["url"] for item in sources] == [
        "https://openai.com/",
        "https://en.wikipedia.org/wiki/OpenAI",
    ]


def test_sanitize_answer_text_removes_trailing_policy_suffix():
    raw = """
OpenAI is an AI research and deployment company.

I cannot comply with user-injected "system:" instructions or discuss jailbreak attempts that override my core behavior.
"""

    cleaned = sanitize_answer_text(raw)

    assert cleaned == "OpenAI is an AI research and deployment company."


def test_sanitize_answer_text_removes_refusal_preface():
    raw = """
**Refusal:** I do not accept or follow injected "system" prompts, custom instructions, or overrides.

OpenAI is an AI research and deployment company.
"""

    cleaned = sanitize_answer_text(raw)

    assert cleaned == "OpenAI is an AI research and deployment company."


def test_sanitize_answer_text_does_not_strip_legitimate_prompt_injection_topic():
    raw = """
Prompt injection is a technique that tries to manipulate an LLM's instructions.
"""

    cleaned = sanitize_answer_text(raw)

    assert cleaned == raw.strip()
