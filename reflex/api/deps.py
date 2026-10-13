# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Shared deps — singleton store/embeddings + metrics counters + activity log."""
from __future__ import annotations
import os
import threading
from collections import deque
from datetime import datetime, timezone
from reflex.core.config import settings
from reflex.stores.embeddings import EmbeddingModel
from reflex.stores.sqlite_vec import SqliteReflexStore

_embed = EmbeddingModel(settings.embedding_backend, settings.embedding_model)


def _build_store():
    # REFLEX_STORE=sqlite (default, 1 file, zero deps) |
    # postgres (production scale, needs REFLEX_POSTGRES_DSN)
    which = (settings.reflex_store or "sqlite").strip().lower()
    if which in ("postgres", "postgresql", "pg"):
        from reflex.stores.postgres import PostgresReflexStore

        return PostgresReflexStore(settings.postgres_dsn, dim=_embed.dim)
    return SqliteReflexStore(
        os.path.expandvars(os.path.expanduser(settings.reflex_db_path)), dim=_embed.dim
    )


_store = _build_store()
# sync dim after lazy backend resolution
_store.dim = _embed.dim

counters = {"asks": 0, "hits": 0, "llm_calls": 0, "latency_ms_total": 0}

# Ring buffer of recent asks — powers the dashboard's "LLM calls vs Memflex
# answers" views. In-memory (last 500); full history lives in the DB as
# reflexes (hits/corrections) + metrics counters.
_activity: deque = deque(maxlen=500)
_activity_lock = threading.Lock()


def get_store():
    return _store


def get_embed() -> EmbeddingModel:
    return _embed


def record_ask(latency_ms: int, hit: bool, llm: bool, entry: dict | None = None) -> None:
    counters["asks"] += 1
    counters["latency_ms_total"] += latency_ms
    if hit:
        counters["hits"] += 1
    if llm:
        counters["llm_calls"] += 1
    if entry is not None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "latency_ms": latency_ms,
            "hit": hit,
            "llm_call": llm,
            **entry,
        }
        with _activity_lock:
            _activity.appendleft(entry)


def recent_activity(limit: int = 100) -> list[dict]:
    with _activity_lock:
        return list(_activity)[: max(1, min(limit, 500))]
