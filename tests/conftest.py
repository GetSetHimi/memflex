# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Hermetic tests: every test module gets a FRESH sqlite store.

The API uses process-global singletons (reflex.api.deps._store), and the old
/tmp/reflex_test.db persisted across runs — corrections/confidence leaked
between tests. This module-scoped autouse fixture swaps in a temp-DB store
per test file, so results are order- and history-independent.
"""
import os
import tempfile

os.environ.setdefault("EMBEDDING_BACKEND", "hash")

import pytest


@pytest.fixture(scope="module", autouse=True)
def _fresh_store():
    from reflex.api import deps
    from reflex.stores.sqlite_vec import SqliteReflexStore

    tmp = tempfile.mkdtemp(prefix="reflex_test_")
    fresh = SqliteReflexStore(os.path.join(tmp, "t.db"), dim=deps.get_embed().dim)
    old, deps._store = deps._store, fresh
    old_counters = dict(deps.counters)
    for k in deps.counters:
        deps.counters[k] = 0
    try:
        yield fresh
    finally:
        deps._store = old
        deps.counters.update(old_counters)
