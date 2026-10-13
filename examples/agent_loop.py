# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Tool-aware support agent: Memflex sits in front of a plan→act→answer loop.

Run 1 (novel):  planner (LLM) picks tools → tools execute → COMPOSED answer
                memorized via POST /reflexes (upsert, no duplicates).
Run 2 (repeat): reflex serves the composed answer — planner AND tools fire
                ZERO times, LLM fires ZERO times.

Usage:
    python3 examples/agent_loop.py                        # mock, keyless
    python3 examples/agent_loop.py --llm ollama-cloud/gpt-oss:20b   # real planning

Requires the API running:  python3 -m reflex.api.app
"""
import argparse
import json
import sys

sys.path.insert(0, ".")

from reflex import Client

TOOL_CALLS: list[str] = []


def get_order_status(order_id: str) -> str:
    TOOL_CALLS.append(f"get_order_status({order_id})")
    return f"Order {order_id}: shipped, arriving in 2 days"


def compute_refund_eta(order_id: str) -> str:
    TOOL_CALLS.append(f"compute_refund_eta({order_id})")
    return f"Order {order_id}: refund processing, ETA 3-5 days"


def plan_with_llm(llm: str, message: str) -> list[dict]:
    """Ask the LLM which tools to run (real agentic planning)."""
    from reflex.llm.factory import get_provider

    prompt = (
        "You route support requests. Reply with ONLY a JSON list like "
        '[{"tool": "get_order_status", "order_id": "ORD-1"}]. '
        "Tools: get_order_status, compute_refund_eta. "
        f"Request: {message}"
    )
    try:
        text = get_provider(llm).complete(prompt, system="Reply with only JSON.").text
        start, end = text.find("["), text.rfind("]")
        return json.loads(text[start : end + 1]) if start != -1 and end != -1 else []
    except Exception:
        return []


def demo_router(message: str) -> list[dict]:
    """Transparent fallback when llm=mock (mock can't plan — keywords stand in)."""
    low = message.lower()
    if "refund" in low or "रिफंड" in message or "wapas" in low:
        return [{"tool": "compute_refund_eta", "order_id": "ORD-9981"}]
    return [{"tool": "get_order_status", "order_id": "ORD-9981"}]


def agent_answer(rx: Client, llm: str, user_id: str, message: str) -> dict:
    # 1. Memflex first — repeats skip EVERYTHING below (no planner, no tools, no LLM).
    res = rx.ask(user_id=user_id, message=message, llm=llm)
    if res.source.startswith("reflex"):
        return {"answer": res.answer, "source": res.source, "tools": []}

    # 2. Miss → plan + act (System 2 + real tools).
    calls = plan_with_llm(llm, message) if not llm.startswith("mock/") else demo_router(message)
    facts = []
    for c in calls:
        if c.get("tool") == "get_order_status":
            facts.append(get_order_status(c.get("order_id", "ORD-9981")))
        elif c.get("tool") == "compute_refund_eta":
            facts.append(compute_refund_eta(c.get("order_id", "ORD-9981")))
    composed = " | ".join(facts) if facts else res.answer

    # 3. Memorize the COMPOSED answer (upserts the echo saved by step 1).
    rx.save_reflex(user_id=user_id, message=message, answer=composed)
    return {"answer": composed, "source": "llm+tools", "tools": list(TOOL_CALLS)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", default="mock/mock-echo")
    ap.add_argument("--api", default="http://localhost:8000")
    args = ap.parse_args()
    rx = Client(args.api)
    for q in ["When will my refund arrive? ORD-9981", "Where is my order ORD-9981?"]:
        for run in (1, 2):
            TOOL_CALLS.clear()
            out = agent_answer(rx, args.llm, "agent_demo", q)
            print(f"Q={q[:32]!r} run{run}: source={out['source']} tools={out['tools']}")
            print(f"   A: {out['answer'][:100]}")


if __name__ == "__main__":
    main()
