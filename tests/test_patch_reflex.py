# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""PATCH /reflexes/{id}: user-customizable TTL and confidence."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app

client = TestClient(app)


def test_patch_ttl_and_confidence():
    seed = client.post("/reflexes", json={
        "user_id": "patcher", "message": "PTCH store timing?",
        "answer": "9 to 9", "confidence": 0.9}).json()
    assert seed["ttl_days"] == 30, seed  # stable content → long TTL

    r = client.patch(f"/reflexes/{seed['id']}", json={"ttl_days": 2})
    assert r.status_code == 200, r.text
    assert r.json()["ttl_days"] == 2, r.json()

    r = client.patch(f"/reflexes/{seed['id']}", json={"confidence": 0.5})
    assert r.json()["confidence"] == 0.5

    # clamping: absurd values stay in range
    r = client.patch(f"/reflexes/{seed['id']}", json={"ttl_days": 9999, "confidence": 9})
    assert r.json()["ttl_days"] == 365 and r.json()["confidence"] == 0.99

    # empty body + unknown id
    assert client.patch(f"/reflexes/{seed['id']}", json={}).status_code == 400
    assert client.patch("/reflexes/rfx_nope", json={"ttl_days": 3}).status_code == 404


def test_ask_ttl_override_wins_over_inference():
    client.post("/ask", json={"user_id": "patcher2", "message": "PTCH2 refund status now?",
                              "llm": "mock/mock-echo", "ttl_days": 7})
    got = client.get("/reflexes", params={"user_id": "patcher2"}).json()
    assert got and got[0]["ttl_days"] == 7, got
