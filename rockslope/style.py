"""rockslope.style — tüm modüller için ortak, rapor kalitesinde matplotlib stili."""
from __future__ import annotations

import matplotlib as mpl
import numpy as np

# Kurumsal palet
NAVY = "#1f3b5a"
GREY = "#5b6770"
LIGHT = "#eef1f5"
ROCK = "#d8cfbf"
ROCK_EDGE = "#8c7b64"
J1 = "#c0392b"
J2 = "#2874a6"
FACE = "#7f8c8d"
UPPER = "#27ae60"
TC = "#e67e22"
WATER = "#3498db"
BOLT = "#1e8449"
SEIS = "#d35400"
MODE_COLORS = {"stabil": "#a9dfbf", "devrilme": "#f1948a", "kayma": "#f9e79f"}


def apply_style():
    mpl.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelsize": 9,
        "axes.edgecolor": GREY,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": "#d5dbe1",
        "grid.linewidth": 0.5,
        "grid.linestyle": "-",
        "xtick.color": GREY,
        "ytick.color": GREY,
        "legend.frameon": True,
        "legend.framealpha": 0.95,
        "legend.edgecolor": "#c9d1dc",
        "legend.fontsize": 8,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.dpi": 160,
        "savefig.bbox": "tight",
    })


def title(ax, main: str, sub: str = ""):
    ax.set_title(main, loc="left", color=NAVY, fontweight="bold", fontsize=11, pad=14 if sub else 6)
    if sub:
        ax.text(0.0, 1.015, sub, transform=ax.transAxes, fontsize=8, color=GREY, va="bottom")


def result_box(ax, lines, loc="upper right"):
    """Sağ üstte FS/özet kutusu."""
    txt = "\n".join(lines)
    x, y, ha, va = {"upper right": (0.985, 0.975, "right", "top"),
                    "upper left": (0.015, 0.975, "left", "top"),
                    "lower right": (0.985, 0.03, "right", "bottom"),
                    "lower left": (0.015, 0.03, "left", "bottom")}[loc]
    ax.text(x, y, txt, transform=ax.transAxes, ha=ha, va=va, fontsize=8.5, family="monospace",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor=NAVY, linewidth=1.0), zorder=20)


def fs_text(fs: float) -> str:
    return "∞" if np.isinf(fs) else f"{fs:.3f}"


def arrow(ax, x0, y0, dx, dy, color, label=None, lw=1.8, ms=12, lpos="end", zorder=10):
    """Etiketli kuvvet oku (2D)."""
    ax.annotate("", xy=(x0 + dx, y0 + dy), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, mutation_scale=ms), zorder=zorder)
    if label:
        lx, ly = (x0 + dx, y0 + dy) if lpos == "end" else (x0, y0)
        ax.annotate(label, (lx, ly), xytext=(4, 4), textcoords="offset points", fontsize=8, color=color,
                    fontweight="bold", bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=color, lw=0.6, alpha=0.9), zorder=zorder + 1)


def dim_line(ax, p0, p1, text, offset=(0, 0), color=GREY):
    """Ölçü çizgisi + metin."""
    ax.annotate("", xy=p1, xytext=p0, arrowprops=dict(arrowstyle="<->", color=color, lw=0.8, shrinkA=0, shrinkB=0))
    mx, my = (p0[0] + p1[0]) / 2 + offset[0], (p0[1] + p1[1]) / 2 + offset[1]
    ax.text(mx, my, text, fontsize=8, color=color, ha="center", va="center", zorder=30,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9))


def angle_arc(ax, center, radius, a0, a1, text, color=GREY):
    from matplotlib.patches import Arc
    ax.add_patch(Arc(center, 2 * radius, 2 * radius, angle=0, theta1=a0, theta2=a1, color=color, lw=0.9, zorder=25))
    am = np.radians((a0 + a1) / 2)
    ax.text(center[0] + 1.3 * radius * np.cos(am), center[1] + 1.3 * radius * np.sin(am), text,
            fontsize=8, color=color, ha="center", va="center", zorder=30,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
