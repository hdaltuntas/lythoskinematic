"""rockslope.bolts — bulon karelaj/boy tasarımı ve seçilen tasarımın kapasite kontrolü (kama + düzlemsel)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

import numpy as np

from ..i18n import T as _tr
from .core import unit, trend_plunge_vector
from .text import LABEL_WIDTH, WARNING_PREFIX
from .wedge import WedgeInput, WedgeResult, Support, build_wedge, analyze, required_support
from .planar import PlanarInput, PlanarResult, planar_analyze, planar_required_support

@dataclass
class BoltSpec:
    """
    capacity      : bulonun çalışma (izin verilen) çekme kapasitesi, kN
                    (ör. Ø25 mm St 500: akma ≈ 245 kN, çalışma ≈ 0.6×akma ≈ 150 kN)
    hole_diameter : delik çapı, mm
    bond_strength : harç–kaya nihai aderans (bond) dayanımı, kPa
                    (zayıf kaya 300–700, orta 700–1500, sağlam 1500–3000+ kPa)
    fs_bond       : kök boyu güvenlik sayısı (genelde 2–3)
    min_bond      : minimum kök boyu, m
    extra_length  : baş plakası / dış pay, m
    s_min, s_max  : izin verilen karelaj aralığı, m
    step          : aralık ve boy yuvarlama adımı, m
    """
    capacity: float = 150.0
    hole_diameter: float = 76.0
    bond_strength: float = 800.0
    fs_bond: float = 2.5
    min_bond: float = 2.0
    extra_length: float = 0.5
    s_min: float = 1.0
    s_max: float = 3.0
    step: float = 0.25

    def bond_length(self) -> float:
        d = self.hole_diameter / 1000.0
        Lb = self.capacity * self.fs_bond / (np.pi * d * self.bond_strength)
        return max(Lb, self.min_bond)


@dataclass
class BoltPattern:
    required_force: float
    n_bolts: float                  # planar: adet/m şev uzunluğu; kama: toplam adet
    spacing: float                  # kare karelaj s (m)
    spacing_theoretical: float
    face_area: float                # planar: m²/m (yüz uzunluğu); kama: m²
    free_lengths: List[Tuple[float, float]]   # (konum, serbest boy)
    free_max: float
    bond_length: float
    total_length: float
    capacity_provided: float
    warnings: List[str]
    per_metre: bool

    def summary(self) -> str:
        u = "kN/m" if self.per_metre else "kN"
        w = LABEL_WIDTH
        count_unit = (_tr("adet / m şev uzunluğu", "bolts / m of slope length") if self.per_metre
                      else _tr("adet (toplam)", "bolts (total)"))
        L = ["=" * 62,
             "  " + _tr("BULON KARELAJ VE BOY TASARIMI", "BOLT SPACING AND LENGTH DESIGN"),
             "=" * 62,
             f"{_tr('Gerekli destek', 'Required support'):<{w}}: {self.required_force:10.1f} {u}",
             f"{_tr('Bulon sayısı', 'Number of bolts'):<{w}}: {self.n_bolts:10.2f} {count_unit}",
             f"{_tr('Teorik maks. aralık', 'Theoretical max. spacing'):<{w}}: {self.spacing_theoretical:10.2f} m",
             f"{_tr('TASARIM KARELAJI', 'DESIGN SPACING'):<{w}}: {self.spacing:10.2f} m × {self.spacing:.2f} m",
             f"{_tr('Sağlanan kapasite', 'Capacity provided'):<{w}}: {self.capacity_provided:10.1f} {u}",
             "-" * 62,
             _tr("Serbest boy (yüz konumu → kayma yüzeyine, bulon doğrultusunda):",
               "Free length (face position → sliding surface, along the bolt axis):")]
        for pos, lf in self.free_lengths:
            L.append(f"   {_tr('yüzde', 'at face'):<8} {pos:6.2f} m : {lf:6.2f} m")
        L += ["-" * 62,
              f"{_tr('Maks. serbest boy', 'Max. free length'):<{w}}: {self.free_max:10.2f} m",
              f"{_tr('Kök (bond) boyu', 'Bond length'):<{w}}: {self.bond_length:10.2f} m",
              f"{_tr('MİNİMUM BULON BOYU', 'MINIMUM BOLT LENGTH'):<{w}}: {self.total_length:10.2f} m  "
              f"({_tr('serbest + kök + pay', 'free + bond + allowance')})",
              "=" * 62]
        L += [WARNING_PREFIX() + x for x in self.warnings]
        return "\n".join(L)


def _design_spacing(T_req, area, spec: BoltSpec, warnings):
    n_req = T_req / spec.capacity
    s_theo = np.sqrt(area / n_req) if n_req > 0 else np.inf
    s = np.floor(min(s_theo, spec.s_max) / spec.step) * spec.step
    if s < spec.s_min:
        warnings.append(_tr(
            f"Gerekli aralık ({s_theo:.2f} m) minimum aralığın ({spec.s_min} m) altında: "
            f"daha yüksek kapasiteli bulon/ankraj veya ek önlem gerekir. s = {spec.s_min} m alındı.",
            f"The required spacing ({s_theo:.2f} m) is below the minimum ({spec.s_min} m): a higher-capacity "
            f"bolt/anchor or an additional measure is needed. s = {spec.s_min} m was used."))
        s = spec.s_min
    n_prov = area / s ** 2
    return n_req, s_theo, s, n_prov * spec.capacity


def bolt_pattern_planar(res: PlanarResult, T_req: float, angle: float, spec: BoltSpec,
                        n_rows: int = 6) -> BoltPattern:
    """Düzlemsel: T_req kN/m, karelaj şev yüzüne yayılır; serbest boy her sıra için hesaplanır."""
    i = res.inp
    pf, pp, th = map(np.radians, (i.face_angle, i.plane_angle, angle))
    warnings = []
    # bloğun şev yüzündeki uzunluğu (çatlak yüzdeyse çatlağa kadar)
    y_top = res.polygon[1][1] if not res.tc_on_face else res.polygon[1][1]
    L_face = y_top / np.sin(pf)
    n_req, s_theo, s, cap = _design_spacing(T_req, L_face, spec, warnings)
    # serbest boy: yüz üzerindeki noktadan bulon doğrultusunda kayma düzlemine
    den = np.sin(th) + np.cos(th) * np.tan(pp)
    if den <= 1e-9:
        raise ValueError(_tr("Bulon doğrultusu kayma düzlemini kesmiyor (açı çok yukarı) — θ'yı artırın.",
                           "The bolt axis does not cross the sliding plane (angle too far up) — increase θ."))
    free = []
    for k in range(n_rows + 1):
        y = y_top * (k + 0.5) / (n_rows + 1) if k < n_rows else y_top * 0.999
        x = y / np.tan(pf)
        t = (y - x * np.tan(pp)) / den
        free.append((y / np.sin(pf), max(t, 0.0)))
    fmax = max(f for _, f in free)
    Lb = spec.bond_length()
    total = np.ceil((fmax + Lb + spec.extra_length) / spec.step) * spec.step
    if total > 12:
        warnings.append(_tr(f"Bulon boyu {total:.1f} m > 12 m: öngermeli kablo ankraj daha uygun olabilir.",
                          f"Bolt length {total:.1f} m > 12 m: a pre-stressed cable anchor may be more "
                          f"suitable."))
    if s > 0.5 * total + 1e-9 and s > 1.5:
        warnings.append(_tr(f"Aralık ({s:.2f} m) bulon boyunun yarısından büyük; blok bütünlüğü için "
                          f"s ≤ L/2 ≈ {0.5 * total:.2f} m önerilir.",
                          f"The spacing ({s:.2f} m) exceeds half the bolt length; s ≤ L/2 ≈ "
                          f"{0.5 * total:.2f} m is recommended for block integrity."))
    if angle < 0:
        warnings.append(_tr("Bulon yukarı eğimli (θ<0): harç enjeksiyonu/drenaj güçtür; uygulamada 5–15° "
                          "aşağı eğim tercih edilir (kapasite kaybı için 'Gerekli kuvvet'i o açıyla "
                          "yeniden hesaplayın).",
                          "The bolt points upward (θ<0): grouting/drainage is difficult; 5–15° downward is "
                          "preferred in practice (recompute 'Required support' at that angle to see the "
                          "capacity loss)."))
    return BoltPattern(T_req, n_req / 1.0, s, s_theo, L_face, free, fmax, Lb, total, cap, warnings, True)


def bolt_pattern_wedge(res: WedgeResult, T_req: float, trend: float, plunge: float,
                       spec: BoltSpec, grid: int = 12) -> BoltPattern:
    """Kama: T_req toplam kN, karelaj kamanın şev yüzündeki üçgen alanına yayılır."""
    geo = res.geometry
    warnings = []
    A_face = geo.areas["Face"]
    n_req, s_theo, s, cap = _design_spacing(T_req, A_face, spec, warnings)
    b = trend_plunge_vector(trend, plunge)
    A, B, C = geo.vertices["A"], geo.vertices["B"], geo.vertices["C"]
    exit_planes = [k for k in geo.faces if k != "Face"]
    free = []
    for u in np.linspace(0.05, 0.95, grid):
        for v in np.linspace(0.05, 0.95, grid):
            if u + v > 0.98:
                continue
            P = A + u * (B - A) + v * (C - A)
            ts = []
            for k in exit_planes:
                n = geo.normals[k]; P0 = geo.vertices[geo.faces[k][0]]
                den = n @ b
                if abs(den) > 1e-12:
                    t = (n @ (P0 - P)) / den
                    if t > 1e-9:
                        ts.append(t)
            if ts:
                free.append((float(np.linalg.norm(P - A)), float(min(ts))))
    if not free:
        raise ValueError(_tr("Bulon doğrultusu kamayı kesmiyor — yönü kontrol edin.",
                           "The bolt axis does not cross the wedge — check the direction."))
    fmax = max(f for _, f in free)
    free_sorted = sorted(free, key=lambda x: -x[1])[:6]
    Lb = spec.bond_length()
    total = np.ceil((fmax + Lb + spec.extra_length) / spec.step) * spec.step
    if total > 12:
        warnings.append(_tr(f"Bulon boyu {total:.1f} m > 12 m: öngermeli kablo ankraj daha uygun olabilir.",
                            f"Bolt length {total:.1f} m > 12 m: a pre-stressed cable anchor may be more "
                            f"suitable."))
    if s > 0.5 * total + 1e-9 and s > 1.5:
        warnings.append(_tr(f"Aralık ({s:.2f} m) bulon boyunun yarısından büyük; "
                          f"s ≤ L/2 ≈ {0.5 * total:.2f} m önerilir.",
                          f"The spacing ({s:.2f} m) exceeds half the bolt length; "
                          f"s ≤ L/2 ≈ {0.5 * total:.2f} m is recommended."))
    if plunge < 0:
        warnings.append(_tr("Bulon yukarı eğimli (plunge<0): harç/drenaj güçtür; uygulamada 5–15° aşağı "
                          "eğim tercih edilir.",
                          "The bolt points upward (plunge<0): grouting/drainage is difficult; 5–15° "
                          "downward is preferred in practice."))
    warnings.append(_tr("Serbest boylar kama yüzeyinde noktasal örneklemeyle bulundu; "
                      "'yüz konumu' A ucundan uzaklıktır.",
                      "Free lengths were sampled point-wise on the wedge face; 'face position' is the "
                      "distance from the apex A."))
    return BoltPattern(T_req, n_req, s, s_theo, A_face, free_sorted, fmax, Lb, total, cap, warnings, False)


# =========================================================================== #
#  SEÇİLEN KARELAJ + BOY İLE KAPASİTE / FS KONTROLÜ
# =========================================================================== #

STANDARD_LENGTHS = [3.0, 4.0, 5.0, 6.0, 8.0, 9.0, 10.0, 12.0, 15.0, 18.0, 20.0, 25.0]


def _bolt_capacity(free_len: float, L: float, spec: BoltSpec) -> Tuple[float, float]:
    """Verilen boyda bir bulonun etkin kapasitesi (kN) ve mevcut kök boyu (m)."""
    bond_avail = L - free_len - spec.extra_length
    if bond_avail <= 0:
        return 0.0, bond_avail
    d = spec.hole_diameter / 1000.0
    cap_bond = np.pi * d * spec.bond_strength * bond_avail / spec.fs_bond
    return float(min(spec.capacity, cap_bond)), bond_avail


@dataclass
class BoltCheck:
    spacing: float
    length: float
    rows: List[Tuple[float, float, float, float]]   # (yüz konumu, serbest boy, kök boyu, kapasite)
    n_bolts: float
    n_effective: float
    T_provided: float
    T_required: float
    fs: float
    target_fs: float
    per_metre: bool
    warnings: List[str]

    @property
    def ok(self) -> bool:
        return self.fs >= self.target_fs

    def summary(self) -> str:
        u = "kN/m" if self.per_metre else "kN"
        w = LABEL_WIDTH
        unit = _tr("adet/m", "bolts/m") if self.per_metre else _tr("adet", "bolts")
        verdict = _tr("UYGUN ✓", "ADEQUATE ✓") if self.ok else _tr("YETERSİZ ✗", "INADEQUATE ✗")
        L = ["=" * 62,
             "  " + _tr(f"SEÇİLEN TASARIM KONTROLÜ:  s = {self.spacing:.2f} m,  L = {self.length:.2f} m",
                      f"CHECK OF THE SELECTED DESIGN:  s = {self.spacing:.2f} m,  L = {self.length:.2f} m"),
             "=" * 62,
             f"{_tr('Bulon sayısı', 'Number of bolts'):<{w}}: {self.n_bolts:8.2f} {unit}  "
             f"({_tr('etkin', 'effective')}: {self.n_effective:.2f})",
             f"{_tr('Sağlanan kapasite', 'Capacity provided'):<{w}}: {self.T_provided:10.1f} {u}",
             f"{_tr('Gerekli kapasite', 'Capacity required'):<{w}}: {self.T_required:10.1f} {u}",
             f"{_tr('Kullanım oranı', 'Utilisation'):<{w}}: "
             f"{100 * self.T_provided / max(self.T_required, 1e-9):8.1f} %",
             f"{_tr('Elde edilen FS', 'Achieved FS'):<{w}}: {self.fs:10.3f}   "
             f"({_tr('hedef', 'target')} {self.target_fs:.2f})  → {verdict}",
             "-" * 62,
             _tr("Sıra bazında (yüz konumu | serbest | kök | kapasite/bulon):",
               "Per row (face position | free | bond | capacity/bolt):")]
        for pos, f, b, c in self.rows:
            flag = "" if c > 0 else _tr("  ← kayma yüzeyini geçmiyor", "  ← does not cross the sliding surface")
            L.append(f"   {pos:7.2f} m | {f:6.2f} m | {max(b, 0):5.2f} m | {c:7.1f} kN{flag}")
        L.append("=" * 62)
        L += [WARNING_PREFIX() + x for x in self.warnings]
        return "\n".join(L)


def _row_positions(L_face: float, s: float) -> np.ndarray:
    n = max(int(np.floor(L_face / s)), 1)
    return (np.arange(n) + 0.5) * s if n * s <= L_face else np.array([L_face / 2])


def bolt_check_planar(inp: PlanarInput, s: float, L: float, angle: float, spec: BoltSpec,
                      target_fs: float, passive: bool = False) -> BoltCheck:
    from copy import deepcopy
    base = deepcopy(inp); base.support_force = 0.0
    r0 = planar_analyze(base)
    pf, pp, th = map(np.radians, (inp.face_angle, inp.plane_angle, angle))
    y_top = r0.polygon[1][1]
    L_face = y_top / np.sin(pf)
    den = np.sin(th) + np.cos(th) * np.tan(pp)
    rows, T_tot, n_eff = [], 0.0, 0.0
    for pos in _row_positions(L_face, s):
        y = pos * np.sin(pf); x = y / np.tan(pf)
        free = (y - x * np.tan(pp)) / den if den > 1e-9 else np.inf
        cap, bond = _bolt_capacity(free, L, spec)
        rows.append((float(pos), float(free), float(bond), cap))
        T_tot += cap / s
        n_eff += (1.0 / s) if cap > 0 else 0.0
    T_req, _, _ = planar_required_support(inp, target_fs, angle, passive)
    chk = deepcopy(inp); chk.support_force = T_tot; chk.support_angle = angle; chk.support_passive = passive
    fs = planar_analyze(chk).factor_of_safety if T_tot > 0 else r0.factor_of_safety
    warnings = []
    if any(c == 0 for *_, c in rows):
        warnings.append(_tr("Bazı sıralarda bulon kayma yüzeyini geçmiyor: bu sıralar taşımaya katılmaz. "
                          "Boyu artırın ya da sıralara farklı boy verin.",
                          "In some rows the bolts do not cross the sliding surface: those rows carry no "
                          "load. Increase the length or use different lengths per row."))
    return BoltCheck(s, L, rows, len(rows) / s, n_eff, T_tot, max(T_req, 0.0), fs, target_fs, True, warnings)


def bolt_check_wedge(inp: WedgeInput, s: float, L: float, trend: float, plunge: float,
                     spec: BoltSpec, target_fs: float, passive: bool = False) -> BoltCheck:
    from copy import deepcopy
    base = deepcopy(inp); base.support = Support(0.0, trend, plunge, passive)
    geo = build_wedge(base)
    A, B, C = geo.vertices["A"], geo.vertices["B"], geo.vertices["C"]
    b = trend_plunge_vector(trend, plunge)
    nF = geo.normals["Face"]
    # yüz düzleminde gerçek karelaj: A orijin, e1 = AB yönü, e2 dik
    e1 = unit(B - A); e2 = unit(np.cross(nF, e1))
    P2 = np.array([[(V - A) @ e1, (V - A) @ e2] for V in (A, B, C)])
    umin, umax = P2[:, 0].min(), P2[:, 0].max(); vmin, vmax = P2[:, 1].min(), P2[:, 1].max()

    def sgn(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    def inside(p):
        d1, d2, d3 = sgn(p, P2[0], P2[1]), sgn(p, P2[1], P2[2]), sgn(p, P2[2], P2[0])
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

    exit_planes = [k for k in geo.faces if k != "Face"]
    rows, T_tot, n_eff, n = [], 0.0, 0, 0
    for uu in np.arange(umin + s / 2, umax, s):
        for vv in np.arange(vmin + s / 2, vmax, s):
            if not inside((uu, vv)):
                continue
            P = A + uu * e1 + vv * e2
            ts = []
            for k in exit_planes:
                nk = geo.normals[k]; P0 = geo.vertices[geo.faces[k][0]]
                dn = nk @ b
                if abs(dn) > 1e-12:
                    t = (nk @ (P0 - P)) / dn
                    if t > 1e-9:
                        ts.append(t)
            free = min(ts) if ts else np.inf
            cap, bond = _bolt_capacity(free, L, spec)
            rows.append((float(np.linalg.norm(P - A)), float(free), float(bond), cap))
            T_tot += cap; n += 1; n_eff += 1 if cap > 0 else 0
    if n == 0:
        raise ValueError(_tr(f"s = {s} m karelajı kama yüzeyine hiç bulon sığdırmıyor — aralığı küçültün.",
                           f"A spacing of s = {s} m fits no bolt on the wedge face — reduce the spacing."))
    sr = required_support(inp, target_fs, trend, plunge, passive)
    chk = deepcopy(inp); chk.support = Support(T_tot, trend, plunge, passive)
    fs = analyze(chk, geo).factor_of_safety if T_tot > 0 else analyze(base, geo).factor_of_safety
    rows = sorted(rows, key=lambda r: -r[1])[:10]
    warnings = [_tr("Sıra listesi serbest boya göre en uzun 10 bulon.",
                  "The row list shows the 10 bolts with the longest free length.")]
    if n_eff < n:
        warnings.append(_tr(f"{n - n_eff} bulon kayma yüzeyini geçmiyor (taşımaya katılmaz). Boyu artırın.",
                          f"{n - n_eff} bolts do not cross the sliding surface (they carry no load). "
                          f"Increase the length."))
    return BoltCheck(s, L, rows, n, n_eff, T_tot, sr.force if sr.achievable else np.nan, fs, target_fs, False, warnings)


def bolt_options_table(check_fn, spacings: List[float], lengths: List[float]) -> str:
    """check_fn(s, L) -> BoltCheck. Aralık × boy → FS tablosu (metin)."""
    hdr = "  s (m) \\ L (m) " + "".join(f"{L:8.1f}" for L in lengths)
    lines = [hdr, "-" * len(hdr)]
    best = None      # en geniş aralık, onun içinde en kısa boy
    for s in sorted(spacings):
        row = f"  {s:6.2f}        "
        for L in sorted(lengths):
            try:
                c = check_fn(s, L)
                fs = c.fs
                row += (f"{fs:7.2f}" if np.isfinite(fs) else "    inf") + ('*' if c.ok else ' ')
                if c.ok and (best is None or s > best[0]):
                    best = (s, L, fs)
            except Exception:
                row += "     -- "
        lines.append(row)
    lines.append("  " + _tr("(* : hedef FS sağlanıyor)", "(* : target FS is met)"))
    if best:
        lines.append("  " + _tr(f"ÖNERİ: en geniş karelajda en kısa boy → s = {best[0]:.2f} m, "
                              f"L = {best[1]:.1f} m (FS = {best[2]:.2f})",
                              f"RECOMMENDATION: shortest length at the widest spacing → s = {best[0]:.2f} m, "
                              f"L = {best[1]:.1f} m (FS = {best[2]:.2f})"))
    else:
        lines.append("  " + _tr("Hiçbir kombinasyon hedefi sağlamıyor: daha yüksek kapasiteli ankraj veya "
                             "daha sık aralık gerekir.",
                             "No combination meets the target: a higher-capacity anchor or a tighter "
                             "spacing is required."))
    return "\n".join(lines)


