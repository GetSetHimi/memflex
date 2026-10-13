# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Embedding backends — local-first, keyless fallback.

Backends (EMBEDDING_BACKEND):
  bge-m3   : sentence-transformers BAAI/bge-m3 (default, strong Hindi)
  qwen3    : sentence-transformers Qwen/Qwen3-Embedding-0.6B
  ollama   : Ollama embeddings (OLLAMA_EMBED_MODEL)
  hash     : deterministic hashed bag-of-tokens (CI/keyless, no downloads)
"""
from __future__ import annotations
import hashlib
import re

import numpy as np

_DIM = 256


def _hash_embed(text: str, dim: int = _DIM) -> np.ndarray:
    toks = re.findall(r"[\u0900-\u097F\w]+", text.lower())
    vec = np.zeros(dim, dtype=np.float32)
    for t in toks:
        h = int(hashlib.sha256(t.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
        vec[(h >> 16) % dim] += 0.5
    n = float(np.linalg.norm(vec))
    if n > 0:
        vec /= n
    return vec


class EmbeddingModel:
    def __init__(self, backend: str = "bge-m3", model: str = "BAAI/bge-m3"):
        self.backend = backend
        self.model_name = model
        self._st = None
        self.dim = _DIM
        if backend in ("bge-m3", "qwen3"):
            try:
                from sentence_transformers import SentenceTransformer

                name = model if backend == "bge-m3" else "Qwen/Qwen3-Embedding-0.6B"
                self._st = SentenceTransformer(name)
                self.dim = int(self._st.get_sentence_embedding_dimension())
            except Exception:
                self._st = None
                self.backend = "hash"

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._st is not None:
            try:
                v = self._st.encode(texts, normalize_embeddings=True)
                return np.asarray(v, dtype=np.float32)
            except Exception:
                pass
        if self.backend == "ollama":
            return np.stack([self._ollama_embed(t) for t in texts]).astype(np.float32)
        return np.stack([_hash_embed(t, self.dim) for t in texts]).astype(np.float32)

    def _ollama_embed(self, text: str) -> np.ndarray:
        import os

        import httpx

        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        model = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        headers: dict = {}
        if "ollama.com" in host:
            key = os.environ.get("OLLAMA_API_KEY", "")
            k = key.strip().strip("\"'").strip()
            if k[:7].lower() == "bearer ":
                k = k[7:].strip().strip("\"'").strip()
            k = "".join(k.split())
            if k:
                headers["Authorization"] = f"Bearer {k}"
        try:
            r = httpx.post(
                f"{host}/api/embeddings",
                json={"model": model, "prompt": text},
                headers=headers or None,
                timeout=15,
            )
            r.raise_for_status()
            v = np.asarray(r.json()["embedding"], dtype=np.float32)
            if v.shape[0] != self.dim and self.dim == _DIM:
                # project/truncate to fixed dim for sqlite-vec compat
                if v.shape[0] > self.dim:
                    v = v[: self.dim]
                else:
                    p = np.zeros(self.dim, dtype=np.float32)
                    p[: v.shape[0]] = v
                    v = p
                n = float(np.linalg.norm(v))
                if n > 0:
                    v /= n
            else:
                self.dim = int(v.shape[0])
            return v
        except Exception:
            return _hash_embed(text, self.dim)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    # Raw cosine clamped to [0, 1]. (An earlier (v+1)/2 mapping gave *unrelated*
    # texts a 0.5 baseline, which pushed cross-language false matches into the
    # serve band. Orthogonal = 0.0, identical = 1.0 — as calibration expects.)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return max(0.0, min(1.0, float(np.dot(a, b) / denom)))
