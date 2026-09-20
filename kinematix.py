"""
kinematix.py — Kinematix: kaya şevi stabilite analizi için PySide6 (LGPL) masaüstü arayüzü.
Hesap çekirdeği `rockslope/` paketindedir (bu arayüz ondan bağımsız).

Çalıştırma:  python kinematix.py
Gereksinim:  pip install PySide6 numpy scipy matplotlib reportlab
"""
from __future__ import annotations

import os
import sys
import json
import datetime
import traceback

# --- Qt bağlaması matplotlib'den ÖNCE ve tek başına yüklenmeli ---------------
# Aksi hâlde matplotlib makinede PyQt5/PyQt6 bulursa önce onu yükler; ikinci bir Qt6Core.dll
# aynı işleme girince Windows "DLL load failed / belirtilen yordam bulunamadı" hatası verir.
os.environ["QT_API"] = "pyside6"
from PySide6.QtCore import Qt, QSettings, QThread, Signal, QSize
from PySide6.QtGui import QAction, QFont, QColor, QKeySequence
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
                               QLabel, QLineEdit, QDoubleSpinBox, QSpinBox, QCheckBox, QComboBox, QTabWidget,
                               QPlainTextEdit, QTableWidget, QTableWidgetItem, QScrollArea, QDockWidget,
                               QStackedWidget, QFileDialog, QMessageBox, QToolBar, QStatusBar, QSizePolicy,
                               QHeaderView, QProgressBar)

import numpy as np
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT

from rockslope import (Joint, Plane, TensionCrack, Water, Seismic, Support, WedgeInput, analyze, plot_wedge,
                       plot_stereonet, required_support, PlanarInput, planar_analyze, planar_required_support,
                       plot_planar, BoltSpec, bolt_pattern_planar, bolt_pattern_wedge, bolt_check_planar,
                       bolt_check_wedge, STANDARD_LENGTHS, TopplingInput, toppling_analyze,
                       toppling_required_support, plot_toppling, Report)
from rockslope import style as rstyle

APP_NAME = "Kinematix"
ORG = "KGM-ArGe"

# --------------------------------------------------------------------------- #
#  Açık / koyu tema (QSS) — "Fusion" temel stilinin üzerine
# --------------------------------------------------------------------------- #

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
        QPushButton:default {{ background: {accent}; color: {accent_text}; border-color: {accent}; }}
        QPushButton:default:hover {{ background: {accent_hover}; }}

        QTabWidget::pane {{ border: 1px solid {border}; border-radius: 6px; background: {panel}; top: -1px; }}
        QTabBar::tab {{ background: {bg2}; border: 1px solid {border}; border-bottom: none; color: {muted};
                       padding: 7px 16px; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
        QTabBar::tab:selected {{ background: {panel}; color: {accent}; font-weight: 600; }}
        QTabBar::tab:hover {{ color: {text}; }}

        QTableWidget {{ background: {panel}; alternate-background-color: {bg2}; gridline-color: {border};
                       border: 1px solid {border}; border-radius: 6px; }}
        QHeaderView {{ background: {bg2}; }}
        QHeaderView::section {{ background: {bg2}; color: {text}; padding: 5px; border: none;
                               border-bottom: 1px solid {border}; border-right: 1px solid {border}; font-weight: 600; }}
        QTableWidget::item:selected {{ background: {selection}; color: {accent_text}; }}
        QTableCornerButton::section {{ background: {bg2}; border: none; border-bottom: 1px solid {border};
                                       border-right: 1px solid {border}; }}

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


THEME_LIGHT = _build_qss(bg="#ffffff", bg2="#eef1f5", panel="#ffffff", border="#d7dce3",
                         text="#1f2937", muted="#5b6770", accent="#1f3b5a", accent_hover="#2874a6",
                         accent_text="#ffffff", selection="#cfe0ee")

THEME_DARK = _build_qss(bg="#20242b", bg2="#2a2f38", panel="#262b33", border="#3a4048",
                        text="#e6e9ee", muted="#9aa4b2", accent="#5aa9d6", accent_hover="#6fb8e0",
                        accent_text="#12161c", selection="#3a5570")

THEMES = {"light": THEME_LIGHT, "dark": THEME_DARK}

# --------------------------------------------------------------------------- #
#  Yardımcı widget'lar
# --------------------------------------------------------------------------- #

class Num(QDoubleSpinBox):
    """Sayısal alan: aralık, ondalık, birim soneki."""
    def __init__(self, value=0.0, lo=-1e9, hi=1e9, dec=2, suffix="", step=1.0):
        super().__init__()
        self.setRange(lo, hi); self.setDecimals(dec); self.setSingleStep(step); self.setValue(value)
        if suffix:
            self.setSuffix(" " + suffix)
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setMinimumWidth(70); self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        return QSize(90, super().sizeHint().height())

    def minimumSizeHint(self):
        return QSize(70, super().minimumSizeHint().height())


class Opt(QLineEdit):
    """Boş bırakılabilen sayısal alan (boş = otomatik)."""
    def __init__(self, placeholder="otomatik"):
        super().__init__(); self.setPlaceholderText(placeholder); self.setMinimumWidth(70)
        self.setAlignment(Qt.AlignmentFlag.AlignRight); self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def value(self):
        t = self.text().strip().replace(",", ".")
        return float(t) if t else None


def note(text):
    l = QLabel(text); l.setWordWrap(True); l.setStyleSheet("color:#5b6770;"); return l


class MplTab(QWidget):
    """Matplotlib tuvali + araç çubuğu."""
    def __init__(self):
        super().__init__()
        self.fig = Figure(figsize=(9, 6)); self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(self.toolbar); lay.addWidget(self.canvas)

    def clear(self):
        self.fig.clear(); self.canvas.draw_idle()

    def ax(self, projection=None):
        self.fig.clear(); return self.fig.add_subplot(111, projection=projection)

    def draw(self):
        self.fig.tight_layout(); self.canvas.draw_idle()


class Worker(QThread):
    """Uzun hesapları (bulon öneri matrisi) arka planda çalıştırır."""
    done = Signal(object); failed = Signal(str)

    def __init__(self, fn, *args):
        super().__init__(); self.fn, self.args = fn, args

    def run(self):
        try:
            self.done.emit(self.fn(*self.args))
        except Exception as e:
            self.failed.emit(f"{e}\n{traceback.format_exc()}")


# --------------------------------------------------------------------------- #
#  Ana pencere
# --------------------------------------------------------------------------- #

class MainWindow(QMainWindow):
    MODES = [("wedge", "Kama (Swedge)"), ("planar", "Düzlemsel (RocPlane)"), ("toppling", "Devrilme (RocTopple)")]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kinematix — Kaya Şevi Stabilite Analizi")
        self.resize(1440, 900)
        self.f = {}                # key -> widget
        self.last = None           # (mode, inp, res, figs)
        self.worker = None
        self._build_toolbar()
        self._build_dock()
        self._build_central()
        self.setStatusBar(QStatusBar())
        self._load_settings()
        self._switch_mode()

    # ---------------------------------------------------------------- UI
    def _build_toolbar(self):
        tb = QToolBar("Ana"); tb.setMovable(False); tb.setIconSize(QSize(18, 18)); self.addToolBar(tb)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        tb.addWidget(QLabel("  Analiz türü: "))
        self.mode_box = QComboBox()
        for key, lab in self.MODES:
            self.mode_box.addItem(lab, key)
        self.mode_box.currentIndexChanged.connect(self._switch_mode)
        tb.addWidget(self.mode_box); tb.addSeparator()

        def act(text, slot, shortcut=None, tip=""):
            a = QAction(text, self); a.triggered.connect(slot)
            if shortcut: a.setShortcut(QKeySequence(shortcut))
            a.setToolTip(tip or text); tb.addAction(a); return a
        self.a_run = act("▶ Analiz Et", self.on_analyze, "F5", "Seçili analizi çalıştır (F5)")
        self.a_req = act("Gerekli Destek", self.on_required, "F6", "Hedef FS için gerekli destek kuvveti (F6)")
        self.a_bolt = act("Bulon Önerisi", self.on_bolts, "F7", "Karelaj × boy öneri matrisi (F7)")
        self.a_chk = act("Bulon Kontrol", self.on_bolt_check, "F8", "Seçilen karelaj + boy ile kapasite/FS kontrolü (F8)")
        tb.addSeparator()
        act("PDF Rapor", self.on_pdf, "Ctrl+P")
        tb.addSeparator()
        act("Kaydet", self.on_save, "Ctrl+S"); act("Yükle", self.on_load, "Ctrl+O")

        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self.a_theme = act("🌙 Koyu tema", self.on_toggle_theme, tip="Açık/koyu temayı değiştir")

    def _apply_theme(self, name: str):
        self.theme = name if name in THEMES else "light"
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(THEMES[self.theme])
        if hasattr(self, "a_theme"):
            self.a_theme.setText("☀ Açık tema" if self.theme == "dark" else "🌙 Koyu tema")

    def on_toggle_theme(self):
        self._apply_theme("dark" if self.theme == "light" else "light")
        QSettings(ORG, APP_NAME).setValue("theme", self.theme)

    def _build_dock(self):
        dock = QDockWidget("Girdiler", self); dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setMinimumWidth(480)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget(); self.dock_lay = QVBoxLayout(host); self.dock_lay.setSpacing(6)
        self.stack = QStackedWidget(); self.stack.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.stack.addWidget(self._wedge_form()); self.stack.addWidget(self._planar_form()); self.stack.addWidget(self._toppling_form())
        self.dock_lay.addWidget(self.stack)
        self.dock_lay.addWidget(self._bolt_form())
        self.dock_lay.addWidget(self._report_form())
        self.dock_lay.addStretch(1)
        scroll.setWidget(host); dock.setWidget(scroll)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    def _grp(self, title):
        g = QGroupBox(title); fl = QFormLayout(g); fl.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        fl.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        fl.setVerticalSpacing(4); g.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum); return g, fl

    def _row(self, fl, label, key, widget):
        self.f[key] = widget; fl.addRow(label, widget); return widget

    def _pair(self, fl, l1, k1, w1, l2, k2, w2):
        """İki alanı tek satırda yerleştir."""
        self.f[k1], self.f[k2] = w1, w2
        box = QWidget(); h = QHBoxLayout(box); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(6)
        h.addWidget(w1, 1)
        if l2: h.addWidget(QLabel(l2))
        h.addWidget(w2, 1); fl.addRow(l1, box)

    # ---- Kama formu
    def _wedge_form(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0)
        for j, dflt in (("j1", (45, 105, 24, 20)), ("j2", (70, 235, 48, 30))):
            g, fl = self._grp(f"Eklem {j[-1]}")
            self._pair(fl, "Dip / Dip dir", f"{j}_dip", Num(dflt[0], 0, 90, 1, "°"), "", f"{j}_dd", Num(dflt[1], 0, 360, 1, "°"))
            self._pair(fl, "c / φ", f"{j}_c", Num(dflt[2], 0, 1e5, 1, "kPa"), "", f"{j}_phi", Num(dflt[3], 0, 89, 1, "°"))
            v.addWidget(g)
        g, fl = self._grp("Şev geometrisi")
        self._pair(fl, "Şev yüzü dip / dip dir", "face_dip", Num(65, 1, 90, 1, "°"), "", "face_dd", Num(185, 0, 360, 1, "°"))
        self._pair(fl, "Üst şev dip / dip dir", "up_dip", Num(12, 0, 89, 1, "°"), "", "up_dd", Num(195, 0, 360, 1, "°"))
        self._pair(fl, "Şev yüksekliği / γ", "H", Num(40, 0.1, 1e4, 2, "m"), "", "gamma", Num(25, 1, 40, 2, "kN/m³"))
        self.scale_box = QComboBox()
        for lab, key in (("Şev yüksekliği (maks. kama)", "height"), ("Tepe uzunluğu (m)", "crest_length"),
                         ("Basamak genişliği (m)", "bench_width"), ("Kama hacmi (m³)", "volume"), ("Kama ağırlığı (kN)", "weight")):
            self.scale_box.addItem(lab, key)
        self.f["scale_mode"] = self.scale_box
        self._pair(fl, "Kamayı ölçekle", "scale_mode", self.scale_box, "değer", "scale_value", Opt("—"))
        v.addWidget(g)
        g, fl = self._grp("Çekme çatlağı")
        self._row(fl, "", "tc_on", QCheckBox("Çekme çatlağı var"))
        self._pair(fl, "Dip / Dip dir", "tc_dip", Num(70, 1, 90, 1, "°"), "", "tc_dd", Num(165, 0, 360, 1, "°"))
        self._row(fl, "Tepeden mesafe", "tc_L", Num(8, 0, 1e4, 2, "m"))
        v.addWidget(g)
        g, fl = self._grp("Su basıncı")
        wb = QComboBox()
        for lab, key in (("Kuru", "dry"), ("Dolu çatlak (Hoek & Bray)", "filled"), ("Yüzde dolu", "percent"), ("Özel basınç", "custom")):
            wb.addItem(lab, key)
        self._row(fl, "Model", "water_mode", wb)
        self._pair(fl, "γw / doluluk", "gw", Num(9.81, 1, 15, 2, "kN/m³"), "", "w_pct", Num(100, 0, 100, 0, "%"))
        self._pair(fl, "u J1 / u J2", "u1", Num(0, 0, 1e5, 1, "kPa"), "", "u2", Num(0, 0, 1e5, 1, "kPa"))
        self._row(fl, "u çatlak", "ut", Num(0, 0, 1e5, 1, "kPa"))
        v.addWidget(g)
        g, fl = self._grp("Sismik yük (pseudo-statik)")
        self._pair(fl, "Katsayı α / trend", "ah", Num(0, 0, 2, 3, "", 0.05), "", "s_trend", Opt("şev yönü"))
        self._row(fl, "Plunge", "s_plunge", Num(0, -90, 90, 1, "°"))
        v.addWidget(g)
        g, fl = self._grp("Destek (bulon / ankraj)")
        self._pair(fl, "Kuvvet / hedef FS", "T", Num(0, 0, 1e9, 1, "kN"), "", "FS_target", Num(1.5, 1, 5, 2, "", 0.1))
        self._pair(fl, "Trend / plunge", "T_trend", Opt("optimum"), "", "T_plunge", Opt("optimum"))
        self._row(fl, "", "T_passive", QCheckBox("Pasif (varsayılan aktif)"))
        v.addWidget(g); v.addStretch(1)
        return w

    # ---- Düzlemsel formu
    def _planar_form(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0)
        g, fl = self._grp("Şev ve kayma düzlemi (2D kesit, 1 m)")
        self._pair(fl, "H / şev yüzü ψf", "p_H", Num(20, 0.1, 1e4, 2, "m"), "", "p_face", Num(72, 1, 89.9, 1, "°"))
        self._pair(fl, "Kayma ψp / üst şev ψs", "p_plane", Num(34, 0.1, 89, 1, "°"), "", "p_upper", Num(0, -30, 60, 1, "°"))
        self._pair(fl, "c / φ", "p_c", Num(0, 0, 1e5, 1, "kPa"), "", "p_phi", Num(31, 0, 89, 1, "°"))
        self._row(fl, "γ kaya", "p_gamma", Num(25, 1, 40, 2, "kN/m³"))
        v.addWidget(g)
        g, fl = self._grp("Çekme çatlağı")
        cb = QCheckBox("Çekme çatlağı var"); cb.setChecked(True); self._row(fl, "", "p_tc_on", cb)
        self._row(fl, "Tepeden yatay mesafe b", "p_tc_b", Num(6, -1e4, 1e4, 2, "m"))
        fl.addRow("", note("<i>b &lt; 0: çatlak şev yüzünde</i>"))
        v.addWidget(g)
        g, fl = self._grp("Su basıncı")
        wb = QComboBox()
        for lab, key in (("Kuru", "dry"), ("Çatlak % dolu (Hoek & Bray)", "percent"), ("Özel basınç", "custom")):
            wb.addItem(lab, key)
        self._row(fl, "Model", "p_water", wb)
        self._pair(fl, "γw / doluluk", "p_gw", Num(9.81, 1, 15, 2, "kN/m³"), "", "p_wpct", Num(100, 0, 100, 0, "%"))
        self._pair(fl, "u düzlem / u çatlak", "p_up", Num(0, 0, 1e5, 1, "kPa"), "", "p_ut", Num(0, 0, 1e5, 1, "kPa"))
        v.addWidget(g)
        g, fl = self._grp("Sismik yük (pseudo-statik)")
        self._pair(fl, "αh / αv (aşağı +)", "p_ah", Num(0, 0, 2, 3, "", 0.05), "", "p_av", Num(0, -1, 1, 3, "", 0.05))
        v.addWidget(g)
        g, fl = self._grp("Destek (kN/m)")
        self._pair(fl, "T / hedef FS", "p_T", Num(0, 0, 1e7, 1, "kN/m"), "", "p_FS", Num(1.5, 1, 5, 2, "", 0.1))
        self._pair(fl, "Açı θ (aşağı +)", "p_theta", Opt("optimum"), "", "p_passive", QCheckBox("Pasif"))
        fl.addRow("", note("<i>θ boş: optimum açı tan(ψp+θ) = tanφ/FS</i>"))
        v.addWidget(g); v.addStretch(1)
        return w

    # ---- Devrilme formu
    def _toppling_form(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0)
        g, fl = self._grp("Blok devrilme geometrisi (Goodman & Bray)")
        self._pair(fl, "Şev yüzü ψf / üst şev ψs", "t_face", Num(56.6, 1, 89.9, 1, "°"), "", "t_upper", Num(4, -30, 60, 1, "°"))
        self._pair(fl, "Süreksizlik ψd / taban ψb", "t_disc", Num(60, 1, 89.9, 1, "°"), "", "t_base", Num(35.8, 0, 89, 1, "°"))
        self._pair(fl, "Δx / γ", "t_dx", Num(10, 0.01, 1e3, 2, "m"), "", "t_gamma", Num(25, 1, 40, 2, "kN/m³"))
        nb = QSpinBox(); nb.setRange(1, 500); nb.setValue(10); na = QSpinBox(); na.setRange(0, 500); na.setValue(6)
        self._pair(fl, "Blok sayısı tepe altı / üstü", "t_nb", nb, "", "t_na", na)
        self._row(fl, "φ", "t_phi", Num(38.15, 0, 44.9, 2, "°"))
        fl.addRow("", note("<i>ψp = 90 − ψd (blok tabanı eğimi), ψb ≥ ψp</i>"))
        v.addWidget(g)
        g, fl = self._grp("Su ve sismik yük")
        self._pair(fl, "Eklem su doluluğu / γw", "t_water", Num(0, 0, 100, 0, "%"), "", "t_gw", Num(9.81, 1, 15, 2, "kN/m³"))
        self._row(fl, "Yatay αh", "t_ah", Num(0, 0, 2, 3, "", 0.05))
        v.addWidget(g)
        g, fl = self._grp("Topuk ankrajı (kN/m)")
        self._pair(fl, "T / açı δ (aşağı +)", "t_T", Num(0, 0, 1e7, 1, "kN/m"), "", "t_delta", Num(0, -60, 60, 1, "°"))
        self._pair(fl, "Tabandan yükseklik / hedef FS", "t_hT", Opt("y1/2"), "", "t_FS", Num(1.3, 1, 5, 2, "", 0.1))
        v.addWidget(g); v.addStretch(1)
        return w

    # ---- Bulon ve rapor (ortak)
    def _bolt_form(self):
        g, fl = self._grp("Bulon karelaj / boy tasarımı")
        self._pair(fl, "Kapasite / delik çapı", "b_cap", Num(150, 1, 1e4, 0, "kN"), "", "b_dia", Num(76, 20, 300, 0, "mm"))
        self._pair(fl, "Aderans τb / FS kök", "b_bond", Num(800, 50, 1e4, 0, "kPa"), "", "b_fsb", Num(2.5, 1, 5, 1))
        self._pair(fl, "Min. kök / baş payı", "b_minb", Num(2.0, 0, 10, 2, "m"), "", "b_extra", Num(0.5, 0, 3, 2, "m"))
        self._pair(fl, "Aralık s min / s maks", "b_smin", Num(1.0, 0.25, 10, 2, "m"), "", "b_smax", Num(3.0, 0.25, 10, 2, "m"))
        self.sp_box = QComboBox(); self.f["b_s_sel"] = self.sp_box
        self.L_box = QComboBox(); self.L_box.setEditable(True)
        for L in STANDARD_LENGTHS:
            self.L_box.addItem(f"{L:g}")
        self.f["b_L_sel"] = self.L_box
        self._pair(fl, "Seçim: s / L", "b_s_sel", self.sp_box, "", "b_L_sel", self.L_box)
        fl.addRow("", note("<i>Sıra: Gerekli Destek → Bulon Önerisi → seçim → Bulon Kontrol</i>"))
        return g

    def _report_form(self):
        g, fl = self._grp("Rapor bilgileri")
        for key, lab in (("rp_proj", "Proje"), ("rp_loc", "Konum"), ("rp_km", "Km / Kesit"), ("rp_eng", "Hazırlayan"),
                         ("rp_chk", "Kontrol"), ("rp_doc", "Doküman No"), ("rp_note", "Değerlendirme notu")):
            self._row(fl, lab, key, QLineEdit())
        return g

    def _build_central(self):
        self.tabs = QTabWidget()
        self.txt = QPlainTextEdit(); self.txt.setReadOnly(True)
        mono = QFont("Consolas" if sys.platform.startswith("win") else "DejaVu Sans Mono"); mono.setPointSize(9); self.txt.setFont(mono)
        self.tab_fig = MplTab(); self.tab_stereo = MplTab()
        self.table = QTableWidget(); self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.txt, "Sonuçlar"); self.tabs.addTab(self.tab_fig, "Grafik")
        self.tabs.addTab(self.tab_stereo, "Stereonet"); self.tabs.addTab(self.table, "Tablo")
        self.setCentralWidget(self.tabs)
        self.progress = QProgressBar(); self.progress.setRange(0, 0); self.progress.setMaximumWidth(160); self.progress.hide()

    # ---------------------------------------------------------------- yardımcılar
    @property
    def mode(self):
        return self.mode_box.currentData()

    def val(self, key):
        w = self.f[key]
        if isinstance(w, (QDoubleSpinBox, QSpinBox)): return w.value()
        if isinstance(w, QCheckBox): return w.isChecked()
        if isinstance(w, Opt): return w.value()
        if isinstance(w, QComboBox): return w.currentData() if w.currentData() is not None else w.currentText()
        return w.text()

    def setval(self, key, v):
        w = self.f.get(key)
        if w is None or v is None: return
        if isinstance(w, (QDoubleSpinBox, QSpinBox)): w.setValue(type(w.value())(v))
        elif isinstance(w, QCheckBox): w.setChecked(bool(v))
        elif isinstance(w, QComboBox):
            idx = w.findData(v)
            if idx < 0: idx = w.findText(str(v))
            if idx >= 0: w.setCurrentIndex(idx)
            elif w.isEditable(): w.setEditText(str(v))
        else: w.setText("" if v is None else str(v))

    def _switch_mode(self):
        idx = self.mode_box.currentIndex(); self.stack.setCurrentIndex(idx)
        self.tabs.setTabVisible(2, self.mode == "wedge")
        self.a_bolt.setEnabled(self.mode != "toppling"); self.a_chk.setEnabled(self.mode != "toppling")
        self.last = None; self.txt.clear(); self.tab_fig.clear(); self.tab_stereo.clear(); self.table.clear()
        self.statusBar().showMessage(f"Mod: {self.mode_box.currentText()}", 3000)

    def _error(self, msg):
        self.txt.setPlainText("ANALİZ YAPILAMADI\n\n" + msg); self.tab_fig.clear(); self.tab_stereo.clear(); self.table.clear()
        self.tabs.setCurrentIndex(0); QMessageBox.critical(self, "Hata", msg)

    def _busy(self, on: bool):
        if on:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); self.statusBar().addPermanentWidget(self.progress); self.progress.show()
        else:
            QApplication.restoreOverrideCursor(); self.progress.hide()

    # ---------------------------------------------------------------- girdi okuma
    def read_wedge(self) -> WedgeInput:
        v = self.val
        tc = TensionCrack(v("tc_dip"), v("tc_dd"), v("tc_L")) if v("tc_on") else None
        water = Water(v("water_mode"), v("gw"), v("w_pct"), v("u1"), v("u2"), v("ut"))
        seis = Seismic(v("ah"), v("s_trend"), v("s_plunge"))
        T = v("T")
        if T > 0 and (v("T_trend") is None or v("T_plunge") is None):
            raise ValueError("Destek kuvveti > 0 için trend ve plunge girilmeli (veya 'Gerekli Destek' ile otomatik doldurun).")
        sup = Support(T, v("T_trend") or 0.0, v("T_plunge") or 0.0, v("T_passive"))
        mode = v("scale_mode"); sval = None if mode == "height" else v("scale_value")
        return WedgeInput(Joint(v("j1_dip"), v("j1_dd"), v("j1_c"), v("j1_phi")), Joint(v("j2_dip"), v("j2_dd"), v("j2_c"), v("j2_phi")),
                          Plane(v("face_dip"), v("face_dd")), Plane(v("up_dip"), v("up_dd")), v("H"), v("gamma"), tc, water, seis, sup,
                          scale_mode=mode, scale_value=sval)

    def read_planar(self) -> PlanarInput:
        v = self.val
        T = v("p_T")
        if T > 0 and v("p_theta") is None:
            raise ValueError("Destek kuvveti > 0 için açı θ girilmeli (veya 'Gerekli Destek' ile otomatik doldurun).")
        return PlanarInput(v("p_H"), v("p_face"), v("p_plane"), v("p_upper"), v("p_c"), v("p_phi"), v("p_gamma"),
                           v("p_tc_b") if v("p_tc_on") else None, v("p_water"), v("p_gw"), v("p_wpct"), v("p_up"), v("p_ut"),
                           v("p_ah"), v("p_av"), T, v("p_theta") or 0.0, v("p_passive"))

    def read_toppling(self) -> TopplingInput:
        v = self.val
        return TopplingInput(v("t_face"), v("t_upper"), v("t_disc"), v("t_base"), v("t_dx"), int(v("t_nb")), int(v("t_na")),
                             v("t_phi"), v("t_gamma"), v("t_water"), v("t_gw"), v("t_ah"), v("t_T"), v("t_delta"), v("t_hT"))

    def bolt_spec(self) -> BoltSpec:
        v = self.val
        return BoltSpec(v("b_cap"), v("b_dia"), v("b_bond"), v("b_fsb"), v("b_minb"), v("b_extra"), v("b_smin"), v("b_smax"))

    # ---------------------------------------------------------------- analiz
    def on_analyze(self):
        try:
            if self.mode == "wedge":
                inp = self.read_wedge(); res = analyze(inp)
                self.txt.setPlainText(res.summary())
                self.tab_fig.fig.clear(); plot_wedge(res, show=False, fig=self.tab_fig.fig); self.tab_fig.canvas.draw_idle()
                ax = self.tab_stereo.ax(); plot_stereonet(inp, res.geometry, ax=ax, show=False, res=res); self.tab_stereo.canvas.draw_idle()
                self._fill_table([["Büyüklük", "Değer"], ["FS", f"{res.factor_of_safety:.3f}"], ["Mod", res.mode],
                                  ["Hacim (m³)", f"{res.volume:,.1f}"], ["Ağırlık (kN)", f"{res.weight:,.1f}"],
                                  *[[f"Alan {k} (m²)", f"{a:,.1f}"] for k, a in res.areas.items()],
                                  *[[f"Normal kuvvet {k} (kN)", f"{n:,.1f}"] for k, n in res.normal_forces.items()],
                                  ["Kaydırıcı (kN)", f"{res.driving_force:,.1f}"], ["Direnç (kN)", f"{res.resisting_force:,.1f}"]])
                self.last = ("wedge", inp, res, [self.tab_fig.fig, self.tab_stereo.fig])
            elif self.mode == "planar":
                inp = self.read_planar(); res = planar_analyze(inp)
                self.txt.setPlainText(res.summary())
                ax = self.tab_fig.ax(); plot_planar(res, ax=ax, show=False); self.tab_fig.canvas.draw_idle()
                self._fill_table([["Büyüklük", "Değer (kN/m)"], ["FS", f"{res.factor_of_safety:.3f}"], ["W", f"{res.weight:,.1f}"],
                                  ["U (düzlem)", f"{res.water_U:,.1f}"], ["V (çatlak)", f"{res.water_V:,.1f}"], ["αhW", f"{res.seismic_force:,.1f}"],
                                  ["N'", f"{res.normal_force:,.1f}"], ["S", f"{res.driving:,.1f}"], ["R", f"{res.resisting:,.1f}"]])
                self.last = ("planar", inp, res, [self.tab_fig.fig])
            else:
                inp = self.read_toppling(); res = toppling_analyze(inp)
                self.txt.setPlainText(res.summary())
                ax = self.tab_fig.ax(); plot_toppling(res, ax=ax, show=False); self.tab_fig.canvas.draw_idle()
                rows = [["Blok", "y (m)", "y/Δx", "W (kN)", "U (kN)", "V (kN)", "Mod", "P(n−1) kN/m"]]
                for bl in res.blocks:
                    rows.append([str(bl["n"]), f"{bl['y']:.2f}", f"{bl['y'] / inp.block_width:.2f}", f"{bl['W']:,.0f}",
                                 f"{bl['U']:,.0f}", f"{bl['V']:,.0f}", bl["mode"], f"{bl['P']:,.1f}"])
                self._fill_table(rows, color_col=6, colors={"stabil": "#a9dfbf", "devrilme": "#f1948a", "kayma": "#f9e79f"})
                self.last = ("toppling", inp, res, [self.tab_fig.fig])
            self.tabs.setCurrentIndex(0)
            fs = res.factor_of_safety if self.mode != "toppling" else res.fs
            self.statusBar().showMessage(f"Analiz tamam — FS = {rstyle.fs_text(fs)}", 8000)
        except Exception as e:
            self._error(str(e))

    def _fill_table(self, rows, color_col=None, colors=None, fs_cells=False):
        self.table.clear(); self.table.setRowCount(len(rows) - 1); self.table.setColumnCount(len(rows[0]))
        self.table.setHorizontalHeaderLabels(rows[0])
        for r, row in enumerate(rows[1:]):
            for c, val in enumerate(row):
                it = QTableWidgetItem(str(val)); it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c > 0: it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if color_col is not None and c == color_col and colors and str(val) in colors:
                    it.setBackground(QColor(colors[str(val)]))
                if fs_cells and c > 0:
                    try:
                        ok = str(val).endswith("*"); it.setBackground(QColor("#d5f5e3" if ok else "#fadbd8"))
                    except Exception:
                        pass
                self.table.setItem(r, c, it)
        self.table.resizeRowsToContents()

    # ---------------------------------------------------------------- gerekli destek
    def on_required(self):
        try:
            if self.mode == "wedge":
                self.setval("T", 0.0); inp = self.read_wedge()
                self._busy(True); QApplication.processEvents()
                try:
                    sr = required_support(inp, self.val("FS_target"), self.val("T_trend"), self.val("T_plunge"), self.val("T_passive"))
                finally:
                    self._busy(False)
                if not sr.achievable:
                    QMessageBox.warning(self, "Hedef sağlanamıyor", sr.summary()); return
                if sr.force == 0.0:
                    QMessageBox.information(self, "Destek gerekmiyor", sr.summary()); return
                self.setval("T", sr.force); self.setval("T_trend", f"{sr.trend:.1f}"); self.setval("T_plunge", f"{sr.plunge:.1f}")
                self.on_analyze(); self.txt.appendPlainText("\n" + sr.summary()); QMessageBox.information(self, "Gerekli destek", sr.summary())
            elif self.mode == "planar":
                self.setval("p_T", 0.0); inp = self.read_planar(); tgt = self.val("p_FS")
                T, ang, fs0 = planar_required_support(inp, tgt, self.val("p_theta"), self.val("p_passive"))
                if T == 0.0:
                    QMessageBox.information(self, "Destek gerekmiyor", f"Mevcut FS = {fs0:.3f} zaten hedef FS = {tgt:.2f} değerini sağlıyor."); return
                if not np.isfinite(T) or T < 0:
                    QMessageBox.warning(self, "Hedef sağlanamıyor", f"Bu açıyla (θ = {ang:.1f}°) hedef FS sağlanamıyor; açıyı boş bırakın."); return
                self.setval("p_T", T); self.setval("p_theta", f"{ang:.1f}"); self.on_analyze()
                msg = f"Mevcut FS = {fs0:.3f} → hedef {tgt:.2f}\nGerekli destek: {T:,.1f} kN/m (θ = {ang:.1f}°, {'pasif' if self.val('p_passive') else 'aktif'})"
                self.txt.appendPlainText("\n" + msg); QMessageBox.information(self, "Gerekli destek", msg)
            else:
                self.setval("t_T", 0.0); inp = self.read_toppling(); tgt = self.val("t_FS")
                T = toppling_required_support(inp, tgt); fs0 = toppling_analyze(inp).fs
                if T <= 0:
                    QMessageBox.information(self, "Ankraj gerekmiyor", f"Mevcut FS = {fs0:.3f} hedef FS = {tgt:.2f} değerini sağlıyor."); return
                self.setval("t_T", T); self.on_analyze()
                msg = f"Mevcut FS = {fs0:.3f} → hedef {tgt:.2f}\nTopuk bloğuna gerekli ankraj: {T:,.1f} kN/m (δ = {self.val('t_delta'):.1f}°)"
                self.txt.appendPlainText("\n" + msg); QMessageBox.information(self, "Gerekli ankraj", msg)
        except Exception as e:
            self._error(str(e))

    # ---------------------------------------------------------------- bulon
    def on_bolts(self):
        try:
            spec = self.bolt_spec()
            if self.mode == "planar":
                inp = self.read_planar()
                if inp.support_force <= 0: raise ValueError("Destek kuvveti 0 — önce 'Gerekli Destek' ile T'yi hesaplayın.")
                res = planar_analyze(inp); bp = bolt_pattern_planar(res, inp.support_force, inp.support_angle, spec)
                fn = lambda s_, L_: bolt_check_planar(inp, s_, L_, inp.support_angle, spec, self.val("p_FS"), self.val("p_passive"))
            elif self.mode == "wedge":
                inp = self.read_wedge()
                if inp.support.force <= 0: raise ValueError("Destek kuvveti 0 — önce 'Gerekli Destek' ile T'yi hesaplayın.")
                res = analyze(inp); bp = bolt_pattern_wedge(res, inp.support.force, inp.support.trend, inp.support.plunge, spec)
                fn = lambda s_, L_: bolt_check_wedge(inp, s_, L_, inp.support.trend, inp.support.plunge, spec, self.val("FS_target"), self.val("T_passive"))
            else:
                return
        except Exception as e:
            self._error(str(e)); return
        spacings = [round(x, 2) for x in np.arange(spec.s_min, spec.s_max + 1e-9, 0.25)]
        lengths = [L for L in STANDARD_LENGTHS if L <= max(bp.total_length * 1.5, 6)] or STANDARD_LENGTHS[:4]
        self.txt.setPlainText(res.summary() + "\n\n" + bp.summary() + "\n\nÖneri matrisi hesaplanıyor…")
        self.sp_box.clear()
        for s_ in spacings: self.sp_box.addItem(f"{s_:g}")
        self.setval("b_s_sel", f"{bp.spacing:g}"); self.setval("b_L_sel", f"{bp.total_length:g}")
        self._busy(True)

        def compute():
            mat = []
            for s_ in spacings:
                row = []
                for L_ in lengths:
                    try:
                        c = fn(s_, L_); row.append((c.fs, c.ok))
                    except Exception:
                        row.append((np.nan, False))
                mat.append(row)
            return mat
        self.worker = Worker(compute)
        self.worker.done.connect(lambda mat: self._bolts_done(mat, spacings, lengths, res, bp))
        self.worker.failed.connect(lambda m: (self._busy(False), self._error(m)))
        self.worker.start()

    def _bolts_done(self, mat, spacings, lengths, res, bp):
        self._busy(False)
        rows = [["s (m) \\ L (m)"] + [f"{L:g}" for L in lengths]]
        best = None
        for s_, row in zip(spacings, mat):
            cells = []
            for (fs, ok), L_ in zip(row, lengths):
                cells.append(("∞" if np.isinf(fs) else f"{fs:.2f}" if np.isfinite(fs) else "—") + ("*" if ok else ""))
                if ok and (best is None or s_ > best[0]): best = (s_, L_, fs)
            rows.append([f"{s_:g}"] + cells)
        self._fill_table(rows, fs_cells=True)
        lines = ["ÖNERİ TABLOSU — FS (aralık × boy; * hedef sağlanıyor)", "  L (m):  " + "".join(f"{L:8g}" for L in lengths)]
        for r in rows[1:]:
            lines.append(f"  s={r[0]:>5} " + "".join(f"{c:>8}" for c in r[1:]))
        if best:
            lines.append(f"\nÖNERİ: en geniş karelajda en kısa boy → s = {best[0]:.2f} m, L = {best[1]:g} m (FS = {best[2]:.2f})")
            self.setval("b_s_sel", f"{best[0]:g}"); self.setval("b_L_sel", f"{best[1]:g}")
        else:
            lines.append("\nHiçbir kombinasyon hedefi sağlamıyor: daha yüksek kapasite veya daha sık aralık gerekir.")
        self.txt.setPlainText(res.summary() + "\n\n" + bp.summary() + "\n\n" + "\n".join(lines))
        self.tabs.setCurrentIndex(3); self.statusBar().showMessage("Bulon öneri matrisi hazır — Tablo sekmesi", 8000)

    def on_bolt_check(self):
        try:
            spec = self.bolt_spec(); s_ = float(self.sp_box.currentText()); L_ = float(self.L_box.currentText().replace(",", "."))
            if self.mode == "planar":
                inp = self.read_planar()
                chk = bolt_check_planar(inp, s_, L_, inp.support_angle, spec, self.val("p_FS"), self.val("p_passive"))
            else:
                inp = self.read_wedge()
                chk = bolt_check_wedge(inp, s_, L_, inp.support.trend, inp.support.plunge, spec, self.val("FS_target"), self.val("T_passive"))
        except Exception as e:
            self._error(str(e)); return
        self.txt.appendPlainText("\n" + chk.summary()); self.tabs.setCurrentIndex(0)
        rows = [["Yüz konumu (m)", "Serbest boy (m)", "Kök boyu (m)", "Kapasite (kN)"]]
        rows += [[f"{p:.2f}", f"{f:.2f}", f"{max(b, 0):.2f}", f"{c:.1f}"] for p, f, b, c in chk.rows]
        self._fill_table(rows)
        util = 100 * chk.T_provided / max(chk.T_required, 1e-9)
        QMessageBox.information(self, "Tasarım kontrolü", f"s = {s_:.2f} m, L = {L_:.1f} m → FS = {chk.fs:.3f}\n"
                                f"{'UYGUN ✓' if chk.ok else 'YETERSİZ ✗'}  (kullanım %{util:.0f})")

    # ---------------------------------------------------------------- rapor
    def on_pdf(self):
        if not self.last:
            QMessageBox.warning(self, "Rapor", "Önce bir analiz çalıştırın (F5)."); return
        mode, inp, res, figs = self.last
        path, _ = QFileDialog.getSaveFileName(self, "PDF raporu kaydet", f"kinematix_{mode}_{datetime.date.today()}.pdf", "PDF (*.pdf)")
        if not path: return
        v = self.val
        project = {"Proje": v("rp_proj") or "—", "Konum": v("rp_loc") or "—", "Km / Kesit": v("rp_km") or "—",
                   "Hazırlayan": v("rp_eng") or "—", "Kontrol": v("rp_chk") or "—", "Doküman No": v("rp_doc") or "—",
                   "Revizyon": "0", "Tarih": datetime.date.today().strftime("%d.%m.%Y")}
        from reportlab.lib.units import mm
        try:
            title, sub, key, inputs, figcaps, tables, warns = self._report_content(mode, inp, res, figs)
            tables = [(n, r, [w_ * mm for w_ in wd]) for n, r, wd in tables]
            Report(project).build(path, title, sub, mode, key, inputs, figcaps, tables,
                                  [("Program çıktısı (tam metin)", self.txt.toPlainText().strip())], v("rp_note"), warns)
        except Exception as e:
            QMessageBox.critical(self, "Rapor hatası", f"{e}\n{traceback.format_exc()}"); return
        self.statusBar().showMessage(f"PDF oluşturuldu: {path}", 10000)
        QMessageBox.information(self, "Rapor", f"PDF oluşturuldu:\n{path}")

    def _report_content(self, mode, inp, res, figs):
        v = self.val
        if mode == "wedge":
            j1, j2, tgt = inp.joint1, inp.joint2, v("FS_target"); fs = res.factor_of_safety
            title, sub = "Kama Stabilite Analizi", "Tetrahedral kama — Hoek & Bray vektörel limit denge yöntemi"
            inputs = [("Eklem 1 (dip/dip dir)", f"{j1.dip:g}° / {j1.dipdir:g}°"), ("Eklem 1 c / φ", f"{j1.cohesion:g} kPa / {j1.friction:g}°"),
                      ("Eklem 2 (dip/dip dir)", f"{j2.dip:g}° / {j2.dipdir:g}°"), ("Eklem 2 c / φ", f"{j2.cohesion:g} kPa / {j2.friction:g}°"),
                      ("Şev yüzü", f"{inp.slope_face.dip:g}° / {inp.slope_face.dipdir:g}°"), ("Üst şev", f"{inp.upper_slope.dip:g}° / {inp.upper_slope.dipdir:g}°"),
                      ("Şev yüksekliği", f"{inp.slope_height:g} m"), ("Birim hacim ağırlığı", f"{inp.unit_weight:g} kN/m³"),
                      ("Kama ölçekleme", f"{inp.scale_mode}" + (f" = {inp.scale_value:g}" if inp.scale_value else "")),
                      ("Çekme çatlağı", f"{inp.tension_crack.dip:g}°/{inp.tension_crack.dipdir:g}°, {inp.tension_crack.distance_from_crest:g} m" if inp.tension_crack else "yok"),
                      ("Su basıncı", {"dry": "kuru", "filled": "dolu çatlak (H&B)", "percent": f"%{inp.water.percent:g} dolu", "custom": "özel"}[inp.water.mode]),
                      ("Sismik katsayı", f"α = {inp.seismic.coefficient:g}"),
                      ("Destek", f"{inp.support.force:,.0f} kN @ {inp.support.trend:g}°/{inp.support.plunge:g}° ({'pasif' if inp.support.passive else 'aktif'})"),
                      ("Hedef FS", f"{tgt:g}")]
            key = [("Güvenlik sayısı", f"{fs:.3f}", fs >= tgt), ("Göçme modu", res.mode.split(" (")[0], None),
                   ("Kama hacmi", f"{res.volume:,.0f} m³", None), ("Kama ağırlığı", f"{res.weight:,.0f} kN", None)]
            figcaps = [(figs[0], "Kama geometrisi, göçme modu ve kayma yönü (3D)"), (figs[1], "Stereonet — düzlemler, kesişim çizgisi ve sürtünme konisi")]
            tables = [("Kuvvet dengesi", [["Büyüklük", "Değer"], ["Kama ağırlığı", f"{res.weight:,.1f} kN"],
                                          *[[f"Su kuvveti {k}", f"{u:,.1f} kN"] for k, u in res.water_forces.items()],
                                          ["Sismik kuvvet", f"{res.seismic_force:,.1f} kN"], ["Destek kuvveti", f"{res.support_force:,.1f} kN"],
                                          *[[f"Normal kuvvet {k}", f"{n:,.1f} kN"] for k, n in res.normal_forces.items()],
                                          ["Kaydırıcı kuvvet", f"{res.driving_force:,.1f} kN"], ["Direnç kuvveti", f"{res.resisting_force:,.1f} kN"],
                                          ["Güvenlik sayısı", f"{fs:.3f}"]], [90, 90]),
                      ("Geometri", [["Büyüklük", "Değer"], *[[f"Alan {k}", f"{a:,.1f} m²"] for k, a in res.areas.items()],
                                    ["Tepe uzunluğu |BC|", f"{res.geometry.crest_length:,.1f} m"], ["Basamak genişliği", f"{res.geometry.bench_width:,.1f} m"],
                                    ["Kesişim çizgisi", f"trend {res.intersection_line[0]:.1f}°, plunge {res.intersection_line[1]:.1f}°"]], [90, 90])]
            return title, sub, key, inputs, figcaps, tables, list(res.warnings)
        if mode == "planar":
            tgt = v("p_FS"); fs = res.factor_of_safety
            title, sub = "Düzlemsel Kayma Analizi", "Hoek & Bray düzlemsel limit denge çözümü — 1 m şev uzunluğu"
            inputs = [("Şev yüksekliği H", f"{inp.slope_height:g} m"), ("Şev yüzü ψf", f"{inp.face_angle:g}°"),
                      ("Kayma düzlemi ψp", f"{inp.plane_angle:g}°"), ("Üst şev ψs", f"{inp.upper_angle:g}°"),
                      ("Kohezyon c", f"{inp.cohesion:g} kPa"), ("Sürtünme açısı φ", f"{inp.friction:g}°"),
                      ("Birim hacim ağırlığı", f"{inp.unit_weight:g} kN/m³"),
                      ("Çekme çatlağı", f"b = {inp.tc_distance:g} m" if inp.tc_distance is not None else "yok"),
                      ("Su", {"dry": "kuru", "percent": f"çatlak %{inp.water_percent:g} dolu", "custom": "özel basınç"}[inp.water_mode]),
                      ("Sismik αh / αv", f"{inp.seismic_h:g} / {inp.seismic_v:g}"),
                      ("Destek", f"{inp.support_force:,.0f} kN/m @ {inp.support_angle:g}° ({'pasif' if inp.support_passive else 'aktif'})"),
                      ("Hedef FS", f"{tgt:g}")]
            key = [("Güvenlik sayısı", f"{fs:.3f}", fs >= tgt), ("Blok ağırlığı", f"{res.weight:,.0f} kN/m", None),
                   ("Çatlak derinliği", f"{res.tc_depth:.2f} m" if inp.tc_distance is not None else "—", None),
                   ("Su kuvvetleri U / V", f"{res.water_U:,.0f} / {res.water_V:,.0f}", None)]
            figcaps = [(figs[0], "Düzlemsel kayma kesiti, su basıncı dağılımı ve kuvvetler")]
            tables = [("Kuvvet dengesi (kN/m)", [["Büyüklük", "Değer"], ["Blok alanı", f"{res.area:,.2f} m²"], ["Ağırlık W", f"{res.weight:,.1f}"],
                                                 ["Kayma düzlemi uzunluğu", f"{res.plane_length:,.2f} m"], ["Su U (düzlem)", f"{res.water_U:,.1f}"],
                                                 ["Su V (çatlak)", f"{res.water_V:,.1f}"], ["Sismik αhW", f"{res.seismic_force:,.1f}"],
                                                 ["Etkin normal kuvvet", f"{res.normal_force:,.1f}"], ["Kaydırıcı kuvvet", f"{res.driving:,.1f}"],
                                                 ["Direnç kuvveti", f"{res.resisting:,.1f}"], ["Güvenlik sayısı", f"{fs:.3f}"]], [90, 90])]
            return title, sub, key, inputs, figcaps, tables, list(res.warnings)
        tgt = v("t_FS")
        title, sub = "Blok Devrilme Analizi", "Goodman & Bray (1976) blok devrilme limit denge yöntemi — 1 m şev uzunluğu"
        inputs = [("Şev yüzü ψf", f"{inp.face_angle:g}°"), ("Üst şev ψs", f"{inp.upper_angle:g}°"),
                  ("Süreksizlik eğimi ψd", f"{inp.disc_dip:g}° (ψp = {90 - inp.disc_dip:g}°)"), ("Taban genel eğimi ψb", f"{inp.base_angle:g}°"),
                  ("Blok genişliği Δx", f"{inp.block_width:g} m"), ("Blok sayısı", f"{inp.n_below} tepe altı + {inp.n_above} tepe üstü"),
                  ("Sürtünme açısı φ", f"{inp.friction:g}°"), ("Birim hacim ağırlığı", f"{inp.unit_weight:g} kN/m³"),
                  ("Eklem su doluluğu", f"%{inp.water_percent:g}"), ("Sismik αh", f"{inp.seismic_h:g}"),
                  ("Topuk ankrajı", f"{inp.support_force:,.0f} kN/m @ {inp.support_angle:g}°"), ("Hedef FS", f"{tgt:g}")]
        key = [("Güvenlik sayısı", f"{res.fs:.3f}", res.fs >= tgt), ("Gerekli φ", f"{res.phi_required:.2f}°", None),
               ("Topuk ankrajı (φ mevcut)", f"{res.T_required:,.0f} kN/m", None), ("Şev yüksekliği", f"{res.slope_height:.1f} m", None)]
        figcaps = [(figs[0], "Blok kolonları, göçme modları ve eklem su seviyeleri")]
        rows = [["Blok", "y (m)", "y/Δx", "W (kN)", "U (kN)", "V (kN)", "Mod", "P(n−1) (kN/m)"]]
        for bl in res.blocks:
            rows.append([str(bl["n"]), f"{bl['y']:.2f}", f"{bl['y'] / inp.block_width:.2f}", f"{bl['W']:,.0f}", f"{bl['U']:,.0f}",
                         f"{bl['V']:,.0f}", bl["mode"], f"{bl['P']:,.1f}"])
        return title, sub, key, inputs, [(figs[0], figcaps[0][1])], [("Blok bazında sonuçlar", rows, [14, 20, 16, 26, 22, 22, 24, 36])], list(res.warnings)

    # ---------------------------------------------------------------- kaydet / yükle / ayarlar
    def _state(self):
        d = {k: self.val(k) for k in self.f}
        d["mode"] = self.mode; return d

    def _apply_state(self, d):
        if "mode" in d:
            idx = self.mode_box.findData(d["mode"])
            if idx >= 0: self.mode_box.setCurrentIndex(idx)
        for k, v in d.items():
            if k in self.f: self.setval(k, v)

    def on_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Girdileri kaydet", "kinematix_girdi.json", "JSON (*.json)")
        if not path: return
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self._state(), fh, indent=2, ensure_ascii=False)
        self.statusBar().showMessage(f"Kaydedildi: {path}", 6000)

    def on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Girdileri yükle", "", "JSON (*.json)")
        if not path: return
        with open(path, encoding="utf-8") as fh:
            self._apply_state(json.load(fh))
        self.statusBar().showMessage(f"Yüklendi: {path}", 6000)

    def _load_settings(self):
        s = QSettings(ORG, APP_NAME)
        self._apply_theme(s.value("theme", "light"))
        raw = s.value("state")
        if raw:
            try: self._apply_state(json.loads(raw))
            except Exception: pass
        geo = s.value("geometry")
        if geo: self.restoreGeometry(geo)

    def closeEvent(self, ev):
        s = QSettings(ORG, APP_NAME)
        s.setValue("state", json.dumps(self._state(), ensure_ascii=False)); s.setValue("geometry", self.saveGeometry())
        super().closeEvent(ev)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME); app.setOrganizationName(ORG); app.setStyle("Fusion")
    win = MainWindow(); win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
