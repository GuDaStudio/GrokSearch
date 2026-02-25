"""Test all tools after refactor: web_search, search_followup, search_reflect."""
import asyncio, os, sys, json

# Load .env
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from grok_search.server import web_search, search_followup, search_reflect


async def main():
    results = {}

    # 1. web_search (simplified — no follow_up/conversation_id params)
    print("=" * 60)
    print("1. web_search (simplified)")
    try:
        r = await web_search(query="FastMCP Python library")
        print(f"   ✅ Keys: {list(r.keys())}")
        print(f"   session_id: {r.get('session_id')}")
        print(f"   conversation_id: {r.get('conversation_id')}")
        print(f"   sources_count: {r.get('sources_count')}")
        print(f"   content length: {len(r.get('content', ''))}")
        # Verify removed fields
        assert "follow_up" not in str(web_search.__code__.co_varnames), "follow_up param should be removed"
        assert "can_follow_up" not in r, "can_follow_up should NOT be in return"
        assert "search_count" not in r, "search_count should NOT be in return"
        assert "conversation_id" in r, "conversation_id should be in return"
        print("   ✅ No follow_up param, no can_follow_up/search_count in return")
        results["web_search"] = {"status": "OK"}
        conv_id = r["conversation_id"]
    except Exception as e:
        results["web_search"] = {"status": "ERROR", "error": str(e)}
        print(f"   ❌ {e}")
        conv_id = ""

    # 2. search_followup (using conversation_id from step 1)
    print("=" * 60)
    print("2. search_followup")
    try:
        if conv_id:
            r2 = await search_followup(query="What are the key features?", conversation_id=conv_id)
            print(f"   ✅ Keys: {list(r2.keys())}")
            print(f"   conversation_id matches: {r2.get('conversation_id') == conv_id}")
            print(f"   content length: {len(r2.get('content', ''))}")
            results["search_followup"] = {"status": "OK"}
        else:
            results["search_followup"] = {"status": "SKIPPED"}
    except Exception as e:
        results["search_followup"] = {"status": "ERROR", "error": str(e)}
        print(f"   ❌ {e}")

    # 3. search_followup with expired session
    print("=" * 60)
    print("3. search_followup (expired session)")
    try:
        r3 = await search_followup(query="test", conversation_id="nonexistent_id")
        print(f"   ✅ Error response: {r3}")
        assert "error" in r3, "Should return error for expired session"
        results["search_followup_expired"] = {"status": "OK"}
    except Exception as e:
        results["search_followup_expired"] = {"status": "ERROR", "error": str(e)}
        print(f"   ❌ {e}")

    # 4. search_reflect (1 round, no cross-validation)
    print("=" * 60)
    print("4. search_reflect (1 round)")
    try:
        r4 = await search_reflect(
            query="Python asyncio vs threading performance comparison",
            max_reflections=1,
            cross_validate=False,
            extra_sources=2,
        )
        print(f"   ✅ Keys: {list(r4.keys())}")
        print(f"   reflection_log: {json.dumps(r4.get('reflection_log', []), ensure_ascii=False, indent=2)}")
        print(f"   search_rounds: {r4.get('search_rounds')}")
        print(f"   sources_count: {r4.get('sources_count')}")
        print(f"   content length: {len(r4.get('content', ''))}")
        results["search_reflect_basic"] = {"status": "OK", "search_rounds": r4.get("search_rounds")}
    except Exception as e:
        results["search_reflect_basic"] = {"status": "ERROR", "error": str(e)}
        print(f"   ❌ {e}")

    # 5. search_reflect (with cross-validation)
    print("=" * 60)
    print("5. search_reflect (cross_validate=True)")
    try:
        r5 = await search_reflect(
            query="重庆师范大学 人工智能 考研 分数线",
            max_reflections=1,
            cross_validate=True,
            extra_sources=2,
        )
        print(f"   ✅ Keys: {list(r5.keys())}")
        print(f"   reflection_log: {json.dumps(r5.get('reflection_log', []), ensure_ascii=False, indent=2)}")
        if "validation" in r5:
            print(f"   validation: {json.dumps(r5['validation'], ensure_ascii=False)}")
        print(f"   search_rounds: {r5.get('search_rounds')}")
        print(f"   content length: {len(r5.get('content', ''))}")
        results["search_reflect_validate"] = {"status": "OK", "has_validation": "validation" in r5}
    except Exception as e:
        results["search_reflect_validate"] = {"status": "ERROR", "error": str(e)}
        print(f"   ❌ {e}")

    # 6. Hard budget test
    print("=" * 60)
    print("6. Hard budget (max_reflections=10 → capped to 3)")
    from grok_search.reflect import MAX_REFLECTIONS_HARD_LIMIT
    assert MAX_REFLECTIONS_HARD_LIMIT == 3, f"Hard limit should be 3, got {MAX_REFLECTIONS_HARD_LIMIT}"
    print(f"   ✅ MAX_REFLECTIONS_HARD_LIMIT = {MAX_REFLECTIONS_HARD_LIMIT}")
    results["hard_budget"] = {"status": "OK"}

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    for name, info in results.items():
        icon = "✅" if info["status"] == "OK" else ("⏭️" if info["status"] == "SKIPPED" else "❌")
        print(f"  {icon} {name}: {info['status']}")

    out_path = os.path.join(os.path.dirname(__file__), "test_new_tools_output.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
