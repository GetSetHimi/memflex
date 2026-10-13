# Copyright (c) 2026 Himanshu Sharma — Memflex, licensed under FSL-1.1-ALv2 (see LICENSE).
"""Multilingual proof: EVERY language gets reflex hits — not just English/Hindi.

For each language: ask 3x (establish), then assert pure "reflex" source.
Same-script repeats always match; the normalizer additionally converges
Hindi Devanagari <-> Roman/Hinglish to one situation key.
"""
import os

os.environ["EMBEDDING_BACKEND"] = "hash"
os.environ["REFLEX_DB_PATH"] = "/tmp/reflex_test.db"

from fastapi.testclient import TestClient
from reflex.api.app import app
from reflex.core.normalizer import normalize_situation

client = TestClient(app)

CASES = [
    ("hindi", "मेरा रिफंड कब आएगा?"),
    ("hinglish", "mera refund kab ayega?"),
    ("english", "When will my refund arrive?"),
    ("tamil", "எனது பணம் திரும்ப எப்போது வரும்?"),
    ("telugu", "నా వాపసు ఎప్పుడు వస్తుంది?"),
    ("bengali", "আমার রিফান্ড কখন আসবে?"),
    ("marathi", "माझा परतावा कधी येईल?"),
    ("gujarati", "મારું રિફંડ ક્યારે આવશે?"),
    ("kannada", "ನನ್ನ ಮರುಪಾವತಿ ಯಾವಾಗ ಬರುತ್ತದೆ?"),
    ("malayalam", "എന്റെ റീഫണ്ട് എപ്പോൾ വരും?"),
    ("punjabi", "ਮੇਰਾ ਰਿਫੰਡ ਕਦੋਂ ਆਵੇਗਾ?"),
    ("spanish", "¿Cuándo llegará mi reembolso?"),
    ("french", "Quand mon remboursement arrivera-t-il ?"),
    ("arabic", "متى سيصل استرداد أموالي؟"),
    ("portuguese", "Quando meu reembolso vai chegar?"),
    ("russian", "Когда вернут мои деньги за возврат?"),
    ("japanese", "返金はいつ届きますか?"),
    ("chinese", "我的退款什么时候到?"),
    ("turkish", "İadem ne zaman gelecek?"),
]


def test_mock_answers_in_kind_worldwide():
    from reflex.llm.base import MockProvider

    mock = MockProvider()
    assert "reembolso" in mock.complete("Quando meu reembolso vai chegar?").text.lower()
    assert "возврат" in mock.complete("Когда вернут мои деньги за возврат?").text.lower()
    assert "返金" in mock.complete("返金はいつ届きますか?").text
    assert "退款" in mock.complete("我的退款什么时候到?").text
    # Turkish dotted-İ must fold: real Turkish answer, not an echo
    assert "İade" in mock.complete("İadem ne zaman gelecek?").text


def test_turkish_dotted_i_folds():
    from reflex.core.normalizer import normalize_situation

    assert normalize_situation("İadem ne zaman gelecek?") == normalize_situation(
        "iadem ne zaman gelecek?")


def test_hindi_hinglish_converge_to_same_situation():
    assert normalize_situation("मेरा रिफंड कब आएगा?") == normalize_situation("mera refund kab ayega?")


def test_every_language_gets_reflex_hits():
    for lang, msg in CASES:
        uid = f"ml_{lang}"
        res = {}
        for _ in range(5):
            r = client.post("/ask", json={"user_id": uid, "message": msg, "llm": "mock/mock-echo"})
            assert r.status_code == 200, (lang, r.text)
            res = r.json()
            if res["source"] == "reflex":
                break
        assert res["source"] == "reflex", (lang, res)
        assert res["latency_ms"] < 500, (lang, res)
