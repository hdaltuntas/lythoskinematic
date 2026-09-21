"""
lythos.ui.screening — Lythos Kinematic / Kinematik Tarama paneli.

Markland kinematik kontrolleri, stereonet ve Monte Carlo olasılık analizi.
(Eski SlopeKinematics uygulamasının PySide6'ya taşınmış ve Lythos çekirdeğine
bağlanmış hâli: stereonet artık `lythos.stereonet`, hesaplar `lythos.kinematics`.)
"""
from __future__ import annotations

import io
from typing import List, Optional

from . import qt  # noqa: F401  (Qt bağlamasını matplotlib'den önce sabitler)

from PySide6.QtCore import Qt, QMarginsF, QThread, QUrl, Signal
from PySide6.QtGui import QImage, QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QPushButton, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
                               QTextEdit, QVBoxLayout, QWidget)

import numpy as np

from .. import theme
from ..kinematics import engine as eng
from ..kinematics import htmlreport as H
from ..kinematics.i18n import LANG
from ..kinematics.plots import plot_screening
from .widgets import MplTab

DEFAULT_JOINTS = [("T2", 73, 152, 2.5), ("T1", 69, 189, 3.0), ("E3", 34, 232, 2.0),
                  ("E1", 28, 104, 2.5), ("E2", 21, 303, 2.0), ("J6", 50, 60, 3.0)]


class MonteCarloWorker(QThread):
    """Monte Carlo simülasyonunu arka planda çalıştırır; arayüz donmaz."""
    finished_result = Signal(object)

    def __init__(self, args):
        super().__init__()
        self.args = args

    def run(self):
        self.finished_result.emit(eng.run_monte_carlo(*self.args))


class ScreeningPanel(QWidget):
    """Kinematik tarama paneli.

    `handoff` sinyali, en kritik bileşenin limit denge modülüne aktarılması için
    gereken tüm veriyi taşıyan bir sözlük yayar.
    """
    handoff = Signal(dict)
    language_changed = Signal(str)
    status = Signal(str)

    def __init__(self, lang: str = "TR"):
        super().__init__()
        self.current_lang = lang if lang in LANG else "TR"
        self._theme = "light"
        self._mc_request = 0
        self._mc_workers: List[MonteCarloWorker] = []
        self._mc_context = None
        self._result: Optional[eng.ScreeningResult] = None
        self.report_body, self.prob_body = "", ""
        self.report_html, self.prob_html = "", ""

        self._build()
        self.update_ui_texts()
        self.update_analysis()

    # ------------------------------------------------------------------ kurulum
    def _build(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12); main.setSpacing(12)

        left = QVBoxLayout(); left.setSpacing(10)

        self.lbl_lang = QLabel()
        self.combo_lang = QComboBox(); self.combo_lang.addItems(["TR - Türkçe", "EN - English"])
        self.combo_lang.setCurrentIndex(0 if self.current_lang == "TR" else 1)
        self.combo_lang.currentIndexChanged.connect(self._on_language_changed)
        row = QHBoxLayout(); row.setSpacing(8)
        row.addWidget(self.lbl_lang); row.addWidget(self.combo_lang, 1)
        left.addLayout(row)

        # --- şev ve malzeme parametreleri
        self.grp_slope = QGroupBox()
        form = QFormLayout(self.grp_slope); form.setSpacing(8); form.setContentsMargins(12, 10, 12, 12)

        def spin(lo, hi, val, step=1):
            s = QSpinBox(); s.setRange(lo, hi); s.setValue(val); s.setSingleStep(step); return s

        self.lbl_slope_dip = QLabel(); self.slope_dip_input = spin(0, 90, 72)
        self.lbl_slope_dir = QLabel(); self.slope_dir_input = spin(0, 360, 230)
        self.lbl_frict = QLabel(); self.friction_input = spin(0, 90, 31)
        self.lbl_lat = QLabel(); self.lateral_input = spin(0, 90, 20)
        self.lbl_sim = QLabel(); self.sim_input = spin(100, 200000, 5000, 1000)
        self.lbl_type = QLabel(); self.combo_analysis = QComboBox()
        for lbl, w in [(self.lbl_slope_dip, self.slope_dip_input), (self.lbl_slope_dir, self.slope_dir_input),
                       (self.lbl_frict, self.friction_input), (self.lbl_lat, self.lateral_input),
                       (self.lbl_sim, self.sim_input), (self.lbl_type, self.combo_analysis)]:
            form.addRow(lbl, w)
        self.cb_risk_zone = QCheckBox(); self.cb_risk_zone.setChecked(True)
        self.cb_density = QCheckBox(); self.cb_density.setChecked(True)
        form.addRow(self.cb_risk_zone); form.addRow(self.cb_density)
        left.addWidget(self.grp_slope)

        # --- süreksizlik tablosu
        self.grp_joints = QGroupBox()
        jl = QVBoxLayout(self.grp_joints); jl.setSpacing(8); jl.setContentsMargins(12, 10, 12, 12)
        self.table = QTableWidget(len(DEFAULT_JOINTS), 4)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for r, vals in enumerate(DEFAULT_JOINTS):
            for c, val in enumerate(vals):
                it = QTableWidgetItem(str(val)); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(r, c, it)
        jl.addWidget(self.table)
        self.lbl_note = QLabel(); self.lbl_note.setWordWrap(True)
        self.lbl_note.setStyleSheet("color:#7a838f; font-size:8.5pt; font-weight:normal;")
        jl.addWidget(self.lbl_note)
        rb = QHBoxLayout(); rb.setSpacing(8)
        self.btn_add = QPushButton(); self.btn_add.clicked.connect(lambda: self.table.insertRow(self.table.rowCount()))
        self.btn_del = QPushButton(); self.btn_del.clicked.connect(self._del_row)
        rb.addWidget(self.btn_add); rb.addWidget(self.btn_del)
        jl.addLayout(rb)
        left.addWidget(self.grp_joints, 1)

        self.btn_plot = QPushButton(); self.btn_plot.setObjectName("run")
        self.btn_plot.clicked.connect(self.update_analysis)
        self.btn_handoff = QPushButton(); self.btn_handoff.setObjectName("handoff")
        self.btn_handoff.clicked.connect(self._on_handoff)
        self.btn_save_pdf = QPushButton(); self.btn_save_pdf.setObjectName("pdf")
        self.btn_save_pdf.clicked.connect(self.save_pdf)
        left.addWidget(self.btn_plot); left.addWidget(self.btn_handoff); left.addWidget(self.btn_save_pdf)
        main.addLayout(left, 1)

        # --- sonuç sekmeleri
        self.tabs = QTabWidget()
        self.plot_tab = MplTab(figsize=(7.4, 7.4))
        self.ax = self.plot_tab.fig.add_subplot(111)
        self.tabs.addTab(self.plot_tab, "")
        self.report_text = QTextEdit(); self.report_text.setReadOnly(True)
        self.report_text.document().setDocumentMargin(18)
        self.tabs.addTab(self.report_text, "")
        self.prob_text = QTextEdit(); self.prob_text.setReadOnly(True)
        self.prob_text.document().setDocumentMargin(18)
        self.tabs.addTab(self.prob_text, "")
        main.addWidget(self.tabs, 3)

    # ------------------------------------------------------------------ dil / tema
    @property
    def t(self) -> dict:
        return LANG[self.current_lang]

    def _on_language_changed(self, index: int):
        self.set_language("TR" if index == 0 else "EN")
        self.language_changed.emit(self.current_lang)

    def set_language(self, lang: str):
        if lang not in LANG or lang == self.current_lang:
            return
        self.current_lang = lang
        self.combo_lang.blockSignals(True)
        self.combo_lang.setCurrentIndex(0 if lang == "TR" else 1)
        self.combo_lang.blockSignals(False)
        self.update_ui_texts()
        self.update_analysis()

    def apply_theme(self, name: str):
        """Tema değişince figürü yeniden çiz (etiket renkleri paletten gelir)."""
        self._theme = name
        self.update_plot()

    def update_ui_texts(self):
        t = self.t
        self.lbl_lang.setText(t["lbl_lang"])
        self.grp_slope.setTitle(t["grp_slope"]); self.grp_joints.setTitle(t["grp_joints"])
        self.lbl_slope_dip.setText(t["lbl_slope_dip"]); self.lbl_slope_dir.setText(t["lbl_slope_dir"])
        self.lbl_frict.setText(t["lbl_frict"]); self.lbl_lat.setText(t["lbl_lat"]); self.lbl_sim.setText(t["lbl_sim"])
        self.lbl_type.setText(t["lbl_type"])
        self.cb_risk_zone.setText(t["chk_risk"]); self.cb_density.setText(t["chk_density"])
        self.lbl_note.setText(t["note_std"])
        self.btn_add.setText(t["btn_add"]); self.btn_del.setText(t["btn_del"])
        self.btn_plot.setText(t["btn_run"]); self.btn_save_pdf.setText(t["btn_pdf"])
        self.btn_handoff.setText(t["btn_handoff"]); self.btn_handoff.setToolTip(t["handoff_tip"])
        idx = max(self.combo_analysis.currentIndex(), 0)
        self.combo_analysis.blockSignals(True)
        self.combo_analysis.clear(); self.combo_analysis.addItems(t["types"])
        self.combo_analysis.setCurrentIndex(idx)
        self.combo_analysis.blockSignals(False)
        self.table.setHorizontalHeaderLabels([t["col_label"], t["col_dip"], t["col_dipdir"], t["col_std"]])
        for i, key in enumerate(("tab_plot", "tab_rep", "tab_prob")):
            self.tabs.setTabText(i, t[key])

    # ------------------------------------------------------------------ veri
    def _del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def table_data(self):
        """Tablodan (etiketler, dip, dip dir, std) döndürür; eksik/bozuk satırlar atlanır."""
        labels, dips, dip_dirs, stds = [], [], [], []
        for row in range(self.table.rowCount()):
            items = [self.table.item(row, c) for c in range(4)]
            if all(it and it.text().strip() for it in items):
                try:
                    d, dd, s = (float(items[1].text().replace(",", ".")),
                                float(items[2].text().replace(",", ".")),
                                float(items[3].text().replace(",", ".")))
                except ValueError:
                    continue
                labels.append(items[0].text().strip()); dips.append(d); dip_dirs.append(dd); stds.append(s)
        return labels, np.array(dips), np.array(dip_dirs), np.array(stds)

    def params(self):
        """(şev eğimi, şev yönü, φ, yanal limit, mod indeksi)."""
        return (self.slope_dip_input.value(), self.slope_dir_input.value(), self.friction_input.value(),
                self.lateral_input.value(), self.combo_analysis.currentIndex())

    # ------------------------------------------------------------------ ana akış
    def update_analysis(self):
        labels, dips, dip_dirs, _ = self.table_data()
        slope_dip, slope_dir, friction, lateral, mode = self.params()
        self._result = (eng.screen(labels, dips, dip_dirs, slope_dip, slope_dir, friction, lateral, mode)
                        if len(dips) else None)
        self.update_plot()
        self.generate_text_report()
        self.run_probability_analysis()

    def update_plot(self):
        t = self.t
        labels, dips, dip_dirs, _ = self.table_data()
        pal = theme.mpl_palette(self._theme)
        self.plot_tab.fig.patch.set_facecolor(pal["figure"])
        if self._result is None:
            self.ax.clear()
            from .. import stereonet as _st
            _st.draw_net(self.ax, grid_color=pal["grid"], edge_color=pal["accent"],
                         text_color=pal["muted"], labels=t["dirs"])
            self.plot_tab.canvas.draw_idle()
            return
        title = t[("plot_planar", "plot_wedge", "plot_toppling")[self._result.mode]]
        plot_screening(self.ax, self._result, labels, dips, dip_dirs,
                       show_zone=self.cb_risk_zone.isChecked(),
                       show_density=self.cb_density.isChecked(),
                       title=title, palette=pal, direction_labels=t["dirs"],
                       slope_label=t["slope_face"], cone_label=t["cone"])
        self.plot_tab.canvas.draw_idle()

    def generate_text_report(self):
        self.report_body = H.kinematic_report(self.t, self._result)
        self.report_html = H.wrap(self.report_body)
        self.report_text.setHtml(self.report_html)

    def run_probability_analysis(self):
        t = self.t
        labels, dips, dip_dirs, stds = self.table_data()
        if len(dips) == 0:
            self.prob_body = H.empty_report(t, "prob_title", "prob_subtitle")
            self.prob_html = H.wrap(self.prob_body)
            self.prob_text.setHtml(self.prob_html)
            return

        slope_dip, slope_dir, friction, lateral, mode = self.params()
        n_trials = self.sim_input.value()

        self._mc_request += 1
        request_id = self._mc_request
        self._mc_context = dict(t=t, labels=list(labels), mode=mode)

        self.prob_text.setHtml(H.wrap(H.waiting_report(t)))
        self.btn_plot.setEnabled(False); self.btn_save_pdf.setEnabled(False)
        self.status.emit(t["prob_running"])

        worker = MonteCarloWorker((dips, dip_dirs, stds, slope_dip, slope_dir, friction,
                                   lateral, mode, n_trials))
        worker.finished_result.connect(lambda result, rid=request_id: self._on_montecarlo_done(rid, result))
        worker.finished.connect(lambda w=worker: self._mc_workers.remove(w) if w in self._mc_workers else None)
        self._mc_workers.append(worker)
        worker.start()

    def _on_montecarlo_done(self, request_id: int, mc: eng.MonteCarloResult):
        # Arayüz beklerken tablo/parametreler değiştiyse bu sonuç artık geçersizdir.
        if request_id != self._mc_request:
            return
        self.btn_plot.setEnabled(True); self.btn_save_pdf.setEnabled(True)
        ctx = self._mc_context
        self.prob_body = H.probabilistic_report(ctx["t"], mc, ctx["labels"], ctx["mode"])
        self.prob_html = H.wrap(self.prob_body)
        self.prob_text.setHtml(self.prob_html)
        self.status.emit(f"{ctx['t']['prob_pof']}: %{mc.pof:.2f}")

    # ------------------------------------------------------------------ limit dengeye aktarım
    def _on_handoff(self):
        t = self.t
        if self._result is None or not self._result.critical_items:
            QMessageBox.information(self, t["btn_handoff"], t["handoff_none"])
            return
        labels, dips, dip_dirs, _ = self.table_data()
        slope_dip, slope_dir, friction, lateral, mode = self.params()

        # En kritik bileşen: kamada en dik kesişim, diğerlerinde en dik süreksizlik
        crit = self._result.critical_items
        item = max(crit, key=lambda i: (i.value1 if not np.isnan(i.value1) else -1))

        payload = {"mode": mode, "name": item.name, "slope_dip": float(slope_dip),
                   "slope_dir": float(slope_dir), "friction": float(friction),
                   "lateral": float(lateral)}
        if mode == eng.WEDGE:
            i, j = item.index
            payload.update(j1=(float(dips[i]), float(dip_dirs[i])), j2=(float(dips[j]), float(dip_dirs[j])),
                           plunge=float(item.value1), trend=float(item.value2))
        else:
            payload.update(dip=float(item.value1), dipdir=float(item.value2))
        self.handoff.emit(payload)
        self.status.emit(t["handoff_ok"].format(item.name))

    # ------------------------------------------------------------------ PDF
    def save_pdf(self):
        t = self.t
        path, _ = QFileDialog.getSaveFileName(self, "PDF", t["pdf_name"], "PDF (*.pdf)")
        if not path:
            return
        buf = io.BytesIO()
        self.plot_tab.fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor="white")
        buf.seek(0)
        img = QImage.fromData(buf.getvalue())

        doc = QTextDocument()
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl("stereonet.png"), img)
        body = (self.report_body
                + "<div style='page-break-before:always;'></div>"
                + self.prob_body
                + "<div style='page-break-before:always;'></div>"
                + H.section(t["pdf_fig"])
                + "<p align='center'><img src='stereonet.png' width='560'></p>")
        doc.setHtml(H.wrap(body))

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
        doc.print_(printer)

        self.status.emit(f"{t['pdf_saved']} {path}")
        QMessageBox.information(self, "PDF", f"{t['pdf_saved']}\n{path}")

    # ------------------------------------------------------------------ durum
    def shutdown(self):
        """Kapanırken arka plan Monte Carlo iş parçacıklarını bekle."""
        for worker in list(self._mc_workers):
            worker.wait(2000)

    def state(self) -> dict:
        labels, dips, dip_dirs, stds = self.table_data()
        return {"lang": self.current_lang, "slope_dip": self.slope_dip_input.value(),
                "slope_dir": self.slope_dir_input.value(), "friction": self.friction_input.value(),
                "lateral": self.lateral_input.value(), "trials": self.sim_input.value(),
                "mode": self.combo_analysis.currentIndex(), "zone": self.cb_risk_zone.isChecked(),
                "density": self.cb_density.isChecked(),
                "joints": [[l, float(d), float(dd), float(s)]
                           for l, d, dd, s in zip(labels, dips, dip_dirs, stds)]}

    def apply_state(self, d: dict):
        if not isinstance(d, dict):
            return
        self.set_language(d.get("lang", self.current_lang))
        for key, widget in (("slope_dip", self.slope_dip_input), ("slope_dir", self.slope_dir_input),
                            ("friction", self.friction_input), ("lateral", self.lateral_input),
                            ("trials", self.sim_input)):
            if key in d:
                widget.setValue(int(d[key]))
        if "mode" in d:
            self.combo_analysis.setCurrentIndex(int(d["mode"]))
        self.cb_risk_zone.setChecked(bool(d.get("zone", True)))
        self.cb_density.setChecked(bool(d.get("density", True)))
        joints = d.get("joints")
        if joints:
            self.table.setRowCount(len(joints))
            for r, row in enumerate(joints):
                for c, val in enumerate(row[:4]):
                    it = QTableWidgetItem(str(val)); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(r, c, it)
        self.update_analysis()
