# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Day-2 scenarios: stale volatile answers must NOT serve; vague follow-ups must resolve."""
import os
from datetime import datetime, timedelta, timezone

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api import deps
from reflex.api.app import app
from reflex.core.distiller import infer_ttl_days

client = TestClient(app)


def test_volatile_answers_get_short_ttl():
    assert infer_ttl_days("refund status?", "processing, ETA 3 days") == 1
    assert infer_ttl_days("Wo ist meine Rückerstattung?", "wird bearbeitet") == 1
    assert infer_ttl_days("What is your return policy?", "30-day returns, see terms") == 30


def test_expired_reflex_is_never_served():
    uid, msg = "stale_user", "STALEX where is my parcel right now?"
    seed = client.post("/reflexes", json={
        "user_id": uid, "message": msg,
        "answer": "shipped yesterday, arriving today (day-1 truth)",
        "confidence": 0.95}).json()
    assert seed["ttl_days"] == 1  # volatile content → 1-day TTL inferred
    # establish a hit first (proves it WOULD serve fresh)
    for _ in range(5):
        r = client.post("/ask", json={"user_id": uid, "message": msg, "llm": "mock/mock-echo"}).json()
        if r["source"] == "reflex":
            break
    assert r["source"] == "reflex", r
    # time-travel 2 days: last verification now older than the 1-day TTL
    store = deps.get_store()
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    store._con.execute("UPDATE reflexes SET last_verified_at=? WHERE id=?", (old, seed["id"]))
    store._con.commit()
    # day-2 ask must go to System 2 for a fresh verdict — never serve stale
    day2 = client.post("/ask", json={"user_id": uid, "message": msg, "llm": "mock/mock-echo"}).json()
    assert day2["source"] == "llm", day2
    # ...and the fresh verdict re-learns into the SAME record (no duplicates)
    rows = [x for x in client.get("/reflexes", params={"user_id": uid}).json()
            if x["situation"] == seed["situation"]]
    assert len(rows) == 1 and rows[0]["id"] == seed["id"], rows


def test_vague_followup_gets_same_answer():
    uid = "followup_user"
    full = "Hii what is status for my refund"
    r1 = client.post("/ask", json={"user_id": uid, "message": full, "llm": "mock/mock-echo"}).json()
    assert r1["source"] == "llm", r1
    # next day: bare "refund??" must resolve to the same conversation + same answer
    r2 = client.post("/ask", json={"user_id": uid, "message": "refund??",
                                   "llm": "mock/mock-echo", "explain": True}).json()
    assert r2["source"] in ("reflex", "reflex+reverify"), r2
    assert r2["answer"] == r1["answer"], (r1, r2)
    assert r2.get("expanded_from") == full, r2  # audit trail of the expansion
