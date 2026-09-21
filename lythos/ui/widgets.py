"""lythos.ui.widgets — modüller arasında paylaşılan küçük arayüz bileşenleri."""
from __future__ import annotations

import traceback

from . import qt  # noqa: F401  (Qt bağlamasını matplotlib'den önce sabitler)

from PySide6.QtCore import Qt, QSize, QThread, Signal
from PySide6.QtWidgets import (QDoubleSpinBox, QLabel, QLineEdit, QSizePolicy, QVBoxLayout, QWidget)

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT


class Num(QDoubleSpinBox):
    """Sayısal alan: aralık, ondalık, birim soneki."""

    def __init__(self, value=0.0, lo=-1e9, hi=1e9, dec=2, suffix="", step=1.0):
        super().__init__()
        self.setRange(lo, hi); self.setDecimals(dec); self.setSingleStep(step); self.setValue(value)
        if suffix:
            self.setSuffix(" " + suffix)
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setMinimumWidth(70)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        return QSize(90, super().sizeHint().height())

    def minimumSizeHint(self):
        return QSize(70, super().minimumSizeHint().height())


class Opt(QLineEdit):
    """Boş bırakılabilen sayısal alan (boş = otomatik)."""

    def __init__(self, placeholder="otomatik"):
        super().__init__()
        self.setPlaceholderText(placeholder); self.setMinimumWidth(70)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def value(self):
        t = self.text().strip().replace(",", ".")
        return float(t) if t else None


def note(text: str) -> QLabel:
    """Form altı açıklama etiketi."""
    l = QLabel(text); l.setWordWrap(True); l.setStyleSheet("color:#5b6770;")
    return l


class MplTab(QWidget):
    """Matplotlib tuvali + gezinme araç çubuğu."""

    def __init__(self, figsize=(9, 6), toolbar: bool = True):
        super().__init__()
        self.fig = Figure(figsize=figsize)
        self.canvas = FigureCanvasQTAgg(self.fig)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.toolbar = NavigationToolbar2QT(self.canvas, self) if toolbar else None
        if self.toolbar is not None:
            lay.addWidget(self.toolbar)
        lay.addWidget(self.canvas)

    def clear(self):
        self.fig.clear(); self.canvas.draw_idle()

    def ax(self, projection=None):
        self.fig.clear()
        return self.fig.add_subplot(111, projection=projection)

    def draw(self):
        self.fig.tight_layout(); self.canvas.draw_idle()


class Worker(QThread):
    """Uzun hesapları arka planda çalıştırır; arayüz donmaz."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args

    def run(self):
        try:
            self.done.emit(self.fn(*self.args))
        except Exception as e:                      # arayüze taşınacak hata metni
            self.failed.emit(f"{e}\n{traceback.format_exc()}")
