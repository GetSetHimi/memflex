# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
def test_mem0_shim_import():
    from reflex.compat.mem0 import mem0
    c = mem0.MemoryClient(base_url="http://localhost:8000")
    assert hasattr(c, "add") and hasattr(c, "search")
