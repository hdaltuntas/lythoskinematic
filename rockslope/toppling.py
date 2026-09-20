"""rockslope.toppling — blok devrilmesi (Goodman & Bray 1976; Wyllie & Mah 2004, Bölüm 9), RocTopple karşılığı.

Su modeli (RocTopple ile aynı mantık):
  * Bloklar arası eklem j (n ile n+1 arasında) su yüksekliği  h_j = p · min(y_n, y_n+1)
    (p = doluluk yüzdesi/100); şev yüzündeki ilk eklem serbest drenajlı (h_0 = 0).
  * Eklemde üçgen basınç dağılımı → V_j = ½·γw·h_j², tabandan h_j/3 yükseklikte, tabana paralel.
  * Blok tabanında yamuk dağılım (uç basınçları γw·h_n-1 ve γw·h_n) → U_n = ½·γw·(h_n-1 + h_n)·Δx,
    kaldırma kuvveti dönme noktasından x_U = Δx·(h_n-1 + 2h_n) / (3(h_n-1 + h_n)) uzaklıkta.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

import numpy as np

from . import style


@dataclass
class TopplingInput:
    """
    Açılar derece, 1 m şev uzunluğu başına.
      face_angle  ψf  : şev yüzü eğimi
      upper_angle ψs  : üst şev eğimi
      disc_dip    ψd  : süreksizliklerin şev içine eğimi; blok tabanı ψp = 90 − ψd
      base_angle  ψb  : basamaklı tabanın genel eğimi (ψb ≥ ψp; b = Δx·tan(ψb−ψp))
      block_width Δx  : blok genişliği (süreksizlik aralığı)
      n_below/n_above : tepe altı (tepe bloğu dahil) / tepe üstü blok sayısı
      friction φ      : taban ve yan yüzey sürtünme açısı
      water_percent   : eklemlerdeki su doluluğu (%; 0 = kuru)
      seismic_h       : yatay pseudo-statik katsayı
      support T, δ    : topuk bloğuna ankraj (kN/m), δ yataydan aşağı +; support_height tabandan yükseklik
    """
    face_angle: float
    upper_angle: float
    disc_dip: float
    base_angle: float
    block_width: float
    n_below: int
    n_above: int
    friction: float
    unit_weight: float = 25.0
    water_percent: float = 0.0
    gamma_w: float = 9.81
    seismic_h: float = 0.0
    support_force: float = 0.0
    support_angle: float = 0.0
    support_height: Optional[float] = None


@dataclass
class TopplingResult:
    fs: float
    phi_required: float
    blocks: List[Dict]
    P0: float
    T_required: float
    slope_height: float
    kinematic_ok: bool
    a1: float
    a2: float
    b: float
    water_heights: List[float]     # h_0..h_N (eklem su yükseklikleri)
    inp: TopplingInput
    warnings: List[str]

    def summary(self) -> str:
        i = self.inp
        L = ["=" * 66, "  BLOK DEVRİLME ANALİZİ  (Goodman & Bray 1976, 1 m şev uzunluğu)", "=" * 66,
             f"ψf = {i.face_angle}°, ψs = {i.upper_angle}°, ψd = {i.disc_dip}° (ψp = {90 - i.disc_dip:.1f}°), "
             f"ψb = {i.base_angle}°, Δx = {i.block_width} m",
             f"Blok sayısı           : {i.n_below} (tepe altı) + {i.n_above} (tepe üstü)",
             f"Şev yüksekliği (yakl.): {self.slope_height:10.2f} m",
             f"a1 / a2 / b           : {self.a1:.3f} / {self.a2:.3f} / {self.b:.3f} m",
             f"Su doluluğu           : {i.water_percent:g} %   sismik αh = {i.seismic_h:g}",
             f"Tabakalar arası kayma : {'mümkün (ψd ≥ 90−ψf+φ)' if self.kinematic_ok else 'koşul sağlanmıyor; blok devrilmesi y/Δx > cotψp ile kontrol edildi'}",
             "-" * 66,
             f"{'Blok':>4} {'y (m)':>7} {'y/Δx':>5} {'W kN':>9} {'U kN':>8} {'V kN':>8} {'Mod':<9} {'P(n-1)':>9}"]
        for bl in self.blocks:
            L.append(f"{bl['n']:>4} {bl['y']:7.2f} {bl['y'] / i.block_width:5.2f} {bl['W']:9.0f} {bl['U']:8.0f} "
                     f"{bl['V']:8.0f} {bl['mode']:<9} {bl['P']:9.1f}")
        L += ["-" * 66,
              f"Topuk bloğu artık kuvvet P0      : {self.P0:9.1f} kN/m  ({'DENGESİZ' if self.P0 > 1e-6 else 'dengede'})",
              f"Gerekli ankraj (topuk, φ mevcut) : {self.T_required:9.1f} kN/m  @ δ = {i.support_angle}°",
              f"Gerekli sürtünme açısı φ_req     : {self.phi_required:9.2f}°  (mevcut {i.friction}°)",
              "=" * 66,
              f"GÜVENLİK SAYISI (FS = tanφ / tanφ_req) : {style.fs_text(self.fs)}",
              "=" * 66]
        L += ["UYARI: " + w for w in self.warnings]
        return "\n".join(L)


def _geometry(i: TopplingInput):
    pf, ps, pb = map(np.radians, (i.face_angle, i.upper_angle, i.base_angle))
    pp = np.radians(90.0 - i.disc_dip)
    dx = i.block_width
    a1 = dx * np.tan(pf - pp); a2 = dx * np.tan(pp - ps); b = dx * np.tan(pb - pp)
    if a1 - b <= 0:
        raise ValueError("a1 − b ≤ 0: blok yükseklikleri artmıyor (ψf çok küçük ya da ψb çok büyük).")
    if b < 0:
        raise ValueError("ψb < ψp: basamaklı taban eğimi blok tabanı eğiminden küçük olamaz.")
    N = i.n_below + i.n_above
    ys = []
    for n in range(1, N + 1):
        ys.append(n * (a1 - b) if n <= i.n_below else ys[-1] - a2 - b)
    if any(y <= 0 for y in ys):
        raise ValueError("Tepe üstü blok yüksekliği sıfırın altına düşüyor: tepe üstü blok sayısını azaltın.")
    return pp, a1, a2, b, ys


def _water_heights(i: TopplingInput, ys):
    p = np.clip(i.water_percent, 0, 100) / 100.0
    N = len(ys)
    h = [0.0] * (N + 1)                     # h[j]: eklem j (blok j ile j+1 arası); h[0]=yüz, h[N]=en arka
    for j in range(1, N):
        h[j] = p * min(ys[j - 1], ys[j])
    h[N] = p * ys[N - 1]
    return h


def _march(i: TopplingInput, tanphi: float, T: float):
    """Tepeden topuğa kuvvet iletimi. Döndürür (P0, bloklar[1..N], ys, a1, a2, b, h)."""
    pp, a1, a2, b, ys = _geometry(i)
    h = _water_heights(i, ys)
    dx, g, ah, gw = i.block_width, i.unit_weight, i.seismic_h, i.gamma_w
    N = len(ys); sp, cp = np.sin(pp), np.cos(pp)
    P = 0.0; blocks = []
    for n in range(N, 0, -1):
        y = ys[n - 1]; W = g * dx * y
        if n < i.n_below:  M, Lm = y, y - a1
        elif n == i.n_below: M, Lm = y - a2, y - a1
        else: M, Lm = y - a2, y
        hu, hd = h[n], h[n - 1]                       # arka (uphill) ve ön (downhill) eklem su yükseklikleri
        Vu, Vd = 0.5 * gw * hu ** 2, 0.5 * gw * hd ** 2
        U = 0.5 * gw * (hu + hd) * dx
        xU = dx * (hd + 2 * hu) / (3 * (hd + hu)) if (hd + hu) > 0 else 0.0
        We_cos = W * cp - ah * W * sp
        We_sin = W * sp + ah * W * cp
        # devrilme momentleri (dönme noktası: ön alt köşe)
        num_t = (P * (M - dx * tanphi) + 0.5 * W * (y * sp - dx * cp) + 0.5 * ah * W * (y * cp + dx * sp)
                 + Vu * hu / 3.0 - Vd * hd / 3.0 + U * xU)
        den_s = 1.0 - tanphi ** 2
        drive = We_sin + Vu - Vd
        if n == 1 and T > 0:
            d = np.radians(i.support_angle)
            hT = i.support_height if i.support_height is not None else 0.5 * y
            num_t -= T * hT * np.cos(pp + d)
            P_t = num_t / Lm if Lm > 1e-9 else np.inf
            P_s = P + (Vu - Vd) - ((We_cos - U) * tanphi - We_sin) / den_s - T * (np.cos(pp + d) + tanphi * np.sin(pp + d)) / den_s
        else:
            P_t = num_t / Lm if Lm > 1e-9 else np.inf
            P_s = P + (Vu - Vd) - ((We_cos - U) * tanphi - We_sin) / den_s
        can_topple = (y / dx) > (cp / sp)
        cand = [("kayma", P_s)] + ([("devrilme", P_t)] if can_topple else [])
        mode, Pn = max(cand, key=lambda c: c[1])
        if Pn <= 0:
            mode, Pn = "stabil", 0.0
        blocks.append({"n": n, "y": y, "W": W, "U": U, "V": Vu, "mode": mode, "P": Pn, "M": M, "L": Lm})
        P = Pn
    return P, blocks[::-1], ys, a1, a2, b, h


def toppling_analyze(i: TopplingInput) -> TopplingResult:
    from copy import deepcopy
    i = deepcopy(i)
    warnings = []
    if i.friction >= 45:
        warnings.append("φ ≥ 45°: kayma denklemindeki (1 − tan²φ) terimi işaret değiştirir; sonuçlar güvenilmez.")
    tanphi = np.tan(np.radians(i.friction))
    P0, blocks, ys, a1, a2, b, h = _march(i, tanphi, i.support_force)
    kin_ok = i.disc_dip >= (90 - i.face_angle) + i.friction - 1e-9

    def p0_at(ph):
        return _march(i, np.tan(np.radians(ph)), i.support_force)[0]

    lo, hi = 0.5, 44.9
    if p0_at(hi) > 1e-6:
        phi_req, fs = np.nan, 0.0
        warnings.append("φ = 45° ile bile denge sağlanmıyor — FS tanımsız (0 alındı). Su/sismik yükü ve geometriyi kontrol edin.")
    elif p0_at(lo) <= 1e-6:
        phi_req, fs = lo, np.inf
    else:
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if p0_at(mid) > 1e-6:
                lo = mid
            else:
                hi = mid
        phi_req = hi; fs = tanphi / np.tan(np.radians(phi_req))

    # Mevcut φ ile topuk ankrajı
    P0_free, bl_free, *_ = _march(i, tanphi, 0.0)
    T_req = 0.0
    if P0_free > 1e-6:
        pp = np.radians(90 - i.disc_dip); d = np.radians(i.support_angle)
        y1 = ys[0]; W1 = i.unit_weight * i.block_width * y1; dx = i.block_width; ah = i.seismic_h; gw = i.gamma_w
        P1 = bl_free[1]["P"] if len(bl_free) > 1 else 0.0
        b1 = bl_free[0]; M1, L1 = b1["M"], b1["L"]
        hT = i.support_height if i.support_height is not None else 0.5 * y1
        sp, cp = np.sin(pp), np.cos(pp)
        hu, hd = h[1], h[0]; Vu, Vd = 0.5 * gw * hu ** 2, 0.5 * gw * hd ** 2
        U = 0.5 * gw * (hu + hd) * dx; xU = dx * (hd + 2 * hu) / (3 * (hd + hu)) if (hd + hu) > 0 else 0.0
        num = (P1 * (M1 - dx * tanphi) + 0.5 * W1 * (y1 * sp - dx * cp) + 0.5 * ah * W1 * (y1 * cp + dx * sp)
               + Vu * hu / 3 - Vd * hd / 3 + U * xU)
        T_t = num / (hT * np.cos(pp + d))
        T_s = ((P1 + Vu - Vd) * (1 - tanphi ** 2) - (W1 * cp - ah * W1 * sp - U) * tanphi + (W1 * sp + ah * W1 * cp)) \
              / (tanphi * np.sin(pp + d) + np.cos(pp + d))
        T_req = max(T_t, T_s, 0.0)

    pp = np.radians(90 - i.disc_dip)
    H = ys[i.n_below - 1] * np.cos(pp) + i.n_below * i.block_width * np.sin(pp) if i.n_below > 0 else 0.0
    return TopplingResult(float(fs), float(phi_req), blocks, float(P0), float(T_req), float(H), bool(kin_ok),
                          a1, a2, b, h, i, warnings)


def toppling_required_support(i: TopplingInput, target_fs: float) -> float:
    """Hedef FS için topuk ankrajı: dayanım tanφ/FS'ye indirilip gereken T hesaplanır."""
    from copy import deepcopy
    j = deepcopy(i)
    j.friction = float(np.degrees(np.arctan(np.tan(np.radians(i.friction)) / target_fs)))
    j.support_force = 0.0
    return toppling_analyze(j).T_required


def plot_toppling(res: TopplingResult, ax=None, show: bool = True, savepath: Optional[str] = None):
    """Rapor kalitesinde kesit: blok kolonları moda göre renkli, su seviyeleri, ankraj, özet kutusu."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Patch
    style.apply_style()
    i = res.inp
    pp = np.radians(90 - i.disc_dip); dx = i.block_width
    if ax is None:
        fig, ax = plt.subplots(figsize=(10.5, 6.2))
    else:
        fig = ax.figure
    e_par = np.array([np.cos(pp), np.sin(pp)]); e_nor = np.array([-np.sin(pp), np.cos(pp)])
    origin = np.array([0.0, 0.0])
    tops = []
    for bl in res.blocks:
        n = bl["n"]; y = bl["y"]
        base0 = origin + (n - 1) * dx * e_par + (n - 1) * res.b * e_nor
        p1 = base0; p2 = base0 + dx * e_par; p3 = p2 + y * e_nor; p4 = p1 + y * e_nor
        ax.add_patch(Polygon([p1, p2, p3, p4], closed=True, facecolor=style.MODE_COLORS[bl["mode"]],
                             edgecolor=style.NAVY, lw=0.7, zorder=4))
        ax.text(*(base0 + 0.5 * dx * e_par + 0.5 * y * e_nor), str(n), ha="center", va="center", fontsize=7, color=style.NAVY, zorder=6)
        tops += [p4, p3]
        # su seviyesi (arka eklem)
        hw = res.water_heights[n]
        if hw > 0:
            q0 = p2; q1 = p2 + hw * e_nor
            ax.plot([q0[0], q1[0]], [q0[1], q1[1]], color=style.WATER, lw=2.4, alpha=0.85, zorder=5)
    # zemin altı kaya
    allp = np.array(tops); xmin, xmax = -0.1 * allp[:, 0].max() - 2, allp[:, 0].max() * 1.05
    ymin = -0.12 * allp[:, 1].max()
    base_line = [origin + (n) * dx * e_par + (n) * res.b * e_nor for n in range(0, len(res.blocks) + 1)]
    rock = [(xmin, 0), (0, 0)] + [tuple(p) for p in base_line] + [(xmax, base_line[-1][1]), (xmax, ymin), (xmin, ymin)]
    ax.add_patch(Polygon(rock, closed=True, facecolor=style.ROCK, edgecolor=style.ROCK_EDGE, hatch="//", lw=1.0, zorder=1))
    if i.support_force > 0:
        y1 = res.blocks[0]["y"]; hT = i.support_height if i.support_height is not None else 0.5 * y1
        pt = origin + hT * e_nor; d = np.radians(i.support_angle); Ln = 0.6 * y1
        style.arrow(ax, pt[0] - Ln * np.cos(d), pt[1] + Ln * np.sin(d), Ln * np.cos(d), -Ln * np.sin(d), style.BOLT,
                    f"T = {i.support_force:,.0f} kN/m @ {i.support_angle:g}°", lpos="start")
    ax.set_aspect("equal"); ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, allp[:, 1].max() * 1.18)
    ax.set_xlabel("Yatay mesafe (m)"); ax.set_ylabel("Kot (m)")
    style.title(ax, "Blok devrilme — kesit ve blok modları",
                f"ψf = {i.face_angle:g}°, ψs = {i.upper_angle:g}°, ψd = {i.disc_dip:g}°, ψb = {i.base_angle:g}°, Δx = {dx:g} m, "
                f"φ = {i.friction:g}°, su %{i.water_percent:g}, αh = {i.seismic_h:g}")
    handles = [Patch(fc=style.MODE_COLORS[k], ec=style.NAVY, label=lab) for k, lab in
               (("stabil", "Stabil"), ("devrilme", "Devrilme"), ("kayma", "Kayma"))]
    if i.water_percent > 0:
        handles.append(plt.Line2D([0], [0], color=style.WATER, lw=2.4, label="Eklem su seviyesi"))
    ax.legend(handles=handles, loc="upper left", fontsize=8)
    style.result_box(ax, [f"FS = {style.fs_text(res.fs)}", f"φ_req = {res.phi_required:.2f}°",
                          f"P0 = {res.P0:,.0f} kN/m", f"T_req = {res.T_required:,.0f} kN/m"], loc="lower right")
    if savepath:
        fig.savefig(savepath)
    if show:
        plt.show()
    return fig
