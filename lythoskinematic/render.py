"""
lythoskinematic.render — figür üretimi.

Arayüz tarayıcıda çalıştığı için çizimler sunucuda üretilip PNG olarak
gönderilir. Aynı figür fonksiyonları PDF raporunda da kullanılır; böylece
ekranda görülen ile rapora giren görsel birebir aynıdır.

matplotlib başsız (Agg) arka uçla kullanılır: sunucunun bir ekrana ihtiyacı yoktur.
"""
from __future__ import annotations

import io
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from . import theme
from .kinematics.plots import plot_screening
from .rockslope import plot_planar, plot_stereonet, plot_toppling, plot_wedge

#: PNG çıktısının çözünürlüğü (ekran için yeterli, rapora da girer)
DPI = 130


def figure_to_png(fig: Figure, dpi: int = DPI) -> bytes:
    """Figürü PNG baytlarına çevirir ve figürü kapatır."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
#  Kinematik tarama
# --------------------------------------------------------------------------- #

def screening_figure(result, labels, dips, dip_dirs, *, title: str = "",
                     show_zone: bool = True, show_density: bool = True,
                     direction_labels=("K", "D", "G", "B"),
                     slope_label: str = "Şev yüzü", cone_label: str = "Limit konisi",
                     size: float = 7.4) -> Figure:
    """Tarama stereoneti."""
    fig = Figure(figsize=(size, size))
    fig.patch.set_facecolor("white")
    ax = fig.add_subplot(111)
    plot_screening(ax, result, labels, dips, dip_dirs, show_zone=show_zone,
                   show_density=show_density, title=title, palette=theme.mpl_palette(),
                   direction_labels=direction_labels, slope_label=slope_label,
                   cone_label=cone_label)
    return fig


# --------------------------------------------------------------------------- #
#  Limit denge
# --------------------------------------------------------------------------- #

def equilibrium_figure(mode: str, inp, res, kind: str = "main") -> Figure:
    """Limit denge çizimi.

    `kind`: kamada "main" (3B geometri) veya "stereonet"; diğer modlarda "main"
    (2B kesit).
    """
    if mode == "wedge" and kind == "stereonet":
        fig = Figure(figsize=(7.4, 8.0))
        fig.patch.set_facecolor("white")
        ax = fig.add_subplot(111)
        plot_stereonet(inp, res.geometry, ax=ax, show=False, res=res)
        return fig

    fig = Figure(figsize=(9.5, 6.4))
    fig.patch.set_facecolor("white")
    if mode == "wedge":
        plot_wedge(res, show=False, fig=fig)
        return fig
    ax = fig.add_subplot(111)
    if mode == "planar":
        plot_planar(res, ax=ax, show=False)
    else:
        plot_toppling(res, ax=ax, show=False)
    fig.tight_layout()
    return fig


def equilibrium_figures(mode: str, inp, res):
    """Rapora giren figürler, sırayla."""
    figs = [equilibrium_figure(mode, inp, res, "main")]
    if mode == "wedge":
        figs.append(equilibrium_figure(mode, inp, res, "stereonet"))
    return figs
