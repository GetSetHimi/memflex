# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""LangGraph bot sketch — requires langchain-core/langgraph installed."""
try:
    from langgraph.graph import StateGraph  # type: ignore
    from reflex.contrib.langgraph import ReflexNode

    def build():
        g = StateGraph(dict)
        g.add_node("respond", ReflexNode(llm="mock/mock-echo", thresholds={"serve": 0.85}))
        g.set_entry_point("respond")
        g.set_finish_point("respond")
        return g.compile()

    if __name__ == "__main__":
        app = build()
        print(app.invoke({"user_id": "u1", "message": "When will my refund arrive?"}))
except ImportError:
    print("pip install langgraph to run this example")
