"""
lythos.ui.equilibrium — Lythos Kinematic / Limit Denge paneli.

Kama (Swedge), düzlemsel (RocPlane) ve blok devrilme (RocTopple) limit denge
analizleri, bulon karelaj/boy tasarımı ve PDF rapor.
(Eski Kinematix uygulamasının, Lythos Suite içine gömülebilen panel hâli.)

Panel bir QMainWindow'dur: kendi araç çubuğunu, girdi dock'unu ve durum çubuğunu
taşır; suite kabuğu onu bir sekmenin içine yerleştirir.
"""
from __future__ import annotations

import sys
import json
import datetime
import traceback

from . import qt  # noqa: F401  (Qt bağlamasını matplotlib'den önce sabitler)

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDockWidget, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
                               QProgressBar, QScrollArea, QSizePolicy, QSpinBox, QStackedWidget,
                               QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem, QToolBar,
                               QVBoxLayout, QWidget)

import numpy as np

from ..rockslope import (Joint, Plane, TensionCrack, Water, Seismic, Support, WedgeInput, analyze,
                         plot_wedge, plot_stereonet, required_support, PlanarInput, planar_analyze,
                         planar_required_support, plot_planar, BoltSpec, bolt_pattern_planar,
                         bolt_pattern_wedge, bolt_check_planar, bolt_check_wedge, STANDARD_LENGTHS,
                         TopplingInput, toppling_analyze, toppling_required_support, plot_toppling, Report)
from ..rockslope import style as rstyle
from ..rockslope.report import PROJECT_FIELDS, PROJECT_LABEL
from ..rockslope.text import ACTIVE, MODE_TEXT, NONE_TEXT, PASSIVE, WATER_MODE
from ..i18n import T as _tr
from ..i18n import pct
from ..i18n import language as _lang
from .widgets import MplTab, Num, Opt, Worker, note


class EquilibriumPanel(QMainWindow):
    """Limit denge paneli.

    Arayüz tamamen `lythos.i18n` üzerinden çift dillidir. Dil değişince panel,
    girdi durumunu koruyarak kendini yeniden kurar (`set_language`); böylece her
    etiket için ayrı bir referans tutmak gerekmez.
    """

    MODE_KEYS = ("wedge", "planar", "toppling")

    @staticmethod
    def mode_labels():
        return {"wedge": _tr("Kama (Swedge)", "Wedge (Swedge)"),
                "planar": _tr("Düzlemsel (RocPlane)", "Planar (RocPlane)"),
                "toppling": _tr("Devrilme (RocTopple)", "Toppling (RocTopple)")}

    def __init__(self, parent=None):
        super().__init__(parent)
        # Gömülü panel: pencere değil, sekme içeriği olarak yaşar.
        self.setWindowFlags(Qt.WindowType.Widget)
        self._lang = _lang()
        self.f = {}                # key -> widget
        self.last = None           # (mode, inp, res, figs)
        self.worker = None
        self.toolbar = None
        self.dock = None
        self.setStatusBar(QStatusBar())
        self._build_all()

    def _build_all(self):
        self._build_toolbar()
        self._build_dock()
        self._build_central()
        self._switch_mode()

    # ---------------------------------------------------------------- dil
    def set_language(self, lang: str):
        """Dili değiştirir ve paneli girdileri koruyarak yeniden kurar."""
        if lang == self._lang:
            return
        state = self.state()
        self._lang = lang
        if self.toolbar is not None:
            self.removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
            self.toolbar = None
        if self.dock is not None:
            self.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        self.f = {}
        self.last = None
        self._build_all()
        self.apply_state(state)

    # ---------------------------------------------------------------- UI
    def _build_toolbar(self):
        tb = QToolBar("Lythos Kinematic"); tb.setMovable(False); tb.setIconSize(QSize(18, 18))
        self.addToolBar(tb); self.toolbar = tb
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        tb.addWidget(QLabel("  " + _tr("Analiz türü: ", "Analysis type: ")))
        self.mode_box = QComboBox()
        labels = self.mode_labels()
        for key in self.MODE_KEYS:
            self.mode_box.addItem(labels[key], key)
        self.mode_box.currentIndexChanged.connect(self._switch_mode)
        tb.addWidget(self.mode_box); tb.addSeparator()

        def act(text, slot, shortcut=None, tip=""):
            a = QAction(text, self); a.triggered.connect(slot)
            if shortcut: a.setShortcut(QKeySequence(shortcut))
            a.setToolTip(tip or text); tb.addAction(a); return a
        self.a_run = act(_tr("▶ Analiz Et", "▶ Analyse"), self.on_analyze, "F5",
                         _tr("Seçili analizi çalıştır (F5)", "Run the selected analysis (F5)"))
        self.a_req = act(_tr("Gerekli Destek", "Required Support"), self.on_required, "F6",
                         _tr("Hedef FS için gerekli destek kuvveti (F6)",
                             "Support force required for the target FS (F6)"))
        self.a_bolt = act(_tr("Bulon Önerisi", "Bolt Recommendation"), self.on_bolts, "F7",
                          _tr("Karelaj × boy öneri matrisi (F7)", "Spacing × length recommendation matrix (F7)"))
        self.a_chk = act(_tr("Bulon Kontrol", "Bolt Check"), self.on_bolt_check, "F8",
                         _tr("Seçilen karelaj + boy ile kapasite/FS kontrolü (F8)",
                             "Capacity/FS check for the chosen spacing + length (F8)"))
        tb.addSeparator()
        act(_tr("PDF Rapor", "PDF Report"), self.on_pdf, "Ctrl+P")
        tb.addSeparator()
        act(_tr("Kaydet", "Save"), self.on_save, "Ctrl+S")
        act(_tr("Yükle", "Load"), self.on_load, "Ctrl+O")

        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

    def _build_dock(self):
        dock = QDockWidget(_tr("Girdiler", "Inputs"), self); self.dock = dock
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
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
            g, fl = self._grp(f"{_tr('Eklem', 'Joint')} {j[-1]}")
            self._pair(fl, _tr("Dip / Dip dir", "Dip / Dip dir"), f"{j}_dip", Num(dflt[0], 0, 90, 1, "°"),
                       "", f"{j}_dd", Num(dflt[1], 0, 360, 1, "°"))
            self._pair(fl, "c / φ", f"{j}_c", Num(dflt[2], 0, 1e5, 1, "kPa"), "", f"{j}_phi", Num(dflt[3], 0, 89, 1, "°"))
            v.addWidget(g)
        g, fl = self._grp(_tr("Şev geometrisi", "Slope geometry"))
        self._pair(fl, _tr("Şev yüzü dip / dip dir", "Slope face dip / dip dir"), "face_dip", Num(65, 1, 90, 1, "°"),
                   "", "face_dd", Num(185, 0, 360, 1, "°"))
        self._pair(fl, _tr("Üst şev dip / dip dir", "Upper slope dip / dip dir"), "up_dip", Num(12, 0, 89, 1, "°"),
                   "", "up_dd", Num(195, 0, 360, 1, "°"))
        self._pair(fl, _tr("Şev yüksekliği / γ", "Slope height / γ"), "H", Num(40, 0.1, 1e4, 2, "m"),
                   "", "gamma", Num(25, 1, 40, 2, "kN/m³"))
        self.scale_box = QComboBox()
        for lab, key in ((_tr("Şev yüksekliği (maks. kama)", "Slope height (max. wedge)"), "height"),
                         (_tr("Tepe uzunluğu (m)", "Crest length (m)"), "crest_length"),
                         (_tr("Basamak genişliği (m)", "Bench width (m)"), "bench_width"),
                         (_tr("Kama hacmi (m³)", "Wedge volume (m³)"), "volume"),
                         (_tr("Kama ağırlığı (kN)", "Wedge weight (kN)"), "weight")):
            self.scale_box.addItem(lab, key)
        self.f["scale_mode"] = self.scale_box
        self._pair(fl, _tr("Kamayı ölçekle", "Scale the wedge"), "scale_mode", self.scale_box,
                   _tr("değer", "value"), "scale_value", Opt("—"))
        v.addWidget(g)
        g, fl = self._grp(_tr("Çekme çatlağı", "Tension crack"))
        self._row(fl, "", "tc_on", QCheckBox(_tr("Çekme çatlağı var", "Tension crack present")))
        self._pair(fl, _tr("Dip / Dip dir", "Dip / Dip dir"), "tc_dip", Num(70, 1, 90, 1, "°"),
                   "", "tc_dd", Num(165, 0, 360, 1, "°"))
        self._row(fl, _tr("Tepeden mesafe", "Distance from crest"), "tc_L", Num(8, 0, 1e4, 2, "m"))
        v.addWidget(g)
        g, fl = self._grp(_tr("Su basıncı", "Water pressure"))
        wb = QComboBox()
        for lab, key in ((_tr("Kuru", "Dry"), "dry"),
                         (_tr("Dolu çatlak (Hoek & Bray)", "Filled crack (Hoek & Bray)"), "filled"),
                         (_tr("Yüzde dolu", "Percent filled"), "percent"),
                         (_tr("Özel basınç", "Custom pressure"), "custom")):
            wb.addItem(lab, key)
        self._row(fl, _tr("Model", "Model"), "water_mode", wb)
        self._pair(fl, _tr("γw / doluluk", "γw / filling"), "gw", Num(9.81, 1, 15, 2, "kN/m³"),
                   "", "w_pct", Num(100, 0, 100, 0, "%"))
        self._pair(fl, "u J1 / u J2", "u1", Num(0, 0, 1e5, 1, "kPa"), "", "u2", Num(0, 0, 1e5, 1, "kPa"))
        self._row(fl, _tr("u çatlak", "u crack"), "ut", Num(0, 0, 1e5, 1, "kPa"))
        v.addWidget(g)
        g, fl = self._grp(_tr("Sismik yük (pseudo-statik)", "Seismic load (pseudo-static)"))
        self._pair(fl, _tr("Katsayı α / trend", "Coefficient α / trend"), "ah", Num(0, 0, 2, 3, "", 0.05),
                   "", "s_trend", Opt(_tr("şev yönü", "slope direction")))
        self._row(fl, "Plunge", "s_plunge", Num(0, -90, 90, 1, "°"))
        v.addWidget(g)
        g, fl = self._grp(_tr("Destek (bulon / ankraj)", "Support (bolt / anchor)"))
        self._pair(fl, _tr("Kuvvet / hedef FS", "Force / target FS"), "T", Num(0, 0, 1e9, 1, "kN"),
                   "", "FS_target", Num(1.5, 1, 5, 2, "", 0.1))
        self._pair(fl, _tr("Trend / plunge", "Trend / plunge"), "T_trend", Opt(_tr("optimum", "optimum")),
                   "", "T_plunge", Opt(_tr("optimum", "optimum")))
        self._row(fl, "", "T_passive", QCheckBox(_tr("Pasif (varsayılan aktif)", "Passive (active by default)")))
        v.addWidget(g); v.addStretch(1)
        return w

    # ---- Düzlemsel formu
    def _planar_form(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0)
        g, fl = self._grp(_tr("Şev ve kayma düzlemi (2D kesit, 1 m)", "Slope and sliding plane (2D section, 1 m)"))
        self._pair(fl, _tr("H / şev yüzü ψf", "H / slope face ψf"), "p_H", Num(20, 0.1, 1e4, 2, "m"),
                   "", "p_face", Num(72, 1, 89.9, 1, "°"))
        self._pair(fl, _tr("Kayma ψp / üst şev ψs", "Sliding ψp / upper slope ψs"), "p_plane", Num(34, 0.1, 89, 1, "°"),
                   "", "p_upper", Num(0, -30, 60, 1, "°"))
        self._pair(fl, "c / φ", "p_c", Num(0, 0, 1e5, 1, "kPa"), "", "p_phi", Num(31, 0, 89, 1, "°"))
        self._row(fl, _tr("γ kaya", "γ rock"), "p_gamma", Num(25, 1, 40, 2, "kN/m³"))
        v.addWidget(g)
        g, fl = self._grp(_tr("Çekme çatlağı", "Tension crack"))
        cb = QCheckBox(_tr("Çekme çatlağı var", "Tension crack present")); cb.setChecked(True)
        self._row(fl, "", "p_tc_on", cb)
        self._row(fl, _tr("Tepeden yatay mesafe b", "Horizontal distance from crest b"), "p_tc_b",
                  Num(6, -1e4, 1e4, 2, "m"))
        fl.addRow("", note(_tr("<i>b &lt; 0: çatlak şev yüzünde</i>", "<i>b &lt; 0: crack on the slope face</i>")))
        v.addWidget(g)
        g, fl = self._grp(_tr("Su basıncı", "Water pressure"))
        wb = QComboBox()
        for lab, key in ((_tr("Kuru", "Dry"), "dry"),
                         (_tr("Çatlak % dolu (Hoek & Bray)", "Crack % filled (Hoek & Bray)"), "percent"),
                         (_tr("Özel basınç", "Custom pressure"), "custom")):
            wb.addItem(lab, key)
        self._row(fl, _tr("Model", "Model"), "p_water", wb)
        self._pair(fl, _tr("γw / doluluk", "γw / filling"), "p_gw", Num(9.81, 1, 15, 2, "kN/m³"),
                   "", "p_wpct", Num(100, 0, 100, 0, "%"))
        self._pair(fl, _tr("u düzlem / u çatlak", "u plane / u crack"), "p_up", Num(0, 0, 1e5, 1, "kPa"),
                   "", "p_ut", Num(0, 0, 1e5, 1, "kPa"))
        v.addWidget(g)
        g, fl = self._grp(_tr("Sismik yük (pseudo-statik)", "Seismic load (pseudo-static)"))
        self._pair(fl, _tr("αh / αv (aşağı +)", "αh / αv (down +)"), "p_ah", Num(0, 0, 2, 3, "", 0.05),
                   "", "p_av", Num(0, -1, 1, 3, "", 0.05))
        v.addWidget(g)
        g, fl = self._grp(_tr("Destek (kN/m)", "Support (kN/m)"))
        self._pair(fl, _tr("T / hedef FS", "T / target FS"), "p_T", Num(0, 0, 1e7, 1, "kN/m"),
                   "", "p_FS", Num(1.5, 1, 5, 2, "", 0.1))
        self._pair(fl, _tr("Açı θ (aşağı +)", "Angle θ (down +)"), "p_theta", Opt(_tr("optimum", "optimum")),
                   "", "p_passive", QCheckBox(_tr("Pasif", "Passive")))
        fl.addRow("", note(_tr("<i>θ boş: optimum açı tan(ψp+θ) = tanφ/FS</i>",
                               "<i>θ empty: optimum angle tan(ψp+θ) = tanφ/FS</i>")))
        v.addWidget(g); v.addStretch(1)
        return w

    # ---- Devrilme formu
    def _toppling_form(self):
        w = QWidget(); v = QVBoxLayout(w); v.setContentsMargins(0, 0, 0, 0)
        g, fl = self._grp(_tr("Blok devrilme geometrisi (Goodman & Bray)",
                              "Block toppling geometry (Goodman & Bray)"))
        self._pair(fl, _tr("Şev yüzü ψf / üst şev ψs", "Slope face ψf / upper slope ψs"),
                   "t_face", Num(56.6, 1, 89.9, 1, "°"), "", "t_upper", Num(4, -30, 60, 1, "°"))
        self._pair(fl, _tr("Süreksizlik ψd / taban ψb", "Discontinuity ψd / base ψb"),
                   "t_disc", Num(60, 1, 89.9, 1, "°"), "", "t_base", Num(35.8, 0, 89, 1, "°"))
        self._pair(fl, "Δx / γ", "t_dx", Num(10, 0.01, 1e3, 2, "m"), "", "t_gamma", Num(25, 1, 40, 2, "kN/m³"))
        nb = QSpinBox(); nb.setRange(1, 500); nb.setValue(10)
        na = QSpinBox(); na.setRange(0, 500); na.setValue(6)
        self._pair(fl, _tr("Blok sayısı tepe altı / üstü", "Blocks below / above crest"), "t_nb", nb, "", "t_na", na)
        self._row(fl, "φ", "t_phi", Num(38.15, 0, 44.9, 2, "°"))
        fl.addRow("", note(_tr("<i>ψp = 90 − ψd (blok tabanı eğimi), ψb ≥ ψp</i>",
                               "<i>ψp = 90 − ψd (block base angle), ψb ≥ ψp</i>")))
        v.addWidget(g)
        g, fl = self._grp(_tr("Su ve sismik yük", "Water and seismic load"))
        self._pair(fl, _tr("Eklem su doluluğu / γw", "Joint water filling / γw"), "t_water", Num(0, 0, 100, 0, "%"),
                   "", "t_gw", Num(9.81, 1, 15, 2, "kN/m³"))
        self._row(fl, _tr("Yatay αh", "Horizontal αh"), "t_ah", Num(0, 0, 2, 3, "", 0.05))
        v.addWidget(g)
        g, fl = self._grp(_tr("Topuk ankrajı (kN/m)", "Toe anchor (kN/m)"))
        self._pair(fl, _tr("T / açı δ (aşağı +)", "T / angle δ (down +)"), "t_T", Num(0, 0, 1e7, 1, "kN/m"),
                   "", "t_delta", Num(0, -60, 60, 1, "°"))
        self._pair(fl, _tr("Tabandan yükseklik / hedef FS", "Height above base / target FS"),
                   "t_hT", Opt("y1/2"), "", "t_FS", Num(1.3, 1, 5, 2, "", 0.1))
        v.addWidget(g); v.addStretch(1)
        return w

    # ---- Bulon ve rapor (ortak)
    def _bolt_form(self):
        g, fl = self._grp(_tr("Bulon karelaj / boy tasarımı", "Bolt spacing / length design"))
        self._pair(fl, _tr("Kapasite / delik çapı", "Capacity / hole diameter"), "b_cap", Num(150, 1, 1e4, 0, "kN"),
                   "", "b_dia", Num(76, 20, 300, 0, "mm"))
        self._pair(fl, _tr("Aderans τb / FS kök", "Bond τb / FS bond"), "b_bond", Num(800, 50, 1e4, 0, "kPa"),
                   "", "b_fsb", Num(2.5, 1, 5, 1))
        self._pair(fl, _tr("Min. kök / baş payı", "Min. bond / head allowance"), "b_minb", Num(2.0, 0, 10, 2, "m"),
                   "", "b_extra", Num(0.5, 0, 3, 2, "m"))
        self._pair(fl, _tr("Aralık s min / s maks", "Spacing s min / s max"), "b_smin", Num(1.0, 0.25, 10, 2, "m"),
                   "", "b_smax", Num(3.0, 0.25, 10, 2, "m"))
        self.sp_box = QComboBox(); self.f["b_s_sel"] = self.sp_box
        self.L_box = QComboBox(); self.L_box.setEditable(True)
        for L in STANDARD_LENGTHS:
            self.L_box.addItem(f"{L:g}")
        self.f["b_L_sel"] = self.L_box
        self._pair(fl, _tr("Seçim: s / L", "Selection: s / L"), "b_s_sel", self.sp_box, "", "b_L_sel", self.L_box)
        fl.addRow("", note(_tr("<i>Sıra: Gerekli Destek → Bulon Önerisi → seçim → Bulon Kontrol</i>",
                               "<i>Order: Required Support → Bolt Recommendation → select → Bolt Check</i>")))
        return g

    def _report_form(self):
        g, fl = self._grp(_tr("Rapor bilgileri", "Report information"))
        for key in PROJECT_FIELDS:
            if key in ("date", "revision"):          # otomatik doldurulur
                continue
            self._row(fl, PROJECT_LABEL(key), "rp_" + key, QLineEdit())
        self._row(fl, _tr("Değerlendirme notu", "Assessment note"), "rp_note", QLineEdit())
        return g

    def _build_central(self):
        self.tabs = QTabWidget()
        self.txt = QPlainTextEdit(); self.txt.setReadOnly(True)
        mono = QFont("Consolas" if sys.platform.startswith("win") else "DejaVu Sans Mono"); mono.setPointSize(9); self.txt.setFont(mono)
        self.tab_fig = MplTab(); self.tab_stereo = MplTab()
        self.table = QTableWidget(); self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.txt, _tr("Sonuçlar", "Results"))
        self.tabs.addTab(self.tab_fig, _tr("Grafik", "Plot"))
        self.tabs.addTab(self.tab_stereo, "Stereonet")
        self.tabs.addTab(self.table, _tr("Tablo", "Table"))
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
        self.statusBar().showMessage(f"{_tr('Mod', 'Mode')}: {self.mode_box.currentText()}", 3000)

    def _error(self, msg):
        self.txt.setPlainText(_tr("ANALİZ YAPILAMADI", "ANALYSIS FAILED") + "\n\n" + msg)
        self.tab_fig.clear(); self.tab_stereo.clear(); self.table.clear()
        self.tabs.setCurrentIndex(0); QMessageBox.critical(self, _tr("Hata", "Error"), msg)

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
            raise ValueError(_tr("Destek kuvveti > 0 için trend ve plunge girilmeli "
                                 "(veya 'Gerekli Destek' ile otomatik doldurun).",
                                 "Trend and plunge are required when the support force is > 0 "
                                 "(or let 'Required Support' fill them in)."))
        sup = Support(T, v("T_trend") or 0.0, v("T_plunge") or 0.0, v("T_passive"))
        mode = v("scale_mode"); sval = None if mode == "height" else v("scale_value")
        return WedgeInput(Joint(v("j1_dip"), v("j1_dd"), v("j1_c"), v("j1_phi")), Joint(v("j2_dip"), v("j2_dd"), v("j2_c"), v("j2_phi")),
                          Plane(v("face_dip"), v("face_dd")), Plane(v("up_dip"), v("up_dd")), v("H"), v("gamma"), tc, water, seis, sup,
                          scale_mode=mode, scale_value=sval)

    def read_planar(self) -> PlanarInput:
        v = self.val
        T = v("p_T")
        if T > 0 and v("p_theta") is None:
            raise ValueError(_tr("Destek kuvveti > 0 için açı θ girilmeli "
                                 "(veya 'Gerekli Destek' ile otomatik doldurun).",
                                 "The angle θ is required when the support force is > 0 "
                                 "(or let 'Required Support' fill it in)."))
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
                self._fill_table([[_tr("Büyüklük", "Quantity"), _tr("Değer", "Value")],
                                  ["FS", f"{res.factor_of_safety:.3f}"],
                                  [_tr("Mod", "Mode"), res.mode],
                                  [_tr("Hacim (m³)", "Volume (m³)"), f"{res.volume:,.1f}"],
                                  [_tr("Ağırlık (kN)", "Weight (kN)"), f"{res.weight:,.1f}"],
                                  *[[f"{_tr('Alan', 'Area')} {k} (m²)", f"{a:,.1f}"] for k, a in res.areas.items()],
                                  *[[f"{_tr('Normal kuvvet', 'Normal force')} {k} (kN)", f"{n:,.1f}"]
                                    for k, n in res.normal_forces.items()],
                                  [_tr("Kaydırıcı (kN)", "Driving (kN)"), f"{res.driving_force:,.1f}"],
                                  [_tr("Direnç (kN)", "Resisting (kN)"), f"{res.resisting_force:,.1f}"]])
                self.last = ("wedge", inp, res, [self.tab_fig.fig, self.tab_stereo.fig])
            elif self.mode == "planar":
                inp = self.read_planar(); res = planar_analyze(inp)
                self.txt.setPlainText(res.summary())
                ax = self.tab_fig.ax(); plot_planar(res, ax=ax, show=False); self.tab_fig.canvas.draw_idle()
                self._fill_table([[_tr("Büyüklük", "Quantity"), _tr("Değer (kN/m)", "Value (kN/m)")],
                                  ["FS", f"{res.factor_of_safety:.3f}"], ["W", f"{res.weight:,.1f}"],
                                  [f"U ({_tr('düzlem', 'plane')})", f"{res.water_U:,.1f}"],
                                  [f"V ({_tr('çatlak', 'crack')})", f"{res.water_V:,.1f}"],
                                  ["αhW", f"{res.seismic_force:,.1f}"],
                                  ["N'", f"{res.normal_force:,.1f}"], ["S", f"{res.driving:,.1f}"],
                                  ["R", f"{res.resisting:,.1f}"]])
                self.last = ("planar", inp, res, [self.tab_fig.fig])
            else:
                inp = self.read_toppling(); res = toppling_analyze(inp)
                self.txt.setPlainText(res.summary())
                ax = self.tab_fig.ax(); plot_toppling(res, ax=ax, show=False); self.tab_fig.canvas.draw_idle()
                rows = [[_tr("Blok", "Block"), "y (m)", "y/Δx", "W (kN)", "U (kN)", "V (kN)",
                         _tr("Mod", "Mode"), "P(n−1) kN/m"]]
                for bl in res.blocks:
                    rows.append([str(bl["n"]), f"{bl['y']:.2f}", f"{bl['y'] / inp.block_width:.2f}", f"{bl['W']:,.0f}",
                                 f"{bl['U']:,.0f}", f"{bl['V']:,.0f}", MODE_TEXT(bl["mode"]), f"{bl['P']:,.1f}"])
                self._fill_table(rows, color_col=6,
                                 colors={MODE_TEXT(k): c for k, c in rstyle.MODE_COLORS.items()})
                self.last = ("toppling", inp, res, [self.tab_fig.fig])
            self.tabs.setCurrentIndex(0)
            fs = res.factor_of_safety if self.mode != "toppling" else res.fs
            self.statusBar().showMessage(
                f"{_tr('Analiz tamam', 'Analysis complete')} — FS = {rstyle.fs_text(fs)}", 8000)
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
                    QMessageBox.warning(self, _tr("Hedef sağlanamıyor", "Target not achievable"),
                                        sr.summary()); return
                if sr.force == 0.0:
                    QMessageBox.information(self, _tr("Destek gerekmiyor", "No support required"),
                                            sr.summary()); return
                self.setval("T", sr.force); self.setval("T_trend", f"{sr.trend:.1f}"); self.setval("T_plunge", f"{sr.plunge:.1f}")
                self.on_analyze(); self.txt.appendPlainText("\n" + sr.summary())
                QMessageBox.information(self, _tr("Gerekli destek", "Required support"), sr.summary())
            elif self.mode == "planar":
                self.setval("p_T", 0.0); inp = self.read_planar(); tgt = self.val("p_FS")
                T, ang, fs0 = planar_required_support(inp, tgt, self.val("p_theta"), self.val("p_passive"))
                if T == 0.0:
                    QMessageBox.information(
                        self, _tr("Destek gerekmiyor", "No support required"),
                        _tr(f"Mevcut FS = {fs0:.3f} zaten hedef FS = {tgt:.2f} değerini sağlıyor.",
                            f"The current FS = {fs0:.3f} already meets the target FS = {tgt:.2f}.")); return
                if not np.isfinite(T) or T < 0:
                    QMessageBox.warning(
                        self, _tr("Hedef sağlanamıyor", "Target not achievable"),
                        _tr(f"Bu açıyla (θ = {ang:.1f}°) hedef FS sağlanamıyor; açıyı boş bırakın.",
                            f"The target FS cannot be reached at this angle (θ = {ang:.1f}°); "
                            f"leave the angle empty.")); return
                self.setval("p_T", T); self.setval("p_theta", f"{ang:.1f}"); self.on_analyze()
                sup_mode = PASSIVE() if self.val("p_passive") else ACTIVE()
                msg = _tr(f"Mevcut FS = {fs0:.3f} → hedef {tgt:.2f}\n"
                          f"Gerekli destek: {T:,.1f} kN/m (θ = {ang:.1f}°, {sup_mode})",
                          f"Current FS = {fs0:.3f} → target {tgt:.2f}\n"
                          f"Required support: {T:,.1f} kN/m (θ = {ang:.1f}°, {sup_mode})")
                self.txt.appendPlainText("\n" + msg)
                QMessageBox.information(self, _tr("Gerekli destek", "Required support"), msg)
            else:
                self.setval("t_T", 0.0); inp = self.read_toppling(); tgt = self.val("t_FS")
                T = toppling_required_support(inp, tgt); fs0 = toppling_analyze(inp).fs
                if T <= 0:
                    QMessageBox.information(
                        self, _tr("Ankraj gerekmiyor", "No anchor required"),
                        _tr(f"Mevcut FS = {fs0:.3f} hedef FS = {tgt:.2f} değerini sağlıyor.",
                            f"The current FS = {fs0:.3f} meets the target FS = {tgt:.2f}.")); return
                self.setval("t_T", T); self.on_analyze()
                msg = _tr(f"Mevcut FS = {fs0:.3f} → hedef {tgt:.2f}\n"
                          f"Topuk bloğuna gerekli ankraj: {T:,.1f} kN/m (δ = {self.val('t_delta'):.1f}°)",
                          f"Current FS = {fs0:.3f} → target {tgt:.2f}\n"
                          f"Anchor required at the toe block: {T:,.1f} kN/m (δ = {self.val('t_delta'):.1f}°)")
                self.txt.appendPlainText("\n" + msg)
                QMessageBox.information(self, _tr("Gerekli ankraj", "Required anchor"), msg)
        except Exception as e:
            self._error(str(e))

    # ---------------------------------------------------------------- bulon
    def on_bolts(self):
        try:
            spec = self.bolt_spec()
            if self.mode == "planar":
                inp = self.read_planar()
                if inp.support_force <= 0:
                    raise ValueError(_tr("Destek kuvveti 0 — önce 'Gerekli Destek' ile T'yi hesaplayın.",
                                         "Support force is 0 — compute T with 'Required Support' first."))
                res = planar_analyze(inp); bp = bolt_pattern_planar(res, inp.support_force, inp.support_angle, spec)
                fn = lambda s_, L_: bolt_check_planar(inp, s_, L_, inp.support_angle, spec, self.val("p_FS"), self.val("p_passive"))
            elif self.mode == "wedge":
                inp = self.read_wedge()
                if inp.support.force <= 0:
                    raise ValueError(_tr("Destek kuvveti 0 — önce 'Gerekli Destek' ile T'yi hesaplayın.",
                                         "Support force is 0 — compute T with 'Required Support' first."))
                res = analyze(inp); bp = bolt_pattern_wedge(res, inp.support.force, inp.support.trend, inp.support.plunge, spec)
                fn = lambda s_, L_: bolt_check_wedge(inp, s_, L_, inp.support.trend, inp.support.plunge, spec, self.val("FS_target"), self.val("T_passive"))
            else:
                return
        except Exception as e:
            self._error(str(e)); return
        spacings = [round(x, 2) for x in np.arange(spec.s_min, spec.s_max + 1e-9, 0.25)]
        lengths = [L for L in STANDARD_LENGTHS if L <= max(bp.total_length * 1.5, 6)] or STANDARD_LENGTHS[:4]
        self.txt.setPlainText(res.summary() + "\n\n" + bp.summary() + "\n\n"
                              + _tr("Öneri matrisi hesaplanıyor…", "Computing the recommendation matrix…"))
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
        lines = [_tr("ÖNERİ TABLOSU — FS (aralık × boy; * hedef sağlanıyor)",
                     "RECOMMENDATION TABLE — FS (spacing × length; * target met)"),
                 "  L (m):  " + "".join(f"{L:8g}" for L in lengths)]
        for r in rows[1:]:
            lines.append(f"  s={r[0]:>5} " + "".join(f"{c:>8}" for c in r[1:]))
        if best:
            lines.append("\n" + _tr(f"ÖNERİ: en geniş karelajda en kısa boy → s = {best[0]:.2f} m, "
                                     f"L = {best[1]:g} m (FS = {best[2]:.2f})",
                                     f"RECOMMENDATION: shortest length at the widest spacing → "
                                     f"s = {best[0]:.2f} m, L = {best[1]:g} m (FS = {best[2]:.2f})"))
            self.setval("b_s_sel", f"{best[0]:g}"); self.setval("b_L_sel", f"{best[1]:g}")
        else:
            lines.append("\n" + _tr("Hiçbir kombinasyon hedefi sağlamıyor: daha yüksek kapasite veya daha sık "
                                    "aralık gerekir.",
                                    "No combination meets the target: a higher capacity or a tighter spacing "
                                    "is required."))
        self.txt.setPlainText(res.summary() + "\n\n" + bp.summary() + "\n\n" + "\n".join(lines))
        self.tabs.setCurrentIndex(3)
        self.statusBar().showMessage(_tr("Bulon öneri matrisi hazır — Tablo sekmesi",
                                         "Bolt recommendation matrix ready — Table tab"), 8000)

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
        rows = [[_tr("Yüz konumu (m)", "Face position (m)"), _tr("Serbest boy (m)", "Free length (m)"),
                 _tr("Kök boyu (m)", "Bond length (m)"), _tr("Kapasite (kN)", "Capacity (kN)")]]
        rows += [[f"{p:.2f}", f"{f:.2f}", f"{max(b, 0):.2f}", f"{c:.1f}"] for p, f, b, c in chk.rows]
        self._fill_table(rows)
        util = 100 * chk.T_provided / max(chk.T_required, 1e-9)
        verdict = _tr("UYGUN ✓", "ADEQUATE ✓") if chk.ok else _tr("YETERSİZ ✗", "INADEQUATE ✗")
        QMessageBox.information(
            self, _tr("Tasarım kontrolü", "Design check"),
            _tr(f"s = {s_:.2f} m, L = {L_:.1f} m → FS = {chk.fs:.3f}\n{verdict}  "
                f"(kullanım {pct(util, 0)})",
                f"s = {s_:.2f} m, L = {L_:.1f} m → FS = {chk.fs:.3f}\n{verdict}  "
                f"(utilisation {util:.0f}%)"))

    # ---------------------------------------------------------------- rapor
    def on_pdf(self):
        if not self.last:
            QMessageBox.warning(self, _tr("Rapor", "Report"),
                                _tr("Önce bir analiz çalıştırın (F5).", "Run an analysis first (F5).")); return
        mode, inp, res, figs = self.last
        path, _ = QFileDialog.getSaveFileName(self, _tr("PDF raporu kaydet", "Save PDF report"),
                                              f"lythos_{mode}_{datetime.date.today()}.pdf", "PDF (*.pdf)")
        if not path: return
        v = self.val
        project = {key: v("rp_" + key) or "—" for key in PROJECT_FIELDS if "rp_" + key in self.f}
        project["revision"] = "0"
        project["date"] = datetime.date.today().strftime("%d.%m.%Y")
        from reportlab.lib.units import mm
        try:
            title, sub, key, inputs, figcaps, tables, warns = self._report_content(mode, inp, res, figs)
            tables = [(n, r, [w_ * mm for w_ in wd]) for n, r, wd in tables]
            Report(project).build(path, title, sub, mode, key, inputs, figcaps, tables,
                                  [(_tr("Program çıktısı (tam metin)", "Program output (full text)"),
                                    self.txt.toPlainText().strip())], v("rp_note"), warns)
        except Exception as e:
            QMessageBox.critical(self, _tr("Rapor hatası", "Report error"),
                                 f"{e}\n{traceback.format_exc()}"); return
        self.statusBar().showMessage(_tr(f"PDF oluşturuldu: {path}", f"PDF created: {path}"), 10000)
        QMessageBox.information(self, _tr("Rapor", "Report"),
                                _tr(f"PDF oluşturuldu:\n{path}", f"PDF created:\n{path}"))

    def _report_content(self, mode, inp, res, figs):
        """PDF raporunun mod bağımlı içeriği: başlık, künye, KPI, şekil ve tablolar."""
        v = self.val
        QTY, VAL = _tr("Büyüklük", "Quantity"), _tr("Değer", "Value")
        FS_LABEL = _tr("Güvenlik sayısı", "Factor of safety")
        TARGET_FS = _tr("Hedef FS", "Target FS")
        UNIT_WEIGHT = _tr("Birim hacim ağırlığı", "Unit weight")
        SUPPORT = _tr("Destek", "Support")
        TC = _tr("Çekme çatlağı", "Tension crack")

        if mode == "wedge":
            j1, j2, tgt = inp.joint1, inp.joint2, v("FS_target"); fs = res.factor_of_safety
            title = _tr("Kama Stabilite Analizi", "Wedge Stability Analysis")
            sub = _tr("Tetrahedral kama — Hoek & Bray vektörel limit denge yöntemi",
                      "Tetrahedral wedge — Hoek & Bray vector limit-equilibrium method")
            sup_mode = PASSIVE() if inp.support.passive else ACTIVE()
            inputs = [(f"{_tr('Eklem 1', 'Joint 1')} (dip/dip dir)", f"{j1.dip:g}° / {j1.dipdir:g}°"),
                      (f"{_tr('Eklem 1', 'Joint 1')} c / φ", f"{j1.cohesion:g} kPa / {j1.friction:g}°"),
                      (f"{_tr('Eklem 2', 'Joint 2')} (dip/dip dir)", f"{j2.dip:g}° / {j2.dipdir:g}°"),
                      (f"{_tr('Eklem 2', 'Joint 2')} c / φ", f"{j2.cohesion:g} kPa / {j2.friction:g}°"),
                      (_tr("Şev yüzü", "Slope face"), f"{inp.slope_face.dip:g}° / {inp.slope_face.dipdir:g}°"),
                      (_tr("Üst şev", "Upper slope"), f"{inp.upper_slope.dip:g}° / {inp.upper_slope.dipdir:g}°"),
                      (_tr("Şev yüksekliği", "Slope height"), f"{inp.slope_height:g} m"),
                      (UNIT_WEIGHT, f"{inp.unit_weight:g} kN/m³"),
                      (_tr("Kama ölçekleme", "Wedge scaling"),
                       f"{inp.scale_mode}" + (f" = {inp.scale_value:g}" if inp.scale_value else "")),
                      (TC, (f"{inp.tension_crack.dip:g}°/{inp.tension_crack.dipdir:g}°, "
                            f"{inp.tension_crack.distance_from_crest:g} m") if inp.tension_crack else NONE_TEXT()),
                      (_tr("Su basıncı", "Water pressure"),
                       f"{pct(inp.water.percent, 0)} {_tr('dolu', 'filled')}" if inp.water.mode == "percent"
                       else WATER_MODE(inp.water.mode)),
                      (_tr("Sismik katsayı", "Seismic coefficient"), f"α = {inp.seismic.coefficient:g}"),
                      (SUPPORT, f"{inp.support.force:,.0f} kN @ {inp.support.trend:g}°/"
                                f"{inp.support.plunge:g}° ({sup_mode})"),
                      (TARGET_FS, f"{tgt:g}")]
            key = [(FS_LABEL, f"{fs:.3f}", fs >= tgt),
                   (_tr("Göçme modu", "Failure mode"), res.mode.split(" (")[0], None),
                   (_tr("Kama hacmi", "Wedge volume"), f"{res.volume:,.0f} m³", None),
                   (_tr("Kama ağırlığı", "Wedge weight"), f"{res.weight:,.0f} kN", None)]
            figcaps = [(figs[0], _tr("Kama geometrisi, göçme modu ve kayma yönü (3D)",
                                     "Wedge geometry, failure mode and sliding direction (3D)")),
                       (figs[1], _tr("Stereonet — düzlemler, kesişim çizgisi ve sürtünme konisi",
                                     "Stereonet — planes, line of intersection and friction cone"))]
            tables = [(_tr("Kuvvet dengesi", "Force balance"),
                       [[QTY, VAL], [_tr("Kama ağırlığı", "Wedge weight"), f"{res.weight:,.1f} kN"],
                        *[[f"{_tr('Su kuvveti', 'Water force')} {k}", f"{u:,.1f} kN"]
                          for k, u in res.water_forces.items()],
                        [_tr("Sismik kuvvet", "Seismic force"), f"{res.seismic_force:,.1f} kN"],
                        [_tr("Destek kuvveti", "Support force"), f"{res.support_force:,.1f} kN"],
                        *[[f"{_tr('Normal kuvvet', 'Normal force')} {k}", f"{n:,.1f} kN"]
                          for k, n in res.normal_forces.items()],
                        [_tr("Kaydırıcı kuvvet", "Driving force"), f"{res.driving_force:,.1f} kN"],
                        [_tr("Direnç kuvveti", "Resisting force"), f"{res.resisting_force:,.1f} kN"],
                        [FS_LABEL, f"{fs:.3f}"]], [90, 90]),
                      (_tr("Geometri", "Geometry"),
                       [[QTY, VAL],
                        *[[f"{_tr('Alan', 'Area')} {k}", f"{a:,.1f} m²"] for k, a in res.areas.items()],
                        [_tr("Tepe uzunluğu |BC|", "Crest length |BC|"), f"{res.geometry.crest_length:,.1f} m"],
                        [_tr("Basamak genişliği", "Bench width"), f"{res.geometry.bench_width:,.1f} m"],
                        [_tr("Kesişim çizgisi", "Line of intersection"),
                         f"trend {res.intersection_line[0]:.1f}°, plunge {res.intersection_line[1]:.1f}°"]],
                       [90, 90])]
            return title, sub, key, inputs, figcaps, tables, list(res.warnings)

        if mode == "planar":
            tgt = v("p_FS"); fs = res.factor_of_safety
            title = _tr("Düzlemsel Kayma Analizi", "Planar Sliding Analysis")
            sub = _tr("Hoek & Bray düzlemsel limit denge çözümü — 1 m şev uzunluğu",
                      "Hoek & Bray planar limit-equilibrium solution — 1 m slope length")
            sup_mode = PASSIVE() if inp.support_passive else ACTIVE()
            water = (f"{_tr('çatlak', 'crack')} {pct(inp.water_percent, 0)} {_tr('dolu', 'filled')}"
                     if inp.water_mode == "percent" else WATER_MODE(inp.water_mode))
            inputs = [(_tr("Şev yüksekliği H", "Slope height H"), f"{inp.slope_height:g} m"),
                      (_tr("Şev yüzü ψf", "Slope face ψf"), f"{inp.face_angle:g}°"),
                      (_tr("Kayma düzlemi ψp", "Sliding plane ψp"), f"{inp.plane_angle:g}°"),
                      (_tr("Üst şev ψs", "Upper slope ψs"), f"{inp.upper_angle:g}°"),
                      (_tr("Kohezyon c", "Cohesion c"), f"{inp.cohesion:g} kPa"),
                      (_tr("Sürtünme açısı φ", "Friction angle φ"), f"{inp.friction:g}°"),
                      (UNIT_WEIGHT, f"{inp.unit_weight:g} kN/m³"),
                      (TC, f"b = {inp.tc_distance:g} m" if inp.tc_distance is not None else NONE_TEXT()),
                      (_tr("Su", "Water"), water),
                      (_tr("Sismik αh / αv", "Seismic αh / αv"), f"{inp.seismic_h:g} / {inp.seismic_v:g}"),
                      (SUPPORT, f"{inp.support_force:,.0f} kN/m @ {inp.support_angle:g}° ({sup_mode})"),
                      (TARGET_FS, f"{tgt:g}")]
            key = [(FS_LABEL, f"{fs:.3f}", fs >= tgt),
                   (_tr("Blok ağırlığı", "Block weight"), f"{res.weight:,.0f} kN/m", None),
                   (_tr("Çatlak derinliği", "Crack depth"),
                    f"{res.tc_depth:.2f} m" if inp.tc_distance is not None else "—", None),
                   (_tr("Su kuvvetleri U / V", "Water forces U / V"),
                    f"{res.water_U:,.0f} / {res.water_V:,.0f}", None)]
            figcaps = [(figs[0], _tr("Düzlemsel kayma kesiti, su basıncı dağılımı ve kuvvetler",
                                     "Planar sliding section, water pressure distribution and forces"))]
            tables = [(_tr("Kuvvet dengesi (kN/m)", "Force balance (kN/m)"),
                       [[QTY, VAL], [_tr("Blok alanı", "Block area"), f"{res.area:,.2f} m²"],
                        [_tr("Ağırlık W", "Weight W"), f"{res.weight:,.1f}"],
                        [_tr("Kayma düzlemi uzunluğu", "Sliding plane length"), f"{res.plane_length:,.2f} m"],
                        [f"{_tr('Su', 'Water')} U ({_tr('düzlem', 'plane')})", f"{res.water_U:,.1f}"],
                        [f"{_tr('Su', 'Water')} V ({_tr('çatlak', 'crack')})", f"{res.water_V:,.1f}"],
                        [_tr("Sismik αhW", "Seismic αhW"), f"{res.seismic_force:,.1f}"],
                        [_tr("Etkin normal kuvvet", "Effective normal force"), f"{res.normal_force:,.1f}"],
                        [_tr("Kaydırıcı kuvvet", "Driving force"), f"{res.driving:,.1f}"],
                        [_tr("Direnç kuvveti", "Resisting force"), f"{res.resisting:,.1f}"],
                        [FS_LABEL, f"{fs:.3f}"]], [90, 90])]
            return title, sub, key, inputs, figcaps, tables, list(res.warnings)

        tgt = v("t_FS")
        title = _tr("Blok Devrilme Analizi", "Block Toppling Analysis")
        sub = _tr("Goodman & Bray (1976) blok devrilme limit denge yöntemi — 1 m şev uzunluğu",
                  "Goodman & Bray (1976) block toppling limit-equilibrium method — 1 m slope length")
        inputs = [(_tr("Şev yüzü ψf", "Slope face ψf"), f"{inp.face_angle:g}°"),
                  (_tr("Üst şev ψs", "Upper slope ψs"), f"{inp.upper_angle:g}°"),
                  (_tr("Süreksizlik eğimi ψd", "Discontinuity dip ψd"),
                   f"{inp.disc_dip:g}° (ψp = {90 - inp.disc_dip:g}°)"),
                  (_tr("Taban genel eğimi ψb", "Overall base angle ψb"), f"{inp.base_angle:g}°"),
                  (_tr("Blok genişliği Δx", "Block width Δx"), f"{inp.block_width:g} m"),
                  (_tr("Blok sayısı", "Number of blocks"),
                   _tr(f"{inp.n_below} tepe altı + {inp.n_above} tepe üstü",
                       f"{inp.n_below} below crest + {inp.n_above} above crest")),
                  (_tr("Sürtünme açısı φ", "Friction angle φ"), f"{inp.friction:g}°"),
                  (UNIT_WEIGHT, f"{inp.unit_weight:g} kN/m³"),
                  (_tr("Eklem su doluluğu", "Joint water filling"), pct(inp.water_percent, 0)),
                  (_tr("Sismik αh", "Seismic αh"), f"{inp.seismic_h:g}"),
                  (_tr("Topuk ankrajı", "Toe anchor"),
                   f"{inp.support_force:,.0f} kN/m @ {inp.support_angle:g}°"),
                  (TARGET_FS, f"{tgt:g}")]
        key = [(FS_LABEL, f"{res.fs:.3f}", res.fs >= tgt),
               (_tr("Gerekli φ", "Required φ"), f"{res.phi_required:.2f}°", None),
               (_tr("Topuk ankrajı (φ mevcut)", "Toe anchor (current φ)"), f"{res.T_required:,.0f} kN/m", None),
               (_tr("Şev yüksekliği", "Slope height"), f"{res.slope_height:.1f} m", None)]
        caption = _tr("Blok kolonları, göçme modları ve eklem su seviyeleri",
                      "Block columns, failure modes and joint water levels")
        rows = [[_tr("Blok", "Block"), "y (m)", "y/Δx", "W (kN)", "U (kN)", "V (kN)",
                 _tr("Mod", "Mode"), "P(n−1) (kN/m)"]]
        for bl in res.blocks:
            rows.append([str(bl["n"]), f"{bl['y']:.2f}", f"{bl['y'] / inp.block_width:.2f}", f"{bl['W']:,.0f}",
                         f"{bl['U']:,.0f}", f"{bl['V']:,.0f}", MODE_TEXT(bl["mode"]), f"{bl['P']:,.1f}"])
        tables = [(_tr("Blok bazında sonuçlar", "Per-block results"), rows, [14, 20, 16, 26, 22, 22, 24, 36])]
        return title, sub, key, inputs, [(figs[0], caption)], tables, list(res.warnings)

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
        path, _ = QFileDialog.getSaveFileName(self, _tr("Girdileri kaydet", "Save inputs"),
                                              "lythos_inputs.json", "JSON (*.json)")
        if not path: return
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self._state(), fh, indent=2, ensure_ascii=False)
        self.statusBar().showMessage(f"{_tr('Kaydedildi', 'Saved')}: {path}", 6000)

    def on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, _tr("Girdileri yükle", "Load inputs"), "", "JSON (*.json)")
        if not path: return
        with open(path, encoding="utf-8") as fh:
            self._apply_state(json.load(fh))
        self.statusBar().showMessage(f"{_tr('Yüklendi', 'Loaded')}: {path}", 6000)

    # dışa açık ad: suite girdi durumunu kaydedip geri yükler
    state = _state
    apply_state = _apply_state

    # ---------------------------------------------------------------- kinematik taramadan aktarım
    def apply_from_screening(self, payload: dict):
        """Kinematik tarama panelinden gelen kritik bileşeni girdi olarak yükler.

        Kama modunda iki eklem takımı ve şev yüzü, düzlemsel/devrilme modunda ise
        kayma/süreksizlik açıları ile şev yüzü doldurulur; sürtünme açısı her
        durumda taramada kullanılan değerle eşitlenir.
        """
        mode_key = {0: "planar", 1: "wedge", 2: "toppling"}[int(payload["mode"])]
        idx = self.mode_box.findData(mode_key)
        if idx >= 0:
            self.mode_box.setCurrentIndex(idx)
        phi, face_dip, face_dd = payload["friction"], payload["slope_dip"], payload["slope_dir"]

        if mode_key == "wedge":
            (d1, dd1), (d2, dd2) = payload["j1"], payload["j2"]
            for key, v in (("j1_dip", d1), ("j1_dd", dd1), ("j1_phi", phi),
                           ("j2_dip", d2), ("j2_dd", dd2), ("j2_phi", phi),
                           ("face_dip", face_dip), ("face_dd", face_dd)):
                self.setval(key, v)
        elif mode_key == "planar":
            for key, v in (("p_plane", payload["dip"]), ("p_face", min(face_dip, 89.9)),
                           ("p_phi", phi)):
                self.setval(key, v)
        else:
            for key, v in (("t_disc", payload["dip"]), ("t_face", min(face_dip, 89.9)),
                           ("t_phi", min(phi, 44.9))):
                self.setval(key, v)

        name = payload.get("name", "—")
        self.statusBar().showMessage(
            _tr(f"Kinematik taramadan aktarıldı: {name} (φ = {phi:g}°, şev {face_dip:g}/{face_dd:g})",
                f"Transferred from kinematic screening: {name} "
                f"(φ = {phi:g}°, slope {face_dip:g}/{face_dd:g})"), 12000)
        self.on_analyze()
