# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Template rendering: stored {variables} filled per-request, zero LLM."""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app
from reflex.core.renderer import render

client = TestClient(app)


def test_render_unit():
    assert render("Hi {name}, ETA {eta}", {"name": "Ravi", "eta": "3 din"}) == (
        "Hi Ravi, ETA 3 din", True)
    # unknown keys stay literal, never crash
    assert render("Hi {name}, {mystery}", {"name": "Ravi"}) == (
        "Hi Ravi, {mystery}", True)
    assert render("No braces", {"a": 1}) == ("No braces", False)
    assert render("Broken { brace", {"brace": 1})[1] is False
    # no code execution: attribute/item access renders literally, not evaluated
    out, _ = render("{__class__}", {})
    assert out == "{__class__}"


def test_template_served_from_memory():
    uid, msg = "tmpl", "TMPLP mein apna cashback balance kaise dekhun?"
    client.post("/reflexes", json={
        "user_id": uid, "message": msg,
        "answer": "Namaste {name}, aapka cashback balance ₹{balance} hai.",
        "confidence": 0.95})
    r = client.post("/ask", json={"user_id": uid, "message": msg, "llm": "mock/mock-echo",
                                  "context": {"name": "Ravi", "balance": 250}}).json()
    assert r["source"] in ("reflex", "reflex+reverify"), r
    assert r["answer"] == "Namaste Ravi, aapka cashback balance ₹250 hai.", r
    # without context → placeholders stay visible, still from memory
    r2 = client.post("/ask", json={"user_id": uid, "message": msg,
                                   "llm": "mock/mock-echo"}).json()
    assert "{name}" in r2["answer"] and "{balance}" in r2["answer"], r2
