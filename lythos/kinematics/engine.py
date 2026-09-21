"""
lythos.kinematics.engine — kinematik yenilme kontrolleri ve Monte Carlo olasılık motoru.

Yöntemler
---------
Düzlemsel kayma (Markland):  φ ≤ ψp ≤ ψf  ve  |αp − αf| ≤ yanal limit
Kama kayması (Markland):     φ ≤ ψi ≤ görünür şev eğimi  ve  |αi − αf| ≤ yanal limit
Devrilme (Goodman & Bray):   kutup plunge'ı ≤ (ψf − φ)  ve  kutup trendi şev yönüne yakın

Tüm fonksiyonlar vektöreldir (skaler veya numpy dizisi kabul eder); Monte Carlo
tek seferde (n_trials × n_set) dizisi üzerinde çalışır.

Bu modül Qt'den ve matplotlib'den bağımsızdır; doğrudan test edilebilir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple, Union

import numpy as np

from .. import stereonet as _st

PLANAR, WEDGE, TOPPLING = 0, 1, 2
MODES = (PLANAR, WEDGE, TOPPLING)


# --------------------------------------------------------------------------- #
#  Temel geometri
# --------------------------------------------------------------------------- #

def dip_dir_to_strike(dip_dir):
    """Eğim yönü -> doğrultu (sağ el kuralı)."""
    return (np.asarray(dip_dir, dtype=float) - 90.0) % 360.0


def angular_difference(a, b):
    """İki azimut arasındaki en küçük mutlak fark (0–180°)."""
    d = np.abs((np.asarray(a, dtype=float) - np.asarray(b, dtype=float)) % 360.0)
    return np.minimum(d, 360.0 - d)


def plane_normal(dip, dip_dir):
    """Düzlemin yukarı bakan normali (x=Doğu, y=Kuzey, z=Yukarı)."""
    return _st.plane_normal_vec(dip, dip_dir)


def intersection_line(dip1, dd1, dip2, dd2):
    """İki düzlemin kesişim çizgisi -> (plunge, trend), derece.

    Paralel düzlemler NaN üretir (kinematik olarak kritik değildir); bu adımdaki
    geçersiz-değer uyarıları yerel olarak bastırılır.
    """
    with np.errstate(invalid="ignore", divide="ignore"):
        l = np.cross(plane_normal(dip1, dd1), plane_normal(dip2, dd2))
        norm = np.linalg.norm(l, axis=-1)
        norm = np.where(norm < 1e-12, np.nan, norm)
        l = l / norm[..., None]
        l = np.where((l[..., 2] > 0)[..., None], -l, l)       # çizgi aşağı yönlü olsun
        plunge = np.degrees(np.arcsin(np.clip(-l[..., 2], -1.0, 1.0)))
        trend = np.degrees(np.arctan2(l[..., 0], l[..., 1])) % 360.0
    return plunge, trend


# --------------------------------------------------------------------------- #
#  Kinematik kontroller
# --------------------------------------------------------------------------- #

def is_planar_critical(dip, dip_dir, slope_dip, slope_dir, friction, lateral_limit):
    """Markland düzlemsel kayma kriteri."""
    dip = np.asarray(dip, float)
    return (dip >= friction) & (dip <= slope_dip) & \
           (angular_difference(dip_dir, slope_dir) <= lateral_limit)


def is_wedge_critical(plunge, bearing, slope_dip, slope_dir, friction, lateral_limit):
    """Markland kama kriteri: kesişim çizgisi günışığı görmeli ve φ'den dik olmalı."""
    plunge, bearing = np.asarray(plunge, float), np.asarray(bearing, float)
    cosd = np.cos(np.radians(bearing - slope_dir))
    app_dip = np.degrees(np.arctan(np.tan(np.radians(slope_dip)) * np.maximum(cosd, 0.0)))
    return (plunge >= friction) & (angular_difference(bearing, slope_dir) <= lateral_limit) & \
           (plunge <= app_dip)


def is_toppling_critical(dip, dip_dir, slope_dip, slope_dir, friction, lateral_limit):
    """Goodman & Bray eğilme-devrilme kriteri (kutup uzayında)."""
    p_plunge = 90.0 - np.asarray(dip, float)
    p_trend = (np.asarray(dip_dir, float) + 180.0) % 360.0
    return (p_plunge <= (slope_dip - friction)) & \
           (angular_difference(p_trend, slope_dir) <= lateral_limit)


def critical_fn(mode: int):
    """Mod indeksine karşılık gelen kutup-uzayı kriter fonksiyonu."""
    return is_planar_critical if mode == PLANAR else is_toppling_critical


def friction_cone_angle(mode: int, slope_dip: float, friction: float) -> float:
    """Stereonet üzerinde çizilecek sürtünme / kayma limit konisinin yarı açısı.

    Düzlemsel: kutup uzayında φ; kama: çizgi uzayında 90−φ;
    devrilme: Goodman & Bray kayma limiti 90 − (ψf − φ).
    """
    if mode == PLANAR:
        return float(friction)
    if mode == WEDGE:
        return float(90.0 - friction)
    return float(np.clip(90.0 - (slope_dip - friction), 0.0, 90.0))


def critical_zone_grid(mode: int, slope_dip, slope_dir, friction, lateral_limit, step: float = 2.0):
    """Kritik bölgeyi stereonet'te taramak için (plunge, trend) nokta bulutu.

    Düzlemsel/devrilme kutup uzayında, kama kesişim çizgisi uzayında döner.
    """
    g1, g2 = np.meshgrid(np.arange(0, 90 + step, step), np.arange(0, 360, step), indexing="ij")
    if mode == WEDGE:
        mask = is_wedge_critical(g1, g2, slope_dip, slope_dir, friction, lateral_limit)
        return g1[mask], g2[mask]
    mask = critical_fn(mode)(g1, g2, slope_dip, slope_dir, friction, lateral_limit)
    return 90.0 - g1[mask], (g2[mask] + 180.0) % 360.0


# --------------------------------------------------------------------------- #
#  Sonuç veri yapıları
# --------------------------------------------------------------------------- #

@dataclass
class KinematicItem:
    """Tek bir kontrol bileşeni: bir eklem takımı ya da bir eklem çifti kesişimi."""
    name: str
    critical: bool
    value1: float                      # düzlemsel/devrilme: dip;  kama: plunge
    value2: float                      # düzlemsel/devrilme: dip dir;  kama: trend
    index: Union[int, Tuple[int, int]] = -1
    pof: float = float("nan")          # Monte Carlo sonrası doldurulur (%)

    @property
    def is_pair(self) -> bool:
        return isinstance(self.index, tuple)


@dataclass
class ScreeningResult:
    """Deterministik (tek değerli) kinematik tarama sonucu."""
    mode: int
    items: List[KinematicItem] = field(default_factory=list)
    slope_dip: float = 0.0
    slope_dir: float = 0.0
    friction: float = 0.0
    lateral_limit: float = 0.0

    @property
    def n_critical(self) -> int:
        return sum(1 for it in self.items if it.critical)

    @property
    def critical_items(self) -> List[KinematicItem]:
        return [it for it in self.items if it.critical]


@dataclass
class MonteCarloResult:
    """Monte Carlo olasılıksal tarama sonucu."""
    pof: float                          # toplam yenilme olasılığı (%)
    n_fail: int
    n_trials: int
    indices: List[Union[int, Tuple[int, int]]] = field(default_factory=list)
    item_pof: np.ndarray = field(default_factory=lambda: np.array([]))

    def risk_level(self) -> str:
        """Yenilme olasılığına göre risk sınıfı: 'low' / 'moderate' / 'high'."""
        return "low" if self.pof < 5 else ("moderate" if self.pof < 15 else "high")


# --------------------------------------------------------------------------- #
#  Tarama ve Monte Carlo
# --------------------------------------------------------------------------- #

def screen(labels: Sequence[str], dips, dip_dirs, slope_dip, slope_dir, friction,
           lateral_limit, mode: int) -> ScreeningResult:
    """Deterministik kinematik tarama: her bileşen için kritik olup olmadığını döndürür."""
    dips, dip_dirs = np.atleast_1d(np.asarray(dips, float)), np.atleast_1d(np.asarray(dip_dirs, float))
    res = ScreeningResult(mode=mode, slope_dip=float(slope_dip), slope_dir=float(slope_dir),
                          friction=float(friction), lateral_limit=float(lateral_limit))
    if mode == WEDGE:
        for i in range(len(dips)):
            for j in range(i + 1, len(dips)):
                p, b = intersection_line(dips[i], dip_dirs[i], dips[j], dip_dirs[j])
                crit = bool(is_wedge_critical(p, b, slope_dip, slope_dir, friction, lateral_limit))
                res.items.append(KinematicItem(f"{labels[i]} × {labels[j]}", crit,
                                               float(p), float(b), (i, j)))
    else:
        fn = critical_fn(mode)
        for k, (lbl, d, dd) in enumerate(zip(labels, dips, dip_dirs)):
            crit = bool(fn(d, dd, slope_dip, slope_dir, friction, lateral_limit))
            res.items.append(KinematicItem(str(lbl), crit, float(d), float(dd), k))
    return res


def run_monte_carlo(dips, dip_dirs, std_devs, slope_dip, slope_dir, friction, lateral_limit,
                    mode: int, n_trials: int, seed: Optional[int] = 42) -> MonteCarloResult:
    """Tamamen vektörel Monte Carlo simülasyonu.

    Eklem yönelimlerine (dip ve dip yönü) normal dağılımlı belirsizlik uygulanır;
    her denemede seçilen yenilme mekanizması kontrol edilir.
    """
    rng = np.random.default_rng(seed)
    dips, dip_dirs = np.asarray(dips, float), np.asarray(dip_dirs, float)
    std = np.abs(np.asarray(std_devs, float))
    n = len(dips)
    n_trials = int(n_trials)
    sim_dips = np.clip(rng.normal(dips, std, size=(n_trials, n)), 0.0, 90.0)
    sim_dirs = rng.normal(dip_dirs, std, size=(n_trials, n)) % 360.0

    if mode == WEDGE:
        indices: List[Union[int, Tuple[int, int]]] = [(i, j) for i in range(n) for j in range(i + 1, n)]
        item_fail = np.zeros((n_trials, len(indices)), dtype=bool)
        for k, (i, j) in enumerate(indices):
            p, b = intersection_line(sim_dips[:, i], sim_dirs[:, i], sim_dips[:, j], sim_dirs[:, j])
            item_fail[:, k] = is_wedge_critical(p, b, slope_dip, slope_dir, friction, lateral_limit)
    else:
        indices = list(range(n))
        item_fail = critical_fn(mode)(sim_dips, sim_dirs, slope_dip, slope_dir, friction, lateral_limit)

    fails = int(item_fail.any(axis=1).sum()) if item_fail.size else 0
    item_pof = item_fail.mean(axis=0) * 100.0 if item_fail.size else np.array([])
    return MonteCarloResult(pof=fails / n_trials * 100.0, n_fail=fails, n_trials=n_trials,
                            indices=indices, item_pof=item_pof)
