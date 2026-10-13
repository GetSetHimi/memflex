# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""HTTP providers: Ollama, OpenAI-compatible (OpenRouter/DeepSeek/OpenAI),
Anthropic Claude, Google Gemini. All share complete(prompt, system)."""
from __future__ import annotations
import httpx
from reflex.llm.base import LLMResponse


def _clean_key(api_key: str) -> str:
    """Strip whitespace, surrounding quotes, and a pasted `Bearer ` prefix.

    Prevents `Authorization: Bearer Bearer xxx`, `Bearer "xxx"`, or
    `Bearer <empty>` — all of which Ollama Cloud rejects with
    `400: Authorization header is badly formatted`.
    """
    k = (api_key or "").strip().strip("\"'").strip()
    if k[:7].lower() == "bearer ":
        k = k[7:].strip().strip("\"'").strip()
    # keys must be single-line tokens — drop embedded whitespace/newlines
    return "".join(k.split())


class OllamaProvider:
    """Local (http://localhost:11434, no auth) + Cloud (https://ollama.com, Bearer OLLAMA_API_KEY)."""

    def __init__(self, model: str = "qwen2.5:7b", host: str = "http://localhost:11434", api_key: str = ""):
        self.model = model
        self.host = host.rstrip("/")
        import os

        self.api_key = _clean_key(api_key or os.environ.get("OLLAMA_API_KEY", ""))

    def complete(self, prompt: str, system: str = "") -> LLMResponse:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        headers = {"Content-Type": "application/json"}
        if "ollama.com" in self.host:
            if not self.api_key:
                raise ValueError(
                    "OLLAMA_API_KEY is missing: set it (https://ollama.com/settings/keys) "
                    "before using ollama-cloud/* or OLLAMA_HOST=https://ollama.com. "
                    "Empty/missing Bearer is rejected by Ollama Cloud with "
                    "`400: Authorization header is badly formatted`."
                )
            headers["Authorization"] = f"Bearer {self.api_key}"
        r = httpx.post(
            f"{self.host}/api/chat",
            headers=headers,
            json={"model": self.model, "messages": msgs, "stream": False},
            timeout=90,
        )
        r.raise_for_status()
        data = r.json()
        text = data.get("message", {}).get("content", "")
        prefix = "ollama-cloud" if "ollama.com" in self.host else "ollama"
        return LLMResponse(text, f"{prefix}/{self.model}")


class OpenAICompatProvider:
    """Covers OpenRouter + DeepSeek (both OpenAI chat-completions compatible)."""

    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = _clean_key(api_key)
        self.base_url = base_url.rstrip("/")

    def complete(self, prompt: str, system: str = "", tools=None,
                   tool_choice=None, max_tokens=None) -> LLMResponse:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        body: dict = {"model": self.model, "messages": msgs}
        if tools is not None:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        r = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body,
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        msg = data["choices"][0]["message"]
        resp = LLMResponse(msg.get("content") or "", self.model)
        if msg.get("tool_calls"):
            resp.tool_calls = msg["tool_calls"]
            resp.finish_reason = data["choices"][0].get("finish_reason") or "tool_calls"
        return resp


class AnthropicProvider:
    """Claude via the Anthropic Messages API (x-api-key, versioned)."""

    API_VERSION = "2023-06-01"

    def __init__(self, model: str = "claude-sonnet-4-5", api_key: str = "",
                 base_url: str = "https://api.anthropic.com"):
        self.model = model
        self.api_key = _clean_key(api_key)
        self.base_url = base_url.rstrip("/")

    def complete(self, prompt: str, system: str = "") -> LLMResponse:
        body: dict = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        r = httpx.post(
            f"{self.base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self.API_VERSION,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=90,
        )
        r.raise_for_status()
        blocks = r.json().get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        return LLMResponse(text, f"claude/{self.model}")


class GeminiProvider:
    """Google Gemini via generateContent (API key in query param)."""

    def __init__(self, model: str = "gemini-2.5-flash", api_key: str = ""):
        self.model = model
        self.api_key = _clean_key(api_key)

    def complete(self, prompt: str, system: str = "") -> LLMResponse:
        body: dict = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        r = httpx.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent",
            params={"key": self.api_key},
            json=body,
            timeout=90,
        )
        r.raise_for_status()
        cands = r.json().get("candidates", [])
        parts = (cands[0].get("content", {}).get("parts", []) if cands else [])
        # skip thinking/reasoning parts (Gemma "thought": true) — answer only
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        return LLMResponse(text, f"gemini/{self.model}")
