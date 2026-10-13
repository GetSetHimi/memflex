# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Console API client — talks to the Memflex server, forwards the API key."""
import os

import requests

API = os.environ.get("REFLEX_API_URL", "http://localhost:8000")
_API_KEY = os.environ.get("MEMFLEX_API_KEY", "") or os.environ.get("REFLEX_API_KEY", "")


def headers() -> dict:
    return {"X-API-Key": _API_KEY} if _API_KEY else {}


def api_get(path: str, **kw):
    kw.setdefault("headers", {}).update(headers())
    r = requests.get(f"{API}{path}", timeout=15, **kw)
    r.raise_for_status()
    return r.json()


def api_post(path: str, **kw):
    kw.setdefault("headers", {}).update(headers())
    r = requests.post(f"{API}{path}", timeout=90, **kw)
    r.raise_for_status()
    return r.json()


def api_delete(path: str, **kw):
    kw.setdefault("headers", {}).update(headers())
    r = requests.delete(f"{API}{path}", timeout=15, **kw)
    r.raise_for_status()
    return r.json()


def api_patch(path: str, **kw):
    kw.setdefault("headers", {}).update(headers())
    r = requests.patch(f"{API}{path}", timeout=15, **kw)
    r.raise_for_status()
    return r.json()
