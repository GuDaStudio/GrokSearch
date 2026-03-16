import json

import pytest

from grok_search import planning
from grok_search import server


@pytest.fixture(autouse=True)
def reset_planning_state():
    planning.engine.reset()
    yield
    planning.engine.reset()


@pytest.mark.asyncio
async def test_legacy_plan_flow_level_1_still_completes_after_sub_query():
    intent = json.loads(
        await server.plan_intent(
            thought="Simple factual lookup.",
            core_question="What is OpenAI?",
            query_type="factual",
            time_sensitivity="irrelevant",
        )
    )
    session_id = intent["session_id"]

    complexity = json.loads(
        await server.plan_complexity(
            session_id=session_id,
            thought="Low complexity.",
            level=1,
            estimated_sub_queries=1,
            estimated_tool_calls=2,
            justification="One direct lookup is enough.",
        )
    )
    assert complexity["plan_complete"] is False

    decomposition = json.loads(
        await server.plan_sub_query(
            session_id=session_id,
            thought="One sub-query is enough.",
            id="sq1",
            goal="Identify OpenAI.",
            expected_output="One-sentence company definition.",
            boundary="Exclude product history and leadership details.",
            tool_hint="web_search",
        )
    )
    assert decomposition["plan_complete"] is True
    assert decomposition["complexity_level"] == 1


@pytest.mark.asyncio
async def test_missing_session_returns_structured_error():
    result = json.loads(
        await server.plan_complexity(
            session_id="",
            thought="Missing session.",
            level=1,
            estimated_sub_queries=1,
            estimated_tool_calls=2,
            justification="Should fail without a session.",
        )
    )

    assert result["error"] == "session_not_found"
    assert result["restart_from_intent_analysis"] is True
    assert "expected_phase_order" in result


@pytest.mark.asyncio
async def test_out_of_order_phase_returns_error():
    intent = json.loads(
        await server.plan_intent(
            thought="Start planning.",
            core_question="Resolve an ambiguous query.",
            query_type="exploratory",
            time_sensitivity="recent",
        )
    )

    wrong = json.loads(
        await server.plan_sub_query(
            session_id=intent["session_id"],
            thought="Skip complexity on purpose.",
            id="sq1",
            goal="Wrong order",
            expected_output="Should fail.",
            boundary="Testing invalid order.",
            tool_hint="web_search",
        )
    )

    assert "requires 'complexity_assessment'" in wrong["error"]
    assert wrong["expected_phase_order"][0] == "intent_analysis"


@pytest.mark.asyncio
async def test_level_1_blocks_later_phases():
    intent = json.loads(
        await server.plan_intent(
            thought="Simple factual lookup.",
            core_question="What is OpenAI?",
            query_type="factual",
            time_sensitivity="irrelevant",
        )
    )
    session_id = intent["session_id"]

    await server.plan_complexity(
        session_id=session_id,
        thought="Low complexity.",
        level=1,
        estimated_sub_queries=1,
        estimated_tool_calls=2,
        justification="One direct lookup is enough.",
    )

    await server.plan_sub_query(
        session_id=session_id,
        thought="Complete the required level 1 decomposition first.",
        id="sq1",
        goal="Identify OpenAI.",
        expected_output="A short definition.",
        boundary="Exclude unrelated details.",
        tool_hint="web_search",
    )

    result = json.loads(
        await server.plan_search_term(
            session_id=session_id,
            thought="This should be blocked for level 1.",
            term="openai company",
            purpose="sq1",
            round=1,
            approach="targeted",
        )
    )

    assert result["error"] == "Level 1 planning completes after query_decomposition."
