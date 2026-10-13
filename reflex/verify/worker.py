# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""TTL + contradiction verification worker (§4.4)."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from reflex.core.models import VerifyResult


def parse_verdict(text: str) -> str:
    """First CONFIRM/CONFLICT token wins.

    Real LLMs follow the "reply with exactly one word" instruction, but echo
    doubles (Mock) or chatty models can mention both words — substring checks
    then false-flag. First-token parsing is robust either way; anything else
    defaults to CONFIRM (do no harm).
    """
    m = re.search(r"\b(CONFIRM|CONFLICT)\b", (text or "").upper())
    if m and m.group(1) == "CONFLICT":
        return "CONFLICT"
    return "CONFIRM"


def _stale(r, ttl_days: int) -> bool:
    now = datetime.now(timezone.utc)
    lv = r.last_verified_at
    if lv.tzinfo is None:
        lv = lv.replace(tzinfo=timezone.utc)
    return (now - lv).total_seconds() / 86400.0 >= min(ttl_days, r.ttl_days)


def run_verification(store, llm_provider, limit: int = 20) -> VerifyResult:
    all_rx = store.list_reflexes()
    # oldest-verified first
    all_rx.sort(key=lambda r: r.last_verified_at)
    checked = confirmed = flagged = 0
    details: list[dict] = []
    for rx in all_rx[:limit]:
        if not _stale(rx, 30):
            # still re-check a small sample for contradictions even if fresh
            pass
        checked += 1
        try:
            probe = llm_provider.complete(
                f"Situation: {rx.situation}\nStored answer: {rx.decision.payload}\n"
                "Is this still true? Reply with exactly one word: CONFIRM or CONFLICT, then a short reason.",
                system="You are a memory verifier.",
            )
            verdict = parse_verdict(probe.text)
        except Exception as e:
            details.append({"id": rx.id, "status": "error", "error": str(e)})
            continue
        if verdict == "CONFLICT":
            flagged += 1
            try:
                store.record_correction(rx.id)
            except Exception:
                pass
            details.append({"id": rx.id, "status": "flagged", "llm": probe.text[:200]})
        else:
            confirmed += 1
            try:
                store.touch_verified(rx.id)
            except Exception:
                pass
            details.append({"id": rx.id, "status": "confirmed"})
    return VerifyResult(checked=checked, confirmed=confirmed, flagged=flagged, details=details)
