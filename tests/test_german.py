# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""German as a first-class citizen: folding, repeats, native answers, neutral prompts."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app
from reflex.core.normalizer import normalize_situation
from reflex.llm.base import MockProvider

client = TestClient(app)


def test_umlaut_folding_converges():
    assert normalize_situation("Wo ist meine Rückerstattung?") == normalize_situation(
        "Wo ist meine Rueckerstattung?")


def test_german_repeats_hit_reflex():
    for msg in ["Wo ist meine Rückerstattung?",
                "Bitte Bestellung ORD-9911 stornieren",
                "Wann kommt meine Lieferung an?"]:
        uid = f"de_{abs(hash(msg)) % 10000}"
        res = {}
        for _ in range(5):
            r = client.post("/ask", json={"user_id": uid, "message": msg, "llm": "mock/mock-echo"})
            assert r.status_code == 200, r.text
            res = r.json()
            if res["source"] == "reflex":
                break
        assert res["source"] == "reflex", (msg, res)


def test_mock_answers_in_german():
    mock = MockProvider()
    assert "Rückerstattung" in mock.complete("Wo bleibt meine Rückerstattung?").text
    assert "storniert" in mock.complete("Bitte stornieren Sie meine Bestellung").text
    assert "unterwegs" in mock.complete("Wo ist meine Lieferung?").text
    # Hindi still Hindi, English still English
    assert "रिफंड" in mock.complete("मेरा रिफंड कब आएगा?").text
    assert "refund" in mock.complete("When will my refund arrive?").text.lower()


def test_system_prompt_is_language_neutral(monkeypatch):
    import reflex.api.routes as routes

    seen: list[str] = []

    class SpyProvider:
        def complete(self, prompt: str, system: str = "") -> object:
            seen.append(system)
            from reflex.llm.base import LLMResponse
            return LLMResponse("ok", "spy")

    monkeypatch.setattr(routes, "get_provider", lambda model="": SpyProvider())
    client.post("/ask", json={"user_id": "syscheck",
                              "message": "SYSQ Wo bleibt meine einmalige Sonderanfertigung?",
                              "llm": "mock/mock-echo"})
    assert seen, "provider was never called"
    assert all("hindi" not in s.lower() for s in seen), seen
    assert any("same language" in s.lower() for s in seen), seen
