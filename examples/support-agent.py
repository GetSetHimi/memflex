# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Day1/Day30 support-agent story: 10 intents x 3 rounds, four languages.

Same shape as a real support workload — repeats arrive as rephrasings and
in other languages. Watch the first round go to the LLM and later rounds
serve from memory at Rs.0.

Run:  python3 examples/support-agent.py   (needs the API on :8000)
"""
from reflex import Client

rx = Client("http://localhost:8000")

support_queries = [
    "When will my refund arrive?",
    "Where is my package?",
    "Please cancel my order",
    "Wo ist meine Rückerstattung?",
    "Delivery status?",
    "Cancel my order",
    "Refund status?",  # terse follow-up phrasing
    "¿Dónde está mi entrega?",
    "Quand mon remboursement arrivera-t-il ?",
    "Where is my parcel?",
] * 3  # demo sample; scale to 1000 in prod

for i, msg in enumerate(support_queries):
    res = rx.ask(user_id="u123", message=msg, llm="mock/mock-echo",
                 extract_structured=True,
                 output_schema={"refund_status": "str", "eta_days": "list[int]"})
    print(f"{i:02d} [{res.source} {res.confidence:.2f} {res.latency_ms}ms] {msg} -> {res.answer}")

print("\nGET /metrics for hit_rate, avg_latency, cost_saved_30d, calibration")
