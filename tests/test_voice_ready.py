# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Voice-readiness (P0): SSE streaming, explicit tools handling, per-caller memory.

LiveKit-style agents need OpenAI-protocol SSE; ElevenLabs-style gateways need
it too. Nothing here may silently drop fields or bleed memories across callers.
"""
import json
import os

os.environ["EMBEDDING_BACKEND"] = "hash"

import httpx
from fastapi.testclient import TestClient
from reflex.api.app import app

client = TestClient(app)


def _sse_text_events(body: str):
    """Parse SSE body -> (list of chunk payloads, saw_done)."""
    events, done = [], False
    for block in body.split("\n\n"):
        for line in block.splitlines():
            if line == "data: [DONE]":
                done = True
            elif line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events, done


def _reconstruct(events):
    """Rebuild assistant content + tool_calls from chunk deltas."""
    text, calls = [], {}
    finish = None
    for ev in events:
        for ch in ev.get("choices", []):
            delta = ch.get("delta", {})
            if "content" in delta and delta["content"] is not None:
                text.append(delta["content"])
            for tc in delta.get("tool_calls", []):
                slot = calls.setdefault(tc["index"], {"function": {"arguments": ""}})
                fn = tc.get("function", {})
                if fn.get("name"):
                    slot.setdefault("function", {})["name"] = fn["name"]
                slot["function"]["arguments"] += fn.get("arguments", "")
                if tc.get("id"):
                    slot["id"] = tc["id"]
            if ch.get("finish_reason"):
                finish = ch["finish_reason"]
    return "".join(text), list(calls.values()), finish


def test_sse_text_roundtrip_matches_nonstream():
    msg = f"VOXSSE status for parcel {os.getpid()}?"
    base = {"model": "mock/mock-echo",
            "messages": [{"role": "user", "content": msg}], "user": "vox_a"}
    plain = client.post("/v1/chat/completions", json=base).json()
    assert plain["reflex_source"] == "llm"

    r = client.post("/v1/chat/completions", json={**base, "stream": True})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["X-Reflex-Source"] in ("reflex", "reflex+reverify")
    events, done = _sse_text_events(r.text)
    assert done and events, r.text[:300]
    text, _, finish = _reconstruct(events)
    assert finish == "stop"
    assert text == plain["choices"][0]["message"]["content"], (text, plain)
    assert events[0]["object"] == "chat.completion.chunk"
    assert events[0]["choices"][0]["delta"]["role"] == "assistant"


def test_tools_with_unsupported_backend_are_explicit_400():
    tools = [{"type": "function", "function": {"name": "get_order",
             "parameters": {"type": "object", "properties": {}}}}]
    body = {"model": "mock/mock-echo",
            "messages": [{"role": "user", "content": "VOXTOOL hi?"}],
            "user": "vox_tool", "tools": tools, "tool_choice": "auto"}
    assert client.post("/v1/chat/completions", json=body).status_code == 400
    assert client.post("/v1/chat/completions", json={**body, "stream": True}).status_code == 400


def test_tools_forwarded_and_never_memorized(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, json=json)
        msg = {"role": "assistant", "content": None,
               "tool_calls": [{"id": "call_1", "type": "function",
                               "function": {"name": "get_order",
                                            "arguments": '{"order_id":"ORD-1"}'}}]}
        return FakeRespUp({"choices": [{"message": msg, "finish_reason": "tool_calls"}]})

    class FakeRespUp:
        def __init__(self, payload):
            self._p = payload

        def raise_for_status(self):
            pass

        def json(self):
            return self._p

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr("reflex.core.config.settings.openai_api_key", "k-test", raising=False)
    tools = [{"type": "function", "function": {"name": "get_order",
             "parameters": {"type": "object", "properties": {}}}}]
    body = {"model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": "VOXFWD check order ORD-1"}],
            "user": "vox_fwd", "tools": tools, "tool_choice": "required"}
    r = client.post("/v1/chat/completions", json=body)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["choices"][0]["finish_reason"] == "tool_calls"
    assert d["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "get_order"
    assert seen["json"]["tools"] == tools
    assert seen["json"]["tool_choice"] == "required"
    # tool decisions are live-only: nothing memorized for this caller
    assert client.get("/reflexes", params={"user_id": "vox_fwd"}).json() == []

    # same over SSE: deltas must reconstruct the exact tool call
    r2 = client.post("/v1/chat/completions", json={**body, "stream": True})
    assert r2.status_code == 200, r2.text
    events, done = _sse_text_events(r2.text)
    assert done
    _, calls, finish = _reconstruct(events)
    assert finish == "tool_calls"
    assert calls[0]["function"]["name"] == "get_order"
    assert json.loads(calls[0]["function"]["arguments"]) == {"order_id": "ORD-1"}


def test_v1_memory_scoped_per_caller():
    msg = "VOXSCOPE where is my parcel?"
    a = {"model": "mock/mock-echo", "messages": [{"role": "user", "content": msg}], "user": "vox_scope_a"}
    b = dict(a, user="vox_scope_b")
    assert client.post("/v1/chat/completions", json=a).json()["reflex_source"] == "llm"
    for _ in range(4):
        hit = client.post("/v1/chat/completions", json=a).json()
        if hit["reflex_source"] == "reflex":
            break
    assert hit["reflex_source"] == "reflex"
    # caller B never sees caller A's memory
    assert client.post("/v1/chat/completions", json=b).json()["reflex_source"] == "llm"
    # ...but the plain /ask API keeps shared global memory (support-bot mode)
    shared = client.post("/ask", json={"user_id": "vox_scope_c", "message": msg,
                                        "llm": "mock/mock-echo"}).json()
    assert shared["source"] in ("reflex", "reflex+reverify"), shared


def test_v1_messages_metadata_user_isolation():
    def post(uid, text):
        return client.post("/v1/messages", json={
            "model": "mock/mock-echo",
            "messages": [{"role": "user", "content": text}],
            "metadata": {"user_id": uid}}).json()

    msg = "VOXMETA wallet balance?"
    assert post("vox_meta_a", msg)["reflex_source"] == "llm"
    for _ in range(4):
        hit = post("vox_meta_a", msg)
        if hit["reflex_source"] == "reflex":
            break
    assert hit["reflex_source"] == "reflex"
    # different metadata user: isolated miss, not someone else's memory
    assert post("vox_meta_b", msg)["reflex_source"] == "llm"


def test_v1_messages_tools_rejected_explicitly():
    r = client.post("/v1/messages", json={
        "model": "mock/mock-echo",
        "messages": [{"role": "user", "content": "VOXMTOOLS hi?"}],
        "tools": [{"name": "x"}]})
    assert r.status_code == 400
