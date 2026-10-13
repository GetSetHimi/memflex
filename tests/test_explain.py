# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""explain=true: every answer carries WHY it was served."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app

client = TestClient(app)


def test_explain_shows_mechanism():
    uid, msg = "explainer", "EXPLN how do I reset my password?"
    r1 = client.post("/ask", json={"user_id": uid, "message": msg,
                                   "llm": "mock/mock-echo", "explain": True}).json()
    assert r1["source"] == "llm"
    assert r1["similarity"] is not None and r1["threshold"] == 0.85

    res = {}
    for _ in range(5):
        res = client.post("/ask", json={"user_id": uid, "message": msg,
                                        "llm": "mock/mock-echo", "explain": True}).json()
        if res["source"] == "reflex":
            break
    assert res["source"] == "reflex", res
    assert res["similarity"] == 1.0, res
    assert (res["matched_situation"] or "") == "expln how reset password", res


def test_explain_defaults_off():
    r = client.post("/ask", json={"user_id": "explainer", "message": "EXPLN how do I reset my password?",
                                   "llm": "mock/mock-echo"}).json()
    assert r["matched_situation"] is None and r["similarity"] is None
