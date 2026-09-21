"""
lythos.ui.kinematic — Lythos Kinematic modülü.

İki çalışma adımını tek modülde birleştirir:

    1. Kinematik Tarama  — hangi mekanizmanın kinematik olarak mümkün olduğunu,
                           stereonet ve Monte Carlo ile belirler.
    2. Limit Denge       — kinematik olarak kritik bulunan mekanizma için güvenlik
                           sayısını, gerekli desteği ve bulon tasarımını hesaplar.

İki adım arasındaki köprü: tarama panelindeki "Limit Dengeye aktar" düğmesi, en
kritik süreksizliği / kesişimi limit denge girdilerine yazar ve analizi çalıştırır.
"""
from __future__ import annotations

from . import qt  # noqa: F401

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .equilibrium import EquilibriumPanel
from .screening import ScreeningPanel

TAB_TITLES = {
    "TR": ("1 · Kinematik Tarama", "2 · Limit Denge"),
    "EN": ("1 · Kinematic Screening", "2 · Limit Equilibrium"),
}


class KinematicModule(QWidget):
    """"Lythos Kinematic" modülünün kök arayüzü."""
    status = Signal(str)

    def __init__(self, lang: str = "TR"):
        super().__init__()
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.screening = ScreeningPanel(lang=lang)
        self.equilibrium = EquilibriumPanel()
        self.tabs.addTab(self.screening, "")
        self.tabs.addTab(self.equilibrium, "")
        lay.addWidget(self.tabs)

        # tarama -> limit denge köprüsü
        self.screening.handoff.connect(self._on_handoff)
        self.screening.status.connect(self.status)
        self.screening.language_changed.connect(lambda _: self._retitle())
        self._retitle()

    # ------------------------------------------------------------------ köprü
    def _on_handoff(self, payload: dict):
        self.equilibrium.apply_from_screening(payload)
        self.tabs.setCurrentWidget(self.equilibrium)

    def _retitle(self):
        for i, title in enumerate(TAB_TITLES.get(self.screening.current_lang, TAB_TITLES["TR"])):
            self.tabs.setTabText(i, title)

    # ------------------------------------------------------------------ suite arayüzü
    def set_language(self, lang: str):
        self.screening.set_language(lang)
        self._retitle()

    def apply_theme(self, name: str):
        self.screening.apply_theme(name)

    def shutdown(self):
        self.screening.shutdown()

    def state(self) -> dict:
        return {"screening": self.screening.state(), "equilibrium": self.equilibrium.state()}

    def apply_state(self, d: dict):
        if not isinstance(d, dict):
            return
        if isinstance(d.get("equilibrium"), dict):
            self.equilibrium.apply_state(d["equilibrium"])
        if isinstance(d.get("screening"), dict):
            self.screening.apply_state(d["screening"])
        self._retitle()
