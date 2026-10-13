# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Refusal quarantine: model refusals are served once, never memorized."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app
from reflex.core.distiller import is_refusal

client = TestClient(app)


def test_is_refusal_multilingual():
    assert is_refusal("I don't have access to your personal account.")
    assert is_refusal("क्षमा करें, मैं आपके ऑर्डर नहीं देख सकता।")
    assert is_refusal("Ihre Bestellung ist unterwegs.") is False
    assert is_refusal("Your refund is processing.") is False


def test_refusal_never_memorized():
    from unittest.mock import patch
    from reflex.llm.base import LLMResponse
    import reflex.api.routes as routes

    class Refuser:
        def complete(self, prompt: str, system: str = ""):
            return LLMResponse("I don't have access to your personal account.", "mock/refuser")

    with patch.object(routes, "get_provider", lambda model="": Refuser()):
        r1 = client.post("/ask", json={"user_id": "refq", "message": "REFQ my balance?",
                                       "llm": "mock/refuser"}).json()
        assert r1["source"] == "llm" and r1["reflex_id"] is None
        r2 = client.post("/ask", json={"user_id": "refq", "message": "REFQ my balance?",
                                       "llm": "mock/refuser"}).json()
        assert r2["source"] == "llm", r2  # asked again, memorized nothing
    rows = client.get("/reflexes", params={"user_id": "refq"}).json()
    assert rows == [], rows
