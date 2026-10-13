# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
import os
os.environ["EMBEDDING_BACKEND"] = "hash"
os.environ["REFLEX_DB_PATH"] = "/tmp/reflex_test.db"
try:
    os.remove("/tmp/reflex_test.db")
except FileNotFoundError:
    pass

from fastapi.testclient import TestClient
from reflex.api.app import app

client = TestClient(app)


def test_ask_miss_then_hit():
    r1 = client.post("/ask", json={"user_id": "u1", "message": "मेरा रिफंड कब आएगा?", "llm": "mock/mock-echo"})
    assert r1.status_code == 200, r1.text
    assert r1.json()["source"] == "llm"
    r2 = client.post("/ask", json={"user_id": "u1", "message": "मेरा रिफंड कब आएगा?", "llm": "mock/mock-echo"})
    assert r2.status_code == 200
    assert r2.json()["source"] in ("reflex", "reflex+reverify")
    assert "रिफंड" in r2.json()["answer"]


def test_hinglish_matches_hindi():
    client.post("/ask", json={"user_id": "u2", "message": "mera refund kab ayega?", "llm": "mock/mock-echo"})
    r = client.post("/ask", json={"user_id": "u2", "message": "मेरा रिफंड कब आएगा?", "llm": "mock/mock-echo"})
    assert r.json()["source"] in ("reflex", "reflex+reverify", "llm")


def test_remember_and_feedback():
    rm = client.post("/remember", json={"user_id": "u1", "fact": "prefers COD", "confidence": 0.9})
    assert rm.status_code == 200
    rx = client.get("/reflexes", params={"user_id": "u1"}).json()
    assert len(rx) >= 1
    fb = client.post(f"/reflexes/{rx[0]['id']}/feedback", json={"ok": True})
    assert fb.status_code == 200
    m = client.get("/metrics").json()
    assert m["asks"] >= 2 and "calibration" in m


def test_verify_and_delete():
    rx = client.get("/reflexes").json()
    assert len(rx) >= 1
    v = client.post("/verify/run", params={"limit": 5}).json()
    assert v["checked"] >= 1
    d = client.delete(f"/reflexes/{rx[0]['id']}")
    assert d.status_code == 200
