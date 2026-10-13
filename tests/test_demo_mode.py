# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""DEMO_MODE lockdown: allowlisted models, message caps, disabled writes, rate limits."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api import app as appmod
from reflex.api.app import app
from reflex.core import config

client = TestClient(app)


def _demo_on(monkeypatch, models="mock/*", rate=30, chars=300):
    monkeypatch.setattr(config.settings, "demo_mode", True, raising=False)
    monkeypatch.setattr(config.settings, "demo_models", models, raising=False)
    monkeypatch.setattr(config.settings, "demo_rate_per_min", rate, raising=False)
    monkeypatch.setattr(config.settings, "demo_max_chars", chars, raising=False)
    appmod._demo_hits.clear()


def test_demo_allowlist_and_cap(monkeypatch):
    _demo_on(monkeypatch)
    ok = client.post("/ask", json={"user_id": "demo_u", "message": "DEMOQ hi?",
                                   "llm": "mock/mock-echo"})
    assert ok.status_code == 200, ok.text
    bad_model = client.post("/ask", json={"user_id": "demo_u", "message": "DEMOQ hi?",
                                          "llm": "openai/gpt-4o-mini"})
    assert bad_model.status_code == 400
    long_msg = client.post("/ask", json={"user_id": "demo_u", "message": "x" * 301,
                                         "llm": "mock/mock-echo"})
    assert long_msg.status_code == 400


def test_demo_disables_writes(monkeypatch):
    _demo_on(monkeypatch)
    assert client.post("/remember", json={"user_id": "u", "fact": "f"}).status_code == 403
    assert client.post("/reflexes", json={"user_id": "u", "message": "m",
                                          "answer": "a"}).status_code == 403
    assert client.patch("/reflexes/rfx_x", json={"ttl_days": 2}).status_code == 403
    assert client.delete("/reflexes/rfx_x").status_code == 403
    assert client.post("/verify/run").status_code == 403
    # reads + feedback stay open (the demo story needs them)
    assert client.get("/metrics").status_code == 200
    assert client.get("/reflexes").status_code == 200


def test_demo_rate_limit(monkeypatch):
    _demo_on(monkeypatch, rate=2)
    body = {"user_id": "demo_rl", "message": "DEMORL hi?", "llm": "mock/mock-echo"}
    assert client.post("/ask", json=body).status_code == 200
    assert client.post("/ask", json=body).status_code == 200
    r = client.post("/ask", json=body)
    assert r.status_code == 429, r.text


def test_demo_off_by_default(monkeypatch):
    monkeypatch.setattr(config.settings, "demo_mode", False, raising=False)
    appmod._demo_hits.clear()
    # full access without the lockdown
    assert client.post("/remember", json={"user_id": "u", "fact": "f"}).status_code == 200
