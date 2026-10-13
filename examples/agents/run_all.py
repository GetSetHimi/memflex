# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Run every usecase area against a live server with a REAL LLM.

Usage:
    python3 examples/agents/run_all.py --llm gemini/gemma-4-31b-it [--api http://localhost:8000]

Requires the API running with upstream keys in ITS env (never in files).
Writes examples/agents/REPORT.md with the per-area table.
"""
import argparse
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "examples/agents")

from reflex import Client
from runner import agent_answer
from scenarios import SCENARIOS
from tools import CALLS


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", default="gemini/gemma-4-31b-it")
    ap.add_argument("--api", default="http://localhost:8000")
    args = ap.parse_args()
    rx = Client(args.api)
    before = rx._http.get("/metrics").json()
    lines = [f"# Agent runs — {args.llm} — {datetime.datetime.now().isoformat(timespec='minutes')}",
             "", f"Baseline: asks={before['asks']} hit_rate={before['hit_rate']}", ""]
    totals = {"asks": 0, "llm_miss": 0, "reflex": 0, "tools": 0, "llm_calls": 0}
    for area, (user, turns) in SCENARIOS.items():
        lines += [f"## {area} (user {user})"]
        for i, (msg, ctx) in enumerate(turns, 1):
            CALLS.clear()
            out = {"answer": "ERROR: all retries failed", "source": "error",
                   "tools": [], "llm_calls": 0}
            for attempt in range(3):
                try:
                    out = agent_answer(rx, args.llm, f"agent_{user}", msg, dict(ctx))
                    break
                except Exception as e:
                    out = {"answer": f"ERROR: {e}"[:120], "source": "error",
                           "tools": [], "llm_calls": 0}
                    print(f"  [retry {attempt + 1}/3 after: {str(e)[:80]}]", flush=True)
            totals["asks"] += 1
            totals["tools"] += len(out.get("tools", []))
            totals["llm_calls"] += out.get("llm_calls", 0)
            if out["source"] == "llm+tools":
                totals["llm_miss"] += 1
            elif out["source"].startswith("reflex"):
                totals["reflex"] += 1
            line = (f"- run{i} [{out['source']}] tools={out.get('tools', [])} "
                    f"llm_calls={out.get('llm_calls', 0)} :: {msg[:50]!r} → {out['answer'][:90]!r}")
            print(line, flush=True)
            lines.append(line)
        lines.append("")
    after = rx._http.get("/metrics").json()
    lines += ["## Totals",
              f"- asks={totals['asks']} novel(miss)={totals['llm_miss']} "
              f"memory={totals['reflex']} tool_executions={totals['tools']} "
              f"provider_calls={totals['llm_calls']}",
              f"- server metrics: asks={after['asks']} hit_rate={after['hit_rate']} "
              f"saved_rs={after['cost_saved_30d_inr']} reflexes={after['reflex_count']}"]
    open("examples/agents/REPORT.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines[-6:]))
    print("\nREPORT.md written.")


if __name__ == "__main__":
    main()
