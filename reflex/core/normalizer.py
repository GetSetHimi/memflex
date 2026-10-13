# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Language-neutral situation normalizer with per-language plugins.

Core (applies to EVERY language): NFKC, lowercase, order-ID masking,
phone masking, punctuation strip, whitespace collapse. Script characters are
never stripped — Tamil, Arabic, German, … all keep stable keys.

Plugins (opt-in convergence where it genuinely helps):
  hindi  — Devanagari <-> Roman/Hinglish transliteration convergence
           (Romanized Hindi is ubiquitous in India).
  german — umlaut/ß ASCII folding (Rückerstattung ≡ Rueckerstattung)
           + core support-intent synonyms.

Add a language: add a dict to LANGUAGE_MAPS + cases to
tests/test_multilingual.py. Deeper paraphrase matching comes from the
multilingual embedding backend (bge-m3), not from here.
"""
import re
import unicodedata

_ORDER = re.compile(r"\border[_\s-]?#?\s*([A-Za-z0-9-]{3,})\b", re.I)
_PHONE_IN = re.compile(r"\b(\+?91[\s-]?)?[6-9]\d{9}\b")
_PHONE_GENERIC = re.compile(r"\b\+\d[\d\s\-]{7,}\d\b")  # +49..., +1..., applied after order mask

# ---- plugin: hindi (Devanagari <-> Roman) ----
HINDI_MAP = {
    "refund": "refund", "रिफंड": "refund", "रिफन्ड": "refund",
    "wapas": "refund", "वापस": "refund",
    "paisa": "refund", "पैसा": "refund", "पैसे": "refund",
    "kab": "kab", "कब": "kab",
    "ayega": "ayega", "aayega": "ayega", "aega": "ayega",
    "आएगा": "ayega", "आयेगा": "ayega", "आएगी": "ayega",
    "mera": "mera", "meraa": "mera", "मेरा": "mera", "मेरे": "mera",
    "kya": "kya", "क्या": "kya",
    "hai": "hai", "है": "hai",
    "kaise": "kaise", "कैसे": "kaise",
    "kahan": "kahan", "कहाँ": "kahan", "कहां": "kahan",
    "order": "order", "ऑर्डर": "order",
    "delivery": "delivery", "डिलीवरी": "delivery",
    "status": "status", "स्टेटस": "status",
    "cancel": "cancel", "कैंसिल": "cancel", "रद्द": "cancel",
    "में": "mein", "मैं": "mein", "मे": "mein", "mein": "mein",
}

# ---- plugin: german ----
_GERMAN_FOLD = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}  # char-wise, pre-token
GERMAN_MAP = {
    # support intents -> canonical keys (shared across languages on purpose)
    "rueckerstattung": "refund", "rueckzahlung": "refund", "erstatten": "refund",
    "stornierung": "cancel", "stornieren": "cancel", "kuendigen": "cancel",
    "abbestellen": "cancel",
    "lieferung": "delivery", "versand": "delivery", "paket": "delivery",
    "zustellung": "delivery",
    "bestellung": "order",
    "mein": "my", "meine": "my", "meiner": "my", "meinem": "my",
    "wann": "when", "wo": "where", "wie": "how", "was": "what",
    "ist": "is", "sind": "is",
}

# ---- plugin: english (support-domain synonyms; English is the reference
# language so this map only converges true synonyms, never grammar) ----
ENGLISH_MAP = {
    "package": "delivery", "parcel": "delivery",
    "shipment": "delivery", "shipping": "delivery",
}

LANGUAGE_MAPS = {"hindi": HINDI_MAP, "german": GERMAN_MAP, "english": ENGLISH_MAP}
# Back-compat alias (older tests/docs import it).
HINGLISH_MAP = HINDI_MAP

_TOKEN_MAP = {k: v for plugin in LANGUAGE_MAPS.values() for k, v in plugin.items()}

# Distinctive support intents (canonical keys, post-plugin-mapping, so Hindi
# "रिफंड" and German "Rückerstattung" both count as {refund}).
# Used for the cross-intent veto: a query about delivery must never be served
# a refund memory just because both share generic words like "status".
DISTINCTIVE_INTENTS = frozenset({"refund", "cancel", "delivery", "order"})


def situation_intents(normalized_situation: str) -> frozenset:
    return DISTINCTIVE_INTENTS & set(normalized_situation.split())


def intent_veto(query_situation: str, candidate_situation: str) -> bool:
    """True when both sides name *different* distinctive intents.

    "delivery status" vs "refund status" share "status" (generic) but mean
    opposite things — veto forces a miss (fresh LLM answer) instead of
    serving the wrong memory. Veto fires only when BOTH sides carry a
    distinctive intent and share none: vague queries never veto.
    """
    q, c = situation_intents(query_situation), situation_intents(candidate_situation)
    return bool(q and c and q.isdisjoint(c))

# Function words carry no situation meaning ("is", "my", "hai", "der").
# Removing them stops unrelated short queries colliding on stopwords
# (e.g. German refund vs English order sharing "is/my"). Question words
# (when/where/kab…) are KEPT — they distinguish situations.
STOPWORDS = frozenset("""
is are my your the a an me i please to for of on in and do does will can am was were
be have has it its this that these those with by at from
hai mein ka ki ke ko se ne par aur bhi
ist sind der die das den dem ein eine einer eines und oder zu mit von im am bitte
my
est sont mon ma mes le la les un une des du et ou de en avec pour
es son mi mis el la los las un una una y o de del en con por favor
""".split())

_STRIP = ".,!?;:\"'()[]{}«»“”‘’…—–-¿¡।॥"


def normalize_situation(message: str, context: dict | None = None) -> str:
    # Turkish dotted-İ: Python's lower() turns İ into i̇ (i + combining dot),
    # which never matches plain "i". Fold explicitly so İadem ≡ iadem.
    text = unicodedata.normalize("NFKC", message.strip()).replace("İ", "i").lower()
    text = _ORDER.sub("order <ORD>", text)
    text = _PHONE_IN.sub("<PHONE>", text)
    text = _PHONE_GENERIC.sub("<PHONE>", text)
    for src, dst in _GERMAN_FOLD.items():
        text = text.replace(src, dst)
    tokens = []
    for raw in text.split():
        tok = raw.strip(_STRIP)
        tok = _TOKEN_MAP.get(tok, tok)
        if tok and tok not in STOPWORDS:
            tokens.append(tok)
    norm = re.sub(r"\s+", " ", " ".join(tokens)).strip()
    if context and context.get("order_id"):
        norm += " [has_order]"
    return norm or text
