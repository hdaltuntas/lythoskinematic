"""
lythoskinematic.rockslope.text — limit denge çekirdeğinin paylaşılan metin parçaları.

Özet (`summary()`) çıktıları sabit genişlikli metin tablolarıdır; etiket sütunu
`LABEL_WIDTH` ile hizalandığı için iki dilde de düzgün görünür.
"""
from __future__ import annotations

from ..i18n import T as _tr

#: Özet bloklarında etiket sütununun genişliği (karakter)
LABEL_WIDTH = 22


def ACTIVE() -> str:
    return _tr("aktif", "active")


def PASSIVE() -> str:
    return _tr("pasif", "passive")


def WARNING_PREFIX() -> str:
    return _tr("UYARI: ", "WARNING: ")


def NONE_TEXT() -> str:
    return _tr("Yok", "None")


def YES_NO(flag: bool) -> str:
    return _tr("evet", "yes") if flag else _tr("hayır", "no")


def WATER_MODE(mode: str) -> str:
    """Su basıncı modunun okunabilir adı."""
    return {
        "dry": _tr("kuru", "dry"),
        "filled": _tr("dolu çatlak (H&B)", "filled crack (H&B)"),
        "percent": _tr("yüzde dolu", "percent filled"),
        "custom": _tr("özel basınç", "custom pressure"),
    }.get(mode, mode)


#: Devrilme analizinde blok modlarının iç anahtarları (renk/karşılaştırma için sabit)
BLOCK_MODES = ("stabil", "devrilme", "kayma")


def MODE_TEXT(mode: str) -> str:
    """Blok modunun okunabilir adı; iç anahtar her zaman Türkçe sabittir."""
    return {
        "stabil": _tr("stabil", "stable"),
        "devrilme": _tr("devrilme", "toppling"),
        "kayma": _tr("kayma", "sliding"),
    }.get(mode, mode)
