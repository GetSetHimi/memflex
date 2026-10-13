# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Distiller — LLM output -> Memflex (System-2 -> System-1)."""
from __future__ import annotations
import re
from reflex.core.models import Decision, Reflex
from reflex.core.normalizer import normalize_situation


def extract_structured(text: str, schema: dict[str, str] | None) -> dict | None:
    if not schema:
        return None
    out: dict = {}
    if "refund_status" in schema:
        low = text.lower()
        if ("प्रोसेस" in text or "process" in low or "bearbeitet" in low
                or "en cours" in low or "en proceso" in low or "processamento" in low
                or "обрабатыва" in low or "処理中" in text or "处理中" in text):
            out["refund_status"] = "processing"
        elif ("cancel" in low or "कैंसिल" in text or "stornier" in low
                or "annul" in low or "cancelar" in low or "cancelado" in low
                or "отмен" in low or "キャンセル" in text or "已取消" in text):
            out["refund_status"] = "cancelled"
        else:
            out["refund_status"] = "unknown"
    if "eta_days" in schema:
        m = re.search(
            r"(\d+)\s*-\s*(\d+)\s*(?:दिन|day|tagen|tage|jours|d[ií]as|dias|дн[еяй]+|日)",
            text, re.I)
        if m:
            nums = [int(x) for x in m.groups() if x]
            out["eta_days"] = nums[:2] if len(nums) >= 2 else [nums[0], nums[0]]
        else:
            out["eta_days"] = [3, 5]
    return out or None


# Time-varying content must NOT live 30 days: a "processing" status served
# tomorrow is a wrong answer. Volatile signals in either the question or the
# answer earn a 1-day TTL; stable knowledge keeps 30 days. Callers can always
# override explicitly (AskRequest.ttl_days / SaveReflexRequest.ttl_days).
VOLATILE_HINTS = frozenset("""
processing process bearbeitet cours proceso status status statuts zustand
arriv deliver deliver liefer versand paket shipping ship eta arrive reach
today tomorrow heute morgen aj kal will shall soon shortly pending
days din tagen tage jours dias hours hour minute
""".split())

VOLATILE_TTL_DAYS = 1
STABLE_TTL_DAYS = 30


def _scripts(text: str) -> set:
    """Non-Latin scripts present in text (Latin/COMMON ignored — see below)."""
    import unicodedata

    out = set()
    for ch in (text or ""):
        if not ch.isalpha():
            continue
        try:
            first = unicodedata.name(ch).split()[0]
        except ValueError:
            continue
        if first not in ("LATIN",):
            out.add(first)
    return out


def language_match(query: str, answer: str) -> bool:
    """False only when the answer is clearly in a DIFFERENT script family.

    Hindi query → Tamil answer is a memorization bug: serve once, never save.
    But a Latin-script answer (English fallback, or Mock lacking that language)
    always passes — blocking it would break Telugu-style queries whose correct
    answer happens to be English. Latin↔Latin pairs (French→German) can't be
    told apart cheaply either, so they pass here and rely on feedback and
    verification instead. Documented limitation.
    """
    q, a = _scripts(query), _scripts(answer)
    if not q or not a:
        return True
    return bool(q & a)

# Model refusals ("I don't have access…") must NEVER become memories —
# a memorized refusal poisons every repeat with a useless answer.
# Checked case-insensitively across the languages we serve.
REFUSAL_MARKERS = frozenset({
    "i don't have access", "i do not have access", "i can't help",
    "i cannot help", "as an ai,", "as an ai ", "unable to help",
    "cannot access your", "don't have access to your",
    "क्षमा करें, मैं", "मेरे पास आपके",
    "kein zugriff", "keinen zugriff",
    "je n'ai pas accès", "no tengo acceso", "não tenho acesso",
    "u can't help", "access to your personal",
})


def is_refusal(answer: str) -> bool:
    low = (answer or "").lower()
    return any(m in low for m in REFUSAL_MARKERS)


def infer_ttl_days(message: str, answer: str) -> int:
    blob = f"{message} {answer}".lower()
    if any(h in blob for h in VOLATILE_HINTS):
        return VOLATILE_TTL_DAYS
    return STABLE_TTL_DAYS


def distill(message: str, context: dict, llm_text: str, source: str,
            user_id: str = "", output_schema: dict | None = None,
            extract_structured_flag: bool = False,
            ttl_days: int | None = None) -> Reflex:
    situation = normalize_situation(message, context)
    structured = extract_structured(llm_text, output_schema) if extract_structured_flag else None
    return Reflex(
        user_id=user_id, situation=situation,
        decision=Decision(action="answer_template", payload=llm_text.strip(), structured=structured),
        confidence=0.8, source=f"llm:{source}",
        ttl_days=ttl_days or infer_ttl_days(message, llm_text),
    )
