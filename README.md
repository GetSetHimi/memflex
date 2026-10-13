# Memflex — reflexes & verified memory for AI agents

[![License](https://img.shields.io/badge/license-FSL--1.1-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-green)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-62%20passing-brightgreen)](tests/)
[![Self-host](https://img.shields.io/badge/self--host-1%20command-orange)](docker-compose.prod.yml)

> Agents call the LLM only for what they've never seen. Repeats answered in ~50ms at ₹0 from memory — in any language.

**📖 Full guide: [`docs/HOW_TO_USE.md`](docs/HOW_TO_USE.md)** — quickstart, SDK, LangGraph, Mem0 shim, multilingual, the no-LLM-on-hit guarantee, and Memflex vs Jev/Mem0/GPTCache.
**🚀 Hosting: [`docs/HOSTING.md`](docs/HOSTING.md)** — laptop → Docker → $6 VPS → Fly/Render → K8s.

```bash
pip install memflex        # after first PyPI publish; until then: pip install -e .
cp .env.example .env
EMBEDDING_BACKEND=hash REFLEX_DB_PATH=./data/reflex.db python3 -m reflex.api.app  # :8000
# then open http://localhost:8000/docs (Swagger UI) — localhost:8000 alone shows "Not Found", that's normal
# or
docker compose up  # api :8000 + dashboard :8501
```

Plug-and-play from any agent (one line, any framework speaking OpenAI/Claude protocol):

```python
from reflex.plug import openai_client  # or anthropic_client
chat = openai_client()  # base_url -> your Memflex server, key from REFLEX_URL/REFLEX_KEY env
chat.chat.completions.create(model="claude/claude-sonnet-4-5", messages=[{"role": "user", "content": "Hi"}])
```

```python
from reflex import Client
rx = Client("http://localhost:8000")
res = rx.ask(user_id="u123", message="When will my refund arrive?", llm="mock/mock-echo")
print(res.answer, res.source, res.confidence)
rx.remember(user_id="u123", fact="prefers COD", confidence=0.9)
```

* Stores: SQLite-vec lite (`data/reflex.db`, zero deps, default) or Postgres + pgvector (`REFLEX_STORE=postgres`, production scale-out).
* Embeddings: `BAAI/bge-m3` local; `EMBEDDING_BACKEND=hash` for keyless/CI fallback; Ollama Tangential.
* 5-vendor gateway: `mock` → `ollama/*`+`ollama-cloud/*` → `openai/*` → `claude/*` → `gemini/*` → `openrouter/*` / `deepseek/*` (missing key = Mock fallback).
* Speaks OpenAI (`POST /v1/chat/completions`) + Claude (`POST /v1/messages`) protocols — any framework via `base_url`.
* Memory-hit = zero LLM calls (regression-tested); 19 languages verified with zero language privilege (`pytest tests/test_multilingual.py tests/test_german.py`). Mock answers in-kind (DE→DE, JA→JA, HI→HI…); no preferred language anywhere.
* No-LLM answers come in 3 kinds: **verbatim** (exact stored answer), **template** (`{variables}` rendered per-request from `context`), **structured** (typed JSON via `output_schema`, on hits too).
* Endpoints: `POST /ask /remember /reflexes/{id}/feedback /verify/run, GET /reflexes /metrics, DELETE /reflexes/{id}`.
* `GET /metrics` → hit_rate, ₹ saved, latency, calibration curve. `GET /activity` → every LLM call vs every reflex answer.
* Console `:3000` (Next.js, SEO-friendly) — live audit of LLM calls vs memory answers ([guide](docs/HOW_TO_USE.md#console-dashboard--see-every-llm-call-and-every-reflex-answer)). Streamlit `:8501` kept as fallback.
