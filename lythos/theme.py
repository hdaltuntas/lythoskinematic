"""
lythos.theme — Lythos Suite için ortak açık/koyu tema.

Tek bir QSS şablonu, iki renk paletiyle üretilir; böylece suite kabuğu ve tüm
modüller (kinematik tarama + limit denge) aynı görsel dili paylaşır.
Aynı palet matplotlib figürlerine de aktarılır (`mpl_palette`).
"""
from __future__ import annotations

from typing import Dict


def _build_qss(bg, bg2, panel, border, text, muted, accent, accent_hover, accent_text, selection):
    """Ortak QSS şablonu; renk paletini değiştirerek açık/koyu tema üretir."""
    return f"""
        QMainWindow, QDialog {{ background: {bg}; }}
        QWidget {{ color: {text}; selection-background-color: {selection}; selection-color: {accent_text}; }}
        QToolTip {{ background: {panel}; color: {text}; border: 1px solid {border}; padding: 4px; border-radius: 4px; }}

        QToolBar {{ background: {panel}; border: none; border-bottom: 1px solid {border}; spacing: 6px; padding: 5px 8px; }}
        QToolBar QLabel {{ color: {muted}; }}
        QToolBar QComboBox {{ min-height: 22px; }}
        QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 6px; padding: 5px 10px; color: {text}; }}
        QToolButton:hover {{ background: {bg2}; border-color: {border}; }}
        QToolButton:pressed {{ background: {selection}; }}

        QMenuBar {{ background: {panel}; color: {text}; border-bottom: 1px solid {border}; }}
        QMenuBar::item {{ background: transparent; padding: 5px 10px; }}
        QMenuBar::item:selected {{ background: {bg2}; border-radius: 5px; }}

        QStatusBar {{ background: {panel}; border-top: 1px solid {border}; color: {muted}; }}
        QStatusBar::item {{ border: none; }}

        QDockWidget {{ color: {text}; titlebar-close-icon: none; }}
        QDockWidget::title {{ background: {bg2}; padding: 7px 10px; color: {text}; font-weight: 600;
                              border-bottom: 1px solid {border}; }}

        QScrollArea {{ background: {bg}; border: none; }}
        QScrollArea > QWidget > QWidget {{ background: {bg}; }}

        QGroupBox {{ background: {panel}; border: 1px solid {border}; border-radius: 8px;
                    margin-top: 12px; padding-top: 6px; font-weight: 600; color: {accent}; }}
        QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px; }}

        QLabel {{ background: transparent; }}

        QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPlainTextEdit {{
            background: {bg}; border: 1px solid {border}; border-radius: 5px; padding: 3px 6px; color: {text}; }}
        QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
            border: 1px solid {accent}; }}
        QLineEdit:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled {{ color: {muted}; background: {bg2}; }}
        QComboBox::drop-down {{ border: none; width: 18px; }}
        QComboBox QAbstractItemView {{ background: {panel}; border: 1px solid {border};
                                       selection-background-color: {accent}; selection-color: {accent_text}; }}
        QCheckBox {{ spacing: 6px; background: transparent; }}

        QPushButton {{ background: {panel}; border: 1px solid {border}; border-radius: 6px;
                      padding: 5px 12px; color: {text}; }}
        QPushButton:hover {{ border-color: {accent}; }}
        QPushButton:pressed {{ background: {bg2}; }}
        QPushButton:disabled {{ color: {muted}; background: {bg2}; border-color: {border}; }}
        QPushButton:default {{ background: {accent}; color: {accent_text}; border-color: {accent}; }}
        QPushButton:default:hover {{ background: {accent_hover}; }}

        QPushButton#run {{ background: {accent}; color: {accent_text}; border: none; border-radius: 7px;
                          font-weight: 700; padding: 10px 14px; }}
        QPushButton#run:hover {{ background: {accent_hover}; }}
        QPushButton#run:disabled {{ background: {bg2}; color: {muted}; }}
        QPushButton#pdf {{ background: #c0392b; color: #ffffff; border: none; border-radius: 7px;
                          font-weight: 700; padding: 8px 14px; }}
        QPushButton#pdf:hover {{ background: #a63325; }}
        QPushButton#pdf:disabled {{ background: {bg2}; color: {muted}; }}
        QPushButton#handoff {{ font-weight: 600; padding: 8px 14px; }}

        QTabWidget::pane {{ border: 1px solid {border}; border-radius: 6px; background: {panel}; top: -1px; }}
        QTabBar::tab {{ background: {bg2}; border: 1px solid {border}; border-bottom: none; color: {muted};
                       padding: 7px 16px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
        QTabBar::tab:selected {{ background: {panel}; color: {accent}; font-weight: 600; }}
        QTabBar::tab:hover {{ color: {text}; }}

        QTableWidget {{ background: {panel}; alternate-background-color: {bg2}; gridline-color: {border};
                       border: 1px solid {border}; border-radius: 6px; color: {text}; }}
        QHeaderView {{ background: {bg2}; }}
        QHeaderView::section {{ background: {bg2}; color: {text}; padding: 5px; border: none;
                               border-bottom: 1px solid {border}; border-right: 1px solid {border}; font-weight: 600; }}
        QTableWidget::item:selected {{ background: {selection}; color: {accent_text}; }}
        QTableCornerButton::section {{ background: {bg2}; border: none; border-bottom: 1px solid {border};
                                       border-right: 1px solid {border}; }}

        QTextEdit {{ background: #ffffff; color: #222222; border: 1px solid {border}; border-radius: 6px; }}

        QProgressBar {{ border: 1px solid {border}; border-radius: 5px; text-align: center; background: {bg2};
                       color: {text}; }}
        QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}

        QSplitter::handle {{ background: {border}; }}
        QMenu {{ background: {panel}; border: 1px solid {border}; color: {text}; }}
        QMenu::item:selected {{ background: {accent}; color: {accent_text}; }}

        QScrollBar:vertical {{ background: {bg}; width: 13px; margin: 0; }}
        QScrollBar::handle:vertical {{ background: {border}; min-height: 24px; border-radius: 5px; margin: 2px; }}
        QScrollBar::handle:vertical:hover {{ background: {accent}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
        QScrollBar:horizontal {{ background: {bg}; height: 13px; margin: 0; }}
        QScrollBar::handle:horizontal {{ background: {border}; min-width: 24px; border-radius: 5px; margin: 2px; }}
        QScrollBar::handle:horizontal:hover {{ background: {accent}; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
        QScrollBar::corner {{ background: {bg}; }}
    """


LIGHT = dict(bg="#ffffff", bg2="#eef1f5", panel="#ffffff", border="#d7dce3",
             text="#1f2937", muted="#5b6770", accent="#1f3b5a", accent_hover="#2874a6",
             accent_text="#ffffff", selection="#cfe0ee")

DARK = dict(bg="#20242b", bg2="#2a2f38", panel="#262b33", border="#3a4048",
            text="#e6e9ee", muted="#9aa4b2", accent="#5aa9d6", accent_hover="#6fb8e0",
            accent_text="#12161c", selection="#3a5570")

PALETTES: Dict[str, dict] = {"light": LIGHT, "dark": DARK}
THEMES: Dict[str, str] = {name: _build_qss(**p) for name, p in PALETTES.items()}


def qss(name: str) -> str:
    """Tema adına karşılık gelen QSS; bilinmeyen ad açık temaya düşer."""
    return THEMES.get(name, THEMES["light"])


def mpl_palette(name: str) -> dict:
    """Matplotlib figürleri için tema renkleri.

    Figür zemini her zaman beyaz kalır (rapora/PDF'e basılan çıktıyla aynı olsun
    diye); koyu temada yalnızca çerçeve rengi panelle uyumlanır.
    """
    p = PALETTES.get(name, LIGHT)
    return {"fg": "#1f2937", "muted": "#5b6770", "grid": "#e2e6ea", "accent": "#1f3b5a",
            "figure": "#ffffff", "frame": p["panel"]}
