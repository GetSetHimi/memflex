# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Usecase combination matrix: every area × phrasing variations.

For each area: establish with a full question, then fire shorthands,
reorders, cross-language and follow-up variants. Each must serve the SAME
correct answer from memory (never llm). Negatives must never cross-match
(refund variation must not return the cancel answer).

Nonces (UC1..UC7) isolate areas from each other inside the shared test DB;
the no-nonce veto test proves the cross-intent guard on realistic input.
"""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

from fastapi.testclient import TestClient
from reflex.api.app import app

client = TestClient(app)
UID = "uc_matrix"
LLM = "mock/mock-echo"


def ask(uid, msg, **kw):
    r = client.post("/ask", json={"user_id": uid, "message": msg, "llm": LLM, **kw})
    assert r.status_code == 200, (msg, r.text)
    return r.json()


def establish(uid, full):
    first = ask(uid, full)
    assert first["source"] == "llm", (full, first)
    return first["answer"]


def expect_same(uid, variants, expected_answer, tag):
    for v in variants:
        res = None
        for _ in range(5):
            res = ask(uid, v)
            if res["source"] == "reflex":
                break
        assert res["source"] in ("reflex", "reflex+reverify"), (tag, v, res)
        assert res["answer"] == expected_answer, (tag, v, res)


def test_support_refund_combinations():
    ans = establish(UID, "UC1 when will my refund arrive?")
    expect_same(UID, [
        "UC1 refund status?",
        "UC1 refund when?",
        "UC1 refund??",
        "UC1 where is my refund?",
        "UC1 mera refund kab ayega?",
    ], ans, "refund")


def test_support_cancel_combinations():
    ans = establish(UID, "UC2 please cancel my order number five?")
    expect_same(UID, [
        "UC2 cancel my order?",
        "UC2 order cancel??",
        "UC2 cancel order number five",
    ], ans, "cancel")


def test_support_delivery_combinations():
    ans = establish(UID, "UC3 where is my delivery at the moment?")
    expect_same(UID, [
        "UC3 delivery status?",
        "UC3 where is my parcel?",
    ], ans, "delivery")
    # "package kahan hai?" is a genuinely different key (paraphrase needs a
    # semantic backend) — but it must learn its OWN stable delivery memory,
    # never bleed into refund/cancel.
    r1 = ask(UID, "UC3 package kahan hai?")
    assert "on its way" in r1["answer"], r1
    r2 = ask(UID, "UC3 package kahan hai?")
    assert r2["answer"] == r1["answer"] and r2["source"] in ("reflex", "reflex+reverify"), r2


def test_no_cross_intent_bleed():
    # refund variants must never return the cancel (or delivery) answer
    cancel_ans = ask(UID, "UC2 please cancel my order number five?")["answer"]
    for v in ["UC1 refund status?", "UC1 refund when?"]:
        res = ask(UID, v)
        assert res["answer"] != cancel_ans, (v, res)


def test_veto_blocks_realistic_cross_match():
    # No nonces: "delivery status?" must NEVER be served a refund answer,
    # even though both share the generic word "status". Either a miss that
    # learns delivery, or a delivery-family memory — never refund text.
    uid = "veto_user"
    # ensure a refund-status memory exists (source irrelevant — memory or miss
    # both prove the refund family is memorized)
    for _ in range(3):
        seed = ask(uid, "UC6 when will my refund status update?")
    assert "refund is being processed" in seed["answer"], seed
    got = ask(uid, "delivery status?")
    assert "refund is being processed" not in got["answer"], got
    assert "on its way" in got["answer"] or got["source"] == "llm", got


def test_german_combinations():
    ans = establish(UID, "UC4 wo ist meine Rückerstattung bitte?")
    expect_same(UID, [
        "UC4 Rückerstattung?",
        "UC4 wo bleibt meine Rückerstattung?",
    ], ans, "german-refund")


def test_structured_survives_variations():
    full = "UC5 what is the refund status for case seven?"
    first = ask(UID, full, extract_structured=True,
                output_schema={"refund_status": "str", "eta_days": "list[int]"})
    assert first["structured"] and first["structured"]["refund_status"] == "processing", first
    res = None
    for _ in range(5):
        res = ask(UID, "UC5 refund status for case seven?", extract_structured=True,
                  output_schema={"refund_status": "str", "eta_days": "list[int]"})
        if res["source"] in ("reflex", "reflex+reverify"):
            break
    # paraphrase may live in reverify band (sim < 1 caps the score) — but the
    # answer AND the typed payload must be served from memory, never remade.
    assert res["source"] in ("reflex", "reflex+reverify"), res
    assert res["structured"]["refund_status"] == "processing", res
    assert res["answer"] == first["answer"], res
