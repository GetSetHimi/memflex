# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Anthropic-compatible POST /v1/messages: Claude SDK shape in/out, miss→hit."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app

client = TestClient(app)

V1M = {
    "model": "mock/mock-echo",
    "max_tokens": 256,
    "system": "You are a support agent.",
    "messages": [{"role": "user", "content": "V1MSG where is my package?"}],
}


def test_v1_messages_miss_then_hit():
    r1 = client.post("/v1/messages", json=V1M)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["type"] == "message" and d1["role"] == "assistant"
    assert d1["content"][0]["type"] == "text"
    assert d1["reflex_source"] == "llm"

    for _ in range(4):
        r2 = client.post("/v1/messages", json=V1M)
    d2 = r2.json()
    assert d2["reflex_source"] == "reflex", d2
    assert d2["content"][0]["text"] == d1["content"][0]["text"]


def test_v1_messages_content_blocks():
    body = dict(V1M, messages=[{
        "role": "user",
        "content": [{"type": "text", "text": "V1BLK package status?"}],
    }])
    r = client.post("/v1/messages", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["content"][0]["text"]


def test_v1_messages_rejects_stream_and_empty():
    r = client.post("/v1/messages", json={**V1M, "stream": True})
    assert r.status_code == 400
    r = client.post("/v1/messages", json={"model": "mock/mock-echo", "messages": []})
    assert r.status_code in (400, 422)
