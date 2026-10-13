# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Calibrated confidence engine — §4.3 of the doc."""
from __future__ import annotations
from datetime import datetime, timezone


def hit_consistency(hits: int, corrections: int) -> float:
    total = hits + corrections
    if total == 0:
        return 0.5
    return hits / total


def recency_score(last_verified_at: datetime, ttl_days: int = 30) -> float:
    now = datetime.now(timezone.utc)
    if last_verified_at.tzinfo is None:
        last_verified_at = last_verified_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - last_verified_at).total_seconds() / 86400.0)
    return max(0.0, 1.0 - age_days / max(1, ttl_days))


def correction_rate(hits: int, corrections: int) -> float:
    total = hits + corrections
    if total == 0:
        return 0.0
    return corrections / total


def score(
    similarity: float,
    hits: int,
    corrections: int,
    last_verified_at: datetime,
    ttl_days: int = 30,
    w_sim: float = 0.6,
    w_hit: float = 0.2,
    w_recency: float = 0.1,
    w_correction: float = 0.5,
) -> float:
    s = (
        w_sim * similarity
        + w_hit * hit_consistency(hits, corrections)
        + w_recency * recency_score(last_verified_at, ttl_days)
        - w_correction * correction_rate(hits, corrections)
    )
    return max(0.0, min(1.0, s))


def route(score_value: float, serve_threshold: float = 0.85, uncertain_band: float = 0.65) -> str:
    if score_value >= serve_threshold:
        return "reflex"
    if score_value >= uncertain_band:
        return "reflex+reverify"
    return "llm"
