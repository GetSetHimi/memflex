# Copyright (c) 2026 Himanshu Sharma — Reflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""SQLite-vec lite store — single-file, zero-dep self-host.

Tables: reflexes (metadata), reflex_vec (sqlite-vec virtual table), memories.
Falls back to brute-force numpy scan if sqlite-vec extension unavailable.
"""
from __future__ import annotations
import json
import os
import sqlite3
from datetime import datetime, timezone

import numpy as np

from reflex.core.models import Decision, Memory, Reflex
from reflex.stores.embeddings import cosine

SCHEMA = """
CREATE TABLE IF NOT EXISTS reflexes(
  id TEXT PRIMARY KEY, user_id TEXT, situation TEXT,
  action TEXT, payload TEXT, structured TEXT,
  confidence REAL, hits INTEGER, corrections INTEGER, source TEXT,
  created_at TEXT, last_verified_at TEXT, ttl_days INTEGER
);
CREATE TABLE IF NOT EXISTS memories(
  id TEXT PRIMARY KEY, subject TEXT, fact TEXT,
  confidence REAL, last_confirmed_at TEXT, contradictions TEXT
);
CREATE TABLE IF NOT EXISTS reflex_emb(
  id TEXT PRIMARY KEY, vec BLOB, dim INTEGER
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


class SqliteReflexStore:
    def __init__(self, path: str = "./data/reflex.db", dim: int = 256):
        self.path = path
        self.dim = dim
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._con = sqlite3.connect(path, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.executescript(SCHEMA)
        self._use_vec = self._init_vec()

    def _init_vec(self) -> bool:
        try:
            import sqlite_vec  # type: ignore

            self._con.enable_load_extension(True)
            sqlite_vec.load(self._con)
            self._con.enable_load_extension(False)
            self._con.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS reflex_vec USING vec0(id TEXT PRIMARY KEY, embedding FLOAT[%d])" % self.dim
            )
            return True
        except Exception:
            return False

    # -- writes --
    def save_reflex(self, r: Reflex, embedding: np.ndarray) -> Reflex:
        if embedding.shape[0] != self.dim:
            # adapt dim on first write for ollama/sbert dims
            self.dim = int(embedding.shape[0])
        self._con.execute(
            "INSERT OR REPLACE INTO reflexes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                r.id, r.user_id, r.situation, r.decision.action, r.decision.payload,
                json.dumps(r.decision.structured) if r.decision.structured else None,
                r.confidence, r.hits, r.corrections, r.source,
                _iso(r.created_at), _iso(r.last_verified_at), r.ttl_days,
            ),
        )
        self._con.execute(
            "INSERT OR REPLACE INTO reflex_emb VALUES (?,?,?)",
            (r.id, np.asarray(embedding, dtype=np.float32).tobytes(), int(embedding.shape[0])),
        )
        if self._use_vec:
            try:
                self._con.execute("DELETE FROM reflex_vec WHERE id=?", (r.id,))
                self._con.execute(
                    "INSERT INTO reflex_vec(id, embedding) VALUES (?, ?)",
                    (r.id, json.dumps([float(x) for x in np.asarray(embedding, dtype=np.float32)])),
                )
            except Exception:
                pass
        self._con.commit()
        return r

    def record_hit(self, reflex_id: str) -> None:
        self._con.execute("UPDATE reflexes SET hits=hits+1 WHERE id=?", (reflex_id,))
        self._con.commit()

    def record_correction(self, reflex_id: str) -> None:
        self._con.execute(
            "UPDATE reflexes SET corrections=corrections+1, confidence=max(0.05, confidence-0.08) WHERE id=?",
            (reflex_id,),
        )
        self._con.commit()

    def touch_verified(self, reflex_id: str, confidence: float | None = None) -> None:
        now = _iso(datetime.now(timezone.utc))
        if confidence is None:
            self._con.execute("UPDATE reflexes SET last_verified_at=? WHERE id=?", (now, reflex_id))
        else:
            self._con.execute(
                "UPDATE reflexes SET last_verified_at=?, confidence=? WHERE id=?", (now, confidence, reflex_id)
            )
        self._con.commit()

    def update_reflex(self, reflex_id: str, ttl_days: int | None = None,
                        confidence: float | None = None) -> None:
        sets, vals = [], []
        if ttl_days is not None:
            sets.append("ttl_days=?")
            vals.append(ttl_days)
        if confidence is not None:
            sets.append("confidence=?")
            vals.append(confidence)
        if sets:
            vals.append(reflex_id)
            self._con.execute(f"UPDATE reflexes SET {', '.join(sets)} WHERE id=?", vals)
            self._con.commit()

    def delete_reflex(self, reflex_id: str) -> bool:
        c = self._con.execute("DELETE FROM reflexes WHERE id=?", (reflex_id,))
        self._con.execute("DELETE FROM reflex_emb WHERE id=?", (reflex_id,))
        if self._use_vec:
            try:
                self._con.execute("DELETE FROM reflex_vec WHERE id=?", (reflex_id,))
            except Exception:
                pass
        self._con.commit()
        return (c.rowcount or 0) > 0

    # -- reads --
    def _row_to_reflex(self, row: sqlite3.Row) -> Reflex:
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
        row = self._con.execute("SELECT * FROM reflexes WHERE id=?", (reflex_id,)).fetchone()
        return self._row_to_reflex(row) if row else None

    def find_by_situation(self, user_id: str, situation: str) -> Reflex | None:
        row = self._con.execute(
            "SELECT * FROM reflexes WHERE user_id=? AND situation=?", (user_id, situation)
        ).fetchone()
        return self._row_to_reflex(row) if row else None

    # -- per-user conversation context (survives restarts; powers follow-ups) --
    def set_last_message(self, user_id: str, message: str) -> None:
        if not user_id:
            return
        self._con.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", (f"lastmsg:{user_id}", message))
        self._con.commit()

    def get_last_message(self, user_id: str) -> str:
        if not user_id:
            return ""
        row = self._con.execute("SELECT v FROM kv WHERE k=?", (f"lastmsg:{user_id}",)).fetchone()
        return row[0] if row else ""

    def list_reflexes(self, user_id: str = "") -> list[Reflex]:
        if user_id:
            rows = self._con.execute("SELECT * FROM reflexes WHERE user_id=? ORDER BY confidence DESC", (user_id,)).fetchall()
        else:
            rows = self._con.execute("SELECT * FROM reflexes ORDER BY confidence DESC").fetchall()
        return [self._row_to_reflex(r) for r in rows]

    def search(self, embedding: np.ndarray, user_id: str = "", top_k: int = 5) -> list[tuple[Reflex, float]]:
        q = np.asarray(embedding, dtype=np.float32)
        if self._use_vec:
            try:
                js = json.dumps([float(x) for x in q[: self.dim]])
                if user_id:
                    ids = [r["id"] for r in self._con.execute("SELECT id FROM reflexes WHERE user_id=?", (user_id,)).fetchall()]
                    if not ids:
                        return []
                    ph = ",".join("?" for _ in ids)
                    rows = self._con.execute(
                        f"SELECT id, distance FROM reflex_vec WHERE embedding MATCH ? AND id IN ({ph}) ORDER BY distance LIMIT {int(top_k)}",
                        (js, *ids),
                    ).fetchall()
                else:
                    rows = self._con.execute(
                        f"SELECT id, distance FROM reflex_vec WHERE embedding MATCH ? ORDER BY distance LIMIT {int(top_k)}",
                        (js,),
                    ).fetchall()
                out = []
                for r in rows:
                    rx = self.get_reflex(r["id"])
                    if rx:
                        sim = max(0.0, min(1.0, 1.0 - float(r["distance"]) / 2.0))
                        out.append((rx, sim))
                if out:
                    return out
            except Exception:
                pass
        # brute-force fallback
        rows = self._con.execute("SELECT * FROM reflexes" + (" WHERE user_id=?" if user_id else ""), ((user_id,) if user_id else ())).fetchall()
        embs = {r[0]: r[1] for r in self._con.execute("SELECT id, vec FROM reflex_emb").fetchall()}
        scored: list[tuple[Reflex, float]] = []
        for row in rows:
            rx = self._row_to_reflex(row)
            blob = embs.get(rx.id)
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

    # -- memories --
    def save_memory(self, m: Memory) -> Memory:
        self._con.execute(
            "INSERT OR REPLACE INTO memories VALUES (?,?,?,?,?,?)",
            (m.id, m.subject, m.fact, m.confidence, _iso(m.last_confirmed_at), json.dumps(m.contradictions)),
        )
        self._con.commit()
        return m

    def list_memories(self, subject: str = "") -> list[Memory]:
        rows = self._con.execute(
            "SELECT * FROM memories" + (" WHERE subject=?" if subject else ""), ((subject,) if subject else ())
        ).fetchall()
        out = []
        for r in rows:
            out.append(Memory(
                id=r["id"], subject=r["subject"], fact=r["fact"], confidence=float(r["confidence"]),
                last_confirmed_at=_parse_dt(r["last_confirmed_at"]),
                contradictions=json.loads(r["contradictions"]) if r["contradictions"] else [],
            ))
        return out
