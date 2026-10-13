# Contributing to Memflex

Thanks for your interest — this is early Fair Source and every PR matters.

## CLA (required — read first!)

This project is copyrighted by an individual (Himanshu Sharma) and ships
server code under FSL-1.1 with a commercial dual-license path. **No PR is
merged until the Contributor License Agreement is signed** (CLAassistant on
the repo — one click, 30 seconds). Signing assigns the project the rights
needed to keep the FSL→Apache conversion promise and to offer commercial
licenses. Client files (`reflex/client.py`, `reflex/plug.py`) stay
Apache-2.0 forever and are CLA-light: typo/docs fixes there need no CLA.

## Setup (keyless, 2 min)

```bash
cp .env.example .env
pip install -e ".[dev]"
EMBEDDING_BACKEND=hash python -m pytest tests -q   # must stay green
```

`EMBEDDING_BACKEND=hash` keeps tests offline/deterministic (no model downloads).
Each test module gets a fresh temp DB via `tests/conftest.py` — never depend on shared state.

## Ground rules

1. **Memory-hit = zero LLM calls.** Any change to `/ask` routing must keep `tests/test_no_llm_on_hit.py` green.
2. **Multilingual is a feature, not a test.** Don't strip non-Latin script characters in the normalizer; add cases to `tests/test_multilingual.py` when you touch it.
3. **No secrets in the repo.** Keys only via env (`.env` is gitignored). The Mock provider must stay deterministic.
4. **New endpoint → new test + docs row.** Update `docs/HOW_TO_USE.md` API table and, if user-facing, the README bullets.

## PR checklist

- [ ] `pytest` green (hash backend, twice — catches order/state leaks)
- [ ] No API keys, tokens, or personal data in diffs
- [ ] Docs updated (`docs/HOW_TO_USE.md` ± README)

## Big-ticket roadmap (pick one, open an issue first)

- Async re-verification (currently sync on `reflex+reverify` hits)
- Per-user vs global memory scoping option
- Postgres/Qdrant scale-out behind `stores/base.py`
- Published multilingual benchmark numbers (LoCoMo-style split)
