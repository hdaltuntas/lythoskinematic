"""
lythoskinematic.theme — grafiklerin renk paleti.

Arayüzün kendi renkleri `web/static/style.css` içindedir; burada yalnızca
matplotlib figürlerine aktarılan palet tutulur. Figür zemini her iki temada da
beyaz kalır: aynı görsel hem ekranda hem PDF raporunda kullanılır.
"""
from __future__ import annotations

from typing import Dict

#: Kurumsal renkler (rockslope.style ile aynı aile)
NAVY = "#1f3b5a"
GREY = "#5b6770"
GRID = "#e2e6ea"
INK = "#1f2937"

PALETTES: Dict[str, dict] = {
    "light": {"fg": INK, "muted": GREY, "grid": GRID, "accent": NAVY, "figure": "#ffffff"},
    "dark": {"fg": INK, "muted": GREY, "grid": GRID, "accent": NAVY, "figure": "#ffffff"},
}


def mpl_palette(name: str = "light") -> dict:
    """Matplotlib figürleri için tema renkleri."""
    return dict(PALETTES.get(name, PALETTES["light"]))
