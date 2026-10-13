# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""FastAPI app + APScheduler verification loop + OTel hook + API-key auth."""
from __future__ import annotations
import hmac
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from reflex.api.routes import router
from reflex.core.config import settings
from reflex.otel import setup_otel

from contextlib import asynccontextmanager


def _expected_key() -> str:
    return (settings.memflex_api_key or settings.reflex_api_key or "").strip()


async def _auth_middleware(request: Request, call_next):
    # /health stays open (load balancers, uptime checks). Everything else
    # requires a key ONLY when one is configured — empty key = open local mode.
    if request.url.path != "/health":
        expected = _expected_key()
        if expected:
            got = request.headers.get("x-api-key", "")
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                got = got or auth[7:].strip()
            if not got or not hmac.compare_digest(got, expected):
                return JSONResponse({"detail": "Unauthorized — valid X-API-Key required."}, status_code=401)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from reflex.api import deps
        from reflex.core.config import settings
        from reflex.llm.factory import get_provider
        from reflex.verify.worker import run_verification

        def job():
            try:
                run_verification(deps.get_store(), get_provider(settings.default_llm_model),
                                 limit=settings.verify_batch)
            except Exception:
                pass

        sched = BackgroundScheduler()
        sched.add_job(job, "interval", hours=max(1, settings.verify_interval_h))
        sched.start()
        app.state.scheduler = sched
    except Exception:
        pass
    yield
    try:
        sched = getattr(app.state, "scheduler", None)
        if sched:
            sched.shutdown(wait=False)
    except Exception:
        pass


app = FastAPI(title="Memflex — reflexes & verified memory for AI agents", version="0.3.0", lifespan=lifespan)
setup_otel(app)
_cors = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(CORSMiddleware, allow_origins=_cors, allow_methods=["*"], allow_headers=["*"])
app.middleware("http")(_auth_middleware)
app.include_router(router)

@app.get("/health")
def health():
    return {"ok": True, "service": "memflex"}


def run():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    run()
