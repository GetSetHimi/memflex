# How to Use Memflex — Complete Guide

> **Memflex gives AI agents memory + reflexes: repeats are answered in ~50ms at ₹0, in any language. The LLM is called only for what the agent has never seen.**

- New here? Start with [1. Quickstart](#1-quickstart-5-minutes) (5 minutes, no API key needed).
- Building an agent? Read [Why agent builders need this](#why-agent-builders-need-this), then [4. Python SDK](#4-python-sdk), [5. LangGraph](#5-langgraph--langchain), [6. Mem0 drop-in](#6-mem0-shim) and [Console dashboard](#console-dashboard--see-every-llm-call-and-every-reflex-answer).
- Evaluating for production? See [8. The no-LLM-on-hit guarantee](#8-the-no-llm-on-hit-guarantee), [9. Multilingual](#9-multilingual--every-language), [12. Memflex vs Jev vs others](#12-how-reflex-differs-jev-mem0-gptcache).

---

## Why agent builders need this

If you ship an AI agent (support bot, voice agent, triage, RAG assistant), three problems eat you alive — Memflex solves all three with one drop-in layer:

1. **Cost compounds against you.** 60–80% of production agent traffic is repeats (same FAQs, same routing, same extractions) — yet every request burns a full LLM call. Memflex answers repeats from memory at **₹0**, so your cost-per-user *falls* the longer you run. `GET /metrics → cost_saved_30d_inr` shows the number going up.
2. **Latency kills UX.** 2–10s per LLM response is unusable for voice/live-chat. Memflex hits return in **~0–50ms** — two orders of magnitude faster — which is what makes realtime agents feel realtime.
3. **Memory can't be trusted.** Mem0/Zep-style layers store facts but never verify them: one stale fact poisons every future answer silently. Every Memflex memory carries **confidence + provenance + TTL**, gets **re-verified** against the LLM on expiry, and **downgrades after a single 👎**. The dashboard's calibration curve tells you exactly which confidence band is safe to fully automate.

Integration is one node / one call — your agent keeps its LLM for novel thinking (System 2) and Memflex handles everything it has seen before (System 1). Multilingual from day one, self-hosted so customer data never leaves your VPC.

---

## Console dashboard — see every LLM call and every reflex answer

```bash
npm --prefix console run build          # one-time
npx --prefix console serve out -l 3000  # → http://localhost:3000 (static, SEO-friendly)
# dev: npm --prefix console run dev
# legacy Streamlit fallback still works:
python3 -m streamlit run dashboard/app.py   # → http://localhost:8501
```

The console reads the new **`GET /activity`** endpoint (last 500 asks, newest first — every request logged with message, answer, source, confidence, latency, model and ₹ saved) plus `/metrics` and `/reflexes`:

| Tab | What you see | Use it to… |
|---|---|---|
| 📊 **Overview** | Hit-rate, asks, LLM calls vs reflex answers, ₹ saved, LLM-vs-reflex latency, source split + latency-over-time | Prove ROI to yourself/boss: the two latency lines diverge from day one |
| 🔴 **Live activity** | Every single request, expandable (full Q + A + model + confidence + time), filterable: All / LLM-only / Memflex-only | Audit *"is the LLM really not called on repeats?"* — reflex rows show `llm_model: null`, ₹ saved, ~0ms |
| 💾 **Memflex memory** | Every situation→decision the agent remembers, searchable, with 👍/👎/🗑 per row + one-click verification run | Fix wrong memories by hand, erase user data (GDPR), watch confidence move |
| 🎯 **Calibration** | Accuracy-per-confidence-band chart | Decide the automation threshold: auto-approve 0.9+, escalate the rest |

Tip: enable **auto-refresh**, open `/docs`, fire 10 asks — watch LLM rows turn into reflex rows in real time.

---

## 1. Quickstart (5 minutes)

**Prerequisites:** Python 3.10+ (macOS ships `python3`/`pip3`, not `python`/`pip`).

```bash
git clone <your-repo> && cd reflex   # this folder
cp .env.example .env
pip3 install -e .
EMBEDDING_BACKEND=hash REFLEX_DB_PATH=./data/reflex.db python3 -m reflex.api.app
# → running on http://localhost:8000
```

Open **`http://localhost:8000/docs`** (Swagger UI — no terminal needed):
1. Expand `POST /ask` → **Try it out**, paste:
   ```json
   {"user_id": "u123", "message": "When will my refund arrive?", "llm": "mock/mock-echo"}
   ```
2. **Execute** → `"source": "llm"` (first time: System 2 thinks, then saves a reflex).
3. **Execute again** → `"source": "reflex"`, `"confidence": 0.9`, `"latency_ms": 0`. No LLM call. ₹0.

Or one-command Docker (API :8000 + dashboard :8501):

```bash
docker compose up
```

---

## 2. The three ways to talk to Memflex

| Way | When | Example |
|---|---|---|
| **Swagger UI** (`/docs`) | Manual testing, demos | Click, paste JSON, Execute |
| **HTTP API** (curl / any language) | Production, non-Python stacks | `POST /ask` (below) |
| **Python SDK** | Python agents | `Client("http://localhost:8000").ask(...)` |

### curl

```bash
# 1st time → {"source":"llm"} — thinks + memorizes
curl -X POST http://localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"user_id":"u123","message":"When will my refund arrive?","llm":"mock/mock-echo"}'

# 2nd time → {"source":"reflex"} — memory, ~0ms, ₹0
curl -X POST http://localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"user_id":"u123","message":"When will my refund arrive?","llm":"mock/mock-echo"}'

# Health / stats / inspect memory
curl http://localhost:8000/health
curl http://localhost:8000/metrics                 # hit_rate, ₹ saved, latency, calibration
curl "http://localhost:8000/reflexes?user_id=u123" # everything the agent remembers
```

---

## 3. API reference

| Endpoint | What it does |
|---|---|
| `POST /ask` | Main query. Hit → instant answer; miss → LLM → auto-distilled into a reflex |
| `POST /v1/chat/completions` | **OpenAI-compatible** — any framework via `base_url`, extras: `reflex_source/confidence/id` |
| `POST /v1/messages` | **Anthropic-compatible** — Claude SDK via `base_url`, extras: `reflex_source/confidence/id` |
| `POST /remember` | Store a fact explicitly (`{"user_id","fact","confidence"}`) |
| `POST /reflexes` | Explicitly memorize a decision (tool-composed answers, bulk import); same `(user_id, situation)` **upserts** |
| `GET /reflexes?user_id=` | List active reflexes with confidence, hits, provenance |
| `GET /memories?subject=` | List stored facts (`subject` = `user:<id>`) |
| `GET /activity?limit=&source=` | Recent asks newest-first (`source=all/llm/reflex`) with answers, latency, model — console feed |
| `POST /reflexes/{id}/feedback` | `{"ok": true/false}` — 👍 raises confidence, 👎 records a correction (lowers it) |
| `PATCH /reflexes/{id}` | **User-set TTL/confidence**: `{"ttl_days": 2–365, "confidence": 0–0.99}` (clamped) |
| `POST /verify/run?limit=20` | Re-check stale reflexes against the LLM now (flags conflicts) |
| `GET /metrics` | `hit_rate, avg_latency_ms, llm_calls, cost_saved_30d_inr, calibration[]` |
| `DELETE /reflexes/{id}` | Erase one reflex (GDPR-style) |

---

## Agent integration guide — 4 patterns that cover ~every agent

**Pattern 1 — Drop-in base URL (easiest, any language/framework).**
Point your existing OpenAI **or Claude** client at Memflex; `model` is a reflex model-string (upstream used only on misses):

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")
r = client.chat.completions.create(
    model="ollama-cloud/gpt-oss:20b",
    messages=[{"role": "user", "content": "When will my refund arrive?"}],
    user="u123",
)
print(r.choices[0].message.content, "|", r.reflex_source, r.reflex_confidence)

from anthropic import Anthropic
cl = Anthropic(base_url="http://localhost:8000/v1", api_key="not-needed")
m = cl.messages.create(model="claude/claude-sonnet-4-5", max_tokens=256,
    messages=[{"role": "user", "content": "When will my refund arrive?"}])
print(m.content[0].text, "|", m.reflex_source)
# Works with LangChain (ChatOpenAI base_url), LlamaIndex, CrewAI, Claude SDK,
# voice pipelines — anything speaking OpenAI or Anthropic protocol (Ollama and
# Gemini clients have OpenAI-compatible modes pointing at /v1 too).
# Last user message = situation key (cacheable); history/system only enrich the
# miss-path prompt, never hurt hit rate.
```

**Pattern 2 — LangGraph node (native).** `ReflexNode(llm=..., thresholds={"serve": 0.85})` — see §5 and `examples/langgraph-bot.py`.

**Pattern 3 — Tool-using agents (plan→act→answer).** The planner + tools run on a miss; the **composed final answer** is memorized via `POST /reflexes` (upsert, no duplicates), so repeats skip tools *and* the LLM. Runnable proof: `python3 examples/agent_loop.py` — run 1 fires `compute_refund_eta(ORD-9981)`, run 2 serves the same answer with zero tool calls:

```python
res = rx.ask(user_id=uid, message=q, llm=llm)
if res.source.startswith("reflex"):
    return res.answer                          # zero planner, zero tools, zero LLM
facts = run_tools(plan(llm, q))                # System 2 + tools, only on miss
composed = " | ".join(facts)
rx.save_reflex(user_id=uid, message=q, answer=composed)  # memorize composed answer
```

**Pattern 4 — Guardrail / triage gate (structured + confidence).** Route by type, auto-act only when confident:

```python
res = rx.ask(user_id=u, message=msg, llm=llm, extract_structured=True,
             output_schema={"refund_status": "str", "eta_days": "list[int]"})
if res.source.startswith("reflex") and res.confidence >= 0.9:
    auto_approve(res)        # calibrated: safe band
else:
    escalate_to_human(res)   # novel or uncertain
```

---

## Honest scorecard — where Memflex wins, where it loses (Oct 2026)

**Genuinely strong today:** zero-LLM repeat serving (regression-tested, not a claim), 14-language repeats + Hindi↔Hinglish convergence (tested), verified memory with TTL + corrections (no competitor productizes this), OpenAI-compat + LangGraph + Mem0-shim integration, console observability, 1-command self-host, Apache-2.0, CI green.

**Genuinely missing / weaker (no hype):**
- ❌ No generalization to *unseen* decisions — that needs a trained model (Jev) or a frontier LLM; Memflex routes those to System 2 by design.
- ⚠️ `reflex+reverify` hits still make a synchronous verification call (slow on cloud models) — async worker is the next fix (see CONTRIBUTING roadmap).
- ⚠️ Memory search is global across `user_id`s (great for shared support answers, wrong for private multi-tenant data) — per-user scoping option is pending.
- Storage tiers: SQLite is perfect to ~100k reflexes; beyond that set `REFLEX_STORE=postgres` + `REFLEX_POSTGRES_DSN` (pgvector fast path, brute-force fallback, same Protocol — live-tested in `tests/test_postgres.py`).
- ⚠️ No published third-party benchmark yet — calibration numbers are self-reported from hit consistency.

Verdict: a **real, working v0.3 foundation** with tested differentiators — not fluff — but "great OSS project" status needs production hardening + community + independent benchmarks. That's the roadmap, and it's written down in CONTRIBUTING.md instead of hidden.

### `/ask` fields

```json
{
  "user_id": "u123",
  "message": "When will my refund arrive?",
  "context": {"order_id": "ORD-9981"},
  "llm": "mock/mock-echo",
  "serve_threshold": 0.85,
  "extract_structured": true,
  "output_schema": {"refund_status": "str", "eta_days": "list[int]"}
}
```

Response: `{"answer", "source": "reflex|reflex+reverify|llm", "reflex_id", "confidence", "latency_ms", "llm_cost_saved_inr"}`.

`source` meanings: **`reflex`** = pure memory (zero LLM calls — guaranteed, see §8); **`reflex+reverify`** = served from memory + a background re-check of that reflex against the LLM; **`llm`** = novel situation, full LLM call, saved as a new reflex for next time.

---

## 4. Python SDK

```python
from reflex import Client

rx = Client("http://localhost:8000")

res = rx.ask(user_id="u123", message="When will my refund arrive?", llm="mock/mock-echo")
res.answer        # "Your refund is being processed..."
res.source        # "reflex"  ← no LLM call. ₹0. ~0ms.
res.confidence    # 0.9

rx.remember(user_id="u123", fact="prefers COD", confidence=0.9)
rx.reflexes(user_id="u123")          # inspect memory
rx.feedback(reflex_id=res.reflex_id, ok=True)  # 👍/👎 tunes confidence
```

---

## 5. LangGraph / LangChain

```python
from reflex.contrib.langgraph import ReflexNode

graph.add_node("respond", ReflexNode(
    llm="mock/mock-echo",            # used only on misses
    thresholds={"serve": 0.85},
))
# Your agent now gets reflexes + verified memory with zero other changes.
```

See `examples/langgraph-bot.py`. Full LangChain history adapters are on the roadmap.

---

## 6. Mem0-compatible shim

Migrating from Mem0? Swap the import, keep your code:

```python
from reflex.compat import mem0   # drop-in for basic add/search

db = mem0.MemoryClient(base_url="http://localhost:8000")
db.add("prefers email updates, COD orders", user_id="u123")
db.search("COD preference?", user_id="u123")
```

---

## 7. Choosing the LLM (System 2)

The `llm` field per request, or `DEFAULT_LLM_MODEL` env. No key = Mock (deterministic, multilingual, answers in-kind — perfect for dev/tests).

| Value | Backend | Needs |
|---|---|---|
| `mock/mock-echo` (default) | Built-in deterministic replies | Nothing |
| **Ollama** `ollama/qwen2.5:7b` | Local Ollama (`OLLAMA_HOST`) | `ollama pull qwen2.5:7b` |
| **Ollama** `ollama-cloud/gpt-oss:20b` | Hosted Ollama Cloud, Bearer auth | `OLLAMA_API_KEY` (keys at ollama.com/settings/keys) |
| **OpenAI** `openai/gpt-4o-mini` (or bare `gpt-4o`, `o1`…) | api.openai.com | `OPENAI_API_KEY` |
| **Claude** `claude/claude-sonnet-4-5` (or `anthropic/…`) | api.anthropic.com (Messages API) | `ANTHROPIC_API_KEY` |
| **Gemini** `gemini/gemini-2.5-flash` (or `google/…`) | generativelanguage.googleapis.com | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) |
| **OpenRouter** `openrouter/deepseek/deepseek-v4` | openrouter.ai (any model there) | `OPENROUTER_API_KEY` |
| **DeepSeek** `deepseek/deepseek-chat` | api.deepseek.com | `DEEPSEEK_API_KEY` |

Unknown model strings fall back to Mock gracefully — the server never crashes for lack of a key. Available Ollama cloud models change over time; list them with `curl -H "Authorization: Bearer $OLLAMA_API_KEY" https://ollama.com/api/tags`. Provider protocols are unit-tested offline in `tests/test_outbound_providers.py`.

### Embeddings backend (`EMBEDDING_BACKEND`)

| Value | Quality | Needs |
|---|---|---|
| `hash` | Exact + synonym repeats (all languages); no downloads | Nothing — use for CI/dev |
| `bge-m3` (default) | Multilingual semantic similarity, strong coverage across 100+ languages | `pip install sentence-transformers` (auto-downloads `BAAI/bge-m3`) |
| `qwen3` | `Qwen/Qwen3-Embedding-0.6B` semantics | Same package |
| `ollama` | `OLLAMA_EMBED_MODEL` (e.g. `nomic-embed-text`) | Ollama running |

---

## 8. The no-LLM-on-hit guarantee

**If the answer is in memory, Memflex makes zero LLM calls.** This is structural, not a hope:

1. `/ask` first embeds + searches memory (<10ms) and computes a calibrated score:
   `score = 0.6·similarity + 0.2·hit_consistency + 0.1·recency − 0.5·correction_rate`
2. `score ≥ serve_threshold` (default 0.85) → the stored answer returns directly. The LLM provider is never instantiated, never called.
3. Middle band → served from memory + one re-verification (self-correction). Below band → full LLM call, then distilled into a new reflex so the *next* identical request is free.

**Prove it yourself** (regression test ships in the repo):

```bash
EMBEDDING_BACKEND=hash python3 -m pytest tests/test_no_llm_on_hit.py -v
```

It swaps in a call-counting LLM, establishes a reflex, then asserts 3 further asks return `"source": "reflex"` with **0 provider calls**. Typical production curve: ask 1 = LLM, ask 2 = memory (re-verify), ask 3+ = pure memory at 0.9 confidence, 0ms.

Tune with `SERVE_THRESHOLD` / `UNCERTAIN_BAND` envs (or per-request `serve_threshold`). Higher threshold = fewer auto-served answers, fewer mistakes.

### Measured snapshot — 30-ask support workload (Oct 2026)

10 intents × 3 rounds (English, German, Spanish, French + terse follow-ups), fresh DB, keyless `hash` backend:

| Metric | Result |
|---|---|
| Asks served from memory | **22/30 (73.3%)** — repeats at `reflex` 0.90, 0–1ms |
| Distinct reflexes learned | 8 (one per intent) |
| Memory-path latency | ~0.1ms avg (mock backend; vs **7–10s measured on Ollama Cloud** `gpt-oss:20b` earlier the same day) |
| Metered savings | ₹0.24 on 30 asks → scales linearly with repeat traffic |

Scale math: 1 lakh asks/month at 70% repeats ≈ 70,000 free answers. At typical ₹0.30–0.50/LLM-call, that's **₹21,000–35,000/month saved per lakh asks** — before counting the latency win. Reproduce: `examples/support-agent.py` + `GET /metrics`.

### What do no-LLM answers actually look like?

Three kinds — all served with zero model calls:

**1. Verbatim** (the common case). The exact answer the LLM gave the first time, stored as the reflex payload and served as-is. Nothing is regenerated, rephrased, or "reasoned" — that's precisely why it can't hallucinate *new* things (and why a wrong first answer needs 👎/re-verify to dislodge, §10b).

**2. Template with per-request variables.** Save `"Namaste {name}, balance ₹{balance} hai"` via `POST /reflexes`, ask with `"context": {"name": "Ravi", "balance": 250}` → `"Namaste Ravi, balance ₹250 hai"`. Rendering is pure string substitution (unknown keys stay literal `{like_this}`, no code ever executes — see `reflex/core/renderer.py`). Static prose + live variables, still ₹0.

**3. Structured / typed** (Jev-style for machines). Ask with `"extract_structured": true, "output_schema": {...}` and every response — LLM *and* reflex — carries a `structured` object, e.g. `{"refund_status": "processing", "eta_days": [3, 5]}`. Your code branches on JSON, never parses prose.

---

## 9. Multilingual — every language, no favorites

Memflex is language-neutral by architecture — **no language gets top billing anywhere in the serving path.** Same guarantees in Hindi, German, Japanese, Arabic, or anything else:

- **Same-language repeats work in ANY language, including low-resource ones** — English, Hinglish, Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Spanish, French, Arabic, Portuguese, Russian, Japanese, Chinese, Turkish… covered by `tests/test_multilingual.py` (each asserting pure `reflex` hits) plus `tests/test_german.py`.
- **The LLM is instructed neutrally** ("answer in the same language the user wrote in") and the Mock test-double answers *in kind* — German → German (`Ihre Rückerstattung…`), Japanese → Japanese (`返金手続き中…`), Hindi → Hindi. No preferred language exists in code (regression-tested with a provider spy).
- **Language plugins** (`reflex/core/normalizer.py → LANGUAGE_MAPS`) converge spellings that *should* share memory — e.g. Hindi Devanagari ↔ Roman, German umlaut folding (`Rückerstattung` ≡ `Rueckerstattung`, live-proven sim 1.0) — plus core intent synonyms. Scripts are never stripped — Tamil, Arabic, CJK, Cyrillic all keep stable keys.
- **Stopword removal** (`is/my/hai/der/die/…`, question words kept) stops short queries in *different* languages colliding on function words — the false-positive class that serves a wrong-language answer. Caught live, fixed, tested.
- **Order IDs / phone numbers are masked** (`ORD-9981` → `<ORD>`, `+49…` → `<PHONE>`) so per-order queries share one reflex instead of memorizing every ID.
- **Cross-language paraphrase** (Tamil sentence ≈ English sentence) needs a semantic backend (`bge-m3`/`qwen3`, 100+ languages); with the keyless `hash` backend, repeats match in every language but translations of each other don't. Choose per §7.

**Add your language** (5 minutes, no ML needed): add a dict to `LANGUAGE_MAPS` (`token → canonical`), add repeat-cases to `tests/test_multilingual.py`, extend `_INTENTS` in `reflex/llm/base.py` if you want native Mock answers, run `pytest`. See `CONTRIBUTING.md`.

---

## 10. Trust: confidence, verification, feedback

- **Calibrated confidence**: every answer carries a number where higher measurably means more accurate (hit consistency − correction penalty + recency decay). `GET /metrics → calibration[]` is the chart to show customers: *"at 0.9+ confidence we're right ~96% — automate that band."*
- **Verification loop**: every `VERIFY_INTERVAL_H` (default 24h, APScheduler, in-process) stale reflexes past TTL (`REFLEX_TTL_DAYS`, default 30) are re-asked to the LLM: `CONFIRM` → timestamp bumped; `CONFLICT` → confidence slashed + flagged. Trigger manually: `POST /verify/run?limit=20`.
- **Feedback**: `POST /reflexes/{id}/feedback {"ok": false}` records a correction — that reflex's score drops immediately, so a wrong memory stops serving after ~1 correction instead of poisoning every future answer.

---

## 10b. Hallucination safety — will memory make the LLM hallucinate?

Short answer: **memory can serve a wrong answer, but the system is built to catch and bury it fast — and you can audit every decision.** Four layers (all demonstrated live, all tested):

1. **Gated serving, not blind cache.** An answer serves from memory only if `similarity + track-record + recency − corrections` clears 0.85. A vague resemblance (sim 0.5) scores ~0.3 → goes to the LLM. Add `"explain": true` to any `/ask` and the response tells you *why*: `matched_situation`, `similarity`, `threshold`.
2. **Corrections bury bad memories.** One 👎 (`POST /reflexes/{id}/feedback {"ok": false}`) drops confidence 0.08 and counts a correction; ~3–4 reports push any reflex below the band → the next ask goes back to the LLM, which re-learns into the *same* record (upsert, no duplicates). Live-tested: a deliberately wrong "Open 25 hours" answer stopped serving after reports.
3. **TTL + verification loop.** Memories expire (`REFLEX_TTL_DAYS`, default 30) and are re-checked against the LLM (`POST /verify/run`); conflicts get flagged instead of served forever.
4. **Honest residual risks:** a *confidently wrong first answer* serves until someone corrects it (fix: seed critical answers via `POST /reflexes` + start thresholds high); rapidly-changing facts (live prices, stock) should use short TTLs or bypass Memflex — memory is for *stable* knowledge.
5. **Two automatic quarantines:** model refusals are served once, never memorized; answers in a *disjoint non-Latin script* from the query (Hindi Q → Tamil A) are likewise never saved (explicit saves return 422 unless `allow_mismatch=true`). Latin-script answers always pass — English fallbacks are legitimate, and Latin↔Latin pairs rely on feedback/verification.

### Day-2 problems, solved: staleness + vague follow-ups

**"Day-1 refund = processing, day-2 reality = processed — will Memflex lie?"**
No. Answers carrying time-varying signals (*processing, status, ETA, days…*) are auto-assigned **TTL 1 day** at distill time (`infer_ttl_days`; stable FAQs keep 30 days; override per-request via `ttl_days`). And expiry is a **hard boundary**: a reflex older than its TTL is *never served* — the next ask goes to System 2 for a fresh verdict, which re-learns into the same record (upsert, no duplicates). Live-proven in `tests/test_staleness_followup.py::test_expired_reflex_is_never_served`.

**"Day-1: 'Hii what is status for my refund', day-2: just 'refund??' — same answer?"**
Yes. Single-token queries are **expanded with your last message** (persistent per-user context in the DB, survives restarts): `refund??` → resolved as the day-1 question → same situation key → **same answer** (`explain: true` shows `expanded_from` as the audit trail). If there's no history, or it still doesn't match, it safely falls to the LLM. Tested in `test_vague_followup_gets_same_answer`.

## 10c. Where Memflex succeeds (and where it doesn't)

**Sweet spots — repetitive, stable, high-volume:**
- Support FAQs (refund / delivery / cancellation — the support demo serves **~73% from memory** on a cold start, climbing as memories accumulate hits)
- Triage & routing (intent → queue, with `output_schema` typed outputs)
- Extraction & form-filling (same fields, same schema, every time)
- Voice agents & live chat (0ms hits are what make realtime feel realtime)
- Tool-using agents (plan once via `POST /reflexes` upsert, serve composed answers forever — see `examples/agent_loop.py`)

**Bad fits — don't put these in memory:** live prices/inventory, breaking news, one-off reasoning, low-traffic long-tail (nothing repeats → pure overhead), secrets/PII you can't erase (use TTLs + `DELETE`).

## 11. Dashboard, self-hosting, data

- **Console dashboard**: full guide at [Console dashboard](#console-dashboard--see-every-llm-call-and-every-reflex-answer) — `http://localhost:8501`. Or `docker compose up` for API + console together.
- **Storage**: SQLite one file (`REFLEX_DB_PATH`, default `./data/reflex.db`) — no external services, backup = copy the file. Production scale: `REFLEX_STORE=postgres` + `REFLEX_POSTGRES_DSN=postgresql://…` (compose `db` service with `--profile pg`). Qdrant scale-out remains roadmap.
- **GDPR-style erasure**: `DELETE /reflexes/{id}`.
- **K8s**: starter chart in `k8s/helm/`. **Tracing**: OTel activates when `OTEL_EXPORTER_OTLP_ENDPOINT` is set.

---

## 12. How Memflex differs: Jev, Mem0, GPTCache

### Jev (TypeSafe AI) — researched Oct 2026

**What Jev is** (from typesafe.ai, docs.typesafe.ai, and independent references): TypeSafe AI's first **System One model** (founded by Diogo Almeida — ChatGPT/RLHF co-inventor, ex-OpenAI; $40M seed led by DCVC; launched Sept 2026). Instead of generating text, Jev returns **typed decisions** via three primitives — **choice** (pick 1 of ≤255 options), **score** (2–10 scale), **noul** (yes/no probability) — in **70–500ms** (40–200× faster than frontier LLMs), with **calibrated confidence** from RLCD training (Reinforcement Learning for Calibrated Decisions), parallel sampler, type-locked outputs (zero hallucination *by construction*). Pricing ≈ **$42 per billion input tokens** (output free), free tier 100k tokens, **hosted API only** (closed weights), text-only. Variants include Laya (English short-text) and Laya Multilingual (beta).

**Memflex vs Jev:**

| | Memflex (this repo) | Jev (TypeSafe) |
|---|---|---|
| Answers repeats without LLM | ✅ core (retrieval + gating) | ✅ (trained decision model) |
| Handles *unseen* situations | ❌ routes to your LLM (System 2) | ✅ generalizes via training |
| Output | Full answers: any-language prose **+** typed structured | Typed primitives only (choice/score/noul), no prose |
| Cost on repeats | **₹0** (no model call at all) | Tiny per-token fee, never zero |
| Multilingual | ✅ multilingual-first, any-language repeats | English-first, multilingual in beta |
| Self-correction of wrong memory | ✅ verification loop + corrections | ❌ (stateless model) |
| Self-host / data residency | ✅ 1 command, Apache-2.0, data stays local | ❌ hosted API, data leaves |
| Needs training / GPU | ❌ ships today, works with any LLM | ✅ frontier training (their moat, your lock-in) |

Positioning: **"Jev-style reflexes (fast, calibrated, hallucination-free decisions) + verified memory — open-source and multilingual, for the 99% who can't afford frontier decision models or $249/mo memory SaaS."** If you outgrow retrieval (need generalization to *unseen* structured decisions), Jev is the natural upgrade for that slice — Memflex can route low-confidence cases to it like any other System-2 provider.

### Memory / cache landscape

| | Memflex | Mem0 / Zep / Letta | GPTCache |
|---|---|---|---|
| Answers repeats without LLM | ✅ core | ❌ facts only (LLM still runs every request) | ⚠️ similarity match, no gating |
| Calibrated confidence | ✅ per-reflex | partial | ❌ |
| Self-correction loop | ✅ | ❌ | ❌ |
| Hindi/regional native | ✅ | ❌ | ❌ |
| Self-host, 1 command | ✅ | partial | ✅ |
| Schema-enforced structured output | ✅ | ❌ | ❌ |

### Prior art check — does this already exist? (researched Oct 2026)

Short answer: **the direction is validated by giants, but this exact combination has no direct equivalent.** Closest overlaps, and where each stops:

- **Portkey AI Gateway** (OSS MIT, ~13k stars; acquired by Palo Alto Networks May 2026) — has **semantic caching** (cosine threshold, exact-match first). The closest feature overlap. But: semantic mode needs Enterprise plan + your own vector DB, and it has **no confidence calibration, no verification loop, no memory/facts layer, no multilingual focus**. Cache ≠ memory.
- **Helicone** (OSS, maintenance mode under Mintlify) — caching is **exact-hash only** (any param change = miss). No semantic matching at all.
- **LiteLLM / Vercel AI Gateway / Cloudflare AI Gateway** — routing + observability + failover; semantic caching is out of scope or exact-only. They solve a different problem (which provider) and pair *with* Memflex, not against it.
- **GPTCache** (Zilliz, ~8.2k stars, MIT) — the closest OSS ancestor: semantic cache lib + server + LangChain integration. But it's a 2023-era design (ChatGPT + early LangChain), needs Milvus/FAISS plumbing, and has **no confidence gating, no verification, no memory layer, no multilingual story**. Memflex is what GPTCache would look like rebuilt for agents in 2026.
- **Mem0** ($24M raised: Kindred seed, Basis Set Series A; ~62k stars, 14M downloads; CrewAI/Flowise/Langflow native; AWS Agent SDK's memory provider) — the memory leader. But: **cloud-first** (memories live on their servers), **facts-only** (every request still burns an LLM call — it saves *tokens*, not *calls*), entry ~$19/mo. Memflex's lane is the complement: answer repeats with **zero calls**, self-hosted, in every language.
- **Zep** (graph-first, high LoCoMo claims, ~$125/mo entry, Community Edition deprecated) and **Letta/MemGPT** (agent framework with self-editing memory) — different architectures, same LLM-every-request economics.
- **Anthropic/OpenAI prompt caching** — prefix caching of long contexts (up to 90% off input tokens). Orthogonal: it makes the *same* LLM call cheaper; Memflex *eliminates* the call. Use both.

**Verdict for agent builders:** if you want "don't pay for what you've seen" + "don't trust memory blindly" + "every language works" + "runs on my infra for free" — no existing project covers that square. That's the honest moat: a *combination*, not a single trick. And where giants overlap (gateways, hosted memory), Memflex plugs in beside them (`base_url` / shim) instead of demanding rewrites.

---

## 13. Examples, tests, troubleshooting

```bash
python3 examples/support-agent.py   # Day-1→Day-30 story: watch hit_rate climb past 70%
python3 examples/langgraph-bot.py        # needs: pip3 install langgraph
EMBEDDING_BACKEND=hash python3 -m pytest tests -v   # 60+ tests: confidence, hits, 19-language, voice/SSE, no-LLM, mem0 shim
```

| Symptom | Fix |
|---|---|
| `localhost:8000` shows "Not Found" | Normal — no homepage. Use `/docs`, `/health`, `/metrics` |
| `zsh: command not found: pip/python` | macOS: use `pip3` / `python3` |
| `address already in use :8000` | Server already running: `pkill -f reflex.api.app`, or reuse it |
| `ollama-cloud/*` → 401/500 | `export OLLAMA_API_KEY=...` before starting the server |
| Repeats still `"source": "llm"` | Paraphrase too distant for backend (see §9) or threshold too high; check `/reflexes` situations |
| Slow first answers on cloud models | Expected (real inference); repeats are the fast path |

## 14. Roadmap & license

v0.1 (ask/remember API, confidence v1, dashboard) ✅ · v0.2 (verification, feedback, calibration evals, multilingual suite, LangGraph) ✅ · v0.3 (Mem0 shim, Helm, OTel) ✅ · v0.4 (Postgres store, 5-vendor gateway, OpenAI/Claude compat) ✅ → next: Celery workers, Qdrant scale-out, public multilingual benchmark. Fair Source — contributions welcome (CLA).
