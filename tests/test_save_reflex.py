# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""POST /reflexes explicit save/upsert for tool-composed answers."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app

client = TestClient(app)


def test_explicit_save_upserts_same_situation():
    body = {"user_id": "saver", "message": "SVEX refund ETA for ORD-1?", "answer": "v1 answer"}
    r1 = client.post("/reflexes", json=body)
    assert r1.status_code == 200, r1.text
    assert r1.json()["situation"]

    r2 = client.post("/reflexes", json={**body, "answer": "v2 composed with tools"})
    assert r2.status_code == 200
    assert r2.json()["id"] == r1.json()["id"], "same situation must upsert, not duplicate"

    got = client.get("/reflexes", params={"user_id": "saver"}).json()
    assert len([r for r in got if r["situation"] == r1.json()["situation"]]) == 1

    # ask serves the composed answer from memory
    res = None
    for _ in range(5):
        res = client.post("/ask", json={"user_id": "saver", "message": body["message"], "llm": "mock/mock-echo"}).json()
        if res["source"] == "reflex":
            break
    assert res["source"] == "reflex"
    assert res["answer"] == "v2 composed with tools"


def test_explicit_save_rejects_empty():
    r = client.post("/reflexes", json={"user_id": "x", "message": "hi", "answer": "  "})
    assert r.status_code == 400


def test_ask_miss_upserts_never_duplicates():
    # disgraced seed (4x 👎) falls below the serve band → ask misses (llm)
    # yet must reuse the same reflex id instead of duplicating
    seed = client.post("/reflexes", json={
        "user_id": "upserter", "message": "UPSX store lunch timing?",
        "answer": "old answer", "confidence": 0.9}).json()
    for _ in range(4):
        client.post(f"/reflexes/{seed['id']}/feedback", json={"ok": False})
    for _ in range(3):
        res = client.post("/ask", json={"user_id": "upserter", "message": "UPSX store lunch timing?",
                                        "llm": "mock/mock-echo"}).json()
    assert res["source"] == "llm", res
    rows = [r for r in client.get("/reflexes", params={"user_id": "upserter"}).json()
            if r["situation"] == seed["situation"]]
    assert len(rows) == 1, rows
    assert rows[0]["id"] == seed["id"]
    assert rows[0]["decision"]["payload"] != "old answer"  # fresh System-2 verdict stored
