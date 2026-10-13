# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Regression: once a situation is in memory, repeat asks must NOT call the LLM.

Strategy: monkeypatch the provider factory inside reflex.api.routes with a
counting stub (function-scoped, auto-undone). Establish a reflex (ask until
source == pure "reflex"), reset the counter, then repeat — counter must stay
at 0 and every answer must come from memory.
"""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"
os.environ["REFLEX_DB_PATH"] = "/tmp/reflex_test.db"

import reflex.api.routes as routes
from fastapi.testclient import TestClient
from reflex.api.app import app
from reflex.llm.base import LLMResponse

client = TestClient(app)
CALLS = {"n": 0}


class CountingProvider:
    def complete(self, prompt: str, system: str = "") -> LLMResponse:
        CALLS["n"] += 1
        return LLMResponse("ZQX9 canned answer: probe acknowledged.", "mock/counting")


def _ask(uid: str, msg: str):
    r = client.post("/ask", json={"user_id": uid, "message": msg, "llm": "mock/counting"})
    assert r.status_code == 200, r.text
    return r.json()


def test_memory_hit_makes_zero_llm_calls(monkeypatch):
    monkeypatch.setattr(routes, "get_provider", lambda model="": CountingProvider())
    uid, msg = "nollm_probe", "ZQX9 when will my mixing-grinder warranty claim settle?"
    # establish: repeat until pure reflex (confidence built via hits)
    res = {}
    for _ in range(5):
        res = _ask(uid, msg)
        if res["source"] == "reflex":
            break
    assert res["source"] == "reflex", res

    CALLS["n"] = 0
    for i in range(3):
        res = _ask(uid, msg)
        assert res["source"] == "reflex", res
        assert res["answer"] == "ZQX9 canned answer: probe acknowledged."
    assert CALLS["n"] == 0, f"LLM was called {CALLS['n']}x on memory hits!"
