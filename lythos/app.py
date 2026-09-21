"""
lythos.app — Lythos Suite ana programı.

Suite, modülleri barındıran ince bir kabuktur: tema, dil, girdi durumunun
kalıcılığı ve pencere yönetimi burada; mühendislik işi modüllerdedir.
Yeni bir modül eklemek için `MODULES` listesine bir `ModuleSpec` eklemek yeterlidir.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Callable, Dict, List

from .ui import qt  # noqa: F401  (Qt bağlamasını matplotlib'den önce sabitler)

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QMessageBox, QSizePolicy,
                               QStatusBar, QTabWidget, QToolBar, QWidget)

from . import APP_NAME, MODULE_KINEMATIC, ORG, __version__, theme
from .ui.kinematic import KinematicModule

ABOUT = {
    "TR": f"""<h3>{APP_NAME} {__version__}</h3>
<p><b>{MODULE_KINEMATIC}</b> — kaya şevi kinematiği ve stabilitesi.</p>
<p>Bu modül iki uygulamanın birleşimidir:</p>
<ul>
  <li><b>Kinematik Tarama</b> — Markland testi, stereonet, kutup yoğunluğu ve
      Monte Carlo olasılık analizi (eski <i>SlopeKinematics</i>).</li>
  <li><b>Limit Denge</b> — kama, düzlemsel ve blok devrilme analizi, bulon
      karelaj/boy tasarımı ve PDF rapor (eski <i>Kinematix</i>).</li>
</ul>
<p>Yöntemler: Hoek &amp; Bray, Goodman &amp; Bray, Wyllie &amp; Mah.<br>
Lisans: MIT · Arayüz: PySide6 (LGPL)</p>""",
    "EN": f"""<h3>{APP_NAME} {__version__}</h3>
<p><b>{MODULE_KINEMATIC}</b> — rock slope kinematics and stability.</p>
<p>This module merges two applications:</p>
<ul>
  <li><b>Kinematic Screening</b> — Markland test, stereonet, pole density and
      Monte Carlo probabilistic analysis (formerly <i>SlopeKinematics</i>).</li>
  <li><b>Limit Equilibrium</b> — wedge, planar and block toppling analysis, bolt
      spacing/length design and PDF reporting (formerly <i>Kinematix</i>).</li>
</ul>
<p>Methods: Hoek &amp; Bray, Goodman &amp; Bray, Wyllie &amp; Mah.<br>
License: MIT · UI: PySide6 (LGPL)</p>""",
}

UI = {
    "TR": {"module": "Modül:", "theme_dark": "🌙 Koyu tema", "theme_light": "☀ Açık tema",
           "about": "Hakkında", "ready": "Hazır"},
    "EN": {"module": "Module:", "theme_dark": "🌙 Dark theme", "theme_light": "☀ Light theme",
           "about": "About", "ready": "Ready"},
}


@dataclass(frozen=True)
class ModuleSpec:
    """Suite'e kayıtlı bir modül."""
    key: str
    title: str
    factory: Callable[[str], QWidget]


MODULES: List[ModuleSpec] = [
    ModuleSpec("kinematic", MODULE_KINEMATIC, lambda lang: KinematicModule(lang=lang)),
]


class LythosSuite(QMainWindow):
    """Lythos Suite ana penceresi."""

    def __init__(self):
        super().__init__()
        self.lang = "TR"
        self.theme_name = "light"
        self.modules: Dict[str, QWidget] = {}

        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1480, 920)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.setCentralWidget(self.tabs)
        self.setStatusBar(QStatusBar())

        self._build_toolbar()
        for spec in MODULES:
            widget = spec.factory(self.lang)
            if hasattr(widget, "status"):
                widget.status.connect(lambda msg: self.statusBar().showMessage(msg, 10000))
            self.modules[spec.key] = widget
            self.tabs.addTab(widget, spec.title)

        self._load_settings()
        self.statusBar().showMessage(f"{APP_NAME} — {UI[self.lang]['ready']}", 5000)

    # ------------------------------------------------------------------ kabuk
    def _build_toolbar(self):
        tb = QToolBar("Lythos"); tb.setMovable(False); self.addToolBar(tb)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)

        brand = QLabel(f"  <b>{APP_NAME}</b>  ")
        brand.setTextFormat(Qt.TextFormat.RichText)
        tb.addWidget(brand)
        tb.addSeparator()

        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.a_theme = QAction("", self)
        self.a_theme.triggered.connect(self.toggle_theme)
        tb.addAction(self.a_theme)
        self.a_about = QAction("", self)
        self.a_about.setShortcut(QKeySequence("F1"))
        self.a_about.triggered.connect(self.show_about)
        tb.addAction(self.a_about)
        self._retext()

    def _retext(self):
        u = UI[self.lang]
        self.a_theme.setText(u["theme_light"] if self.theme_name == "dark" else u["theme_dark"])
        self.a_about.setText(u["about"])

    # ------------------------------------------------------------------ tema / dil
    def apply_theme(self, name: str):
        self.theme_name = name if name in theme.THEMES else "light"
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(theme.qss(self.theme_name))
        for widget in self.modules.values():
            if hasattr(widget, "apply_theme"):
                widget.apply_theme(self.theme_name)
        self._retext()

    def toggle_theme(self):
        self.apply_theme("dark" if self.theme_name == "light" else "light")
        QSettings(ORG, APP_NAME).setValue("theme", self.theme_name)

    def set_language(self, lang: str):
        if lang not in UI:
            return
        self.lang = lang
        for widget in self.modules.values():
            if hasattr(widget, "set_language"):
                widget.set_language(lang)
        self._retext()

    def show_about(self):
        QMessageBox.about(self, UI[self.lang]["about"], ABOUT[self.lang])

    # ------------------------------------------------------------------ kalıcılık
    def _load_settings(self):
        s = QSettings(ORG, APP_NAME)
        self.apply_theme(s.value("theme", "light"))
        raw = s.value("state")
        if raw:
            try:
                state = json.loads(raw)
            except (ValueError, TypeError):
                state = {}
            self.set_language(state.get("lang", self.lang))
            for key, widget in self.modules.items():
                if hasattr(widget, "apply_state") and isinstance(state.get(key), dict):
                    try:
                        widget.apply_state(state[key])
                    except Exception:            # bozuk/eski ayar dosyası açılışı engellemesin
                        pass
        geo = s.value("geometry")
        if geo:
            self.restoreGeometry(geo)

    def _state(self) -> dict:
        state = {"lang": self.lang}
        for key, widget in self.modules.items():
            if hasattr(widget, "state"):
                try:
                    state[key] = widget.state()
                except Exception:
                    pass
        return state

    def closeEvent(self, ev):
        for widget in self.modules.values():
            if hasattr(widget, "shutdown"):
                widget.shutdown()
        s = QSettings(ORG, APP_NAME)
        s.setValue("state", json.dumps(self._state(), ensure_ascii=False))
        s.setValue("geometry", self.saveGeometry())
        super().closeEvent(ev)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(ORG)
    app.setStyle("Fusion")
    win = LythosSuite()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
