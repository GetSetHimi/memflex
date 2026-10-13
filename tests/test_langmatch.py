# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Language-match quarantine: wrong-script answers are served once, never memorized."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app
from reflex.core.distiller import language_match

client = TestClient(app)


def test_language_match_unit():
    assert language_match("मेरा रिफंड कब आएगा?", "आपका रिफंड प्रोसेस हो रहा है।")
    assert language_match("返金はいつ届きますか?", "返金手続き中です。")
    # Latin answers always pass (English fallback / mock gaps are legitimate)
    assert language_match("मेरा रिफंड कब आएगा?", "Ihre Rückerstattung wird bearbeitet.")
    assert language_match("எனது பணம் திரும்ப?", "Your order is on its way.")
    assert language_match("plain english q?", "plain english a.")
    # ...but disjoint non-Latin scripts are a real mismatch
    assert not language_match("मेरा रिफंड कब आएगा?", "உங்கள் தொகை வரும்.")
    assert not language_match("返金はいつ?", "Ваш возврат готов.")


def test_mismatched_ask_served_once_never_saved():
    from unittest.mock import patch
    from reflex.llm.base import LLMResponse
    import reflex.api.routes as routes

    class Tamilizer:
        def complete(self, prompt: str, system: str = ""):
            return LLMResponse("உங்கள் தொகை வரும்.", "mock/tamilizer")

    with patch.object(routes, "get_provider", lambda model="": Tamilizer()):
        r1 = client.post("/ask", json={"user_id": "langq", "message": "LANQ मेरा पैसा कब आएगा?",
                                       "llm": "mock/tamilizer"}).json()
        assert r1["source"] == "llm" and r1["reflex_id"] is None
        r2 = client.post("/ask", json={"user_id": "langq", "message": "LANQ मेरा पैसा कब आएगा?",
                                       "llm": "mock/tamilizer"}).json()
        assert r2["source"] == "llm", r2  # asked again, memorized nothing
    assert client.get("/reflexes", params={"user_id": "langq"}).json() == []


def test_explicit_mismatch_rejected_unless_allowed():
    bad = {"user_id": "langq2", "message": "LANQ2 मेरा पैसा कब आएगा?",
           "answer": "உங்கள் தொகை வரும்."}
    r = client.post("/reflexes", json=bad)
    assert r.status_code == 422, r.text
    ok = client.post("/reflexes", json={**bad, "allow_mismatch": True})
    assert ok.status_code == 200
