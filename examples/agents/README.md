# Agent demos — real LLM, real tools, real memory loop

Runs every usecase area (support, triage, extraction, voice-style follow-ups,
multilingual) against a live Memflex server with a **real LLM + real tools**.
Watch run 1 think (planner → tools → composed answer memorized) and run 2+
serve from memory with zero tools and zero LLM calls.

## Run it

```bash
# 1. API running with an upstream key, e.g. in .env:
#    GEMINI_API_KEY=...   (or OPENROUTER_API_KEY=...)
python3 -m reflex.api.app

# 2. In another terminal:
python3 examples/agents/run_all.py --llm gemini/gemma-4-31b-it
python3 examples/agents/run_all.py --llm mock/mock-echo   # keyless dry run
```

## Files

| File | What |
|---|---|
| `run_all.py` | Runner — iterates scenarios, retries flaky calls, writes `REPORT.md` |
| `runner.py` | Agent loop — reflex first, plan→act→synthesize on miss, memorize composed answer |
| `scenarios.py` | Per-area scripts (Hindi refund + Hinglish + `refund??`, cancel, delivery, triage, German…) |
| `tools.py` | Deterministic demo tools (`refund_quote`, `cancel_order`, …) — no network |
| `REPORT.md` | Last run's per-area table (regenerated every run) |

## Notes

- Real-LLM runs can hit upstream rate limits — the runner retries 3× and
  records `error` rows honestly instead of faking results.
- Model refusals ("I don't have access…") are served once and **never**
  memorized (see `tests/test_refusal.py`).
