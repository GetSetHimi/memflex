# Copyright (c) 2026 Himanshu Sharma — Memflex client, licensed under Apache-2.0 (see LICENSE-CLIENT).
"""Python SDK — 5-line quickstart from the doc."""
from __future__ import annotations
import httpx


class _Res:
    def __init__(self, d: dict):
        self.answer = d.get("answer", "")
        self.source = d.get("source", "")
        self.reflex_id = d.get("reflex_id")
        self.confidence = d.get("confidence", 0.0)
        self.latency_ms = d.get("latency_ms", 0)
        self.raw = d


class Client:
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 60):
        self.base = base_url.rstrip("/")
        self._http = httpx.Client(base_url=self.base, timeout=timeout)

    def ask(self, user_id: str, message: str, llm: str = "mock/mock-echo",
            serve_threshold: float = 0.85, **kw) -> _Res:
        r = self._http.post("/ask", json={"user_id": user_id, "message": message,
                                          "llm": llm, "serve_threshold": serve_threshold, **kw})
        r.raise_for_status()
        return _Res(r.json())

    def remember(self, user_id: str, fact: str, confidence: float = 0.9):
        r = self._http.post("/remember", json={"user_id": user_id, "fact": fact, "confidence": confidence})
        r.raise_for_status()
        return r.json()

    def reflexes(self, user_id: str = ""):
        r = self._http.get("/reflexes", params={"user_id": user_id} if user_id else {})
        r.raise_for_status()
        return r.json()

    def feedback(self, reflex_id: str, ok: bool, note: str = ""):
        r = self._http.post(f"/reflexes/{reflex_id}/feedback", json={"ok": ok, "note": note})
        r.raise_for_status()
        return r.json()

    def save_reflex(self, user_id: str, message: str, answer: str,
                    structured: dict | None = None, confidence: float = 0.9,
                    context: dict | None = None):
        """Memorize a tool-composed final answer (upserts same situation).

        Pass the SAME context as the ask so the key matches the
        auto-distilled row (upsert) instead of creating a duplicate.
        """
        r = self._http.post("/reflexes", json={
            "user_id": user_id, "message": message, "answer": answer,
            "structured": structured, "confidence": confidence,
            "source": "explicit:agent-tools", "context": context or {},
        })
        r.raise_for_status()
        return r.json()
