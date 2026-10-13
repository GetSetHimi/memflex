# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
import json
import os
os.environ["EMBEDDING_BACKEND"] = "hash"

from reflex.core.normalizer import normalize_situation
from reflex.llm.base import MockProvider


def test_hindi_suite():
    path = os.path.join(os.path.dirname(__file__), "../reflex/evals/hindi_suite.json")
    suite = json.load(open(path, encoding="utf-8"))
    mock = MockProvider()
    for case in suite:
        norm = normalize_situation(case["message"])
        assert norm, case
        ans = mock.complete(case["message"]).text
        # mock is Hindi-aware; just ensure non-empty + normalization stable
        assert len(ans) > 3
        assert normalize_situation(case["message"]) == norm
