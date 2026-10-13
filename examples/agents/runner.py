# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Agent runner: reflex first, planner+tools+synthesis on miss, memorize composed answer.

With a real LLM (gemini/...) planning and synthesis are genuine model calls.
With mock/*, a transparent keyword router stands in (mock cannot plan).
"""
import json
import sys

sys.path.insert(0, ".")

from reflex import Client
from reflex.llm.factory import get_provider

from tools import CALLS, TOOLS

PLAN_SYSTEM = ("You are a support router. Reply with ONLY a JSON list like "
               '[{"tool": "get_order_status", "order_id": "ORD-1"}]. '
               "Available tools: get_order_status, refund_quote, cancel_order, "
               "triage_route. Use order_id from the request or ORD-0000. "
               "If no tool is needed, reply [].")


def _parse_calls(text: str) -> list:
    t = text.strip()
    for fence in ("```json", "```"):
        t = t.replace(fence, "")
    start, end = t.find("["), t.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        out = json.loads(t[start:end + 1])
        return out if isinstance(out, list) else []
    except Exception:
        return []


def _demo_router(message: str) -> list:
    low = message.lower()
    if "refund" in low or "रिफंड" in message or "wapas" in low or "rückerstatt" in low:
        return [{"tool": "refund_quote", "order_id": "ORD-9981"}]
    if "cancel" in low or "stornier" in low or "कैंसिल" in message:
        return [{"tool": "cancel_order", "order_id": "ORD-9981"}]
    if "rout" in low or "triage" in low or "bill" in low or "charge" in low:
        return [{"tool": "triage_route", "text": message}]
    return [{"tool": "get_order_status", "order_id": "ORD-9981"}]


def agent_answer(rx: Client, llm: str, user_id: str, message: str,
                 context: dict | None = None) -> dict:
    """Returns {answer, source, tools_used, llm_calls}."""
    context = context or {}
    stats = {"llm_calls": 0, "tools": []}
    # 1. Reflex first — repeats skip everything below.
    res = rx.ask(user_id=user_id, message=message, llm=llm,
                 context=context, extract_structured=bool(context.get("schema")),
                 output_schema=context.get("schema"))
    if res.source.startswith("reflex"):
        return {"answer": res.answer, "source": res.source,
                "structured": getattr(res, "structured", None),
                "confidence": res.confidence, **stats}
    # 2. Miss → plan (LLM) + act (tools).
    if llm.startswith("mock/"):
        calls = _demo_router(message)
    else:
        stats["llm_calls"] += 1
        plan_text = get_provider(llm).complete(
            f"{message}\nOrder context: {context.get('order_id', 'ORD-9981')}",
            system=PLAN_SYSTEM).text
        calls = _parse_calls(plan_text)
        if not calls:
            calls = _demo_router(message)
    facts = []
    for c in calls:
        fn = TOOLS.get(c.get("tool", ""))
        if not fn:
            continue
        arg = c.get("order_id") or c.get("text") or message
        try:
            facts.append(fn(arg))
        except TypeError:
            facts.append(fn(message))
    stats["tools"] = list(CALLS)
    # 3. Synthesize final answer (LLM) so it reads naturally, then memorize it.
    if llm.startswith("mock/"):
        composed = " | ".join(facts) if facts else res.answer
    else:
        stats["llm_calls"] += 1
        composed = get_provider(llm).complete(
            f"User asked: {message}\nTool results:\n" + "\n".join(facts),
            system="Answer the user concisely in their language, using ONLY these tool results.").text.strip()
    rx.save_reflex(user_id=user_id, message=message, answer=composed,
                   structured=getattr(res, "structured", None), context=context)
    return {"answer": composed, "source": "llm+tools", **stats}
