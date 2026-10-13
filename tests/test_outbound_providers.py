# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Outbound providers: request shapes per vendor API + factory routing.

httpx is stubbed — no network, no keys. Verifies Memflex speaks each vendor's
protocol correctly (headers, body, response parsing) and falls back to Mock
when keys are absent.
"""
import httpx
from reflex.llm.factory import get_provider
from reflex.llm.base import MockProvider
from reflex.llm.providers import AnthropicProvider, GeminiProvider


class FakeResp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def test_anthropic_request_shape(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, json=json)
        return FakeResp({"content": [{"type": "text", "text": "claude says hi"}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = AnthropicProvider("claude-sonnet-4-5", "k-test").complete("hello", system="sys")
    assert out.text == "claude says hi" and out.model == "claude/claude-sonnet-4-5"
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "k-test"
    assert seen["headers"]["anthropic-version"] == "2023-06-01"
    assert seen["json"]["model"] == "claude-sonnet-4-5"
    assert seen["json"]["system"] == "sys"
    assert seen["json"]["messages"] == [{"role": "user", "content": "hello"}]


def test_gemini_request_shape(monkeypatch):
    seen = {}

    def fake_post(url, params=None, json=None, timeout=None):
        seen.update(url=url, params=params, json=json)
        return FakeResp({"candidates": [{"content": {"parts": [
            {"text": "hmm, thinking…", "thought": True},
            {"text": "gemini says hi"},
        ]}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    out = GeminiProvider("gemini-2.5-flash", "k-test").complete("hello", system="sys")
    assert out.text == "gemini says hi" and out.model == "gemini/gemini-2.5-flash"
    assert seen["url"].endswith("gemini-2.5-flash:generateContent")
    assert seen["params"] == {"key": "k-test"}
    assert seen["json"]["contents"][0]["parts"] == [{"text": "hello"}]
    assert seen["json"]["system_instruction"]["parts"] == [{"text": "sys"}]


def test_factory_routes_all_five_vendors(monkeypatch):
    # no keys in CI → graceful Mock fallback (never crashes keyless).
    # Blank settings too: a local .env with real keys must not leak in.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("reflex.core.config.settings.anthropic_api_key", "", raising=False)
    monkeypatch.setattr("reflex.core.config.settings.gemini_api_key", "", raising=False)
    monkeypatch.setattr("reflex.core.config.settings.openai_api_key", "", raising=False)
    for m in ["claude/claude-sonnet-4-5", "anthropic/x", "gemini/gemini-2.5-flash",
              "google/y", "openai/gpt-4o-mini", "gpt-4o", "openrouter/a", "deepseek/b"]:
        assert isinstance(get_provider(m), MockProvider), m


def test_factory_uses_keys_when_present(monkeypatch):
    from reflex.llm import providers as P

    monkeypatch.setattr("reflex.core.config.settings.anthropic_api_key", "k1", raising=False)
    assert isinstance(get_provider("claude/claude-sonnet-4-5"), P.AnthropicProvider)
    monkeypatch.setenv("GOOGLE_API_KEY", "k2")
    monkeypatch.setattr("reflex.core.config.settings.gemini_api_key", "", raising=False)
    assert isinstance(get_provider("gemini/gemini-2.5-flash"), P.GeminiProvider)
