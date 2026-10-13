# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Pydantic models — mirrors REFLEX_documentation.md §4 + §6."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class Decision(BaseModel):
    action: str = "answer_template"
    payload: str
    structured: Optional[dict[str, Any]] = None


class Reflex(BaseModel):
    id: str = Field(default_factory=lambda: new_id("rfx"))
    user_id: str = ""
    situation: str
    decision: Decision
    confidence: float = 0.8
    hits: int = 0
    corrections: int = 0
    source: str = "llm:mock"
    created_at: datetime = Field(default_factory=_now)
    last_verified_at: datetime = Field(default_factory=_now)
    ttl_days: int = 30


class Memory(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mem"))
    subject: str
    fact: str
    confidence: float = 0.8
    last_confirmed_at: datetime = Field(default_factory=_now)
    contradictions: list[str] = Field(default_factory=list)


# ---- API shapes ----
class AskRequest(BaseModel):
    user_id: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    llm: str = "mock/mock-echo"
    serve_threshold: Optional[float] = None
    extract_structured: bool = False
    output_schema: Optional[dict[str, str]] = None
    # optional: richer System-2 prompt on a MISS (situation key stays message-based
    # so multi-turn history never kills the hit rate)
    system: Optional[str] = None
    history: list[dict[str, str]] = Field(default_factory=list)
    # explain=true: response also carries WHY this answer was served
    # (matched situation key, similarity, threshold) — audit trust.
    explain: bool = False
    # override the distiller's inferred TTL for THIS reflex (days).
    # Time-varying answers (status/ETA) default to 1 day; stable FAQs to 30.
    ttl_days: Optional[int] = None
    # Function tools (OpenAI shape). Forwarded to OpenAI-compatible backends
    # on a miss; never silently dropped. A tool_choice that *requires* a call
    # bypasses memory (tool decisions are never cached).
    tools: Optional[list[dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    max_tokens: Optional[int] = None
    # False = scope memory search to this user_id (per-caller isolation for
    # shared servers / voice agents). True (default) = shared global memory.
    shared_memory: bool = True


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """OpenAI-compatible subset — lets ANY agent framework use Memflex via base_url."""

    model: str = "mock/mock-echo"
    messages: list[ChatMessage]
    user: str = "openai"
    stream: bool = False
    temperature: Optional[float] = None
    # Function tools (OpenAI shape). Forwarded to OpenAI-compatible backends;
    # other backends answer 400 explicitly instead of dropping them silently.
    # A tool_choice that requires a call bypasses memory (never cached).
    tools: Optional[list[dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    max_tokens: Optional[int] = None


class AnthropicContentBlock(BaseModel):
    type: str = "text"
    text: str = ""


class AnthropicMessage(BaseModel):
    role: str
    content: Any  # str or list[AnthropicContentBlock]


class AnthropicMessagesRequest(BaseModel):
    """Anthropic-compatible subset — Claude SDK via base_url.

    from anthropic import Anthropic
    client = Anthropic(base_url="http://localhost:8000/v1", api_key="not-needed")
    """

    model: str = "mock/mock-echo"
    messages: list[AnthropicMessage]
    system: Optional[Any] = None  # str or blocks
    max_tokens: int = 1024
    stream: bool = False
    # Per-caller identity (Anthropic metadata.user_id). Memory is scoped to
    # this user; without it all Claude-SDK callers would share one memory.
    metadata: Optional[dict[str, Any]] = None
    # Tools are accepted but NOT forwarded on this endpoint yet — sending them
    # is an explicit 400, never a silent drop.
    tools: Optional[Any] = None
    tool_choice: Optional[Any] = None


def anthropic_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            (b.get("text", "") if isinstance(b, dict) else getattr(b, "text", ""))
            for b in content
        )
    return str(content or "")


class AskResponse(BaseModel):
    answer: str
    source: str  # "reflex" | "reflex+reverify" | "llm"
    reflex_id: Optional[str] = None
    confidence: float
    latency_ms: int
    llm_cost_saved_inr: float
    # present only when explain=true
    matched_situation: Optional[str] = None
    similarity: Optional[float] = None
    threshold: Optional[float] = None
    expanded_from: Optional[str] = None  # follow-up expansion source, if any
    # typed machine-readable output (when the reflex carries structured data)
    structured: Optional[dict[str, Any]] = None
    # function tool calls (when the request carried tools and upstream
    # decided to call them — served live, never from memory)
    tool_calls: Optional[list[dict[str, Any]]] = None
    finish_reason: Optional[str] = None


class RememberRequest(BaseModel):
    user_id: str
    fact: str
    confidence: float = 0.9


class FeedbackRequest(BaseModel):
    ok: bool  # True=👍, False=👎
    note: str = ""


class PatchReflexRequest(BaseModel):
    """User-customizable memory controls: TTL in days (1–365) and/or confidence."""

    ttl_days: Optional[int] = None
    confidence: Optional[float] = None


class SaveReflexRequest(BaseModel):
    """Explicitly memorize a decision — for tool-composed answers, bulk import,
    migration. Same (user_id, situation) upserts instead of duplicating."""

    user_id: str = ""
    message: str = ""       # normalized to the situation key (preferred)
    context: dict[str, Any] = Field(default_factory=dict)  # same masking as /ask
    situation: str = ""     # ...or pass the key directly
    answer: str             # decision payload to serve on hits
    action: str = "answer_template"
    structured: Optional[dict[str, Any]] = None
    confidence: float = 0.9
    source: str = "explicit:api"
    ttl_days: Optional[int] = None  # default: inferred from content volatility
    allow_mismatch: bool = False  # True = save even if answer script != query script


class VerifyResult(BaseModel):
    checked: int
    confirmed: int
    flagged: int
    details: list[dict[str, Any]] = Field(default_factory=list)
