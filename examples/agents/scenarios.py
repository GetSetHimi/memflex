# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Real-world scenario scripts per usecase area. Each turn: (message, context)."""
SCENARIOS = {
    "support_refund": ("rani", [
        ("When will my refund arrive? Order ORD-7741", {"order_id": "ORD-7741"}),
        ("When will my refund arrive? Order ORD-7741", {"order_id": "ORD-7741"}),
        ("mera refund kab ayega ORD-7741?", {"order_id": "ORD-7741"}),
        ("refund??", {}),
    ]),
    "support_cancel": ("amit", [
        ("Please cancel my order ORD-2203, wrong size ordered", {"order_id": "ORD-2203"}),
        ("Please cancel my order ORD-2203, wrong size ordered", {"order_id": "ORD-2203"}),
    ]),
    "delivery_tracking": ("zara", [
        ("Where is my order ORD-9910? supposed to arrive today", {"order_id": "ORD-9910"}),
        ("Where is my order ORD-9910?", {"order_id": "ORD-9910"}),
        ("package?", {}),
    ]),
    "triage_routing": ("ops", [
        ("Customer charged twice on card ending 4412, very angry", {}),
        ("Customer charged twice on card ending 4412, very angry", {}),
    ]),
    "extraction": ("ops2", [
        ("What is the refund status for ticket T-555?", {"schema": {"refund_status": "str"}}),
        ("What is the refund status for ticket T-555?", {"schema": {"refund_status": "str"}}),
    ]),
    "voice_short": ("driver", [
        ("Refund status?", {}),
        ("Refund status?", {}),
    ]),
    "multilingual_de": ("hans", [
        ("Wo ist meine Rückerstattung? Bestellung ORD-3130", {"order_id": "ORD-3130"}),
        ("Wo ist meine Rueckerstattung? Bestellung ORD-3130", {"order_id": "ORD-3130"}),
    ]),
    "world_fr": ("pierre", [
        ("Où est mon remboursement ? Commande ORD-4410", {"order_id": "ORD-4410"}),
        ("Où est mon remboursement ? Commande ORD-4410", {"order_id": "ORD-4410"}),
    ]),
    "world_es": ("carmen", [
        ("Por favor cancele mi pedido ORD-5521", {"order_id": "ORD-5521"}),
        ("Por favor cancele mi pedido ORD-5521", {"order_id": "ORD-5521"}),
    ]),
    "world_ta": ("divya", [
        ("எனது பணம் திரும்ப எப்போது வரும்? ஆர்டர் ORD-6632", {"order_id": "ORD-6632"}),
        ("எனது பணம் திரும்ப எப்போது வரும்? ஆர்டர் ORD-6632", {"order_id": "ORD-6632"}),
    ]),
    "world_ja": ("yuki", [
        ("注文 ORD-7743 はどこですか?", {"order_id": "ORD-7743"}),
        ("注文 ORD-7743 はどこですか?", {"order_id": "ORD-7743"}),
    ]),
    "world_pt": ("ana", [
        ("Qual é o status do meu reembolso? Pedido ORD-8854", {"order_id": "ORD-8854"}),
        ("Qual é o status do meu reembolso? Pedido ORD-8854", {"order_id": "ORD-8854"}),
    ]),
}
