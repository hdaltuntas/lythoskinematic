"""rockslope.planar — düzlemsel kayma (Hoek & Bray, RocPlane karşılığı), 1 m şev başına."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

import numpy as np

from . import style
from ..i18n import T as _tr
from .text import ACTIVE, LABEL_WIDTH, PASSIVE, WARNING_PREFIX

@dataclass
class PlanarInput:
    """
    2D kesit, birim şev uzunluğu (1 m) başına.
    Açılar derece, uzunluklar m, kuvvetler kN/m, c kPa, γ kN/m³.
      slope_height   : H (topuk-tepe düşey)
      face_angle     : ψf şev yüzü eğimi
      plane_angle    : ψp kayma düzlemi eğimi (ψs < ψp < ψf)
      upper_angle    : ψs üst şev eğimi (yatay = 0)
      tc_distance    : çekme çatlağı konumu; tepeden yatay mesafe b (m).
                       None -> çatlak yok. b < 0 -> çatlak şev yüzünde.
      water_mode     : 'dry' | 'percent' | 'custom'
      water_percent  : çatlak var: çatlağın % doluluğu (zw = p·z).
                       çatlak yok: H&B modeli, düzlemde max basınç ortada,
                       hw = p·H/... yerine hw = p/100 · (düzlem üstü ortalama kalınlık)
      u_plane, u_tc  : 'custom' modda düzlem ve çatlaktaki ortalama basınç (kPa)
      seismic_h/v    : pseudo-statik katsayılar (yatay şeve doğru +, düşey aşağı +)
      support_force  : T (kN/m); support_angle θ: yataydan açı, aşağı + (RocPlane)
    """
    slope_height: float
    face_angle: float
    plane_angle: float
    upper_angle: float = 0.0
    cohesion: float = 0.0
    friction: float = 30.0
    unit_weight: float = 26.0
    tc_distance: Optional[float] = None
    water_mode: str = "dry"
    gamma_w: float = 9.81
    water_percent: float = 100.0
    u_plane: float = 0.0
    u_tc: float = 0.0
    seismic_h: float = 0.0
    seismic_v: float = 0.0
    support_force: float = 0.0
    support_angle: float = 0.0
    support_passive: bool = False


@dataclass
class PlanarResult:
    factor_of_safety: float
    weight: float
    area: float
    plane_length: float
    tc_depth: float
    tc_x: Optional[float]
    tc_on_face: bool
    water_U: float
    water_V: float
    water_height: float
    seismic_force: float
    normal_force: float
    driving: float
    resisting: float
    polygon: List[Tuple[float, float]]
    inp: PlanarInput
    warnings: List[str]

    def summary(self) -> str:
        i = self.inp
        w = LABEL_WIDTH
        L = ["=" * 62,
             "  " + _tr("DÜZLEMSEL KAYMA ANALİZİ  (Hoek & Bray, 1 m şev uzunluğu)",
                      "PLANAR SLIDING ANALYSIS  (Hoek & Bray, 1 m slope length)"),
             "=" * 62,
             f"{_tr('Şev', 'Slope')}: H = {i.slope_height:.2f} m, ψf = {i.face_angle:.1f}°, "
             f"ψp = {i.plane_angle:.1f}°, ψs = {i.upper_angle:.1f}°",
             f"{_tr('Blok alanı', 'Block area'):<{w}}: {self.area:10.3f} m²",
             f"{_tr('Blok ağırlığı W', 'Block weight W'):<{w}}: {self.weight:10.2f} kN/m",
             f"{_tr('Kayma düzlemi uzunluğu', 'Sliding plane length'):<{w}}: {self.plane_length:10.3f} m"]
        tc = f"{_tr('Çekme çatlağı', 'Tension crack'):<{w}}: "
        if self.tc_x is not None:
            where = _tr("şev yüzünde", "on the slope face") if self.tc_on_face else _tr("üst şevde", "in the upper slope")
            L.append(tc + f"{_tr('derinlik', 'depth')} z = {self.tc_depth:.2f} m, {where} (x = {self.tc_x:.2f} m)")
        else:
            L.append(tc + _tr("Yok", "None"))
        L += ["-" * 62,
              f"{_tr('Su yüksekliği zw', 'Water height zw'):<{w}}: {self.water_height:10.2f} m",
              f"{_tr('Su kuvveti U (düzlem)', 'Water force U (plane)'):<{w}}: {self.water_U:10.2f} kN/m",
              f"{_tr('Su kuvveti V (çatlak)', 'Water force V (crack)'):<{w}}: {self.water_V:10.2f} kN/m",
              f"{_tr('Sismik kuvvet (yatay)', 'Seismic force (horiz.)'):<{w}}: {self.seismic_force:10.2f} kN/m",
              f"{_tr('Destek kuvveti T', 'Support force T'):<{w}}: {i.support_force:10.2f} kN/m  "
              f"@ {i.support_angle:.1f}° ({PASSIVE() if i.support_passive else ACTIVE()})",
              "-" * 62,
              f"{_tr('Etkin normal kuvvet', 'Effective normal force'):<{w}}: {self.normal_force:10.2f} kN/m",
              f"{_tr('Kaydırıcı kuvvet', 'Driving force'):<{w}}: {self.driving:10.2f} kN/m",
              f"{_tr('Direnç kuvveti', 'Resisting force'):<{w}}: {self.resisting:10.2f} kN/m",
              "=" * 62]
        fs = self.factor_of_safety
        L.append(f"{_tr('GÜVENLİK SAYISI (FS)', 'FACTOR OF SAFETY (FS)'):<{w}}: "
                 f"{_tr('∞ (stabil)', '∞ (stable)') if np.isinf(fs) else f'{fs:.3f}'}")
        L.append("=" * 62)
        L += [WARNING_PREFIX() + x for x in self.warnings]
        return "\n".join(L)


def _planar_geometry(i: PlanarInput):
    """Topuk orijinde, x şev içine doğru pozitif, y yukarı."""
    H = i.slope_height
    pf, pp, ps = map(np.radians, (i.face_angle, i.plane_angle, i.upper_angle))
    if not (i.upper_angle < i.plane_angle < i.face_angle):
        raise ValueError(
            _tr(f"ψs < ψp < ψf olmalı (ψs={i.upper_angle}°, ψp={i.plane_angle}°, ψf={i.face_angle}°). "
              "Kayma düzlemi şev yüzünden dik ise gün ışığına çıkmaz; üst şevden yatıksa blok kapanmaz.",
              f"ψs < ψp < ψf is required (ψs={i.upper_angle}°, ψp={i.plane_angle}°, ψf={i.face_angle}°). "
              "A sliding plane steeper than the face does not daylight; one flatter than the upper slope "
              "does not close the block."))
    if i.face_angle >= 90:
        raise ValueError(_tr("Şev yüzü eğimi 90°'den küçük olmalı (düşey/askıda şev bu yöntemle çözülmez).",
                           "The slope face angle must be below 90° (a vertical/overhanging face is outside "
                           "this method)."))
    xc = H / np.tan(pf)                      # tepe
    tp, ts = np.tan(pp), np.tan(ps)
    warnings = []
    poly = [(0.0, 0.0), (xc, H)]
    if i.tc_distance is None:
        x_top = (H - xc * ts) / (tp - ts)
        if x_top <= xc:
            raise ValueError(_tr("Kayma düzlemi üst şeve ulaşmadan şev yüzünden çıkıyor — geometri geçersiz.",
                               "The sliding plane exits through the face before reaching the upper slope — "
                               "invalid geometry."))
        poly.append((x_top, x_top * tp))
        x_bot, z, tc_on_face, tc_x = x_top, 0.0, False, None
    else:
        tc_x = xc + i.tc_distance
        if tc_x <= 0:
            raise ValueError(_tr("Çekme çatlağı topuğun gerisinde — geçersiz.",
                               "The tension crack lies behind the toe — invalid."))
        tc_on_face = tc_x < xc
        y_s = tc_x * np.tan(pf) if tc_on_face else H + (tc_x - xc) * ts
        y_p = tc_x * tp
        z = y_s - y_p
        if z <= 0:
            raise ValueError(_tr("Çekme çatlağı kayma düzleminin altında kalıyor (z ≤ 0) — mesafeyi azaltın.",
                               "The tension crack falls below the sliding plane (z ≤ 0) — reduce the distance."))
        if tc_on_face:
            poly = [(0.0, 0.0), (tc_x, y_s), (tc_x, y_p)]
        else:
            poly += [(tc_x, y_s), (tc_x, y_p)]
        x_bot = tc_x
    xs, ys = zip(*poly)
    area = 0.5 * abs(sum(xs[k] * ys[(k + 1) % len(xs)] - xs[(k + 1) % len(xs)] * ys[k] for k in range(len(xs))))
    L_plane = x_bot / np.cos(pp)
    return poly, area, L_plane, z, tc_x, tc_on_face, warnings


def planar_analyze(i: PlanarInput) -> PlanarResult:
    from copy import deepcopy
    i = deepcopy(i)
    poly, A, Lp, z, tc_x, tc_on_face, warnings = _planar_geometry(i)
    pp = np.radians(i.plane_angle)
    phi = np.radians(i.friction)
    W = i.unit_weight * A

    # --- Su ---
    U = V = zw = 0.0
    if i.water_mode == "custom":
        U = i.u_plane * Lp
        V = i.u_tc * z if tc_x is not None else 0.0
    elif i.water_mode == "percent":
        p = np.clip(i.water_percent, 0, 100) / 100.0
        if tc_x is not None:
            zw = p * z
            V = 0.5 * i.gamma_w * zw ** 2                    # çatlakta üçgen dağılım
            U = 0.5 * i.gamma_w * zw * Lp                   # düzlemde: çatlak dibinde γw·zw, topukta 0
        else:
            # H&B çatlaksız model: düzlem uçlarında 0, ortada maksimum
            hw = p * (A / Lp)                               # ortalama blok kalınlığı ölçeği
            zw = hw
            U = 0.5 * i.gamma_w * hw * Lp
    elif i.water_mode != "dry":
        raise ValueError(_tr(f"Bilinmeyen su modu: {i.water_mode}", f"Unknown water mode: {i.water_mode}"))

    # --- Sismik ---
    Fh = i.seismic_h * W                                    # yatay, şev dışına
    Wv = W * (1.0 + i.seismic_v)                            # düşey katsayı (aşağı +)

    # --- Kuvvet bileşenleri (düzleme paralel/dik) ---
    N = Wv * np.cos(pp) - Fh * np.sin(pp) - U - V * np.sin(pp)
    S = Wv * np.sin(pp) + Fh * np.cos(pp) + V * np.cos(pp)

    T, th = i.support_force, np.radians(i.support_angle)
    Tpar, Tnor = T * np.cos(th + pp), T * np.sin(th + pp)
    if T > 0 and not i.support_passive:
        N += Tnor
        S -= Tpar
    resisting = i.cohesion * Lp + max(N, 0.0) * np.tan(phi)
    if T > 0 and i.support_passive:
        resisting += Tpar + Tnor * np.tan(phi)
    if N <= 0:
        warnings.append(_tr("Etkin normal kuvvet ≤ 0: blok düzlemden ayrılıyor (su/sismik çok yüksek).",
                          "Effective normal force ≤ 0: the block separates from the plane "
                          "(water/seismic load too high)."))
    fs = np.inf if S <= 1e-9 else resisting / S
    return PlanarResult(float(fs), W, A, Lp, z, tc_x, tc_on_face, U, V, zw, Fh,
                        float(N), float(S), float(resisting), poly, i, warnings)


def planar_required_support(i: PlanarInput, target_fs: float, angle: Optional[float] = None,
                            passive: bool = False):
    """
    Hedef FS için gerekli T (kN/m). angle None -> optimum açı:
      aktif : tan(ψp+θ) = tanφ / FS_hedef   (Hoek & Bray)
      pasif : tan(ψp+θ) = tanφ
    Döndürür: (T, θ, FS_mevcut)
    """
    from copy import deepcopy
    b = deepcopy(i); b.support_force = 0.0
    r0 = planar_analyze(b)
    pp, phi = np.radians(i.plane_angle), np.radians(i.friction)
    if angle is None:
        k = np.tan(phi) / (target_fs if not passive else 1.0)
        angle = float(np.degrees(np.arctan(k)) - i.plane_angle)
    th = np.radians(angle)
    if r0.factor_of_safety >= target_fs:
        return 0.0, angle, r0.factor_of_safety
    R0, D0 = r0.resisting, r0.driving
    cpar, snor = np.cos(th + pp), np.sin(th + pp)
    if passive:
        den = cpar + snor * np.tan(phi)
    else:
        den = target_fs * cpar + snor * np.tan(phi)
    if den <= 1e-9:
        return np.nan, angle, r0.factor_of_safety
    T = (target_fs * D0 - R0) / den
    return float(T), angle, r0.factor_of_safety


def plot_planar(res: PlanarResult, ax=None, show: bool = True, savepath: Optional[str] = None):
    """Rapor kalitesinde 2D kesit: kaya taraması, blok, çatlak, su, kuvvet okları, ölçüler."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    style.apply_style()
    i = res.inp
    if ax is None:
        fig, ax = plt.subplots(figsize=(9.5, 6))
    else:
        fig = ax.figure
    H = i.slope_height; pf, ps, pp = map(np.radians, (i.face_angle, i.upper_angle, i.plane_angle))
    xc = H / np.tan(pf)
    xr = max(p[0] for p in res.polygon) * 1.45 + 2
    x_left = -max(0.35 * xc + 2, 0.55 * H + 2)
    y_top = H + (xr - xc) * np.tan(ps)
    y_bot = -0.18 * H
    ground = [(x_left, 0), (0, 0), (xc, H), (xr, y_top)]
    rock = ground + [(xr, y_bot), (x_left, y_bot)]
    ax.add_patch(Polygon(rock, closed=True, facecolor=style.ROCK, edgecolor="none", hatch="//", lw=0, zorder=1))
    ax.plot(*zip(*ground), color=style.ROCK_EDGE, lw=2.2, zorder=3)
    ax.add_patch(Polygon(res.polygon, closed=True, facecolor="#f5b7b1", edgecolor=style.J1, lw=1.6, alpha=0.95, zorder=4))
    xb = res.polygon[-1][0]
    ax.plot([0, xb], [0, xb * np.tan(pp)], color=style.J1, lw=2.0, ls="--", zorder=5, label=f"{_tr('Kayma düzlemi', 'Sliding plane')} ψp = {i.plane_angle:g}°")
    if res.tc_x is not None:
        yb = res.tc_x * np.tan(pp); ys_ = yb + res.tc_depth
        ax.plot([res.tc_x, res.tc_x], [yb, ys_], color=style.TC, lw=2.2, zorder=6, label=f"{_tr('Çekme çatlağı', 'Tension crack')} z = {res.tc_depth:.1f} m")
        if res.water_height > 0:
            ax.fill_betweenx([yb, yb + res.water_height], res.tc_x - 0.012 * xr, res.tc_x + 0.012 * xr,
                             color=style.WATER, alpha=0.75, zorder=7)
            ax.annotate(f"zw = {res.water_height:.1f} m", (res.tc_x, yb + res.water_height), xytext=(6, 2),
                        textcoords="offset points", fontsize=8, color=style.WATER, fontweight="bold")
            pmax = 0.06 * H
            tri = [(0, 0), (xb, xb * np.tan(pp)), (xb + pmax * np.sin(pp), xb * np.tan(pp) - pmax * np.cos(pp))]
            ax.add_patch(Polygon(tri, closed=True, facecolor=style.WATER, alpha=0.35, edgecolor=style.WATER, lw=0.6, zorder=3))
    elif res.water_height > 0:
        ax.text(0.5 * xb, 0.5 * xb * np.tan(pp) - 0.06 * H, f"U = {res.water_U:.0f} kN/m", color=style.WATER, fontsize=8, ha="center")
    cx = np.mean([p[0] for p in res.polygon]); cy = np.mean([p[1] for p in res.polygon])
    sc = 0.28 * H / max(res.weight, 1e-9)
    style.arrow(ax, cx, cy, 0, -res.weight * sc, "k", f"W = {res.weight:,.0f} kN/m")
    if res.seismic_force > 0:
        style.arrow(ax, cx, cy, -res.seismic_force * sc, 0, style.SEIS, f"αhW = {res.seismic_force:,.0f}")
    if i.support_force > 0:
        th = np.radians(i.support_angle); ln = 0.45 * H
        yf = 0.45 * H; px, py = yf / np.tan(pf), yf            # şev yüzü üzerindeki uygulama noktası
        style.arrow(ax, px - ln * np.cos(th), py + ln * np.sin(th), ln * np.cos(th), -ln * np.sin(th), style.BOLT,
                    f"T = {i.support_force:,.0f} kN/m @ {i.support_angle:.0f}°", lpos="start")
    style.dim_line(ax, (x_left * 0.88, 0), (x_left * 0.88, H), f"H = {H:g} m", offset=(0.055 * xr, 0))
    style.angle_arc(ax, (0, 0), 0.22 * H, 0, i.face_angle, f"ψf = {i.face_angle:g}°")
    style.angle_arc(ax, (0, 0), 0.36 * H, 0, i.plane_angle, f"ψp = {i.plane_angle:g}°")
    if res.tc_x is not None and not res.tc_on_face:
        style.dim_line(ax, (xc, H + 0.06 * H), (res.tc_x, H + 0.06 * H), f"b = {i.tc_distance:g} m", offset=(0, 0.05 * H))
    ax.set_aspect("equal"); ax.set_xlim(x_left, xr); ax.set_ylim(y_bot, y_top + 0.35 * H)
    ax.set_xlabel(_tr("Yatay mesafe (m)", "Horizontal distance (m)")); ax.set_ylabel(_tr("Kot (m)", "Elevation (m)"))
    style.title(ax, _tr("Düzlemsel kayma — 2D kesit (1 m şev uzunluğu)",
                      "Planar sliding — 2D section (1 m slope length)"),
                f"ψf = {i.face_angle:g}°, ψp = {i.plane_angle:g}°, ψs = {i.upper_angle:g}°, c = {i.cohesion:g} kPa, φ = {i.friction:g}°, γ = {i.unit_weight:g} kN/m³")
    style.result_box(ax, [f"FS = {style.fs_text(res.factor_of_safety)}",
                          f"N' = {res.normal_force:,.0f} kN/m", f"S  = {res.driving:,.0f} kN/m",
                          f"R  = {res.resisting:,.0f} kN/m"], loc="upper right")
    ax.legend(loc="lower right", fontsize=7.5)
    if savepath:
        fig.savefig(savepath)
    if show:
        plt.show()
    return fig
