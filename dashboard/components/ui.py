# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Console UI kit — brand topbar, KPI cards, badges, relative time, empty states."""
import html
import pathlib
from datetime import datetime, timezone

import streamlit as st


def inject_css() -> None:
    css = pathlib.Path(__file__).with_name("..").joinpath("style.css").resolve()
    try:
        st.markdown(f"<style>{css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


def topbar(connected: bool, api_url: str) -> None:
    dot = "ok" if connected else "down"
    state = "Connected" if connected else "API unreachable"
    st.markdown(
        f"""<div class="mx-topbar">
        <svg width="26" height="26" viewBox="0 0 32 32" fill="none">
          <rect x="2" y="2" width="28" height="28" rx="8" fill="#c8ff2e"/>
          <path d="M9 21c4-1 5-8 9-9 2.4-.6 4 .8 5 2" stroke="#0c0e02"
                stroke-width="2.6" stroke-linecap="round"/>
          <circle cx="22.5" cy="11.5" r="2.2" fill="#0c0e02"/>
        </svg>
        <span class="mx-brand">memflex console</span>
        <span class="mx-dot {dot}"></span>
        <span class="mx-sub">{html.escape(state)} · {html.escape(api_url)}</span>
        </div>""",
        unsafe_allow_html=True,
    )


def kpi_row(cards: list[tuple[str, str]]) -> None:
    # One HTML grid (not st.columns): auto-fit wraps cards on narrow screens
    # instead of squeezing N columns into unreadability.
    cells = "".join(
        f'<div class="mx-kpi"><div class="v">{value}</div>'
        f'<div class="l">{html.escape(label)}</div></div>'
        for value, label in cards
    )
    st.markdown(f'<div class="mx-kpis">{cells}</div>', unsafe_allow_html=True)


def source_badge(source: str) -> str:
    kind = "llm" if source == "llm" else "reflex"
    label = "LLM call" if source == "llm" else "Reflex answer"
    return f'<span class="mx-badge {kind}">{label}</span>'


def conf_bar(confidence: float) -> None:
    st.progress(min(1.0, max(0.0, float(confidence or 0))), text=f"confidence {float(confidence or 0):.2f}")


def reltime(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = max(0, int((datetime.now(timezone.utc) - dt).total_seconds()))
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return iso or "—"


def empty_state(title: str, hint: str) -> None:
    st.info(f"**{title}**  \n{hint}")
