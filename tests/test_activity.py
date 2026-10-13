# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""GET /activity powers the console dashboard: every LLM call + reflex answer."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app

client = TestClient(app)


def test_activity_logs_llm_and_reflex():
    uid = "activity_probe_user"
    r1 = client.post("/ask", json={"user_id": uid, "message": "ACTP where is my invoice?", "llm": "mock/mock-echo"})
    assert r1.json()["source"] == "llm"
    for _ in range(4):
        r2 = client.post("/ask", json={"user_id": uid, "message": "ACTP where is my invoice?", "llm": "mock/mock-echo"})
    assert r2.json()["source"] == "reflex"

    a = client.get("/activity", params={"limit": 10}).json()
    assert a["count"] >= 5 and a["llm_calls"] >= 1 and a["reflex_answers"] >= 1
    mine = [i for i in a["items"] if i["user_id"] == uid]
    assert {i["source"] for i in mine} >= {"llm", "reflex"}
    assert all("answer" in i and "confidence" in i and "ts" in i for i in mine)

    only_llm = client.get("/activity", params={"source": "llm"}).json()
    assert all(i["source"] == "llm" for i in only_llm["items"])
