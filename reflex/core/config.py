# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Central settings — env-driven, keyless defaults."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    serve_threshold: float = 0.85
    uncertain_band: float = 0.65
    w_sim: float = 0.6
    w_hit: float = 0.2
    w_recency: float = 0.1
    w_correction: float = 0.5

    reflex_db_path: str = "./data/reflex.db"
    reflex_ttl_days: int = 30

    default_llm_model: str = "mock/mock-echo"
    openrouter_api_key: str = ""
    deepseek_api_key: str = ""
    ollama_host: str = "http://localhost:11434"
    ollama_api_key: str = ""  # Ollama Cloud key (https://ollama.com/settings/keys), env OLLAMA_API_KEY
    openai_api_key: str = ""  # passthrough for /v1/chat/completions upstream, env OPENAI_API_KEY
    # Store backend: sqlite (default) | postgres. Postgres needs psycopg +
    # REFLEX_POSTGRES_DSN=postgresql://user:pass@host:5432/reflex
    reflex_store: str = "sqlite"
    postgres_dsn: str = ""
    anthropic_api_key: str = ""  # Claude outbound, env ANTHROPIC_API_KEY
    gemini_api_key: str = ""  # Gemini outbound, env GEMINI_API_KEY (or GOOGLE_API_KEY)

    embedding_backend: str = "bge-m3"
    embedding_model: str = "BAAI/bge-m3"
    ollama_embed_model: str = "nomic-embed-text"

    verify_interval_h: int = 24
    verify_batch: int = 20
    cost_per_llm_call_inr: float = 0.011

    # API auth: empty = open local mode. Set MEMFLEX_API_KEY (or legacy
    # REFLEX_API_KEY) to require X-API-Key / Bearer on every route but /health.
    memflex_api_key: str = ""
    reflex_api_key: str = ""
    cors_origins: str = "*"

    # Public demo lockdown. When true: only allowlisted models may be used,
    # messages are length-capped, write/admin endpoints are disabled, and
    # per-IP rate limiting applies. Self-hosted full servers leave this off.
    demo_mode: bool = False
    demo_models: str = "mock/*"
    demo_rate_per_min: int = 30
    demo_max_chars: int = 300

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
