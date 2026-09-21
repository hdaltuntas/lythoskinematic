"""
lythoskinematic.stereonet — ortak alt yarımküre stereonet çekirdeği.

Hem kinematik tarama (Markland) hem de limit denge modülleri bu tek projeksiyon
uygulamasını kullanır; böylece iki modülün stereonetleri birebir aynı geometriyi
ve aynı görsel dili paylaşır.

Eksen takımı `lythoskinematic.rockslope.core` ile aynıdır: x = Doğu, y = Kuzey, z = Yukarı.
Çizgi vektörlerinde plunge > 0 aşağı yönlüdür.

Dış bağımlılık yok: yalnızca numpy + matplotlib (mplstereonet gerekmez).
"""
from __future__ import annotations

from typing import Optional, Sequence, Tuple

import numpy as np

__all__ = [
    "stereo_xy", "great_circle", "small_circle", "pole_xy", "line_xy",
    "plane_normal_vec", "down_dip_vec", "trend_plunge_vec", "vector_to_trend_plunge",
    "draw_net", "density_grid",
]


# --------------------------------------------------------------------------- #
#  Vektör yardımcıları (vektörel: skaler veya dizi kabul eder)
# --------------------------------------------------------------------------- #

def plane_normal_vec(dip, dipdir) -> np.ndarray:
    """Düzlemin yukarı bakan birim normali. Şekil: (..., 3)."""
    d, a = np.radians(np.asarray(dip, float)), np.radians(np.asarray(dipdir, float))
    return np.stack([np.sin(d) * np.sin(a), np.sin(d) * np.cos(a), np.cos(d)], axis=-1)


def down_dip_vec(dip, dipdir) -> np.ndarray:
    """Düzlem içinde eğim yönünde aşağı bakan birim vektör."""
    d, a = np.radians(np.asarray(dip, float)), np.radians(np.asarray(dipdir, float))
    return np.stack([np.cos(d) * np.sin(a), np.cos(d) * np.cos(a), -np.sin(d)], axis=-1)


def trend_plunge_vec(trend, plunge) -> np.ndarray:
    """Trend/plunge (derece) -> birim vektör; plunge > 0 aşağı."""
    t, p = np.radians(np.asarray(trend, float)), np.radians(np.asarray(plunge, float))
    return np.stack([np.cos(p) * np.sin(t), np.cos(p) * np.cos(t), -np.sin(p)], axis=-1)


def vector_to_trend_plunge(v) -> Tuple[np.ndarray, np.ndarray]:
    """Birim vektör -> (trend, plunge) derece. Yukarı bakan vektörler aşağı çevrilir."""
    v = np.asarray(v, float)
    v = v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-15)
    v = np.where((v[..., 2] > 0)[..., None], -v, v)
    plunge = np.degrees(np.arcsin(np.clip(-v[..., 2], -1.0, 1.0)))
    trend = np.degrees(np.arctan2(v[..., 0], v[..., 1])) % 360.0
    return trend, plunge


# --------------------------------------------------------------------------- #
#  Projeksiyon
# --------------------------------------------------------------------------- #

def _radius(plunge, equal_area: bool = True) -> np.ndarray:
    """Plunge (derece) -> birim daire içinde yarıçap."""
    theta = np.radians(90.0 - np.maximum(np.asarray(plunge, float), 0.0)) / 2.0
    # Her iki projeksiyon da birim daireye normalize edilir: yatay çizgi (plunge = 0)
    # r = 1'e, düşey çizgi (plunge = 90) r = 0'a düşer.
    if equal_area:                       # Lambert (Schmidt) eşit alan
        return np.sqrt(2.0) * np.sin(theta)
    return np.tan(theta)                 # eşit açı (Wulff)


def line_xy(trend, plunge, equal_area: bool = True):
    """Trend/plunge -> stereonet (x, y). Vektörel."""
    r = _radius(plunge, equal_area)
    t = np.radians(np.asarray(trend, float))
    return r * np.sin(t), r * np.cos(t)


def stereo_xy(v, equal_area: bool = True):
    """Çizgi vektörü -> stereonet (x, y). Yukarı bakan vektörler aşağı çevrilir."""
    trend, plunge = vector_to_trend_plunge(v)
    return line_xy(trend, plunge, equal_area)


def pole_xy(dip, dipdir, equal_area: bool = True):
    """Düzlemin kutbu (aşağı bakan normal) -> stereonet (x, y)."""
    return stereo_xy(-plane_normal_vec(dip, dipdir), equal_area)


def great_circle(dip: float, dipdir: float, equal_area: bool = True, n: int = 181):
    """Düzlemin büyük dairesi (alt yarımküre izi) -> (xs, ys)."""
    d = down_dip_vec(dip, dipdir)
    strike = np.array([np.sin(np.radians(dipdir + 90.0)), np.cos(np.radians(dipdir + 90.0)), 0.0])
    t = np.linspace(0.0, np.pi, n)[:, None]
    v = np.cos(t) * strike + np.sin(t) * d
    return stereo_xy(v, equal_area)


def small_circle(trend: float, plunge: float, angle: float, equal_area: bool = True, n: int = 361):
    """`(trend, plunge)` ekseni etrafında `angle` yarı açılı küçük daire -> (xs, ys).

    Alt yarımkürede kalmayan kısımlar NaN ile kesilir; matplotlib bu kısımları çizmez.
    """
    axis = trend_plunge_vec(trend, plunge)
    ref = np.array([0.0, 0.0, 1.0]) if abs(axis[2]) < 0.95 else np.array([1.0, 0.0, 0.0])
    e1 = np.cross(axis, ref)
    e1 /= max(np.linalg.norm(e1), 1e-15)
    e2 = np.cross(axis, e1)
    a = np.radians(angle)
    t = np.linspace(0.0, 2.0 * np.pi, n)[:, None]
    v = np.cos(a) * axis + np.sin(a) * (np.cos(t) * e1 + np.sin(t) * e2)
    x, y = stereo_xy(v, equal_area)
    # yukarı yarımküreye taşan kolları kopar (aksi hâlde daire karşı kenara sıçrar)
    upper = v[:, 2] > 1e-9
    x, y = np.where(upper, np.nan, x), np.where(upper, np.nan, y)
    return x, y


# --------------------------------------------------------------------------- #
#  Kutup yoğunluğu (Kamb tarzı sayım, mplstereonet gerekmeden)
# --------------------------------------------------------------------------- #

def density_grid(trends, plunges, equal_area: bool = True, gridsize: int = 140,
                 cone_angle: Optional[float] = None):
    """Kutup yoğunluğu ızgarası.

    Her ızgara düğümünde, düğüm eksenine `cone_angle` derece içinde kalan ölçüm
    sayısı sayılır (sayım konisi yöntemi). Döndürür: (X, Y, Z) — birim daire
    dışındaki düğümler NaN'dır, Z yüzde cinsindendir (% / sayım alanı).
    """
    trends, plunges = np.atleast_1d(trends).astype(float), np.atleast_1d(plunges).astype(float)
    n = len(trends)
    if n == 0:
        return None
    if cone_angle is None:
        # Kamb (1959): sayım alanı hemisferin 9/(n+9)'u kadar, yani örneklem
        # büyüdükçe koni daralır. Küçük örneklemlerde koni tüm ağı kaplayacak
        # kadar açıldığından üst sınırla kırpılır.
        cone_angle = float(np.degrees(np.arccos(1.0 - 9.0 / (n + 9.0))))
        cone_angle = float(np.clip(cone_angle, 8.0, 30.0))

    g = np.linspace(-1.0, 1.0, gridsize)
    X, Y = np.meshgrid(g, g)
    R = np.hypot(X, Y)
    inside = R <= 1.0

    # ızgara (x, y) -> alt yarımküre birim vektörü (projeksiyonun tersi)
    with np.errstate(invalid="ignore"):
        if equal_area:
            theta = 2.0 * np.arcsin(np.clip(R / np.sqrt(2.0), 0.0, 1.0))
        else:
            theta = 2.0 * np.arctan(R)
        plunge_g = 90.0 - np.degrees(theta)
        trend_g = np.degrees(np.arctan2(X, Y)) % 360.0

    nodes = trend_plunge_vec(trend_g[inside], plunge_g[inside])          # (m, 3)
    data = trend_plunge_vec(trends, plunges)                             # (n, 3)
    cos_lim = np.cos(np.radians(cone_angle))
    counts = np.zeros(nodes.shape[0])
    for i in range(0, nodes.shape[0], 2048):                             # bellek dostu parçalı çarpım
        blk = nodes[i:i + 2048]
        counts[i:i + 2048] = (np.abs(blk @ data.T) >= cos_lim).sum(axis=1)

    Z = np.full(X.shape, np.nan)
    Z[inside] = counts / n * 100.0
    return X, Y, Z


# --------------------------------------------------------------------------- #
#  Ağ çizimi
# --------------------------------------------------------------------------- #

def draw_net(ax, equal_area: bool = True, grid_color: str = "#e2e6ea", edge_color: str = "#1f3b5a",
             text_color: str = "#5b6770", labels: Sequence[str] = ("K", "D", "G", "B"),
             tick_step: int = 30):
    """Boş stereonet ağı: plunge daireleri, trend ışınları, dış çember ve yön etiketleri."""
    from matplotlib.patches import Circle

    ax.set_facecolor("none")
    for pl in range(10, 90, 10):
        xs, ys = line_xy(np.linspace(0, 360, 181), pl, equal_area)
        ax.plot(xs, ys, color=grid_color, lw=0.5, zorder=1)
    for t in range(0, 360, tick_step):
        x, y = line_xy(t, 0.0, equal_area)
        ax.plot([0, x], [0, y], color=grid_color, lw=0.5, zorder=1)
        if t % 90:
            ax.text(1.06 * x, 1.06 * y, f"{t}°", fontsize=6.5, color=text_color, ha="center", va="center")
    ax.add_patch(Circle((0, 0), 1, fill=False, lw=1.4, color=edge_color, zorder=3))
    for lab, (x, y) in zip(labels, [(0, 1.10), (1.10, 0), (0, -1.10), (-1.10, 0)]):
        ax.text(x, y, lab, ha="center", va="center", fontsize=10, fontweight="bold", color=edge_color)
    ax.set_aspect("equal")
    ax.set_xlim(-1.22, 1.22); ax.set_ylim(-1.22, 1.22)
    ax.axis("off")
    return ax
