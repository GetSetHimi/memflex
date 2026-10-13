# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""reflex.plug: one-liner pre-pointed SDK clients (openai/anthropic lazy)."""
import sys
import types


def _fake_sdk(name: str, cls_name: str, holder: dict):
    mod = types.ModuleType(name)
    cls = type(cls_name, (), {"__init__": lambda self, **kw: holder.update(kw)})
    setattr(mod, cls_name, cls)
    sys.modules[name] = mod


def test_openai_client_points_at_reflex(monkeypatch):
    holder: dict = {}
    _fake_sdk("openai", "OpenAI", holder)
    monkeypatch.setenv("REFLEX_URL", "http://myhost:9000")
    monkeypatch.setenv("REFLEX_KEY", "k-1")
    from reflex.plug import openai_client

    openai_client()
    assert holder["base_url"] == "http://myhost:9000/v1"
    assert holder["api_key"] == "k-1"


def test_anthropic_client_points_at_reflex(monkeypatch):
    holder = {}
    _fake_sdk("anthropic", "Anthropic", holder)
    monkeypatch.setenv("REFLEX_URL", "http://myhost:9000/")
    from reflex.plug import anthropic_client

    anthropic_client()
    assert holder["base_url"] == "http://myhost:9000/v1"


def test_missing_sdk_gives_pip_hint(monkeypatch):
    import sys

    monkeypatch.delitem(sys.modules, "openai", raising=False)
    for mod in [m for m in sys.modules if m == "openai" or m.startswith("openai.")]:
        monkeypatch.delitem(sys.modules, mod, raising=False)
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "openai" or name.startswith("openai."):
            raise ImportError("No module named 'openai'")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    from reflex.plug import openai_client

    try:
        openai_client()
        raise AssertionError("should have raised")
    except ImportError as e:
        assert "pip install openai" in str(e)
