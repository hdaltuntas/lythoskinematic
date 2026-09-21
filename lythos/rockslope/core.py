"""rockslope.core — ortak vektör/geometri yardımcıları (x=Doğu, y=Kuzey, z=Yukarı)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

import numpy as np

from ..i18n import T as _tr

#  Vektör yardımcıları
# --------------------------------------------------------------------------- #

def unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n < 1e-14:
        raise ValueError(_tr("Sıfır vektör normalize edilemez.",
                             "A zero vector cannot be normalised."))
    return v / n


def plane_normal(dip: float, dipdir: float) -> np.ndarray:
    """Düzlem normali (yukarı bakan)."""
    d, a = np.radians(dip), np.radians(dipdir)
    return np.array([np.sin(d) * np.sin(a), np.sin(d) * np.cos(a), np.cos(d)])


def down_dip_vector(dip: float, dipdir: float) -> np.ndarray:
    """Düzlem içinde, eğim yönünde aşağı bakan birim vektör."""
    d, a = np.radians(dip), np.radians(dipdir)
    return np.array([np.cos(d) * np.sin(a), np.cos(d) * np.cos(a), -np.sin(d)])


def trend_plunge_vector(trend: float, plunge: float) -> np.ndarray:
    """Trend/plunge (derece) -> birim vektör. Plunge > 0 aşağı."""
    t, p = np.radians(trend), np.radians(plunge)
    return np.array([np.cos(p) * np.sin(t), np.cos(p) * np.cos(t), -np.sin(p)])


def vector_to_trend_plunge(v: np.ndarray) -> Tuple[float, float]:
    v = unit(v)
    plunge = np.degrees(np.arcsin(np.clip(-v[2], -1, 1)))
    trend = np.degrees(np.arctan2(v[0], v[1])) % 360.0
    return float(trend), float(plunge)


def intersect_3_planes(n1, p1, n2, p2, n3, p3) -> np.ndarray:
    M = np.vstack([n1, n2, n3])
    b = np.array([n1 @ p1, n2 @ p2, n3 @ p3])
    if abs(np.linalg.det(M)) < 1e-12:
        raise ValueError(_tr("Üç düzlem tek noktada kesişmiyor (paralel/dejenere).",
                             "The three planes do not meet at a single point "
                             "(parallel/degenerate)."))
    return np.linalg.solve(M, b)


def polygon_area(pts: List[np.ndarray], normal: np.ndarray) -> float:
    """Düzlemsel çokgen alanı (köşeler merkez etrafında sıralanır)."""
    if len(pts) < 3:
        return 0.0
    P = np.array(pts)
    c = P.mean(axis=0)
    n = unit(normal)
    # düzlem içi eksenler
    e1 = unit(np.cross(n, [0, 0, 1.0]) if abs(n[2]) < 0.99 else np.cross(n, [1.0, 0, 0]))
    e2 = np.cross(n, e1)
    ang = np.arctan2((P - c) @ e2, (P - c) @ e1)
    P = P[np.argsort(ang)]
    area = 0.0
    for i in range(len(P)):
        area += np.cross(P[i] - c, P[(i + 1) % len(P)] - c) @ n
    return abs(area) / 2.0


# --------------------------------------------------------------------------- #
