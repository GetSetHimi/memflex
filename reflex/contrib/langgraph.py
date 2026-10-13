# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""LangGraph drop-in node — wraps /ask logic in-process (no HTTP)."""
from __future__ import annotations
from typing import Any


class ReflexNode:
    """Usage: graph.add_node("respond", ReflexNode(llm="mock/mock-echo", thresholds={"serve":0.85}))"""

    def __init__(self, llm: str = "mock/mock-echo", thresholds: dict | None = None):
        self.llm = llm
        self.thresholds = thresholds or {"serve": 0.85}

    def __call__(self, state: dict[str, Any]) -> dict[str, Any]:
        from reflex.api.routes import ask as ask_route
        from reflex.core.models import AskRequest

        req = AskRequest(
            user_id=str(state.get("user_id", "anon")),
            message=str(state.get("message", state.get("input", ""))),
            context=dict(state.get("context", {})),
            llm=self.llm,
            serve_threshold=float(self.thresholds.get("serve", 0.85)),
        )
        res = ask_route(req)
        return {**state, "answer": res.answer, "reflex_source": res.source,
                "reflex_confidence": res.confidence, "reflex_id": res.reflex_id}


# Brand alias — same node, Memflex name. ReflexNode kept for backwards compat.
MemflexNode = ReflexNode
