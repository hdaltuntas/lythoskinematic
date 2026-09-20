"""rockslope.wedge — tetrahedral kama stabilitesi (Hoek & Bray vektörel yöntem, Swedge karşılığı)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

import numpy as np
from scipy.spatial import ConvexHull

from .core import *
from . import style

#  Girdi veri yapıları
# --------------------------------------------------------------------------- #

@dataclass
class Joint:
    dip: float
    dipdir: float
    cohesion: float = 0.0      # kPa
    friction: float = 30.0     # derece

    @property
    def normal(self):
        return plane_normal(self.dip, self.dipdir)


@dataclass
class Plane:
    dip: float
    dipdir: float

    @property
    def normal(self):
        return plane_normal(self.dip, self.dipdir)


@dataclass
class TensionCrack:
    dip: float
    dipdir: float
    distance_from_crest: float   # üst şev yüzeyi boyunca, tepeden içeri (m)


@dataclass
class Water:
    """
    mode:
      'dry'      : su yok
      'filled'   : Hoek & Bray dolu çatlak — düzlem ortalama basıncı = gw*Hw/6
      'percent'  : 'filled' basıncının percent/100 katı
      'custom'   : her düzleme sabit basınç (u1, u2, ut) [kPa]
    """
    mode: str = "dry"
    gamma_w: float = 9.81
    percent: float = 100.0
    u1: float = 0.0
    u2: float = 0.0
    ut: float = 0.0


@dataclass
class Seismic:
    coefficient: float = 0.0   # a_h (W'nin katı)
    trend: Optional[float] = None   # None -> şev yüzü eğim yönü (yatay)
    plunge: float = 0.0


@dataclass
class Support:
    force: float = 0.0        # kN (toplam)
    trend: float = 0.0        # bulon ekseninin yönü (kayaya doğru)
    plunge: float = 0.0       # + aşağı, - yukarı
    passive: bool = False     # False: aktif, True: pasif

    @property
    def vector(self):
        return self.force * trend_plunge_vector(self.trend, self.plunge)


@dataclass
class WedgeInput:
    joint1: Joint
    joint2: Joint
    slope_face: Plane
    upper_slope: Plane
    slope_height: float
    unit_weight: float = 26.0
    tension_crack: Optional[TensionCrack] = None
    water: Water = field(default_factory=Water)
    seismic: Seismic = field(default_factory=Seismic)
    support: Support = field(default_factory=Support)
    # Kama ölçekleme (Swedge "Scale wedge by"):
    #   'height'       : şev yüksekliği = slope_height (varsayılan, maksimum kama)
    #   'crest_length' : tepe boyunca kama uzunluğu |BC| = scale_value (m)
    #   'bench_width'  : tepeden apeks D'ye yatay dik mesafe = scale_value (m)
    #   'volume'       : kama hacmi = scale_value (m³)
    #   'weight'       : kama ağırlığı = scale_value (kN)
    scale_mode: str = "height"
    scale_value: Optional[float] = None


# --------------------------------------------------------------------------- #
#  Kama geometrisi
# --------------------------------------------------------------------------- #

@dataclass
class WedgeGeometry:
    vertices: Dict[str, np.ndarray]
    faces: Dict[str, List[str]]          # düzlem adı -> köşe adları
    normals: Dict[str, np.ndarray]       # kamaya DOĞRU bakan normaller
    areas: Dict[str, float]
    volume: float
    centroid: np.ndarray
    intersection_dir: np.ndarray         # J1∩J2 çizgisi, şev yüzüne (dışarı, aşağı) doğru
    height: float                        # kama toplam düşey yüksekliği
    tension_crack_used: bool
    warnings: List[str]
    crest_length: float = 0.0            # |BC|
    bench_width: float = 0.0             # tepeden D'ye yatay dik mesafe
    slope_height_eff: float = 0.0        # ölçekleme sonrası etkin şev yüksekliği
    scale_factor: float = 1.0


def build_wedge(inp: WedgeInput) -> WedgeGeometry:
    H = inp.slope_height
    n1, n2 = inp.joint1.normal, inp.joint2.normal
    nF, nU = inp.slope_face.normal, inp.upper_slope.normal
    warnings: List[str] = []

    # --- Ön kontrol: paralel / çakışık düzlemler ---
    names = {"Eklem 1": n1, "Eklem 2": n2, "Şev yüzü": nF, "Üst şev": nU}
    items = list(names.items())
    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            (na_, va), (nb_, vb) = items[a], items[b]
            ang = np.degrees(np.arccos(np.clip(abs(va @ vb), 0, 1)))
            if ang < 0.5:
                raise ValueError(
                    f"{na_} ile {nb_} paralel (aralarındaki açı {ang:.2f}°) — kama oluşmaz.\n"
                    f"İki eklem birbirini VE şev yüzünü kesmeli; şev yüzü ile üst şev farklı eğimde olmalı.\n"
                    f"Eklem şev yüzüne paralelse bu bir düzlemsel (planar) kayma problemidir, kama analizi değil.")
    if H <= 0:
        raise ValueError("Şev yüksekliği pozitif olmalı.")

    # Tepe (crest) çizgisi orijin O=(0,0,H)'den geçer; A (kama ucu) şev yüzünde z=0
    O = np.array([0.0, 0.0, H])
    dF = down_dip_vector(inp.slope_face.dip, inp.slope_face.dipdir)
    A = O + dF * (H / np.sin(np.radians(inp.slope_face.dip)))

    crest_dir = np.cross(nF, nU)
    if np.linalg.norm(crest_dir) < 1e-9:
        raise ValueError("Şev yüzü ve üst şev paralel — tepe çizgisi tanımsız.")

    # Kesişim çizgisi (J1∩J2)
    i = np.cross(n1, n2)
    if np.linalg.norm(i) < 1e-9:
        raise ValueError("Eklem düzlemleri paralel.")
    i = unit(i)
    if i[2] > 0:
        i = -i   # aşağı yönlü

    # Kesişim çizgisi şev yüzünden dışarı (boşluğa) bakmalı: günışığı koşulu
    tr_i, pl_i = vector_to_trend_plunge(i)
    if pl_i >= inp.slope_face.dip - 1e-6:
        raise ValueError(
            f"Kesişim çizgisinin plunge'ı ({pl_i:.0f}°) şev yüzü eğiminden ({inp.slope_face.dip:.0f}°) "
            f"büyük — çizgi şev yüzünü kesmiyor, kama oluşmaz.")

    if nF @ i <= 1e-9:
        raise ValueError(
            f"Eklem kesişim çizgisi (trend {tr_i:.0f}°, plunge {pl_i:.0f}°) şevin içine doğru dalıyor — "
            f"şev yüzünde (eğim yönü {inp.slope_face.dipdir:.0f}°) gün ışığına çıkmıyor, kama kayamaz.")
    def _tri(name, a, pa, b, pb, c, pc):
        try:
            return intersect_3_planes(a, pa, b, pb, c, pc)
        except ValueError:
            raise ValueError(f"{name} tek noktada kesişmiyor — düzlemlerden ikisinin doğrultusu "
                             f"(strike) aynı ya da bir düzlem diğer ikisinin kesişim çizgisine paralel. "
                             f"Eklem doğrultularını şev doğrultusundan farklı verin.")

    B = _tri("Eklem 1, şev yüzü ve üst şev", n1, A, nF, O, nU, O)   # J1 ∩ yüz ∩ üst
    C = _tri("Eklem 2, şev yüzü ve üst şev", n2, A, nF, O, nU, O)   # J2 ∩ yüz ∩ üst
    D = _tri("Eklem 1, Eklem 2 ve üst şev", n1, A, n2, A, nU, O)    # J1 ∩ J2 ∩ üst

    # --- Kinematik geçerlilik kontrolleri ---
    if nF @ (D - O) > 1e-9:
        tr, pl = vector_to_trend_plunge(i)
        raise ValueError(f"Kesişim çizgisi (trend {tr:.0f}°, plunge {pl:.0f}°) şev yüzünde gün ışığına "
                         f"çıkmıyor — kama şev içinde kalıyor, kinematik olarak kayamaz.\n"
                         f"Kesişim çizgisi şev yüzü eğim yönüne bakmalı ve plunge'ı şev açısından küçük olmalı.")
    if D[2] < A[2]:
        raise ValueError("Kesişim çizgisi şev yüzünden içeri doğru yükseliyor — kama oluşmuyor.")
    G0 = (A + B + C + D) / 4.0
    if n1 @ (G0 - A) < 0 or n2 @ (G0 - A) < 0:
        raise ValueError("Eklem düzlemleri şev yüzünü kesiyor ama aralarında kalan blok şev dışına "
                         "çıkmıyor (kama düzlemlerin altında kalıyor) — geometri geçersiz.")

    # --- Boyutlar ve ölçekleme ---
    c_hat = unit(crest_dir)
    c_h = np.array([c_hat[0], c_hat[1], 0.0])
    c_h = unit(c_h) if np.linalg.norm(c_h) > 1e-9 else c_hat

    def _dims(B_, C_, D_, O_):
        w = D_ - O_
        w = w - (w @ c_h) * c_h
        return float(np.linalg.norm(B_ - C_)), float(np.hypot(w[0], w[1]))

    crest_len, bench = _dims(B, C, D, O)
    vol0 = abs(np.dot(B - A, np.cross(C - A, D - A))) / 6.0
    lam = 1.0
    if inp.scale_mode != "height":
        if inp.scale_value is None or inp.scale_value <= 0:
            raise ValueError("Ölçekleme değeri (scale_value) pozitif olmalı.")
        sv = inp.scale_value
        if inp.scale_mode == "crest_length":
            lam = sv / crest_len
        elif inp.scale_mode == "bench_width":
            lam = sv / bench
        elif inp.scale_mode == "volume":
            lam = (sv / vol0) ** (1 / 3)
        elif inp.scale_mode == "weight":
            lam = (sv / (inp.unit_weight * vol0)) ** (1 / 3)
        else:
            raise ValueError(f"Bilinmeyen ölçekleme modu: {inp.scale_mode}")
        B = A + lam * (B - A); C = A + lam * (C - A); D = A + lam * (D - A)
        O = A + lam * (O - A)
        crest_len, bench = _dims(B, C, D, O)
    slope_h_eff = float(lam * H)
    if crest_len > 20 * slope_h_eff:
        warnings.append(f"Kama tepe boyunca çok uzun ({crest_len:.0f} m, şev yüksekliğinin "
                        f"{crest_len / slope_h_eff:.0f} katı): eklem doğrultusu şev yüzüne "
                        f"neredeyse paralel. Tepe uzunluğu / basamak genişliği ile ölçeklemeyi düşünün.")

    verts = {"A": A, "B": B, "C": C, "D": D}
    faces = {"J1": ["A", "B", "D"], "J2": ["A", "C", "D"],
             "Face": ["A", "B", "C"], "Upper": ["B", "C", "D"]}
    tc_used = False

    # --- Çekme çatlağı ---
    if inp.tension_crack is not None:
        tc = inp.tension_crack
        nT = tc.normal if hasattr(tc, "normal") else plane_normal(tc.dip, tc.dipdir)
        # D'nin tepe çizgisine dik izdüşümü
        Oc = O + c_hat * ((D - O) @ c_hat)
        # üst şev yüzeyinde, tepe çizgisine dik, yüzden uzaklaşan yön
        e = unit(np.cross(nU, c_hat))
        if e @ (D - Oc) < 0:
            e = -e
        P_T = Oc + e * tc.distance_from_crest

        def cut(P, Q):
            """P->Q doğru parçasının T düzlemiyle kesişim parametresi."""
            den = nT @ (Q - P)
            if abs(den) < 1e-12:
                return None
            return (nT @ (P_T - P)) / den

        tAD, tBD, tCD = cut(A, D), cut(B, D), cut(C, D)
        ok = all(t is not None and 0.0 < t < 1.0 for t in (tAD, tBD, tCD))
        if ok:
            G = A + tAD * (D - A)
            E = B + tBD * (D - B)
            F = C + tCD * (D - C)
            verts = {"A": A, "B": B, "C": C, "E": E, "F": F, "G": G}
            faces = {"J1": ["A", "B", "E", "G"], "J2": ["A", "C", "F", "G"],
                     "Face": ["A", "B", "C"], "Upper": ["B", "C", "F", "E"],
                     "TC": ["E", "F", "G"]}
            tc_used = True
        else:
            warnings.append("Çekme çatlağı kamayı kesmiyor (mesafe/yönelim uygun değil) — ihmal edildi.")

    P = np.array(list(verts.values()))
    hull = ConvexHull(P)
    volume = float(hull.volume)
    centroid = P.mean(axis=0)  # dışbükey tetra/pentahedron için hacim ağırlıklı merkez:
    # Daha doğru merkez: hull üçgenlerini tetrahedra'ya böl
    cen = np.zeros(3); vol = 0.0
    ref = P.mean(axis=0)
    for simplex in hull.simplices:
        a, b, c = P[simplex]
        v = abs(np.dot(a - ref, np.cross(b - ref, c - ref))) / 6.0
        cen += v * (a + b + c + ref) / 4.0
        vol += v
    centroid = cen / vol

    raw_normals = {"J1": n1, "J2": n2, "Face": nF, "Upper": nU}
    if tc_used:
        raw_normals["TC"] = plane_normal(inp.tension_crack.dip, inp.tension_crack.dipdir)

    normals, areas = {}, {}
    for name, vnames in faces.items():
        pts = [verts[v] for v in vnames]
        n = raw_normals[name]
        if n @ (centroid - pts[0]) < 0:   # normal kamaya doğru baksın
            n = -n
        normals[name] = n
        areas[name] = polygon_area(pts, n)

    zs = P[:, 2]
    height = float(zs.max() - zs.min())

    return WedgeGeometry(verts, faces, normals, areas, volume, centroid,
                         i, height, tc_used, warnings, crest_len, bench, slope_h_eff, lam)


# --------------------------------------------------------------------------- #
#  Stabilite analizi
# --------------------------------------------------------------------------- #

@dataclass
class WedgeResult:
    factor_of_safety: float
    mode: str
    weight: float
    volume: float
    normal_forces: Dict[str, float]
    driving_force: float
    resisting_force: float
    sliding_direction: Tuple[float, float]       # trend, plunge
    intersection_line: Tuple[float, float]       # trend, plunge
    water_forces: Dict[str, float]
    seismic_force: float
    support_force: float
    areas: Dict[str, float]
    geometry: WedgeGeometry
    warnings: List[str]

    def summary(self) -> str:
        g = self.geometry
        L = []
        L.append("=" * 62)
        L.append("  KAMA STABİLİTE ANALİZİ  (Hoek & Bray vektörel yöntem)")
        L.append("=" * 62)
        L.append(f"Kama hacmi            : {self.volume:10.3f} m³")
        L.append(f"Kama ağırlığı         : {self.weight:10.2f} kN")
        L.append(f"Kama yüksekliği       : {g.height:10.3f} m")
        L.append(f"Etkin şev yüksekliği  : {g.slope_height_eff:10.3f} m  (ölçek λ = {g.scale_factor:.3f})")
        L.append(f"Tepe uzunluğu |BC|    : {g.crest_length:10.3f} m")
        L.append(f"Basamak genişliği     : {g.bench_width:10.3f} m")
        L.append(f"Çekme çatlağı         : {'Var' if g.tension_crack_used else 'Yok'}")
        L.append(f"Kesişim (J1∩J2)       : trend {self.intersection_line[0]:6.1f}°, "
                 f"plunge {self.intersection_line[1]:5.1f}°")
        L.append("-" * 62)
        for k, a in self.areas.items():
            L.append(f"Alan {k:<6}           : {a:10.3f} m²")
        L.append("-" * 62)
        for k, u in self.water_forces.items():
            L.append(f"Su kuvveti {k:<6}     : {u:10.2f} kN")
        L.append(f"Sismik kuvvet         : {self.seismic_force:10.2f} kN")
        L.append(f"Destek kuvveti        : {self.support_force:10.2f} kN")
        L.append("-" * 62)
        L.append(f"Göçme modu            : {self.mode}")
        for k, n in self.normal_forces.items():
            L.append(f"Normal kuvvet {k:<6}  : {n:10.2f} kN")
        L.append(f"Kaydırıcı kuvvet      : {self.driving_force:10.2f} kN")
        L.append(f"Direnç kuvveti        : {self.resisting_force:10.2f} kN")
        L.append(f"Kayma yönü            : trend {self.sliding_direction[0]:6.1f}°, "
                 f"plunge {self.sliding_direction[1]:5.1f}°")
        L.append("=" * 62)
        fs = self.factor_of_safety
        L.append(f"GÜVENLİK SAYISI (FS)  : {'∞ (stabil)' if np.isinf(fs) else f'{fs:.3f}'}")
        L.append("=" * 62)
        for w in self.warnings:
            L.append("UYARI: " + w)
        return "\n".join(L)


def _water_pressures(inp: WedgeInput, geo: WedgeGeometry) -> Dict[str, float]:
    w = inp.water
    names = ["J1", "J2"] + (["TC"] if geo.tension_crack_used else [])
    if w.mode == "dry":
        return {k: 0.0 for k in names}
    if w.mode == "custom":
        return {"J1": w.u1, "J2": w.u2, **({"TC": w.ut} if geo.tension_crack_used else {})}
    # Hoek & Bray: yüzeylerde sıfır, kesişim çizgisi ortasında max = gw*Hw/2,
    # üçgen düzlemde ortalama = gw*Hw/6
    Hw = geo.height
    u = w.gamma_w * Hw / 6.0
    if w.mode == "percent":
        u *= w.percent / 100.0
    elif w.mode != "filled":
        raise ValueError(f"Bilinmeyen su modu: {w.mode}")
    return {k: u for k in names}


def analyze(inp: WedgeInput, geo: Optional[WedgeGeometry] = None) -> WedgeResult:
    geo = geo or build_wedge(inp)
    warnings = list(geo.warnings)
    J1, J2 = inp.joint1, inp.joint2
    n1, n2 = geo.normals["J1"], geo.normals["J2"]
    A1, A2 = geo.areas["J1"], geo.areas["J2"]
    tan1, tan2 = np.tan(np.radians(J1.friction)), np.tan(np.radians(J2.friction))

    # --- Kuvvetler ---
    W = inp.unit_weight * geo.volume
    Wv = np.array([0.0, 0.0, -W])

    press = _water_pressures(inp, geo)
    water_forces, Uv = {}, np.zeros(3)
    for k, u in press.items():
        f = u * geo.areas[k]
        water_forces[k] = f
        Uv += f * geo.normals[k]          # su kamayı düzlemden iter (kamaya doğru normal)

    s = inp.seismic
    Fs = s.coefficient * W
    if Fs > 0:
        tr = inp.slope_face.dipdir if s.trend is None else s.trend
        Sv = Fs * trend_plunge_vector(tr, s.plunge)
    else:
        Sv = np.zeros(3)

    Tv = inp.support.vector if inp.support.force > 0 else np.zeros(3)
    passive = inp.support.passive

    R = Wv + Uv + Sv + (np.zeros(3) if passive else Tv)   # aktif destek R'ye girer

    # --- Göçme modu ---
    s12 = unit(geo.intersection_dir)               # aşağı, dışarı (A yönü)
    M = np.column_stack([n1, n2, -s12])
    N1, N2, S = np.linalg.solve(M, -R)             # R + N1 n1 + N2 n2 - S s = 0
    dN1 = dN2 = dS = 0.0
    if passive and inp.support.force > 0:
        dN1, dN2, dS = np.linalg.solve(M, -Tv)

    normal_forces: Dict[str, float] = {}
    if N1 > 0 and N2 > 0:
        mode = "İki düzlemde kayma (J1 ∩ J2 boyunca)"
        slide = s12
        driving = S
        resisting = N1 * tan1 + N2 * tan2 + J1.cohesion * A1 + J2.cohesion * A2
        if passive:
            resisting += dN1 * tan1 + dN2 * tan2 - dS
        normal_forces = {"J1": N1, "J2": N2}
    else:
        # Tek düzlemde kayma adayları
        def single(n, tanphi, coh, area, name):
            Nn = -(R @ n)
            if Nn <= 0:
                return None
            t = R - (R @ n) * n
            if np.linalg.norm(t) < 1e-9:
                return (name, n, Nn, 0.0, coh * area + Nn * tanphi, np.zeros(3))
            sd = unit(t)
            drv = float(np.linalg.norm(t))
            res = Nn * tanphi + coh * area
            if passive and inp.support.force > 0:
                dNn = -(Tv @ n)
                res += dNn * tanphi - (Tv @ sd)
            return (name, n, Nn, drv, res, sd)

        cands = []
        if N1 <= 0:     # J1 ile temas kaybı -> J2 üzerinde kayma
            c = single(n2, tan2, J2.cohesion, A2, "J2")
            if c and (c[5] @ n1) >= -1e-9:   # J1'den uzaklaşıyor olmalı
                cands.append(c)
        if N2 <= 0:
            c = single(n1, tan1, J1.cohesion, A1, "J1")
            if c and (c[5] @ n2) >= -1e-9:
                cands.append(c)

        if not cands:
            # her iki düzlemden ayrılma
            if R[2] < 0:
                mode = "Düşme / her iki düzlemden ayrılma"
                return WedgeResult(0.0, mode, W, geo.volume, {}, 0.0, 0.0,
                                   vector_to_trend_plunge(R),
                                   vector_to_trend_plunge(s12), water_forces, Fs,
                                   inp.support.force, geo.areas, geo, warnings)
            mode = "Stabil (bileşke kayaya doğru)"
            return WedgeResult(np.inf, mode, W, geo.volume, {}, 0.0, 0.0,
                               (0.0, 0.0), vector_to_trend_plunge(s12), water_forces,
                               Fs, inp.support.force, geo.areas, geo, warnings)

        name, n, Nn, driving, resisting, slide = min(cands, key=lambda c: c[4] / max(c[3], 1e-12))
        mode = f"Tek düzlemde kayma ({name} üzerinde, {'J1' if name == 'J2' else 'J2'} temas kaybı)"
        normal_forces = {name: Nn}

    if driving <= 1e-9:
        fs = np.inf
        mode += " — kaydırıcı kuvvet yok"
    else:
        fs = resisting / driving

    return WedgeResult(float(fs), mode, W, geo.volume, normal_forces, float(driving),
                       float(resisting), vector_to_trend_plunge(slide),
                       vector_to_trend_plunge(s12), water_forces, Fs,
                       inp.support.force, geo.areas, geo, warnings)


@dataclass
class SupportResult:
    force: float                 # kN (NaN: hedef ulaşılamıyor)
    trend: float
    plunge: float
    passive: bool
    fs_achieved: float
    weight: float
    achievable: bool
    fs_initial: float = np.nan
    target_fs: float = np.nan

    @property
    def ratio(self) -> float:
        return self.force / self.weight

    def summary(self) -> str:
        if self.achievable and self.force == 0.0:
            return (f"Destek gerekmiyor: mevcut FS = {self.fs_initial:.3f} zaten hedef "
                    f"FS = {self.target_fs:.2f} değerini sağlıyor. Kuvvet hesaplamak için "
                    f"daha yüksek bir hedef FS girin.")
        if not self.achievable:
            return (f"Hedef FS bu bulon yönüyle (trend {self.trend:.0f}°, plunge {self.plunge:.0f}°) "
                    f"ulaşılamıyor — kuvvet kamayı kaydırıyor veya kilitlemiyor. "
                    f"Optimum yön için trend/plunge boş bırakın.")
        return (f"Mevcut FS = {self.fs_initial:.3f}  →  hedef FS = {self.target_fs:.2f}\n"
                f"Gerekli destek: {self.force:,.0f} kN  (kama ağırlığının %{100*self.ratio:.1f}'i)\n"
                f"Yön: trend {self.trend:.1f}°, plunge {self.plunge:.1f}°  "
                f"({'pasif' if self.passive else 'aktif'}), sağlanan FS = {self.fs_achieved:.3f}")


def optimum_support_direction(inp: WedgeInput, passive: bool = False,
                              geo: Optional[WedgeGeometry] = None) -> Tuple[float, float]:
    """
    Birim destek kuvveti başına en fazla FS artışını veren yön (trend, plunge).
    Kayma yönünün tersi etrafında ±90° trend, ±80° plunge taraması.
    """
    from copy import deepcopy
    geo = geo or build_wedge(inp)
    base = deepcopy(inp); base.support = Support(0.0)
    r0 = analyze(base, geo)
    tr0 = (r0.sliding_direction[0] + 180.0) % 360.0
    T = 0.05 * r0.weight
    best, best_fs = (tr0, 0.0), -np.inf
    for dtr in np.arange(-90, 91, 5):
        for pl in np.arange(-80, 81, 5):
            base.support = Support(T, (tr0 + dtr) % 360, pl, passive)
            fs = analyze(base, geo).factor_of_safety
            if fs > best_fs:
                best_fs, best = fs, ((tr0 + dtr) % 360.0, float(pl))
    return best


def required_support(inp: WedgeInput, target_fs: float, trend: Optional[float] = None,
                     plunge: Optional[float] = None, passive: bool = False,
                     max_ratio: float = 3.0) -> SupportResult:
    """
    Hedef GS'yi sağlayan minimum destek kuvveti.
    trend/plunge verilmezse optimum yön otomatik seçilir.
    max_ratio: aranan en büyük kuvvet, kama ağırlığının katı olarak.
    FS(T) tekdüze olmayabilir (göçme modu değişebilir); bu yüzden önce tarama,
    sonra köklü aralıkta ikiye bölme yapılır.
    """
    from copy import deepcopy
    geo = build_wedge(inp)
    if trend is None or plunge is None:
        trend, plunge = optimum_support_direction(inp, passive, geo)
    base = deepcopy(inp)
    base.support = Support(0.0, trend, plunge, passive)
    W = inp.unit_weight * geo.volume

    def fs_at(T):
        base.support.force = T
        return analyze(base, geo).factor_of_safety

    fs0 = fs_at(0.0)
    if fs0 >= target_fs:
        return SupportResult(0.0, trend, plunge, passive, fs0, W, True, fs0, target_fs)

    # kaba tarama: ağırlığın %0.5'inden max_ratio'ya kadar
    grid = np.concatenate([[0.0], np.geomspace(0.005 * W, max_ratio * W, 120)])
    lo = hi = None
    prev = 0.0
    for T in grid[1:]:
        if fs_at(T) >= target_fs:
            lo, hi = prev, T
            break
        prev = T
    if hi is None:
        return SupportResult(np.nan, trend, plunge, passive, fs_at(max_ratio * W), W, False, fs0, target_fs)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if fs_at(mid) >= target_fs:
            hi = mid
        else:
            lo = mid
    return SupportResult(hi, trend, plunge, passive, fs_at(hi), W, True, fs0, target_fs)


def hoek_bray_short(inp: WedgeInput, geo: Optional[WedgeGeometry] = None) -> float:
    """
    Hoek & Bray kapalı-form kısa çözüm (çekme çatlağı yok, su: dolu çatlak veya kuru).
    Bağımsız doğrulama amaçlı. H = kama toplam düşey yüksekliği.
    """
    geo = geo or build_wedge(inp)
    na, nb = inp.joint1.normal, inp.joint2.normal
    nf, ns = inp.slope_face.normal, inp.upper_slope.normal
    l1, l2 = np.cross(na, nf), np.cross(nb, nf)
    l3, l4 = np.cross(na, ns), np.cross(nb, ns)
    l5 = np.cross(na, nb)

    def sin_between(u, v):
        return np.linalg.norm(np.cross(unit(u), unit(v)))

    def cos_between(u, v):
        return abs(np.dot(unit(u), unit(v)))

    psi5 = np.radians(abs(vector_to_trend_plunge(l5)[1]))
    cnn = np.dot(unit(na), unit(nb))          # işaretli!
    snn2 = 1.0 - cnn ** 2
    pa, pb = np.radians(inp.joint1.dip), np.radians(inp.joint2.dip)
    X = sin_between(l2, l4) / (sin_between(l4, l5) * cos_between(l2, na))
    Y = sin_between(l1, l3) / (sin_between(l3, l5) * cos_between(l1, nb))
    A = (np.cos(pa) - np.cos(pb) * cnn) / (np.sin(psi5) * snn2)
    B = (np.cos(pb) - np.cos(pa) * cnn) / (np.sin(psi5) * snn2)
    g, H = inp.unit_weight, geo.height
    gw = inp.water.gamma_w if inp.water.mode == "filled" else 0.0
    ta, tb = np.tan(np.radians(inp.joint1.friction)), np.tan(np.radians(inp.joint2.friction))
    return (3.0 / (g * H) * (inp.joint1.cohesion * X + inp.joint2.cohesion * Y)
            + (A - gw / (2 * g) * X) * ta + (B - gw / (2 * g) * Y) * tb)


# --------------------------------------------------------------------------- #
#  Stereonet (alt yarımküre)
# --------------------------------------------------------------------------- #

def _stereo_xy(v: np.ndarray, equal_area: bool = True) -> Tuple[float, float]:
    """Alt yarımküre çizgi vektörü -> stereonet (x, y)."""
    tr, pl = vector_to_trend_plunge(v)
    pl = max(pl, 0.0)
    theta = np.radians(90.0 - pl) / 2.0
    r = np.sqrt(2) * np.sin(theta) if equal_area else np.tan(theta)
    r /= (np.sqrt(2) if equal_area else 1.0)   # birim daireye normalize
    return r * np.sin(np.radians(tr)), r * np.cos(np.radians(tr))


def _great_circle(dip: float, dipdir: float, equal_area: bool = True, n: int = 181):
    d = down_dip_vector(dip, dipdir)
    strike = np.array([np.sin(np.radians(dipdir + 90)), np.cos(np.radians(dipdir + 90)), 0.0])
    xs, ys = [], []
    for t in np.linspace(0, np.pi, n):
        v = np.cos(t) * strike + np.sin(t) * d
        x, y = _stereo_xy(v, equal_area)
        xs.append(x); ys.append(y)
    return xs, ys




# --------------------------------------------------------------------------- #
#  Görselleştirme (rapor kalitesi)
# --------------------------------------------------------------------------- #

def plot_wedge(res: WedgeResult, show: bool = True, savepath: Optional[str] = None, fig=None):
    """3D kama: yüzeyler renk kodlu, kayma yönü oku, sonuç kutusu."""
    import matplotlib
    if not show and fig is None:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    style.apply_style()
    geo = res.geometry
    colors = {"J1": style.J1, "J2": style.J2, "Face": style.FACE, "Upper": style.UPPER, "TC": style.TC}
    labels = {"J1": "Eklem 1", "J2": "Eklem 2", "Face": "Şev yüzü", "Upper": "Üst şev", "TC": "Çekme çatlağı"}
    if fig is None:
        fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")
    for name, vnames in geo.faces.items():
        pts = np.array([geo.vertices[v] for v in vnames])
        c = pts.mean(axis=0); n = geo.normals[name]
        e1 = unit(np.cross(n, [0, 0, 1.0]) if abs(n[2]) < 0.99 else np.cross(n, [1.0, 0, 0]))
        e2 = np.cross(n, e1)
        ang = np.arctan2((pts - c) @ e2, (pts - c) @ e1)
        pts = pts[np.argsort(ang)]
        ax.add_collection3d(Poly3DCollection([pts], alpha=0.55, facecolor=colors[name], edgecolor="k", linewidths=0.8))
    for k, p in geo.vertices.items():
        ax.text(*p, f" {k}", fontsize=9, color=style.NAVY, fontweight="bold")
    if res.driving_force > 0:
        d = trend_plunge_vector(*res.sliding_direction) * geo.height * 0.45
        ax.quiver(*geo.centroid, *d, color="k", arrow_length_ratio=0.18, linewidth=2.2)
        ax.text(*(geo.centroid + d), "  kayma yönü", fontsize=8)
    P = np.array(list(geo.vertices.values()))
    mn, mx = P.min(axis=0), P.max(axis=0); span = (mx - mn).max(); mid = (mn + mx) / 2
    ax.set_xlim(mid[0] - span / 2, mid[0] + span / 2); ax.set_ylim(mid[1] - span / 2, mid[1] + span / 2)
    ax.set_zlim(mid[2] - span / 2, mid[2] + span / 2)
    ax.set_xlabel("Doğu (m)"); ax.set_ylabel("Kuzey (m)"); ax.set_zlabel("Kot (m)")
    ax.view_init(elev=22, azim=-135)
    ax.xaxis.pane.set_facecolor(style.LIGHT); ax.yaxis.pane.set_facecolor(style.LIGHT); ax.zaxis.pane.set_facecolor("white")
    ax.set_title(f"Kama geometrisi ve göçme modu", loc="left", color=style.NAVY, fontweight="bold")
    handles = [plt.Rectangle((0, 0), 1, 1, fc=colors[k], alpha=0.6, ec="k") for k in geo.faces]
    ax.legend(handles, [labels[k] for k in geo.faces], loc="upper left", fontsize=8)
    tr, pl = res.intersection_line
    ax.text2D(0.99, 0.98, f"FS = {style.fs_text(res.factor_of_safety)}\n{res.mode}\n"
              f"V = {res.volume:,.0f} m³   W = {res.weight:,.0f} kN\nJ1∩J2: {tr:.0f}°/{pl:.0f}°",
              transform=ax.transAxes, ha="right", va="top", fontsize=8.5, family="monospace",
              bbox=dict(boxstyle="round,pad=0.5", fc="white", ec=style.NAVY))
    if savepath:
        fig.savefig(savepath)
    if show:
        plt.show()
    return fig


def plot_stereonet(inp: WedgeInput, geo: Optional[WedgeGeometry] = None, equal_area: bool = True,
                   ax=None, show: bool = True, savepath: Optional[str] = None, res: Optional[WedgeResult] = None):
    """Alt yarımküre stereonet: büyük daireler, kutuplar, kesişim, sürtünme konisi, kama günışığı bölgesi."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon
    style.apply_style()
    if ax is None:
        fig, ax = plt.subplots(figsize=(7.2, 7.2))
    else:
        fig = ax.figure
    ax.grid(False)
    # ağ: 10° plunge daireleri ve trend ışınları (hafif)
    for pl in range(10, 90, 10):
        xs, ys = zip(*[_stereo_xy(trend_plunge_vector(t, pl), equal_area) for t in np.linspace(0, 360, 181)])
        ax.plot(xs, ys, color="#e2e6ea", lw=0.5, zorder=1)
    for t in range(0, 360, 30):
        x, y = _stereo_xy(trend_plunge_vector(t, 0.0), equal_area)
        ax.plot([0, x], [0, y], color="#e2e6ea", lw=0.5, zorder=1)
        if t % 90:
            ax.text(1.06 * x, 1.06 * y, f"{t}°", fontsize=6.5, color=style.GREY, ha="center", va="center")
    ax.add_patch(Circle((0, 0), 1, fill=False, lw=1.4, color=style.NAVY, zorder=3))
    for lab, (x, y) in {"K": (0, 1.10), "D": (1.10, 0), "G": (0, -1.10), "B": (-1.10, 0)}.items():
        ax.text(x, y, lab, ha="center", va="center", fontsize=10, fontweight="bold", color=style.NAVY)

    # kama günışığı bölgesi: sürtünme konisi dışı ∩ şev yüzü dairesi içi (kabaca gölgele)
    phi = 0.5 * (inp.joint1.friction + inp.joint2.friction)
    nf = plane_normal(inp.slope_face.dip, inp.slope_face.dipdir)
    pts = []
    for t in np.linspace(0, 360, 361):
        for pl in np.linspace(phi, 89.5, 40):
            v = trend_plunge_vector(t, pl)
            if nf @ v > 0 and pl < inp.slope_face.dip:
                pts.append(_stereo_xy(v, equal_area))
    if pts:
        ax.scatter(*zip(*pts), s=3, color="#f9d6d5", zorder=2, linewidths=0)

    planes = [("Eklem 1", inp.joint1.dip, inp.joint1.dipdir, style.J1, "-"),
              ("Eklem 2", inp.joint2.dip, inp.joint2.dipdir, style.J2, "-"),
              ("Şev yüzü", inp.slope_face.dip, inp.slope_face.dipdir, "k", "-"),
              ("Üst şev", inp.upper_slope.dip, inp.upper_slope.dipdir, style.UPPER, "--")]
    if inp.tension_crack is not None:
        tc = inp.tension_crack
        planes.append(("Çekme çatlağı", tc.dip, tc.dipdir, style.TC, "-."))
    for name, dip, dd, col, ls in planes:
        xs, ys = _great_circle(dip, dd, equal_area)
        ax.plot(xs, ys, color=col, lw=1.9, ls=ls, label=f"{name}  {dip:.0f}/{dd:03.0f}", zorder=5)
        px, py = _stereo_xy(-plane_normal(dip, dd), equal_area)
        ax.plot(px, py, "o", color=col, ms=5, mec="white", mew=0.8, zorder=6)
    geo = geo or build_wedge(inp)
    ix, iy = _stereo_xy(geo.intersection_dir, equal_area)
    tr, pl = vector_to_trend_plunge(geo.intersection_dir)
    ax.plot(ix, iy, marker="*", color="#6c3483", ms=15, mec="white", mew=0.8, zorder=8, ls="none",
            label=f"J1∩J2  {tr:.0f}/{pl:.0f}")
    xs, ys = zip(*[_stereo_xy(trend_plunge_vector(t, phi), equal_area) for t in np.linspace(0, 360, 181)])
    ax.plot(xs, ys, color="#7b4b2a", lw=1.1, ls=":", label=f"Sürtünme konisi φ = {phi:.0f}°", zorder=4)
    ax.set_aspect("equal"); ax.set_xlim(-1.22, 1.22); ax.set_ylim(-1.22, 1.22); ax.axis("off")
    ax.set_title("Stereonet — " + ("eşit alan (Schmidt)" if equal_area else "eşit açı (Wulff)") + ", alt yarımküre",
                 loc="left", color=style.NAVY, fontweight="bold")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.01), fontsize=7.5, ncol=3)
    if res is not None:
        style.result_box(ax, [f"FS = {style.fs_text(res.factor_of_safety)}", res.mode.split(" (")[0]], loc="upper right")
    if savepath:
        fig.savefig(savepath)
    if show:
        plt.show()
    return fig
