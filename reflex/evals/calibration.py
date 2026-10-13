# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Calibration buckets — the money chart: conf 0.9+ band accuracy."""
from __future__ import annotations

BUCKETS = [(0.0, 0.65, "low"), (0.65, 0.85, "uncertain"), (0.85, 0.95, "high"), (0.95, 1.01, "very_high")]


def calibration_buckets(reflexes) -> list[dict]:
    out = []
    for lo, hi, name in BUCKETS:
        members = [r for r in reflexes if lo <= float(r.confidence) < hi]
        if not members:
            out.append({"band": name, "range": [lo, hi], "n": 0, "est_accuracy": None})
            continue
        # estimated accuracy from hit consistency (no labels in prod)
        tot_h = sum(r.hits for r in members)
        tot_c = sum(r.corrections for r in members)
        acc = tot_h / max(1, tot_h + tot_c)
        out.append({"band": name, "range": [lo, hi], "n": len(members), "est_accuracy": round(acc, 3)})
    return out
