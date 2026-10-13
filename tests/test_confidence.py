# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
from datetime import datetime, timezone
from reflex.core import confidence as conf


def test_score_bounds():
    now = datetime.now(timezone.utc)
    s = conf.score(0.95, 10, 0, now)
    assert 0.0 <= s <= 1.0
    assert conf.route(0.9) == "reflex"
    assert conf.route(0.7) == "reflex+reverify"
    assert conf.route(0.2) == "llm"


def test_corrections_lower_score():
    now = datetime.now(timezone.utc)
    good = conf.score(0.9, 10, 0, now)
    bad = conf.score(0.9, 5, 5, now)
    assert good > bad
