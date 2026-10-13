# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Route handlers — ask / memory / admin."""
from __future__ import annotations
import json
import re
import threading
import time
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from reflex.api import deps
from reflex.core import confidence as conf
from reflex.core.config import settings
from reflex.core.distiller import distill
from reflex.core.models import (
    AskRequest, AskResponse, AnthropicMessagesRequest, ChatCompletionRequest, Decision,
    FeedbackRequest, Memory, PatchReflexRequest, Reflex, RememberRequest, SaveReflexRequest,
    VerifyResult, anthropic_text, new_id,
)
from reflex.core.normalizer import normalize_situation
from reflex.core.renderer import render as render_answer
from reflex.llm.factory import get_provider
from reflex.llm.providers import OpenAICompatProvider
from reflex.verify.worker import run_verification

router = APIRouter()


def _is_expired(rx) -> bool:
    """True when the reflex outlived its TTL — must be re-learned, not served."""

    now = datetime.now(timezone.utc)
    lv = rx.last_verified_at
    if lv.tzinfo is None:
        lv = lv.replace(tzinfo=timezone.utc)
    age_days = (now - lv).total_seconds() / 86400.0
    return age_days > max(1 / 24, rx.ttl_days or 30)  # min granularity: 1 hour


def _requires_tool_call(tool_choice) -> bool:
    """True when the caller mandates a function call (never servable from memory)."""
    if tool_choice is None:
        return False
    if isinstance(tool_choice, dict):
        return True
    return isinstance(tool_choice, str) and tool_choice not in ("none", "auto")


def _bg_reverify(store, llm: str) -> None:
    """Best-effort verification in a daemon thread — never blocks a response."""
    try:
        run_verification(store, get_provider(llm), limit=1)
    except Exception:
        pass


def _chat_sse_chunks(answer, reflex_id, model, tool_calls=None, finish=None):
    """Yield OpenAI-style SSE chunk lines for an already-resolved answer."""
    cid = f"chatcmpl-{reflex_id or 'llm'}"
    created = int(time.time())

    def line(payload) -> str:
        return "data: " + json.dumps(payload, separators=(",", ":")) + "\n\n"

    def chunk(delta, finish_reason=None):
        return {"id": cid, "object": "chat.completion.chunk", "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]}

    def tc_entry(i, tc):
        fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
        return {"index": i,
                "id": (tc.get("id") if isinstance(tc, dict) else None) or f"call_{i}",
                "type": (tc.get("type") if isinstance(tc, dict) else None) or "function",
                "function": {"name": fn.get("name", ""), "arguments": ""}}

    if tool_calls:
        yield line(chunk({"role": "assistant",
                          "tool_calls": [tc_entry(i, tc) for i, tc in enumerate(tool_calls)]}))
        for i, tc in enumerate(tool_calls):
            fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
            args = fn.get("arguments", "") or ""
            for j in range(0, len(args), 60):
                yield line(chunk({"tool_calls": [{"index": i, "function": {
                    "arguments": args[j:j + 60]}}]}))
        yield line(chunk({}, finish or "tool_calls"))
    else:
        text = answer or ""
        for j in range(0, max(len(text), 1), 24):
            delta = {"content": text[j:j + 24]}
            if j == 0:
                delta = {"role": "assistant", **delta}
            yield line(chunk(delta))
        yield line(chunk({}, finish or "stop"))
    yield "data: [DONE]\n\n"


def _demo_block() -> None:
    """403 for write/admin endpoints on a public demo server."""
    if settings.demo_mode:
        raise HTTPException(403, "Disabled on the public demo server — self-host for full access.")


def _demo_check_ask(req: AskRequest) -> None:
    """Enforce demo allowlist + message cap. No-op unless DEMO_MODE=true."""
    if not settings.demo_mode:
        return
    allowed = [p.strip() for p in (settings.demo_models or "mock/*").split(",") if p.strip()]
    ok = any(req.llm == p or (p.endswith("*") and req.llm.startswith(p[:-1])) for p in allowed)
    if not ok:
        raise HTTPException(400, f"Demo server allows only: {', '.join(allowed)}.")
    if len(req.message or "") > max(1, settings.demo_max_chars):
        raise HTTPException(400, f"Demo messages are capped at {settings.demo_max_chars} characters.")


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    _demo_check_ask(req)
    t0 = time.time()
    store, embed = deps.get_store(), deps.get_embed()
    serve_th = req.serve_threshold or settings.serve_threshold
    situation = normalize_situation(req.message, req.context)
    expanded_from: str | None = None
    # Follow-up resolution: a bare "refund??" / "aur?" carries no meaning alone —
    # expand it with the user's previous message (persistent per-user context),
    # so day-2 shorthand resolves to the day-1 conversation. Only when the
    # current query is a single content token; a miss still falls to the LLM.
    if len(situation.split()) < 2:
        last = store.get_last_message(req.user_id)
        if last and normalize_situation(last, {}) != situation:
            expanded_from = last
            situation = normalize_situation(f"{last} {req.message}", req.context)
    # remember THIS message for the next follow-up (read happened above)
    store.set_last_message(req.user_id, req.message)
    # everything downstream (search vector already encoded, LLM prompt, saved
    # key) uses the resolved text: expanded follow-ups behave as if the user
    # had repeated their full question.
    ask_text = f"{expanded_from} {req.message}" if expanded_from else req.message
    qvec = embed.encode([situation])[0]
    # A mandated tool call is never servable from memory — skip the lookup
    # entirely so tool decisions always come from a live upstream call.
    skip_memory = _requires_tool_call(req.tool_choice)
    scope = "" if req.shared_memory else req.user_id
    cands = [] if skip_memory else store.search(qvec, user_id=scope, top_k=5)
    # prefer same-normalized-situation matches; else best candidate
    best = None
    sim = 0.0
    for rx, s in cands:
        if rx.situation == situation:
            best, sim = rx, max(sim, s)
            break
    if best is None and cands:
        best, sim = cands[0]
    # Cross-intent veto: never serve a memory about a DIFFERENT distinctive
    # intent (delivery Q + refund memory sharing "status" must miss, not serve).
    if best is not None:
        from reflex.core.normalizer import intent_veto

        if intent_veto(situation, best.situation):
            best, sim = None, 0.0
    # Hard expiry: a reflex older than its TTL is NEVER served — time-varying
    # answers ("processing", ETAs) go back to System 2 for a fresh verdict
    # instead of serving yesterday's truth. It re-learns via upsert below.
    if best is not None and _is_expired(best):
        best = None

    def _explain(situation_key: str | None, similarity: float) -> dict:
        if not req.explain:
            return {}
        out = {"matched_situation": situation_key, "similarity": round(similarity, 3),
               "threshold": serve_th}
        if expanded_from:
            out["expanded_from"] = expanded_from
        return out

    if best is not None:
        sc = conf.score(sim, best.hits, best.corrections, best.last_verified_at,
                        best.ttl_days, settings.w_sim, settings.w_hit,
                        settings.w_recency, settings.w_correction)
        action = conf.route(sc, serve_th, settings.uncertain_band)
        if action == "reflex":
            store.record_hit(best.id)
            ms = int((time.time() - t0) * 1000)
            rendered, _ = render_answer(best.decision.payload, req.context)
            deps.record_ask(ms, True, False, {
                "user_id": req.user_id, "message": req.message,
                "answer": rendered, "source": "reflex",
                "reflex_id": best.id, "confidence": round(sc, 3),
                "llm_model": None, "llm_cost_saved_inr": settings.cost_per_llm_call_inr,
            })
            return AskResponse(answer=rendered, source="reflex",
                               reflex_id=best.id, confidence=round(sc, 3),
                               latency_ms=ms, llm_cost_saved_inr=settings.cost_per_llm_call_inr,
                               structured=best.decision.structured,
                               **_explain(best.situation, sim))
        if action == "reflex+reverify":
            store.record_hit(best.id)
            # Re-verify OFF the request path: the stored answer returns
            # immediately (voice-grade latency) while verification updates the
            # record in the background. Daemon thread; sqlite is opened with
            # check_same_thread=False and the scheduler already does this.
            threading.Thread(target=_bg_reverify, args=(store, req.llm), daemon=True).start()
            ms = int((time.time() - t0) * 1000)
            rendered, _ = render_answer(best.decision.payload, req.context)
            deps.record_ask(ms, True, False, {
                "user_id": req.user_id, "message": req.message,
                "answer": rendered, "source": "reflex+reverify",
                "reflex_id": best.id, "confidence": round(sc, 3),
                "llm_model": None, "llm_cost_saved_inr": settings.cost_per_llm_call_inr,
            })
            return AskResponse(answer=rendered, source="reflex+reverify",
                               reflex_id=best.id, confidence=round(sc, 3),
                               latency_ms=ms, llm_cost_saved_inr=settings.cost_per_llm_call_inr,
                               structured=best.decision.structured,
                               **_explain(best.situation, sim))

    # MISS -> System 2
    try:
        provider = get_provider(req.llm)
        mem_ctx = ""
        try:
            mems = store.list_memories(subject=f"user:{req.user_id}")
            if mems:
                mem_ctx = "\nKnown facts: " + "; ".join(m.fact for m in mems[:5])
        except Exception:
            pass
        hist = ""
        if req.history:
            hist = "\nEarlier turns:\n" + "\n".join(
                f"{h.get('role', 'user')}: {h.get('content', '')}" for h in req.history[-6:]
            )
        system = req.system or "Answer concisely, in the same language the user wrote in."
        wants_tools = bool(req.tools) or req.tool_choice is not None or req.max_tokens is not None
        if wants_tools and not isinstance(provider, OpenAICompatProvider):
            raise HTTPException(400, "tools/max_tokens are only supported with OpenAI-compatible "
                                     "models (openai/*, openrouter/*, deepseek/*) — never silently dropped.")
        if isinstance(provider, OpenAICompatProvider):
            resp = provider.complete(f"{ask_text}{hist}{mem_ctx}", system=system,
                                     tools=req.tools, tool_choice=req.tool_choice,
                                     max_tokens=req.max_tokens)
        else:
            resp = provider.complete(f"{ask_text}{hist}{mem_ctx}", system=system)
        llm_text = resp.text
        model_name = resp.model
        upstream_tools = getattr(resp, "tool_calls", None)
    except HTTPException:
        raise
    except Exception as e:
        # Generic upstream message on purpose: raw provider errors can leak
        # key/config details. Full error stays in server logs.
        print(f"[memflex] System-2 provider failed for model={req.llm!r}: {e}")
        raise HTTPException(502, "LLM upstream failed. Check server model config/keys.")

    from reflex.core.distiller import is_refusal as _is_refusal
    from reflex.core.distiller import language_match as _lang_match

    if upstream_tools:
        # Tool decisions are live-only: served to the caller, never memorized.
        ms = int((time.time() - t0) * 1000)
        deps.record_ask(ms, False, True, {
            "user_id": req.user_id, "message": req.message,
            "answer": llm_text, "source": "llm",
            "reflex_id": None, "confidence": 0.8,
            "llm_model": model_name, "llm_cost_saved_inr": 0.0,
        })
        return AskResponse(answer=llm_text, source="llm", reflex_id=None,
                           confidence=0.8, latency_ms=ms, llm_cost_saved_inr=0.0,
                           tool_calls=upstream_tools,
                           finish_reason=getattr(resp, "finish_reason", None) or "tool_calls",
                           structured=None,
                           **_explain(None, 0.0))

    rx = distill(ask_text, req.context, llm_text, model_name, req.user_id,
                 req.output_schema, req.extract_structured, ttl_days=req.ttl_days)
    if _is_refusal(llm_text) or not _lang_match(ask_text, llm_text):
        # Serve once, NEVER memorize: refusals and wrong-script answers would
        # poison every repeat (served answer stays correct, memory stays clean).
        ms = int((time.time() - t0) * 1000)
        deps.record_ask(ms, False, True, {
            "user_id": req.user_id, "message": req.message,
            "answer": llm_text, "source": "llm",
            "reflex_id": None, "confidence": 0.8,
            "llm_model": model_name, "llm_cost_saved_inr": 0.0,
        })
        return AskResponse(answer=llm_text, source="llm", reflex_id=None,
                           confidence=0.8, latency_ms=ms, llm_cost_saved_inr=0.0,
                           structured=rx.decision.structured,
                           **_explain(None, 0.0))
    # Upsert, never duplicate: a miss re-learns the SAME situation (fresh
    # System-2 verdict replaces stale payload; hits history is preserved).
    dupe = store.find_by_situation(req.user_id, rx.situation)
    if dupe is not None:
        rx.id, rx.hits, rx.corrections = dupe.id, dupe.hits, dupe.corrections
    store.save_reflex(rx, qvec)
    # correction signal: if a different near-duplicate existed, mark it corrected
    if best is not None and sim >= 0.9 and best.decision.payload.strip() != llm_text.strip():
        try:
            store.record_correction(best.id)
        except Exception:
            pass
    ms = int((time.time() - t0) * 1000)
    deps.record_ask(ms, False, True, {
        "user_id": req.user_id, "message": req.message,
        "answer": llm_text, "source": "llm",
        "reflex_id": rx.id, "confidence": 0.8,
        "llm_model": model_name, "llm_cost_saved_inr": 0.0,
    })
    return AskResponse(answer=llm_text, source="llm", reflex_id=rx.id,
                       confidence=0.8, latency_ms=ms, llm_cost_saved_inr=0.0,
                       structured=rx.decision.structured,
                       **_explain(best.situation if best is not None else None, sim))


@router.post("/remember", response_model=Memory)
def remember(req: RememberRequest):
    _demo_block()
    store = deps.get_store()
    m = Memory(subject=f"user:{req.user_id}", fact=req.fact, confidence=req.confidence)
    return store.save_memory(m)


@router.get("/reflexes")
def list_reflexes(user_id: str = ""):
    return [r.model_dump(mode="json") for r in deps.get_store().list_reflexes(user_id)]


@router.post("/reflexes", response_model=Reflex)
def save_reflex(req: SaveReflexRequest):
    """Explicit memorize/upsert — tool-using agents save their COMPOSED final
    answer here so repeats serve it without re-running tools or the LLM."""
    _demo_block()
    store, embed = deps.get_store(), deps.get_embed()
    if not req.answer.strip():
        raise HTTPException(400, "answer must be non-empty")
    situation = req.situation.strip() or normalize_situation(req.message, req.context)
    if not situation:
        raise HTTPException(400, "message or situation required")
    from reflex.core.distiller import language_match as _lm

    if not req.allow_mismatch and not _lm(req.message or situation, req.answer):
        raise HTTPException(422, "language mismatch: answer script differs from query "
                                 "(pass allow_mismatch=true to save anyway)")
    from reflex.core.distiller import infer_ttl_days

    existing = store.find_by_situation(req.user_id, situation)
    rx = Reflex(
        id=existing.id if existing else new_id("rfx"),
        user_id=req.user_id,
        situation=situation,
        decision=Decision(action=req.action, payload=req.answer.strip(), structured=req.structured),
        confidence=max(0.05, min(0.99, req.confidence)),
        hits=existing.hits if existing else 0,
        corrections=0,
        source=req.source,
        ttl_days=req.ttl_days or infer_ttl_days(req.message or situation, req.answer),
    )
    store.save_reflex(rx, embed.encode([situation])[0])
    return rx


@router.post("/reflexes/{rid}/feedback")
def feedback(rid: str, req: FeedbackRequest):
    store = deps.get_store()
    rx = store.get_reflex(rid)
    if not rx:
        raise HTTPException(404, "reflex not found")
    if req.ok:
        store.record_hit(rid)
        store.touch_verified(rid, min(0.99, rx.confidence + 0.03))
    else:
        store.record_correction(rid)
    return {"ok": True, "id": rid}


@router.patch("/reflexes/{rid}", response_model=Reflex)
def patch_reflex(rid: str, req: PatchReflexRequest):
    """User controls: change a memory's TTL and/or confidence directly."""
    _demo_block()
    store = deps.get_store()
    rx = store.get_reflex(rid)
    if not rx:
        raise HTTPException(404, "reflex not found")
    updates: dict = {}
    if req.ttl_days is not None:
        updates["ttl_days"] = max(1, min(365, int(req.ttl_days)))
    if req.confidence is not None:
        updates["confidence"] = max(0.05, min(0.99, float(req.confidence)))
    if not updates:
        raise HTTPException(400, "nothing to update (ttl_days and/or confidence)")
    store.update_reflex(rid, **updates)
    return store.get_reflex(rid)


@router.delete("/reflexes/{rid}")
def delete_reflex(rid: str):
    _demo_block()
    if not deps.get_store().delete_reflex(rid):
        raise HTTPException(404, "reflex not found")
    return {"deleted": rid}


@router.post("/verify/run", response_model=VerifyResult)
def verify_run(limit: int = 20):
    _demo_block()
    store = deps.get_store()
    try:
        provider = get_provider(settings.default_llm_model)
    except Exception:
        from reflex.llm.base import MockProvider
        provider = MockProvider()
    return run_verification(store, provider, limit=limit).model_dump()


@router.get("/metrics")
def metrics():
    from reflex.evals.calibration import calibration_buckets
    c = deps.counters
    asks = max(1, c["asks"])
    store = deps.get_store()
    all_rx = store.list_reflexes()
    return {
        "asks": c["asks"],
        "hit_rate": round(c["hits"] / asks, 3),
        "avg_latency_ms": round(c["latency_ms_total"] / asks, 1),
        "llm_calls": c["llm_calls"],
        "cost_saved_30d_inr": round(c["hits"] * settings.cost_per_llm_call_inr, 2),
        "reflex_count": len(all_rx),
        "calibration": calibration_buckets(all_rx),
    }


@router.get("/memories")
def memories(subject: str = ""):
    return [m.model_dump(mode="json") for m in deps.get_store().list_memories(subject)]


@router.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    """OpenAI-compatible chat endpoint.

    Point any OpenAI-based agent at Memflex and get reflexes for free::

        from openai import OpenAI
        client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")
        client.chat.completions.create(
            model="ollama-cloud/gpt-oss:20b",   # reflex model-string; upstream on miss
            messages=[{"role": "user", "content": "When will my refund arrive?"}],
            user="u123",
        )

    The last user message is the situation key (cacheable); earlier turns +
    system messages only enrich the System-2 prompt on a miss, so multi-turn
    history never kills the hit rate. Extra fields (reflex_source,
    reflex_confidence, reflex_id) ride along; OpenAI clients ignore extras.

    stream=true returns OpenAI-style SSE (text/event-stream ending in
    [DONE]) — this is what voice pipelines (LiveKit, ElevenLabs-style
    gateways) require. tools/tool_choice are forwarded to OpenAI-compatible
    backends; other backends answer 400 explicitly instead of dropping them.
    Memory is scoped per caller (user field), so shared servers never bleed
    one caller's memories into another's.
    """
    from reflex.core.models import AskRequest as _Ask

    last_user = ""
    for msg in reversed(req.messages):
        if msg.role == "user":
            last_user = msg.content
            break
    if not last_user:
        raise HTTPException(400, "messages must contain at least one user message")
    system = "\n".join(m.content for m in req.messages if m.role == "system") or None
    history = [{"role": m.role, "content": m.content} for m in req.messages[:-1]]
    context_order = re.search(r"\b[A-Z]{2,5}-\d{3,}\b", last_user)
    res = ask(_Ask(
        user_id=req.user or "openai",
        message=last_user,
        context={"order_id": context_order.group(0)} if context_order else {},
        llm=req.model,
        system=system,
        history=history,
        tools=req.tools,
        tool_choice=req.tool_choice,
        max_tokens=req.max_tokens,
        shared_memory=False,
    ))
    import time as _time

    if req.stream:
        return StreamingResponse(
            _chat_sse_chunks(res.answer, res.reflex_id, req.model,
                             tool_calls=res.tool_calls, finish=res.finish_reason),
            media_type="text/event-stream",
            headers={
                "X-Reflex-Source": res.source,
                "X-Reflex-Confidence": str(res.confidence),
                "X-Reflex-Id": res.reflex_id or "",
                "X-Reflex-Latency-Ms": str(res.latency_ms),
                "Cache-Control": "no-cache",
            },
        )
    message = {"role": "assistant", "content": res.answer or None}
    if res.tool_calls:
        message["tool_calls"] = res.tool_calls
    return {
        "id": f"chatcmpl-{res.reflex_id or 'llm'}",
        "object": "chat.completion",
        "created": int(_time.time()),
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": message,
            "finish_reason": res.finish_reason or "stop",
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "reflex_source": res.source,
        "reflex_confidence": res.confidence,
        "reflex_id": res.reflex_id,
        "latency_ms": res.latency_ms,
    }


@router.post("/v1/messages")
def anthropic_messages(req: AnthropicMessagesRequest):
    """Anthropic-compatible messages endpoint (Claude SDK via base_url).

    from anthropic import Anthropic
    client = Anthropic(base_url="http://localhost:8000/v1", api_key="not-needed")
    client.messages.create(model="claude/claude-sonnet-4-5", max_tokens=256,
        messages=[{"role": "user", "content": "When will my refund arrive?"}])

    Same reflex semantics as OpenAI-compat: last user text is the situation key.
    Extra fields (reflex_source, ...) ride along; Claude clients ignore extras.

    Caller identity comes from metadata.user_id (Anthropic metadata shape);
    memory is scoped to it so Claude-SDK callers never share one memory.
    Tools are accepted but not forwarded on this endpoint yet — sending them
    is an explicit 400, never a silent drop (use /v1/chat/completions for
    function calling).
    """
    from reflex.core.models import AskRequest as _Ask

    if req.stream:
        raise HTTPException(400, "stream=true not supported yet — use stream=false")
    if req.tools is not None or req.tool_choice is not None:
        raise HTTPException(400, "tools are not supported on POST /v1/messages yet — "
                                 "use POST /v1/chat/completions for function calling.")
    last_user = ""
    for msg in reversed(req.messages):
        if msg.role == "user":
            last_user = anthropic_text(msg.content)
            break
    if not last_user.strip():
        raise HTTPException(400, "messages must contain at least one user message")
    system = anthropic_text(req.system) or None
    history = [
        {"role": m.role, "content": anthropic_text(m.content)} for m in req.messages[:-1]
    ]
    context_order = re.search(r"\b[A-Z]{2,5}-\d{3,}\b", last_user)
    meta = req.metadata or {}
    user_id = str(meta.get("user_id") or "anthropic")
    res = ask(_Ask(
        user_id=user_id,
        message=last_user,
        context={"order_id": context_order.group(0)} if context_order else {},
        llm=req.model,
        system=system,
        history=history,
        shared_memory=False,
    ))
    return {
        "id": f"msg_{res.reflex_id or 'llm'}",
        "type": "message",
        "role": "assistant",
        "model": req.model,
        "content": [{"type": "text", "text": res.answer}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "reflex_source": res.source,
        "reflex_confidence": res.confidence,
        "reflex_id": res.reflex_id,
        "latency_ms": res.latency_ms,
    }


@router.get("/activity")
def activity(limit: int = 100, source: str = ""):
    """Recent asks newest-first: every LLM call and every reflex answer.

    Filter: source=all|llm|reflex  ("reflex" includes reflex+reverify).
    Powers the dashboard's observability views.
    """
    items = deps.recent_activity(limit)
    s = (source or "all").lower()
    if s == "llm":
        items = [a for a in items if a.get("source") == "llm"]
    elif s in ("reflex", "memory", "hits"):
        items = [a for a in items if a.get("source") != "llm"]
    llm_rows = [a for a in items if a.get("source") == "llm"]
    reflex_rows = [a for a in items if a.get("source") != "llm"]
    llm_lat = [a["latency_ms"] for a in llm_rows] or [0]
    reflex_lat = [a["latency_ms"] for a in reflex_rows] or [0]
    return {
        "count": len(items),
        "llm_calls": len(llm_rows),
        "reflex_answers": len(reflex_rows),
        "avg_latency_ms_llm": round(sum(llm_lat) / len(llm_lat), 1),
        "avg_latency_ms_reflex": round(sum(reflex_lat) / len(reflex_lat), 1),
        "items": items,
    }
