# Hosting Memflex — from laptop to production

> Rule of thumb: start on a **$6 VPS**, scale when `/metrics` says so. Memflex is one SQLite file + two containers — there is almost nothing to operate.

## Option A — Local (dev / demo)

```bash
pip install memflex          # after first PyPI publish; until then: pip install -e .
cp .env.example .env
EMBEDDING_BACKEND=hash python -m reflex.api.app   # :8000, keyless
python -m streamlit run dashboard/app.py           # :8501 console
```

## Option B — Docker Compose (small prod, recommended start)

```bash
cp .env.example .env   # fill provider keys you actually use
docker compose -f docker-compose.prod.yml up -d --build
# API :8000 (+/docs, /metrics) · console :8501 · data in `reflex-data` volume
docker compose -f docker-compose.prod.yml logs -f api
```

`docker-compose.prod.yml` adds vs dev: `restart: always`, healthchecks, named volume. Back up memory with one command: `docker run --rm -v reflex-data:/d -v $PWD:/b alpine cp /d/reflex.db /b/reflex-backup.db`.

## Option C — Single VPS + public URL (~$6/mo Hetzner/DigitalOcean)

1. Point DNS `reflex.yourdomain.com` → VPS IP.
2. On the VPS: install Docker, clone repo, `docker compose -f docker-compose.prod.yml up -d`.
3. TLS + routing with Caddy (auto-HTTPS, 5 lines):
   ```
   reflex.yourdomain.com {
       reverse_proxy localhost:8000
   }
   console.yourdomain.com {
       reverse_proxy localhost:8501
   }
   ```
4. Your agents use `base_url="https://reflex.yourdomain.com/v1"` — same one-line integration as local (see `reflex/plug.py`: set `REFLEX_URL`).

## Option D — PaaS (zero server management)

- **Fly.io:** `fly launch` (Dockerfile.api works as-is) + `fly volumes create reflex_data` mounted at `/data`.
- **Render / Railway:** deploy from repo, add a persistent disk at `/data`, set `REFLEX_DB_PATH=/data/reflex.db`.
- Note: SQLite = single instance. Two replicas need Postgres/Qdrant scale-out (interfaces in `reflex/stores/base.py` are ready; not implemented yet — see roadmap).

## Option E — Kubernetes

Starter chart in `k8s/helm/` (2 replicas + 10Gi PVC). Turn on when a single VPS saturates — most teams never need it: at ~50ms/hit, one small box serves thousands of repeat-heavy users.

## Managed Memflex (the business, matches open-core plan)

Self-host is Apache-2.0 and free forever. The paid managed tier (future) is for teams that don't want *any* ops: hosted API + team dashboard + SLAs. Same endpoints, so migrating is changing one `base_url`.

## Ops checklist

| Concern | Answer |
|---|---|
| Data loss | Single file `reflex.db` — snapshot the volume nightly |
| Secrets | Only in `.env` (gitignored) / platform secret store — never in images |
| Updates | `git pull && docker compose -f docker-compose.prod.yml up -d --build` (DB is backward-compatible) |
| Scale signal | Watch `/metrics`: `hit_rate` climbing = working; p95 latency rising = time for Postgres/Qdrant |
| Erasure requests | `DELETE /reflexes/{id}` per reflex; document your retention policy |
