# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Postgres store — same Protocol as SQLite-vec, for production scale.

- Metadata tables mirror the SQLite schema (reflexes, memories, kv).
- Vectors: pgvector `vector(dim)` column when the extension exists
  (cosine `<=>` ordering in-DB); otherwise BYTEA blobs + Python brute
  force — identical fallback strategy to the SQLite store.
- Incoming embeddings are resized (truncate/zero-pad) to the store dim,
  so embedding-backend swaps never break the table.
- Needs: pip install "psycopg[binary]" + a reachable Postgres.
  DSN via REFLEX_POSTGRES_DSN, e.g.
  postgresql://user:pass@localhost:5432/reflex
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone

import numpy as np

from reflex.core.models import Decision, Memory, Reflex
from reflex.stores.embeddings import cosine

SCHEMA = """
CREATE TABLE IF NOT EXISTS reflexes(
  id TEXT PRIMARY KEY, user_id TEXT, situation TEXT,
  action TEXT, payload TEXT, structured TEXT,
  confidence DOUBLE PRECISION, hits INTEGER, corrections INTEGER, source TEXT,
  created_at TEXT, last_verified_at TEXT, ttl_days INTEGER
);
CREATE INDEX IF NOT EXISTS idx_reflexes_user ON reflexes(user_id);
CREATE TABLE IF NOT EXISTS memories(
  id TEXT PRIMARY KEY, subject TEXT, fact TEXT,
  confidence DOUBLE PRECISION, last_confirmed_at TEXT, contradictions TEXT
);
CREATE TABLE IF NOT EXISTS reflex_emb(
  id TEXT PRIMARY KEY, vec BYTEA, dim INTEGER
);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
"""


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_dt(s: str) -> datetime:
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return datetime.now(timezone.utc)


class PostgresReflexStore:
    def __init__(self, dsn: str = "", dim: int = 256):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as e:
            raise RuntimeError(
                'Postgres store needs psycopg: pip install "psycopg[binary]" '
                "and set REFLEX_POSTGRES_DSN."
            ) from e
        dsn = dsn or os.environ.get("REFLEX_POSTGRES_DSN", "")
        if not dsn:
            raise RuntimeError("REFLEX_POSTGRES_DSN is not set.")
        self.dim = dim
        self._con = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)
        with self._con.cursor() as cur:
            cur.execute(SCHEMA)
        self._use_vec = self._init_vec()

    def _init_vec(self) -> bool:
        try:
            with self._con.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS reflex_vec"
                    f"(id TEXT PRIMARY KEY, embedding vector({self.dim}))"
                )
                cur.execute("SELECT '[1]'::vector <-> '[2]'::vector")
            return True
        except Exception:
            return False

    def _fit(self, embedding: np.ndarray) -> np.ndarray:
        v = np.asarray(embedding, dtype=np.float32).ravel()
        if v.shape[0] == self.dim:
            return v
        out = np.zeros(self.dim, dtype=np.float32)
        n = min(v.shape[0], self.dim)
        out[:n] = v[:n]
        return out

    # -- writes --
    def save_reflex(self, r: Reflex, embedding: np.ndarray) -> Reflex:
        v = self._fit(np.asarray(embedding, dtype=np.float32))
        with self._con.cursor() as cur:
            cur.execute(
                """INSERT INTO reflexes VALUES
                   (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET
                   user_id=EXCLUDED.user_id, situation=EXCLUDED.situation,
                   action=EXCLUDED.action, payload=EXCLUDED.payload,
                   structured=EXCLUDED.structured, confidence=EXCLUDED.confidence,
                   hits=EXCLUDED.hits, corrections=EXCLUDED.corrections,
                   source=EXCLUDED.source, created_at=EXCLUDED.created_at,
                   last_verified_at=EXCLUDED.last_verified_at, ttl_days=EXCLUDED.ttl_days""",
                (r.id, r.user_id, r.situation, r.decision.action, r.decision.payload,
                 json.dumps(r.decision.structured) if r.decision.structured else None,
                 r.confidence, r.hits, r.corrections, r.source,
                 _iso(r.created_at), _iso(r.last_verified_at), r.ttl_days),
            )
            cur.execute(
                "INSERT INTO reflex_emb VALUES (%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET vec=EXCLUDED.vec, dim=EXCLUDED.dim",
                (r.id, v.tobytes(), self.dim),
            )
            if self._use_vec:
                try:
                    cur.execute(
                        "INSERT INTO reflex_vec VALUES (%s,%s) "
                        "ON CONFLICT (id) DO UPDATE SET embedding=EXCLUDED.embedding",
                        (r.id, "[" + ",".join(f"{x:.6f}" for x in v) + "]"),
                    )
                except Exception:
                    pass
        return r

    def record_hit(self, reflex_id: str) -> None:
        with self._con.cursor() as cur:
            cur.execute("UPDATE reflexes SET hits=hits+1 WHERE id=%s", (reflex_id,))

    def record_correction(self, reflex_id: str) -> None:
        with self._con.cursor() as cur:
            cur.execute(
                "UPDATE reflexes SET corrections=corrections+1, "
                "confidence=greatest(0.05, confidence-0.08) WHERE id=%s",
                (reflex_id,),
            )

    def touch_verified(self, reflex_id: str, confidence: float | None = None) -> None:
        now = _iso(datetime.now(timezone.utc))
        with self._con.cursor() as cur:
            if confidence is None:
                cur.execute("UPDATE reflexes SET last_verified_at=%s WHERE id=%s", (now, reflex_id))
            else:
                cur.execute(
                    "UPDATE reflexes SET last_verified_at=%s, confidence=%s WHERE id=%s",
                    (now, confidence, reflex_id),
                )

    def update_reflex(self, reflex_id: str, ttl_days: int | None = None,
                        confidence: float | None = None) -> None:
        sets, vals = [], []
        if ttl_days is not None:
            sets.append("ttl_days=%s")
            vals.append(ttl_days)
        if confidence is not None:
            sets.append("confidence=%s")
            vals.append(confidence)
        if sets:
            vals.append(reflex_id)
            with self._con.cursor() as cur:
                cur.execute(f"UPDATE reflexes SET {', '.join(sets)} WHERE id=%s", vals)

    def delete_reflex(self, reflex_id: str) -> bool:
        with self._con.cursor() as cur:
            cur.execute("DELETE FROM reflexes WHERE id=%s", (reflex_id,))
            gone = (cur.rowcount or 0) > 0
            cur.execute("DELETE FROM reflex_emb WHERE id=%s", (reflex_id,))
            if self._use_vec:
                try:
                    cur.execute("DELETE FROM reflex_vec WHERE id=%s", (reflex_id,))
                except Exception:
                    pass
            return gone

    # -- reads --
    @staticmethod
    def _row_to_reflex(row: dict) -> Reflex:
        return Reflex(
            id=row["id"], user_id=row["user_id"] or "",
            situation=row["situation"],
            decision=Decision(
                action=row["action"] or "answer_template", payload=row["payload"] or "",
                structured=json.loads(row["structured"]) if row["structured"] else None,
            ),
            confidence=float(row["confidence"]), hits=int(row["hits"]),
            corrections=int(row["corrections"]), source=row["source"] or "",
            created_at=_parse_dt(row["created_at"]), last_verified_at=_parse_dt(row["last_verified_at"]),
            ttl_days=int(row["ttl_days"] or 30),
        )

    def get_reflex(self, reflex_id: str) -> Reflex | None:
        with self._con.cursor() as cur:
            row = cur.execute("SELECT * FROM reflexes WHERE id=%s", (reflex_id,)).fetchone()
            return self._row_to_reflex(row) if row else None

    def find_by_situation(self, user_id: str, situation: str) -> Reflex | None:
        with self._con.cursor() as cur:
            row = cur.execute(
                "SELECT * FROM reflexes WHERE user_id=%s AND situation=%s", (user_id, situation)
            ).fetchone()
            return self._row_to_reflex(row) if row else None

    def list_reflexes(self, user_id: str = "") -> list[Reflex]:
        with self._con.cursor() as cur:
            if user_id:
                rows = cur.execute(
                    "SELECT * FROM reflexes WHERE user_id=%s ORDER BY confidence DESC", (user_id,)
                ).fetchall()
            else:
                rows = cur.execute("SELECT * FROM reflexes ORDER BY confidence DESC").fetchall()
            return [self._row_to_reflex(r) for r in rows]

    def search(self, embedding: np.ndarray, user_id: str = "", top_k: int = 5) -> list[tuple[Reflex, float]]:
        q = self._fit(np.asarray(embedding, dtype=np.float32))
        if self._use_vec:
            try:
                lit = "[" + ",".join(f"{x:.6f}" for x in q) + "]"
                with self._con.cursor() as cur:
                    if user_id:
                        rows = cur.execute(
                            f"""SELECT r.*, v.embedding <=> '{lit}'::vector AS dist FROM reflex_vec v
                                JOIN reflexes r ON r.id = v.id
                                WHERE r.user_id=%s ORDER BY dist LIMIT {int(top_k)}""",
                            (user_id,),
                        ).fetchall()
                    else:
                        rows = cur.execute(
                            f"""SELECT r.*, v.embedding <=> '{lit}'::vector AS dist FROM reflex_vec v
                                JOIN reflexes r ON r.id = v.id
                                ORDER BY dist LIMIT {int(top_k)}""",
                        ).fetchall()
                out = []
                for row in rows:
                    dist = float(row.pop("dist"))
                    out.append((self._row_to_reflex(row), max(0.0, min(1.0, 1.0 - dist))))
                if out:
                    return out
            except Exception:
                pass
        with self._con.cursor() as cur:
            if user_id:
                rows = cur.execute("SELECT * FROM reflexes WHERE user_id=%s", (user_id,)).fetchall()
            else:
                rows = cur.execute("SELECT * FROM reflexes").fetchall()
            blobs = {r["id"]: bytes(r["vec"]) for r in cur.execute("SELECT id, vec FROM reflex_emb").fetchall()}
        scored: list[tuple[Reflex, float]] = []
        for row in rows:
            rx = self._row_to_reflex(row)
            blob = blobs.get(rx.id)
            if blob is None:
                continue
            v = np.frombuffer(blob, dtype=np.float32)
            if v.shape[0] != q.shape[0]:
                n = min(v.shape[0], q.shape[0])
                v, qq = v[:n], q[:n]
            else:
                qq = q
            scored.append((rx, cosine(qq, v)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # -- memories + kv --
    def save_memory(self, m: Memory) -> Memory:
        with self._con.cursor() as cur:
            cur.execute(
                "INSERT INTO memories VALUES (%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET subject=EXCLUDED.subject, fact=EXCLUDED.fact, "
                "confidence=EXCLUDED.confidence, last_confirmed_at=EXCLUDED.last_confirmed_at, "
                "contradictions=EXCLUDED.contradictions",
                (m.id, m.subject, m.fact, m.confidence, _iso(m.last_confirmed_at),
                 json.dumps(m.contradictions)),
            )
        return m

    def list_memories(self, subject: str = "") -> list[Memory]:
        with self._con.cursor() as cur:
            if subject:
                rows = cur.execute("SELECT * FROM memories WHERE subject=%s", (subject,)).fetchall()
            else:
                rows = cur.execute("SELECT * FROM memories").fetchall()
        return [Memory(
            id=r["id"], subject=r["subject"], fact=r["fact"], confidence=float(r["confidence"]),
            last_confirmed_at=_parse_dt(r["last_confirmed_at"]),
            contradictions=json.loads(r["contradictions"]) if r["contradictions"] else [],
        ) for r in rows]

    def set_last_message(self, user_id: str, message: str) -> None:
        if not user_id:
            return
        with self._con.cursor() as cur:
            cur.execute(
                "INSERT INTO kv VALUES (%s,%s) ON CONFLICT (k) DO UPDATE SET v=EXCLUDED.v",
                (f"lastmsg:{user_id}", message),
            )

    def get_last_message(self, user_id: str) -> str:
        if not user_id:
            return ""
        with self._con.cursor() as cur:
            row = cur.execute("SELECT v FROM kv WHERE k=%s", (f"lastmsg:{user_id}",)).fetchone()
            return row["v"] if row else ""
