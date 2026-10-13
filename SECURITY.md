# Security — Memflex

## Supported

Latest `main` and the newest GitHub Release. Older versions: upgrade first,
then report if it reproduces.

## Report privately

- Prefer: GitHub **Private vulnerability reporting** (Security tab → Report).
- Fallback: contact published on memflex.dev at launch.
- Please include: version/commit, repro steps or curl, redacted logs
  (strip API keys), impact assessment.

## What to expect

- Acknowledgement within 72h, fix timeline proportional to severity.
- Please do not disclose publicly before a fix + release (90-day norm).

## Scope notes (known, documented)

- Single-tenant API-key auth today; per-tenant isolation is roadmap.
- Rate limiting is expected at the edge (Caddy/nginx), not in-app.
- `GET /health` is intentionally unauthenticated.
