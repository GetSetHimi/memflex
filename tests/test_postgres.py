# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Postgres store tests — run against a REAL server, skipped otherwise.

Live:  brew install postgresql@17 pgvector  (or docker: pgvector/pgvector:pg17)
        initdb -D /tmp/pgdata -E UTF8 && pg_ctl -D /tmp/pgdata -o "-p 5433" start
        psql -p 5433 -c "CREATE DATABASE reflex_test;" -c "CREATE EXTENSION vector;"
        MEMFLEX_TEST_PG_DSN=postgresql://$USER@localhost:5433/reflex_test \
          EMBEDDING_BACKEND=hash python -m pytest tests/test_postgres.py -q
"""
import os

import pytest

DSN = os.environ.get("MEMFLEX_TEST_PG_DSN", "")
needs_pg = pytest.mark.skipif(not DSN, reason="no MEMFLEX_TEST_PG_DSN — needs live Postgres")

SIT = "PGTX where is my parcel right now?"


@needs_pg
def test_pg_full_loop():
    import numpy as np
    from reflex.core.models import Decision, Memory, Reflex
    from reflex.stores.postgres import PostgresReflexStore

    try:
        store = PostgresReflexStore(DSN, dim=8)
    except Exception as e:
        pytest.skip(f"postgres unreachable: {e}")
    import uuid

    uid = f"pgu_{uuid.uuid4().hex[:6]}"
    vec = np.ones(8, dtype=np.float32) / np.sqrt(8.0)
    sit = f"pgtx where is my parcel right now? {uuid.uuid4().hex[:6]}"
    rx = Reflex(user_id=uid, situation=sit,
                decision=Decision(action="a", payload="on the truck"), confidence=0.9)
    store.save_reflex(rx, vec)
    assert store.get_reflex(rx.id).decision.payload == "on the truck"
    assert store.find_by_situation(uid, rx.situation).id == rx.id
    res = [t for t in store.search(vec, top_k=10) if t[0].id == rx.id]
    assert res and res[0][1] > 0.99, res
    store.record_hit(rx.id)
    assert store.get_reflex(rx.id).hits == 1
    store.record_correction(rx.id)
    assert store.get_reflex(rx.id).corrections == 1
    store.touch_verified(rx.id)
    subj = f"user:{uid}"
    m = store.save_memory(Memory(subject=subj, fact="likes COD", confidence=0.9))
    assert store.list_memories(subj)[0].fact == "likes COD"
    assert m.id in [x.id for x in store.list_memories()]
    store.set_last_message(uid, "hello?")
    assert store.get_last_message(uid) == "hello?"
    assert store.delete_reflex(rx.id) is True
    assert store.get_reflex(rx.id) is None
    assert store.list_reflexes(uid) == []
