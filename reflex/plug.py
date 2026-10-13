# Copyright (c) 2026 Himanshu Sharma — Memflex client, licensed under Apache-2.0 (see LICENSE-CLIENT).
"""Plug-and-play clients — one line from any agent to a Memflex server.

    from reflex.plug import openai_client, anthropic_client

    chat = openai_client()      # OpenAI SDK, base_url -> REFLEX_URL/v1
    chat.chat.completions.create(model="mock/mock-echo", messages=[...])

    claude = anthropic_client() # Anthropic SDK, base_url -> REFLEX_URL/v1
    claude.messages.create(model="mock/mock-echo", max_tokens=256, messages=[...])

Env:
    REFLEX_URL  base URL of the server (default http://localhost:8000)
    REFLEX_KEY  forwarded as the SDK api_key (server ignores it; set anything)

The `openai` / `anthropic` packages are optional — imported lazily, with a
clear error telling you exactly what to pip install.
"""
from __future__ import annotations
import os


def server_url() -> str:
    return os.environ.get("REFLEX_URL", "http://localhost:8000").rstrip("/")


def openai_client(**kw):
    """OpenAI SDK client pre-pointed at this Memflex server's /v1."""
    try:
        from openai import OpenAI
    except ImportError as e:
        raise ImportError("pip install openai  (needed for reflex.plug.openai_client)") from e
    return OpenAI(
        base_url=f"{server_url()}/v1",
        api_key=os.environ.get("REFLEX_KEY", "not-needed"),
        **kw,
    )


def anthropic_client(**kw):
    """Anthropic SDK client pre-pointed at this Memflex server's /v1."""
    try:
        from anthropic import Anthropic
    except ImportError as e:
        raise ImportError("pip install anthropic  (needed for reflex.plug.anthropic_client)") from e
    return Anthropic(
        base_url=f"{server_url()}/v1",
        api_key=os.environ.get("REFLEX_KEY", "not-needed"),
        **kw,
    )
