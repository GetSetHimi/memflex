# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Memflex console — what your agent remembers vs what it pays for.

Run:  python3 -m streamlit run dashboard/app.py   → http://localhost:8501
Env:  REFLEX_API_URL (default http://localhost:8000)
      MEMFLEX_API_KEY (forwarded as X-API-Key when the server is locked)
"""
import html
import time

import pandas as pd
import streamlit as st

from components.api import API, api_delete, api_get, api_patch, api_post
from components.ui import conf_bar, empty_state, inject_css, kpi_row, reltime, source_badge, topbar

st.set_page_config(page_title="Memflex console", layout="wide")
inject_css()

with st.sidebar:
    st.subheader("Session")
    auto = st.checkbox("Auto-refresh every 5s", value=False)
    limit = st.slider("Activity rows", 20, 500, 100, 20)
    if st.button("Refresh now", width="stretch"):
        st.rerun()
if auto:
    time.sleep(5)
    st.rerun()

try:
    m = api_get("/metrics")
    connected = True
except Exception as e:
    topbar(False, API)
    st.error("Console can't reach the API. Start it first: `python3 -m reflex.api.app`")
    st.caption(str(e))
    st.stop()

try:
    act = api_get("/activity", params={"limit": limit})
except Exception as e:
    topbar(False, API)
    st.error(f"Activity feed failed: {e}")
    st.stop()

topbar(True, API)
st.title("What your agent remembers vs what it pays for")
st.caption("Every LLM call costs money and seconds. Every reflex answer costs neither. This console proves it, live.")

items = act.get("items", [])
llm_rows = [a for a in items if a.get("source") == "llm"]
reflex_rows = [a for a in items if a.get("source") != "llm"]

kpi_row([
    (str(m.get("asks", 0)), "Asks (lifetime)"),
    (f"<em>{m.get('hit_rate', 0) * 100:.1f}%</em>", "Hit rate"),
    (str(act.get("llm_calls", m.get("llm_calls", 0))), "LLM calls (window)"),
    (f"<em>{act.get('reflex_answers', 0)}</em>", "Reflex answers (window)"),
    (f"₹{m.get('cost_saved_30d_inr', 0)}", "Saved"),
    (str(m.get("reflex_count", 0)), "Memories stored"),
    (f"{act.get('avg_latency_ms_llm', 0)} ms", "Avg latency — LLM"),
    (f"{act.get('avg_latency_ms_reflex', 0)} ms", "Avg latency — reflex"),
])

tab_over, tab_live, tab_mem, tab_cal = st.tabs(["Overview", "Live activity", "Memory", "Calibration"])

with tab_over:
    st.subheader("Where answers come from")
    if items:
        split = pd.DataFrame(
            {"answers": [len(llm_rows), len(reflex_rows)]},
            index=["LLM calls", "Reflex answers"],
        )
        st.bar_chart(split, color=["#ffb86b", "#c8ff2e"])
        df = pd.DataFrame(items)
        df["ts"] = pd.to_datetime(df["ts"])
        lat = df.groupby([pd.Grouper(key="ts", freq="1min"), "source"])["latency_ms"].mean().unstack(fill_value=0)
        st.subheader("Latency over time (ms per minute)")
        st.line_chart(lat)
    else:
        empty_state("No traffic yet.", "Send an ask: open the API docs at :8000/docs → POST /ask → Try it out.")

with tab_live:
    st.subheader("Request log")
    f = st.radio("Filter", ["All", "LLM calls", "Reflex answers"], horizontal=True, label_visibility="collapsed")
    view = llm_rows if f == "LLM calls" else reflex_rows if f == "Reflex answers" else items
    st.caption(f"Showing {min(len(view), 100)} of {len(view)} · newest first · reflex rows made zero LLM calls.")
    if not view:
        empty_state("Nothing here yet.", "Traffic appears here the moment your agent asks something.")
    with st.container(height=560, border=False):
        for a in view[:100]:
            title = f"{a.get('user_id')} · {str(a.get('message'))[:72]} · {reltime(a.get('ts', ''))}"
            with st.expander(title):
                st.markdown(source_badge(a.get("source", "")), unsafe_allow_html=True)
                st.write(f"**Asked:** {a.get('message')}")
                st.write(f"**Answered:** {a.get('answer')}")
                conf_bar(a.get("confidence", 0))
                st.caption(
                    f"latency {a.get('latency_ms')} ms · model {a.get('llm_model') or '—'} · "
                    f"saved ₹{a.get('llm_cost_saved_inr')} · {html.escape(str(a.get('reflex_id')))}"
                )

with tab_mem:
    st.subheader("Stored memories")
    q = st.text_input("Filter situations", placeholder="type to filter, e.g. refund")
    try:
        rx = api_get("/reflexes")
    except Exception as e:
        st.warning(str(e))
        rx = []
    if q:
        rx = [r for r in rx if q.lower() in str(r.get("situation", "")).lower()]
    st.caption(f"{len(rx)} memories. Thumbs-up raises confidence · thumbs-down records a correction · delete erases.")
    if not rx:
        empty_state("Memory is empty.", "Memories appear after the first novel ask is distilled.")
    with st.container(height=560, border=False):
        for r in rx[:100]:
            rid = r.get("id")
            sit = str(r.get("situation", ""))[:84]
            with st.expander(f"{r.get('confidence', 0):.2f} · {r.get('hits', 0)} hits · {r.get('corrections', 0)} corrections · {sit}"):
                st.write(f"**Situation key:** `{r.get('situation')}`")
                d = r.get("decision", {}) or {}
                st.write(f"**Stored answer:** {d.get('payload')}")
                if d.get("structured"):
                    st.json(d["structured"])
                conf_bar(r.get("confidence", 0))
                st.caption(f"`{rid}` · {r.get('source')} · TTL {r.get('ttl_days')}d · verified {reltime(r.get('last_verified_at', ''))}")
                t1, t2 = st.columns([3, 2])
                new_ttl = t1.number_input("Memory lives (days)", min_value=1, max_value=365,
                                          value=int(r.get("ttl_days") or 30), key=f"ttl_{rid}")
                if t2.button("Set TTL", key=f"ttlgo_{rid}"):
                    try:
                        api_patch(f"/reflexes/{rid}", json={"ttl_days": int(new_ttl)})
                        st.toast(f"TTL set to {int(new_ttl)} days.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"TTL update failed: {e}")
                b1, b2, b3 = st.columns(3)
                if b1.button("Helpful", key=f"ok_{rid}"):
                    api_post(f"/reflexes/{rid}/feedback", json={"ok": True})
                    st.toast("Recorded — confidence raised.")
                    st.rerun()
                if b2.button("Wrong", key=f"no_{rid}"):
                    api_post(f"/reflexes/{rid}/feedback", json={"ok": False})
                    st.toast("Recorded — correction logged, confidence lowered.")
                    st.rerun()
                confirm_key = f"delc_{rid}"
                if not st.session_state.get(confirm_key):
                    if b3.button("Delete", key=f"del_{rid}"):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    st.warning("Delete this memory permanently?")
                    cc1, cc2 = st.columns(2)
                    if cc1.button("Yes, delete", key=f"yes_{rid}"):
                        try:
                            api_delete(f"/reflexes/{rid}")
                            st.session_state.pop(confirm_key, None)
                            st.toast("Memory erased.")
                        except Exception as e:
                            st.error(f"Delete failed (maybe already gone): {e}")
                        st.rerun()
                    if cc2.button("Keep it", key=f"keep_{rid}"):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
    st.divider()
    if st.button("Re-verify stale memories now"):
        try:
            res = api_post("/verify/run", params={"limit": 20})
            st.toast(f"Checked {res.get('checked', 0)}: {res.get('confirmed', 0)} confirmed, {res.get('flagged', 0)} flagged.")
        except Exception as e:
            st.error(str(e))

with tab_cal:
    st.subheader("Does 0.9 confidence mean 90% right?")
    st.caption("Estimated accuracy per band from hit consistency (hits ÷ hits+corrections). "
               "Automate the high band, escalate the rest — this curve is your customer pitch.")
    cal = m.get("calibration", [])
    if cal and any(b.get("n", 0) for b in cal):
        st.bar_chart(pd.DataFrame(cal).set_index("band")[["est_accuracy"]], color="#c8ff2e")
        st.dataframe(pd.DataFrame(cal), width="stretch", height=280)
    else:
        empty_state("No calibration yet.", "Bands populate once memories accumulate hits.")
