# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Model-string router: mock/* | ollama/* | ollama-cloud/* | openrouter/* | deepseek/*
| openai/* | claude/* (Anthropic) | gemini/* (Google). Missing key → Mock fallback."""
from __future__ import annotations
import os
from reflex.core.config import settings
from reflex.llm.base import MockProvider
from reflex.llm.providers import (
    AnthropicProvider,
    GeminiProvider,
    OllamaProvider,
    OpenAICompatProvider,
)


def get_provider(model: str):
    m = (model or settings.default_llm_model).strip()
    if m.startswith("mock/") or m == "mock":
        return MockProvider()
    if m.startswith("ollama-cloud/"):
        # Hosted inference: https://ollama.com/api + Bearer OLLAMA_API_KEY, no local install.
        # e.g. ollama-cloud/gpt-oss:120b  (no :cloud suffix on hosted API)
        name = m.split("/", 1)[1] or "gpt-oss:120b"
        if not (settings.ollama_api_key or "").strip():
            return MockProvider()  # graceful keyless fallback (avoids cloud 400 bad-auth)
        return OllamaProvider(name, "https://ollama.com", settings.ollama_api_key)
    if m.startswith("ollama/"):
        name = m.split("/", 1)[1] or "qwen2.5:7b"
        # If OLLAMA_HOST points at ollama.com (cloud), auth header is added automatically.
        return OllamaProvider(name, settings.ollama_host, settings.ollama_api_key)
    if m.startswith("openrouter/"):
        name = m.split("/", 1)[1]
        if not settings.openrouter_api_key:
            return MockProvider()  # graceful keyless fallback
        return OpenAICompatProvider(name, settings.openrouter_api_key, "https://openrouter.ai/api/v1")
    if m.startswith("deepseek/"):
        name = m.split("/", 1)[1] or "deepseek-chat"
        if not settings.deepseek_api_key:
            return MockProvider()
        return OpenAICompatProvider(name, settings.deepseek_api_key, "https://api.deepseek.com/v1")
    if m.startswith("openai/"):
        name = m.split("/", 1)[1] or "gpt-4o-mini"
        if not settings.openai_api_key:
            return MockProvider()
        return OpenAICompatProvider(name, settings.openai_api_key, "https://api.openai.com/v1")
    if m.startswith(("gpt-", "o1", "o3", "o4")):
        # bare OpenAI model names (agent frameworks send these by default)
        if not settings.openai_api_key:
            return MockProvider()
        return OpenAICompatProvider(m, settings.openai_api_key, "https://api.openai.com/v1")
    if m.startswith(("claude/", "anthropic/")):
        # e.g. claude/claude-sonnet-4-5 — needs ANTHROPIC_API_KEY
        name = m.split("/", 1)[1] or "claude-sonnet-4-5"
        if not settings.anthropic_api_key:
            return MockProvider()
        return AnthropicProvider(name, settings.anthropic_api_key)
    if m.startswith(("gemini/", "google/")):
        # e.g. gemini/gemini-2.5-flash — needs GEMINI_API_KEY (or GOOGLE_API_KEY)
        name = m.split("/", 1)[1] or "gemini-2.5-flash"
        key = settings.gemini_api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not key:
            return MockProvider()
        return GeminiProvider(name, key)
    # bare model name -> try ollama, fallback mock
    try:
        return OllamaProvider(m, settings.ollama_host)
    except Exception:
        return MockProvider()
