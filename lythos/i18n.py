"""
lythos.i18n — uygulama genelinde dil seçimi.

Kullanım, çağrı yerinde iki dilli metin vermeye dayanır:

    from ..i18n import T
    print(T("Şev yüksekliği", "Slope height"))

Böylece anahtar defteri tutulmaz, çeviri kullanıldığı yerde durur ve eksik
anahtar diye bir durum oluşmaz. Seçili dil süreç genelinde tek bir modül
değişkenidir; hesap çekirdeği (`lythos.rockslope`, `lythos.kinematics`) de
arayüzden bağımsız kalarak bu metinleri üretebilir.

Dil değiştirildiğinde ekranda duran metinler kendiliğinden güncellenmez;
arayüz panelleri `set_language()` çağrısından sonra kendilerini yeniden kurar.
"""
from __future__ import annotations

from typing import Callable, List

LANGS = ("TR", "EN")

_lang = "TR"
_listeners: List[Callable[[str], None]] = []


def language() -> str:
    """Seçili dil kodu: 'TR' veya 'EN'."""
    return _lang


def set_language(lang: str) -> bool:
    """Dili değiştirir. Değişiklik olduysa True döner ve dinleyiciler uyarılır."""
    global _lang
    lang = (lang or "").upper()
    if lang not in LANGS or lang == _lang:
        return False
    _lang = lang
    for fn in list(_listeners):
        fn(_lang)
    return True


def on_change(fn: Callable[[str], None]) -> Callable[[str], None]:
    """Dil değişiminde çağrılacak bir geri çağırım kaydeder."""
    _listeners.append(fn)
    return fn


def T(tr: str, en: str) -> str:
    """Seçili dile göre metin döndürür."""
    return en if _lang == "EN" else tr


def pct(value, decimals: int = 2) -> str:
    """Yüzde biçimi: Türkçede işaret önde (%12,34 yerine %12.34), İngilizcede sonda."""
    body = f"{value:.{decimals}f}"
    return f"%{body}" if _lang == "TR" else f"{body}%"


def pick(tr, en):
    """Metin dışı değerler (demet, liste, sözlük) için T'nin karşılığı."""
    return en if _lang == "EN" else tr
