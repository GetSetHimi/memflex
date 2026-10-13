# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""LLM gateway — pluggable System-2 providers."""
from __future__ import annotations
from typing import Protocol


class LLMResponse:
    def __init__(self, text: str, model: str):
        self.text = text
        self.model = model
        # Populated only when the upstream returned function tool calls
        # (OpenAI-compatible backends called with tools=...).
        self.tool_calls = None
        self.finish_reason = None


class LLMProvider(Protocol):
    def complete(self, prompt: str, system: str = "") -> LLMResponse: ...


# Intent keywords per language — Mock answers in the SAME language it was asked.
# Hindi was the first plugin, not the only one: add (keywords, answers) to
# extend coverage. Anything unmatched falls through to a neutral echo.
_INTENTS = [
    ({"refund", "रिफंड", "wapas", "रिफन्ड", "पैसा", "రీఫండ్", "রিফান্ড",
      "rückerstattung", "rückzahlung", "erstatten",
      "remboursement", "reembolso", "devolução", "devolucao",
      "возврат", "рефанд", "返金", "払い戻し", "退款", "iade", "geri ödeme",
      "திரும்ப", "వాపసు", "রিফান্ড"},
     {"hi": "आपका रिफंड प्रोसेस हो रहा है, 3-5 दिन में वापस आ जाएगा।",
      "de": "Ihre Rückerstattung wird bearbeitet und kommt in 3–5 Tagen an.",
      "fr": "Votre remboursement est en cours, il arrivera dans 3 à 5 jours.",
      "es": "Su reembolso está en proceso y llegará en 3 a 5 días.",
      "pt": "Seu reembolso está sendo processado e chegará em 3 a 5 dias.",
      "ru": "Ваш возврат обрабатывается и поступит через 3–5 дней.",
      "ja": "返金手続き中です。3〜5日で到着します。",
      "zh": "您的退款正在处理中，将在3-5天内到账。",
      "tr": "İadeniz işleniyor, 3-5 gün içinde ulaşacak.",
      "ta": "உங்கள் தொகை திரும்பச் செலுத்தப்படுகிறது, 3-5 நாட்களில் வரும்.",
      "te": "మీ రీఫండ్ ప్రాసెస్ చేయబడుతోంది, 3-5 రోజుల్లో వస్తుంది.",
      "bn": "আপনার রিফান্ড প্রক্রিয়াকরণ চলছে, 3-5 দিনের মধ্যে আসবে।",
      "en": "Your refund is being processed and will arrive in 3-5 days."}),
    ({"cancel", "कैंसिल", "रद्द",
      "stornier", "kündig", "abbestell",
      "annul", "cancelar", "cancelamento",
      "отмена", "отменить", "キャンセル", "取消", "iptal"},
     {"hi": "आपका ऑर्डर कैंसिल कर दिया गया है। रिफंड 3-5 दिन में आएगा।",
      "de": "Ihre Bestellung wurde storniert. Die Rückerstattung kommt in 3–5 Tagen.",
      "fr": "Votre commande a été annulée. Le remboursement arrivera dans 3 à 5 jours.",
      "es": "Su pedido ha sido cancelado. El reembolso llegará en 3 a 5 días.",
      "pt": "Seu pedido foi cancelado. O reembolso chegará em 3 a 5 dias.",
      "ru": "Ваш заказ отменён. Возврат поступит через 3–5 дней.",
      "ja": "ご注文はキャンセルされました。返金は3〜5日で届きます。",
      "zh": "您的订单已取消。退款将在3-5天内到账。",
      "tr": "Siparişiniz iptal edildi. İade 3-5 gün içinde ulaşacak.",
      "en": "Your order has been cancelled. The refund will arrive in 3-5 days."}),
    ({"delivery", "डिलीवरी", "status", "स्टेटस",
      "lieferung", "versand", "paket", "zustellung",
      "livraison", "entrega", "envío", "envio",
      "доставка", "заказ", "配送", "注文", "快递", "订单",
      "teslimat", "kargo", "sipariş",
      "package", "parcel", "shipment", "shipping"},
     {"hi": "आपका ऑर्डर रास्ते में है, 2-3 दिन में डिलीवर हो जाएगा।",
      "de": "Ihre Bestellung ist unterwegs und kommt in 2–3 Tagen an.",
      "fr": "Votre commande est en route, livraison dans 2 à 3 jours.",
      "es": "Su pedido está en camino y llegará en 2 a 3 días.",
      "pt": "Seu pedido está a caminho e será entregue em 2 a 3 dias.",
      "ru": "Ваш заказ в пути, доставка через 2–3 дня.",
      "ja": "ご注文は配送中です。2〜3日でお届けします。",
      "zh": "您的订单正在派送中，将在2-3天内送达。",
      "tr": "Siparişiniz yolda, 2-3 gün içinde teslim edilecek.",
      "en": "Your order is on its way and will be delivered in 2-3 days."}),
]

_DEVA = "\u0900-\u097f"
_KANA = "\u3040-\u30ff"
_CJK = "\u4e00-\u9fff"
_CYR = "\u0400-\u04ff"
_TAMIL = "\u0b80-\u0bff"
_TELUGU = "\u0c00-\u0c7f"
_BENGALI = "\u0980-\u09ff"


def _fold_turkish(text: str) -> str:
    # See normalizer: İ.lower() is i̇, not i — fold before any matching.
    return text.replace("İ", "i").replace("I", "ı")


def _lang_of(prompt: str) -> str:
    import re

    prompt = _fold_turkish(prompt)
    if re.search(f"[{_DEVA}]", prompt):
        return "hi"
    if re.search(f"[{_KANA}]", prompt):
        return "ja"  # hiragana/katakana decide Japanese (kanji overlap with Chinese)
    if re.search(f"[{_CJK}]", prompt):
        return "zh"
    if re.search(f"[{_CYR}]", prompt):
        return "ru"
    if re.search(f"[{_TAMIL}]", prompt):
        return "ta"
    if re.search(f"[{_TELUGU}]", prompt):
        return "te"
    if re.search(f"[{_BENGALI}]", prompt):
        return "bn"
    low = prompt.lower()
    if any(k in low for k in ("rück", "lieferung", "bestellung", "stornier", "der ", "die ", "ß")):
        return "de"
    if any(k in low for k in ("remboursement", "livraison", "annul", "commande")):
        return "fr"
    if any(k in low for k in ("reembolso", "devolução", "devolucao", "cancelamento")):
        return "pt"
    if any(k in low for k in ("entrega", "pedido", "envío", "cancelar")):
        return "es"
    if any(k in low for k in ("iade", "iptal", "teslimat", "kargo", "sipariş")):
        return "tr"
    return "en"


class MockProvider:
    """Deterministic, keyless test double — multilingual, answers in kind."""

    name = "mock/mock-echo"

    def complete(self, prompt: str, system: str = "") -> LLMResponse:
        # Verifier probes ("...CONFIRM or CONFLICT...") get a deterministic
        # CONFIRM — Mock holds no newer knowledge to contradict memory with.
        if "CONFIRM or CONFLICT" in prompt.upper():
            return LLMResponse("CONFIRM — mock verification, no contradiction detected.", self.name)
        low = _fold_turkish(prompt).lower()
        lang = _lang_of(prompt)
        for keywords, answers in _INTENTS:
            if any(k in low or k in prompt for k in keywords):
                return LLMResponse(answers.get(lang, answers["en"]), self.name)
        # neutral echo as answer so distiller has something stable
        return LLMResponse(f"Echo: {prompt.strip().splitlines()[-1][:200]}", self.name)
