# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Safe template rendering for stored reflex answers.

A reflex payload may contain {placeholders} filled per-request from the
caller's `context` — e.g. saved "Namaste {name}, refund {eta} me aayega"
asked with {"name": "Ravi", "eta": "3 din"} renders personalized text with
ZERO LLM calls. Rules (safety first):
  - only {keys} present in context are replaced; unknown stay literal
  - values are str()-ified, never evaluated — no code execution, ever
  - unbalanced braces / weird input pass through untouched (no crashes)
"""
import string


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def render(template: str, context: dict | None) -> tuple[str, bool]:
    """Returns (rendered_text, was_anything_rendered)."""
    if not template or "{" not in template or not context:
        return template, False
    try:
        out = string.Formatter().vformat(template, (), _SafeDict(context))
        return out, out != template
    except Exception:
        return template, False
