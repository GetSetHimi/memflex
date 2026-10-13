# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""APScheduler hook (wired in api/app.py). Separated for clarity/testing."""
from __future__ import annotations

def build_job(store, provider, limit: int = 20):
    from reflex.verify.worker import run_verification

    def job():
        return run_verification(store, provider, limit=limit)

    return job
