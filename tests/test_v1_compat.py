# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""OpenAI-compatible endpoint: any framework via base_url, miss→hit reflex loop."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app

client = TestClient(app)

V1 = {
    "model": "mock/mock-echo",
    "messages": [
        {"role": "system", "content": "You are a support agent."},
        {"role": "user", "content": "V1COMP where is my package?"},
    ],
    "user": "v1_probe",
}


def test_v1_chat_completions_miss_then_hit():
    r1 = client.post("/v1/chat/completions", json=V1)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["object"] == "chat.completion"
    assert d1["choices"][0]["message"]["role"] == "assistant"
    assert d1["reflex_source"] == "llm"

    for _ in range(4):
        r2 = client.post("/v1/chat/completions", json=V1)
    d2 = r2.json()
    assert d2["reflex_source"] == "reflex", d2
    assert d2["choices"][0]["message"]["content"] == d1["choices"][0]["message"]["content"]
    assert d2["reflex_confidence"] >= 0.85


def test_v1_streams_sse_and_empty():
    body = dict(V1, messages=[
        {"role": "system", "content": "You are a support agent."},
        {"role": "user", "content": "V1STREAM where is my invoice?"},
    ])
    r = client.post("/v1/chat/completions", json={**body, "stream": True})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["X-Reflex-Source"] == "llm"
    body = r.text
    assert body.rstrip().endswith("data: [DONE]")
    r = client.post("/v1/chat/completions", json={"model": "mock/mock-echo", "messages": []})
    assert r.status_code in (400, 422)
