# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Mem0-compatible shim: from reflex.compat import mem0 — drop-in for basic add/search."""
from __future__ import annotations


class _MemoryClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        from reflex.client import Client
        self._c = Client(base_url)

    def add(self, messages, user_id: str = "default", **kw):
        fact = messages if isinstance(messages, str) else " ".join(
            m.get("content", "") if isinstance(m, dict) else str(m) for m in messages)
        return self._c.remember(user_id=user_id, fact=fact)

    def search(self, query: str, user_id: str = "default", **kw):
        res = self._c.ask(user_id=user_id, message=query)
        return [{"fact": res.answer, "source": res.source, "confidence": res.confidence}]


class mem0:  # noqa: N801 — mirror `import mem0` casing style
    MemoryClient = _MemoryClient
