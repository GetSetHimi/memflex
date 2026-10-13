# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Realistic deterministic tools for agent demos (no network, stable outputs)."""
import hashlib

CALLS: list[str] = []


def _stable_pick(key: str, options: list):
    h = int(hashlib.sha256(key.encode()).hexdigest(), 16)
    return options[h % len(options)]


def get_order_status(order_id: str) -> str:
    CALLS.append(f"get_order_status({order_id})")
    state = _stable_pick(order_id, ["shipped, arriving in 2 days",
                                    "out for delivery today",
                                    "packed, ships tomorrow"])
    return f"Order {order_id}: {state}."


def refund_quote(order_id: str) -> str:
    CALLS.append(f"refund_quote({order_id})")
    amount = 500 + int(hashlib.sha256(order_id.encode()).hexdigest(), 16) % 4500
    return f"Order {order_id}: refund of Rs.{amount} approved, ETA 3-5 days."


def cancel_order(order_id: str) -> str:
    CALLS.append(f"cancel_order({order_id})")
    return f"Order {order_id}: cancelled. Refund initiated, ETA 3-5 days."


def triage_route(text: str) -> str:
    CALLS.append(f"triage_route({text[:40]!r})")
    low = text.lower()
    if any(k in low for k in ("refund", "रिफंड", "wapas", "rückerstatt", "charge", "bill")):
        return "queue=billing priority=high"
    if any(k in low for k in ("cancel", "storn", "रद्द")):
        return "queue=cancellations priority=normal"
    return "queue=general priority=normal"


TOOLS = {"get_order_status": get_order_status, "refund_quote": refund_quote,
         "cancel_order": cancel_order, "triage_route": triage_route}
