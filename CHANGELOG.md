# Changelog — Memflex

All notable changes. Format follows Keep a Changelog. Versions are
PyPI dist versions (`pip install memflex`).

## [Unreleased]

## [0.4.0] — 2026-10

### Added
- Postgres store (`REFLEX_STORE=postgres`, pgvector fast path + brute-force
  fallback) behind the `ReflexStore` Protocol; `db` compose service.
- 5-vendor LLM gateway: OpenAI, Claude (Anthropic), Gemini, Ollama
  (local + Cloud), OpenRouter, DeepSeek. Missing key → Mock fallback.
- OpenAI-compatible `POST /v1/chat/completions` and Anthropic-compatible
  `POST /v1/messages` (any framework via `base_url`).
- `reflex.plug` one-liner clients; `memflex` JS/TS npm client (`clients/js`).
- `POST /reflexes` explicit memorize (upsert); `PATCH /reflexes/{id}`
  (TTL/confidence controls); per-request `ttl_days` override.
- `GET /activity` observability feed; `explain` mode on `/ask`.
- Safe `{variable}` template rendering on memory hits; typed `structured`
  output on hits.
- API-key auth (`MEMFLEX_API_KEY`), security headers, CORS allowlist.
- Next.js console (`console/`, static export) alongside Streamlit fallback.
- memflex.dev marketing site + docs (`site/`, Astro static).

### Fixed
- Cosine scale no longer gives unrelated texts a 0.5 baseline.
- Verifier first-token verdict (was: substring false-CONFLICT with echo models).
- Cross-intent veto (delivery Q can no longer be served a refund memory).
- Refusal quarantine + wrong-script quarantine (served once, never memorized).
- Turkish dotted-İ folding; stopword collisions; miss-path upsert (no dupes).

## [0.3.0] — 2026-09
- Mem0-compatible shim, Helm chart stub, OpenTelemetry hook.

## [0.2.0] — 2026-09
- Verification loop, feedback endpoint, calibration evals, Hindi suite,
  LangGraph node, examples.

## [0.1.0] — 2026-09
- `ask`/`remember` API, confidence engine v1, SQLite-vec store,
  Streamlit dashboard, Docker Compose.
