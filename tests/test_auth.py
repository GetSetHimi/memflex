# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""API-key auth: open local mode when unset, locked hosted mode when set."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app
from reflex.core import config

client = TestClient(app)

OPEN = {"user_id": "authprobe", "message": "AUTHP is the sky blue?", "llm": "mock/mock-echo"}


def _set_key(monkeypatch, value: str):
    monkeypatch.setattr(config.settings, "memflex_api_key", value, raising=False)
    monkeypatch.setattr(config.settings, "reflex_api_key", "", raising=False)


def test_open_mode_by_default(monkeypatch):
    _set_key(monkeypatch, "")
    assert client.get("/health").status_code == 200
    assert client.post("/ask", json=OPEN).status_code == 200


def test_locked_mode_rejects_and_accepts(monkeypatch):
    _set_key(monkeypatch, "secret-123")
    try:
        assert client.get("/health").status_code == 200  # always open
        assert client.post("/ask", json=OPEN).status_code == 401
        assert client.get("/metrics").status_code == 401
        ok = client.post("/ask", json=OPEN, headers={"X-API-Key": "secret-123"})
        assert ok.status_code == 200, ok.text
        bearer = client.get("/metrics", headers={"Authorization": "Bearer secret-123"})
        assert bearer.status_code == 200
        wrong = client.post("/ask", json=OPEN, headers={"X-API-Key": "nope"})
        assert wrong.status_code == 401
    finally:
        _set_key(monkeypatch, "")
