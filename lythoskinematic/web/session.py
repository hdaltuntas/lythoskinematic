"""
lythoskinematic.web.session — sunucunun tuttuğu tek çalışma oturumu.

HTTP katmanından ayrı tutulur: burada ağ yoktur, yalnızca "girdi sözlüğü al,
analizi çalıştır, sonucu sözlük olarak ver" vardır. Böylece arayüzün tüm
davranışı bir soket açmadan test edilebilir.

Uzun süren işler (Monte Carlo, bulon öneri matrisi) bir iş parçacığında çalışır;
arayüz `state()` ile ilerlemeyi yoklar.
"""
from __future__ import annotations

import threading
import traceback
from typing import Any, Dict, List, Optional

import numpy as np

from .. import forms, render
from ..i18n import T as _tr
from ..i18n import language, pct, set_language
from ..kinematics import engine as eng
from ..kinematics import htmlreport as H
from ..kinematics import report as screening_report
from ..kinematics.i18n import LANG
from ..rockslope import (STANDARD_LENGTHS, Report, analyze, bolt_check_planar, bolt_check_wedge,
                         bolt_pattern_planar, bolt_pattern_wedge, planar_analyze,
                         planar_required_support, required_support, style as rstyle,
                         toppling_analyze, toppling_required_support)
from ..rockslope.text import ACTIVE, MODE_TEXT, NONE_TEXT, PASSIVE, WATER_MODE

#: Tarama modunun adı -> motor indeksi
SCREEN_MODE_INDEX = {"planar": eng.PLANAR, "wedge": eng.WEDGE, "toppling": eng.TOPPLING}
SCREEN_MODE_NAME = {v: k for k, v in SCREEN_MODE_INDEX.items()}


def _clean(value):
    """NaN/sonsuz değerleri JSON'a güvenli hâle getirir."""
    if isinstance(value, (np.floating, float)):
        value = float(value)
        if np.isnan(value):
            return None
        if np.isinf(value):
            return "inf" if value > 0 else "-inf"
        return value
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


class Session:
    """Sunucunun bildiği tek analiz oturumu."""

    def __init__(self):
        self.lock = threading.Lock()
        # kinematik tarama
        self.screening: Optional[eng.ScreeningResult] = None
        self.screen_values: Dict[str, Any] = {}
        self.monte_carlo: Optional[eng.MonteCarloResult] = None
        self.labels: List[str] = []
        self.dips: List[float] = []
        self.dip_dirs: List[float] = []
        # limit denge
        self.eq_mode: Optional[str] = None
        self.eq_input = None
        self.eq_result = None
        self.eq_values: Dict[str, Any] = {}
        self.bolt_matrix: Optional[dict] = None
        # arka plan işi
        self.job = "idle"                 # idle | running | done | error
        self.job_kind = ""
        self.job_error = ""
        self.job_detail = ""
        self.job_note = ""

    # ------------------------------------------------------------------ dil
    def set_language(self, lang: str) -> str:
        set_language(lang)
        return language()

    @property
    def t(self) -> dict:
        return LANG.get(language(), LANG["TR"])

    # ------------------------------------------------------------------ iş durumu
    def _begin(self, kind: str) -> bool:
        with self.lock:
            if self.job == "running":
                return False
            self.job, self.job_kind = "running", kind
            self.job_error = self.job_detail = self.job_note = ""
        return True

    def _finish(self, note: str = "") -> None:
        with self.lock:
            self.job, self.job_note = "done", note

    def _fail(self, exc: Exception) -> None:
        with self.lock:
            self.job = "error"
            self.job_error = f"{type(exc).__name__}: {exc}"
            self.job_detail = traceback.format_exc(limit=4)

    def state(self) -> dict:
        # Anlık görüntü kilit altında alınır; raporun HTML'i kilit bırakıldıktan
        # sonra üretilir. (Kilit yeniden girilebilir değildir: rapor üretimini
        # kilit içinde çağırmak kendi kendini bloke eder.)
        with self.lock:
            snapshot = {
                "job": self.job,
                "kind": self.job_kind,
                "error": self.job_error,
                "detail": self.job_detail if self.job == "error" else "",
                "note": self.job_note,
                "has_screening": self.screening is not None,
                "has_monte_carlo": self.monte_carlo is not None,
                "has_equilibrium": self.eq_result is not None,
                "has_bolt_matrix": self.bolt_matrix is not None,
            }
        snapshot["probability_html"] = (H.wrap(self._probability_body())
                                        if snapshot["has_screening"] else "")
        return snapshot

    # ================================================================== tarama
    def screen(self, values: dict) -> dict:
        """Deterministik kinematik tarama; Monte Carlo arka planda başlar."""
        labels, dips, dirs, stds = forms.read_joints(values)
        t = self.t
        if not labels:
            return {"ok": False, "error": t["no_data"]}

        mode = SCREEN_MODE_INDEX.get(values.get("mode", "planar"), eng.PLANAR)
        slope_dip = float(values.get("slope_dip", 0))
        slope_dir = float(values.get("slope_dir", 0))
        friction = float(values.get("friction", 0))
        lateral = float(values.get("lateral", 0))

        result = eng.screen(labels, dips, dirs, slope_dip, slope_dir, friction, lateral, mode)
        with self.lock:
            self.screening = result
            self.screen_values = dict(values)
            self.labels, self.dips, self.dip_dirs = labels, list(dips), list(dirs)
            self.monte_carlo = None

        trials = int(values.get("trials", 5000) or 5000)
        if self._begin("monte_carlo"):
            args = (np.array(dips), np.array(dirs), np.array(stds), slope_dip, slope_dir,
                    friction, lateral, mode, trials)
            threading.Thread(target=self._run_monte_carlo, args=args, daemon=True).start()

        return {"ok": True, "result": self._screening_payload(),
                "report_html": H.wrap(H.kinematic_report(t, result))}

    def _run_monte_carlo(self, *args) -> None:
        try:
            mc = eng.run_monte_carlo(*args)
            with self.lock:
                self.monte_carlo = mc
            self._finish(f"{self.t['prob_pof']}: {pct(mc.pof)}")
        except Exception as exc:                      # arayüzde gösterilir
            self._fail(exc)

    def _screening_payload(self) -> dict:
        result = self.screening
        if result is None:
            return {}
        t = self.t
        return {
            "mode": SCREEN_MODE_NAME[result.mode],
            "mode_label": t["types"][result.mode],
            "n_items": len(result.items),
            "n_critical": result.n_critical,
            "columns": ([t["col_pair"], t["col_plunge"], t["col_trend"], t["col_status"]]
                        if result.mode == eng.WEDGE
                        else [t["col_label"], t["col_dip"], t["col_dipdir"], t["col_status"]]),
            "items": [{
                "name": it.name,
                "v1": _clean(it.value1), "v2": _clean(it.value2),
                "critical": it.critical,
                "status": t["status_crit"] if it.critical else t["status_safe"],
            } for it in result.items],
            "summary": (t["summary_crit"].format(result.n_critical) if result.n_critical
                        else t["summary_safe"]),
        }

    def _probability_body(self) -> str:
        t = self.t
        with self.lock:
            mc, labels, result = self.monte_carlo, list(self.labels), self.screening
        if result is None:
            return H.empty_report(t, "prob_title", "prob_subtitle")
        if mc is None:
            return H.waiting_report(t)
        return H.probabilistic_report(t, mc, labels, result.mode)

    def handoff(self) -> dict:
        """En kritik tarama bileşenini limit denge girdilerine çevirir."""
        t = self.t
        with self.lock:
            result = self.screening
            dips, dirs = list(self.dips), list(self.dip_dirs)
        if result is None or not result.critical_items:
            return {"ok": False, "error": t["handoff_none"]}

        item = max(result.critical_items,
                   key=lambda i: (i.value1 if not np.isnan(i.value1) else -1.0))
        payload = {"mode": SCREEN_MODE_NAME[result.mode], "name": item.name,
                   "slope_dip": result.slope_dip, "slope_dir": result.slope_dir,
                   "friction": result.friction, "lateral": result.lateral_limit}
        if result.mode == eng.WEDGE:
            i, j = item.index
            payload.update(j1=(dips[i], dirs[i]), j2=(dips[j], dirs[j]))
        else:
            payload.update(dip=item.value1, dipdir=item.value2)

        mode, assigned = forms.handoff_values(payload)
        return {"ok": True, "mode": mode, "values": assigned,
                "message": t["handoff_ok"].format(item.name)}

    # ========================================================== limit denge
    def equilibrium(self, mode: str, values: dict) -> dict:
        """Seçili limit denge analizini çalıştırır."""
        inp = forms.read_input(mode, values)
        res = {"wedge": analyze, "planar": planar_analyze, "toppling": toppling_analyze}[mode](inp)
        with self.lock:
            self.eq_mode, self.eq_input, self.eq_result = mode, inp, res
            self.eq_values = dict(values)
            self.bolt_matrix = None
        fs = res.fs if mode == "toppling" else res.factor_of_safety
        return {"ok": True, "mode": mode, "fs": _clean(fs), "fs_text": rstyle.fs_text(fs),
                "summary": res.summary(), "table": self._equilibrium_table(mode, inp, res),
                "warnings": list(res.warnings),
                "figures": ["main", "stereonet"] if mode == "wedge" else ["main"]}

    def _equilibrium_table(self, mode: str, inp, res) -> dict:
        t_qty = _tr("Büyüklük", "Quantity")
        if mode == "wedge":
            rows = [["FS", f"{res.factor_of_safety:.3f}"],
                    [_tr("Göçme modu", "Failure mode"), res.mode],
                    [_tr("Hacim (m³)", "Volume (m³)"), f"{res.volume:,.1f}"],
                    [_tr("Ağırlık (kN)", "Weight (kN)"), f"{res.weight:,.1f}"]]
            rows += [[f"{_tr('Alan', 'Area')} {k} (m²)", f"{a:,.1f}"] for k, a in res.areas.items()]
            rows += [[f"{_tr('Normal kuvvet', 'Normal force')} {k} (kN)", f"{n:,.1f}"]
                     for k, n in res.normal_forces.items()]
            rows += [[_tr("Kaydırıcı (kN)", "Driving (kN)"), f"{res.driving_force:,.1f}"],
                     [_tr("Direnç (kN)", "Resisting (kN)"), f"{res.resisting_force:,.1f}"]]
            return {"columns": [t_qty, _tr("Değer", "Value")], "rows": rows}
        if mode == "planar":
            rows = [["FS", f"{res.factor_of_safety:.3f}"], ["W", f"{res.weight:,.1f}"],
                    [f"U ({_tr('düzlem', 'plane')})", f"{res.water_U:,.1f}"],
                    [f"V ({_tr('çatlak', 'crack')})", f"{res.water_V:,.1f}"],
                    ["αhW", f"{res.seismic_force:,.1f}"],
                    ["N'", f"{res.normal_force:,.1f}"], ["S", f"{res.driving:,.1f}"],
                    ["R", f"{res.resisting:,.1f}"]]
            return {"columns": [t_qty, _tr("Değer (kN/m)", "Value (kN/m)")], "rows": rows}
        rows = []
        for bl in res.blocks:
            rows.append([str(bl["n"]), f"{bl['y']:.2f}", f"{bl['y'] / inp.block_width:.2f}",
                         f"{bl['W']:,.0f}", f"{bl['U']:,.0f}", f"{bl['V']:,.0f}",
                         MODE_TEXT(bl["mode"]), f"{bl['P']:,.1f}"])
        return {"columns": [_tr("Blok", "Block"), "y (m)", "y/Δx", "W (kN)", "U (kN)", "V (kN)",
                            _tr("Mod", "Mode"), "P(n−1) kN/m"],
                "rows": rows, "color_column": 6,
                "colors": {MODE_TEXT(k): c for k, c in rstyle.MODE_COLORS.items()}}

    def required_support(self, mode: str, values: dict) -> dict:
        """Hedef FS için gerekli destek; güncellenen alanları geri döndürür."""
        values = dict(values)
        if mode == "wedge":
            values["T"] = 0.0
            inp = forms.read_wedge(values)
            sr = required_support(inp, float(values.get("FS_target", 1.5)),
                                  forms._maybe(values, "T_trend"), forms._maybe(values, "T_plunge"),
                                  bool(values.get("T_passive")))
            if not sr.achievable:
                return {"ok": False, "error": sr.summary()}
            if sr.force == 0.0:
                return {"ok": True, "changed": {}, "message": sr.summary()}
            return {"ok": True, "message": sr.summary(),
                    "changed": {"T": round(sr.force, 1), "T_trend": round(sr.trend, 1),
                                "T_plunge": round(sr.plunge, 1)}}

        if mode == "planar":
            values["p_T"] = 0.0
            inp = forms.read_planar(values)
            target = float(values.get("p_FS", 1.5))
            T, angle, fs0 = planar_required_support(inp, target, forms._maybe(values, "p_theta"),
                                                    bool(values.get("p_passive")))
            if T == 0.0:
                return {"ok": True, "changed": {},
                        "message": _tr(f"Mevcut FS = {fs0:.3f} zaten hedef FS = {target:.2f} "
                                       f"değerini sağlıyor.",
                                       f"The current FS = {fs0:.3f} already meets the target "
                                       f"FS = {target:.2f}.")}
            if not np.isfinite(T) or T < 0:
                return {"ok": False,
                        "error": _tr(f"Bu açıyla (θ = {angle:.1f}°) hedef FS sağlanamıyor; "
                                     f"açıyı boş bırakın.",
                                     f"The target FS cannot be reached at this angle "
                                     f"(θ = {angle:.1f}°); leave the angle empty.")}
            mode_text = PASSIVE() if values.get("p_passive") else ACTIVE()
            return {"ok": True,
                    "changed": {"p_T": round(float(T), 1), "p_theta": round(float(angle), 1)},
                    "message": _tr(f"Mevcut FS = {fs0:.3f} → hedef {target:.2f}\n"
                                   f"Gerekli destek: {T:,.1f} kN/m (θ = {angle:.1f}°, {mode_text})",
                                   f"Current FS = {fs0:.3f} → target {target:.2f}\n"
                                   f"Required support: {T:,.1f} kN/m "
                                   f"(θ = {angle:.1f}°, {mode_text})")}

        values["t_T"] = 0.0
        inp = forms.read_toppling(values)
        target = float(values.get("t_FS", 1.3))
        T = toppling_required_support(inp, target)
        fs0 = toppling_analyze(inp).fs
        if T <= 0:
            return {"ok": True, "changed": {},
                    "message": _tr(f"Mevcut FS = {fs0:.3f} hedef FS = {target:.2f} değerini sağlıyor.",
                                   f"The current FS = {fs0:.3f} meets the target FS = {target:.2f}.")}
        delta = float(values.get("t_delta", 0))
        return {"ok": True, "changed": {"t_T": round(float(T), 1)},
                "message": _tr(f"Mevcut FS = {fs0:.3f} → hedef {target:.2f}\n"
                               f"Topuk bloğuna gerekli ankraj: {T:,.1f} kN/m (δ = {delta:.1f}°)",
                               f"Current FS = {fs0:.3f} → target {target:.2f}\n"
                               f"Anchor required at the toe block: {T:,.1f} kN/m (δ = {delta:.1f}°)")}

    # ------------------------------------------------------------------ bulon
    def start_bolts(self, mode: str, values: dict) -> dict:
        """Bulon aralık × boy öneri matrisini arka planda hesaplar."""
        if mode == "toppling":
            return {"ok": False, "error": _tr("Devrilme modunda bulon tasarımı yoktur.",
                                              "Bolt design is not available in toppling mode.")}
        spec = forms.read_bolt_spec(values)
        inp = forms.read_input(mode, values)
        force = inp.support_force if mode == "planar" else inp.support.force
        if force <= 0:
            return {"ok": False,
                    "error": _tr("Destek kuvveti 0 — önce 'Gerekli Destek' ile T'yi hesaplayın.",
                                 "Support force is 0 — compute T with 'Required Support' first.")}

        if mode == "planar":
            res = planar_analyze(inp)
            pattern = bolt_pattern_planar(res, inp.support_force, inp.support_angle, spec)
            target, passive = float(values.get("p_FS", 1.5)), bool(values.get("p_passive"))

            def check(s_, L_):
                return bolt_check_planar(inp, s_, L_, inp.support_angle, spec, target, passive)
        else:
            res = analyze(inp)
            pattern = bolt_pattern_wedge(res, inp.support.force, inp.support.trend,
                                         inp.support.plunge, spec)
            target, passive = float(values.get("FS_target", 1.5)), bool(values.get("T_passive"))

            def check(s_, L_):
                return bolt_check_wedge(inp, s_, L_, inp.support.trend, inp.support.plunge,
                                        spec, target, passive)

        spacings = [round(float(x), 2) for x in np.arange(spec.s_min, spec.s_max + 1e-9, 0.25)]
        lengths = [L for L in STANDARD_LENGTHS
                   if L <= max(pattern.total_length * 1.5, 6)] or list(STANDARD_LENGTHS[:4])

        if not self._begin("bolts"):
            return {"ok": False, "error": _tr("Bir hesap zaten sürüyor.",
                                              "An analysis is already running.")}
        threading.Thread(target=self._run_bolts, daemon=True,
                         args=(check, spacings, lengths, pattern)).start()
        return {"ok": True, "pattern": pattern.summary()}

    def _run_bolts(self, check, spacings, lengths, pattern) -> None:
        try:
            rows, best = [], None
            for s_ in spacings:
                cells = []
                for L_ in lengths:
                    try:
                        c = check(s_, L_)
                        fs, ok = float(c.fs), bool(c.ok)
                    except Exception:
                        fs, ok = float("nan"), False
                    cells.append({"fs": _clean(fs), "ok": ok})
                    if ok and (best is None or s_ > best["spacing"]):
                        best = {"spacing": s_, "length": L_, "fs": _clean(fs)}
                rows.append({"spacing": s_, "cells": cells})
            with self.lock:
                self.bolt_matrix = {"lengths": lengths, "rows": rows, "best": best,
                                    "pattern": pattern.summary()}
            if best:
                note = _tr(f"Öneri: s = {best['spacing']:.2f} m, L = {best['length']:g} m",
                           f"Recommendation: s = {best['spacing']:.2f} m, L = {best['length']:g} m")
            else:
                note = _tr("Hiçbir kombinasyon hedefi sağlamıyor.",
                           "No combination meets the target.")
            self._finish(note)
        except Exception as exc:
            self._fail(exc)

    def bolt_matrix_payload(self) -> dict:
        with self.lock:
            return dict(self.bolt_matrix) if self.bolt_matrix else {}

    def bolt_check(self, mode: str, values: dict, spacing: float, length: float) -> dict:
        """Seçilen karelaj ve boy için kapasite/FS kontrolü."""
        if mode == "toppling":
            return {"ok": False, "error": _tr("Devrilme modunda bulon tasarımı yoktur.",
                                              "Bolt design is not available in toppling mode.")}
        spec = forms.read_bolt_spec(values)
        inp = forms.read_input(mode, values)
        if mode == "planar":
            chk = bolt_check_planar(inp, spacing, length, inp.support_angle, spec,
                                    float(values.get("p_FS", 1.5)), bool(values.get("p_passive")))
        else:
            chk = bolt_check_wedge(inp, spacing, length, inp.support.trend, inp.support.plunge,
                                   spec, float(values.get("FS_target", 1.5)),
                                   bool(values.get("T_passive")))
        util = 100 * chk.T_provided / max(chk.T_required, 1e-9)
        verdict = _tr("UYGUN ✓", "ADEQUATE ✓") if chk.ok else _tr("YETERSİZ ✗", "INADEQUATE ✗")
        rows = [[f"{p:.2f}", f"{f:.2f}", f"{max(b, 0):.2f}", f"{c:.1f}"] for p, f, b, c in chk.rows]
        return {"ok": True, "adequate": bool(chk.ok), "fs": _clean(chk.fs), "verdict": verdict,
                "utilisation": round(float(util), 1), "summary": chk.summary(),
                "table": {"columns": [_tr("Yüz konumu (m)", "Face position (m)"),
                                      _tr("Serbest boy (m)", "Free length (m)"),
                                      _tr("Kök boyu (m)", "Bond length (m)"),
                                      _tr("Kapasite (kN)", "Capacity (kN)")], "rows": rows}}

    # ------------------------------------------------------------------ figürler
    def plot(self, target: str, kind: str = "main") -> bytes:
        """İstenen figürü PNG olarak üretir."""
        t = self.t
        if target == "screening":
            with self.lock:
                result, labels = self.screening, list(self.labels)
                dips, dirs, values = list(self.dips), list(self.dip_dirs), dict(self.screen_values)
            if result is None:
                raise ValueError(_tr("Önce kinematik taramayı çalıştırın.",
                                     "Run the kinematic screening first."))
            title = t[("plot_planar", "plot_wedge", "plot_toppling")[result.mode]]
            fig = render.screening_figure(
                result, labels, dips, dirs, title=title,
                show_zone=bool(values.get("zone", True)),
                show_density=bool(values.get("density", True)),
                direction_labels=t["dirs"], slope_label=t["slope_face"], cone_label=t["cone"])
            return render.figure_to_png(fig)

        with self.lock:
            mode, inp, res = self.eq_mode, self.eq_input, self.eq_result
        if res is None:
            raise ValueError(_tr("Önce limit denge analizini çalıştırın.",
                                 "Run the limit-equilibrium analysis first."))
        return render.figure_to_png(render.equilibrium_figure(mode, inp, res, kind))

    # ------------------------------------------------------------------ rapor
    def report(self, target: str, path: str) -> str:
        """PDF raporu yazar ve dosya yolunu döndürür."""
        t = self.t
        if target == "screening":
            with self.lock:
                result, labels = self.screening, list(self.labels)
                dips, dirs = list(self.dips), list(self.dip_dirs)
                values, mc = dict(self.screen_values), self.monte_carlo
            if result is None:
                raise ValueError(_tr("Önce kinematik taramayı çalıştırın.",
                                     "Run the kinematic screening first."))
            title = t[("plot_planar", "plot_wedge", "plot_toppling")[result.mode]]
            fig = render.screening_figure(
                result, labels, dips, dirs, title=title,
                show_zone=bool(values.get("zone", True)),
                show_density=bool(values.get("density", True)),
                direction_labels=t["dirs"], slope_label=t["slope_face"], cone_label=t["cone"])
            return screening_report.build_report(
                path, result=result, labels=labels, joints=values.get("joints", []),
                monte_carlo=mc, figure=fig, project=forms.project_info(values),
                note=str(values.get("rp_note", "")), lang=language())

        with self.lock:
            mode, inp, res, values = self.eq_mode, self.eq_input, self.eq_result, dict(self.eq_values)
        if res is None:
            raise ValueError(_tr("Önce limit denge analizini çalıştırın.",
                                 "Run the limit-equilibrium analysis first."))
        figures = render.equilibrium_figures(mode, inp, res)
        content = equilibrium_report_content(mode, inp, res, values, figures)
        title, subtitle, key, inputs, figcaps, tables, warnings = content
        from reportlab.lib.units import mm
        project = forms.project_info(values)
        return Report(project).build(
            path, title, subtitle, mode, key, inputs, figcaps,
            [(n, r, [w * mm for w in wd]) for n, r, wd in tables],
            [(_tr("Program çıktısı (tam metin)", "Program output (full text)"), res.summary())],
            str(values.get("rp_note", "")), warnings)


# --------------------------------------------------------------------------- #
#  Limit denge raporunun mod bağımlı içeriği
# --------------------------------------------------------------------------- #

def equilibrium_report_content(mode: str, inp, res, values: dict, figures):
    """PDF raporunun başlığı, künyesi, KPI'ları, şekilleri ve tabloları."""
    QTY, VAL = _tr("Büyüklük", "Quantity"), _tr("Değer", "Value")
    FS_LABEL = _tr("Güvenlik sayısı", "Factor of safety")
    TARGET_FS = _tr("Hedef FS", "Target FS")
    UNIT_WEIGHT = _tr("Birim hacim ağırlığı", "Unit weight")
    SUPPORT = _tr("Destek", "Support")
    TC = _tr("Çekme çatlağı", "Tension crack")

    if mode == "wedge":
        j1, j2 = inp.joint1, inp.joint2
        target = float(values.get("FS_target", 1.5))
        fs = res.factor_of_safety
        sup_mode = PASSIVE() if inp.support.passive else ACTIVE()
        inputs = [
            (f"{_tr('Eklem 1', 'Joint 1')} (dip/dip dir)", f"{j1.dip:g}° / {j1.dipdir:g}°"),
            (f"{_tr('Eklem 1', 'Joint 1')} c / φ", f"{j1.cohesion:g} kPa / {j1.friction:g}°"),
            (f"{_tr('Eklem 2', 'Joint 2')} (dip/dip dir)", f"{j2.dip:g}° / {j2.dipdir:g}°"),
            (f"{_tr('Eklem 2', 'Joint 2')} c / φ", f"{j2.cohesion:g} kPa / {j2.friction:g}°"),
            (_tr("Şev yüzü", "Slope face"), f"{inp.slope_face.dip:g}° / {inp.slope_face.dipdir:g}°"),
            (_tr("Üst şev", "Upper slope"), f"{inp.upper_slope.dip:g}° / {inp.upper_slope.dipdir:g}°"),
            (_tr("Şev yüksekliği", "Slope height"), f"{inp.slope_height:g} m"),
            (UNIT_WEIGHT, f"{inp.unit_weight:g} kN/m³"),
            (_tr("Kama ölçekleme", "Wedge scaling"),
             f"{inp.scale_mode}" + (f" = {inp.scale_value:g}" if inp.scale_value else "")),
            (TC, (f"{inp.tension_crack.dip:g}°/{inp.tension_crack.dipdir:g}°, "
                  f"{inp.tension_crack.distance_from_crest:g} m") if inp.tension_crack else NONE_TEXT()),
            (_tr("Su basıncı", "Water pressure"),
             f"{pct(inp.water.percent, 0)} {_tr('dolu', 'filled')}" if inp.water.mode == "percent"
             else WATER_MODE(inp.water.mode)),
            (_tr("Sismik katsayı", "Seismic coefficient"), f"α = {inp.seismic.coefficient:g}"),
            (SUPPORT, f"{inp.support.force:,.0f} kN @ {inp.support.trend:g}°/"
                      f"{inp.support.plunge:g}° ({sup_mode})"),
            (TARGET_FS, f"{target:g}")]
        key = [(FS_LABEL, f"{fs:.3f}", fs >= target),
               (_tr("Göçme modu", "Failure mode"), res.mode.split(" (")[0], None),
               (_tr("Kama hacmi", "Wedge volume"), f"{res.volume:,.0f} m³", None),
               (_tr("Kama ağırlığı", "Wedge weight"), f"{res.weight:,.0f} kN", None)]
        figcaps = [(figures[0], _tr("Kama geometrisi, göçme modu ve kayma yönü (3D)",
                                    "Wedge geometry, failure mode and sliding direction (3D)")),
                   (figures[1], _tr("Stereonet — düzlemler, kesişim çizgisi ve sürtünme konisi",
                                    "Stereonet — planes, line of intersection and friction cone"))]
        tables = [(_tr("Kuvvet dengesi", "Force balance"),
                   [[QTY, VAL], [_tr("Kama ağırlığı", "Wedge weight"), f"{res.weight:,.1f} kN"],
                    *[[f"{_tr('Su kuvveti', 'Water force')} {k}", f"{u:,.1f} kN"]
                      for k, u in res.water_forces.items()],
                    [_tr("Sismik kuvvet", "Seismic force"), f"{res.seismic_force:,.1f} kN"],
                    [_tr("Destek kuvveti", "Support force"), f"{res.support_force:,.1f} kN"],
                    *[[f"{_tr('Normal kuvvet', 'Normal force')} {k}", f"{n:,.1f} kN"]
                      for k, n in res.normal_forces.items()],
                    [_tr("Kaydırıcı kuvvet", "Driving force"), f"{res.driving_force:,.1f} kN"],
                    [_tr("Direnç kuvveti", "Resisting force"), f"{res.resisting_force:,.1f} kN"],
                    [FS_LABEL, f"{fs:.3f}"]], [90, 90]),
                  (_tr("Geometri", "Geometry"),
                   [[QTY, VAL],
                    *[[f"{_tr('Alan', 'Area')} {k}", f"{a:,.1f} m²"] for k, a in res.areas.items()],
                    [_tr("Tepe uzunluğu |BC|", "Crest length |BC|"), f"{res.geometry.crest_length:,.1f} m"],
                    [_tr("Basamak genişliği", "Bench width"), f"{res.geometry.bench_width:,.1f} m"],
                    [_tr("Kesişim çizgisi", "Line of intersection"),
                     f"trend {res.intersection_line[0]:.1f}°, plunge {res.intersection_line[1]:.1f}°"]],
                   [90, 90])]
        return (_tr("Kama Stabilite Analizi", "Wedge Stability Analysis"),
                _tr("Tetrahedral kama — Hoek & Bray vektörel limit denge yöntemi",
                    "Tetrahedral wedge — Hoek & Bray vector limit-equilibrium method"),
                key, inputs, figcaps, tables, list(res.warnings))

    if mode == "planar":
        target = float(values.get("p_FS", 1.5))
        fs = res.factor_of_safety
        sup_mode = PASSIVE() if inp.support_passive else ACTIVE()
        water = (f"{_tr('çatlak', 'crack')} {pct(inp.water_percent, 0)} {_tr('dolu', 'filled')}"
                 if inp.water_mode == "percent" else WATER_MODE(inp.water_mode))
        inputs = [(_tr("Şev yüksekliği H", "Slope height H"), f"{inp.slope_height:g} m"),
                  (_tr("Şev yüzü ψf", "Slope face ψf"), f"{inp.face_angle:g}°"),
                  (_tr("Kayma düzlemi ψp", "Sliding plane ψp"), f"{inp.plane_angle:g}°"),
                  (_tr("Üst şev ψs", "Upper slope ψs"), f"{inp.upper_angle:g}°"),
                  (_tr("Kohezyon c", "Cohesion c"), f"{inp.cohesion:g} kPa"),
                  (_tr("Sürtünme açısı φ", "Friction angle φ"), f"{inp.friction:g}°"),
                  (UNIT_WEIGHT, f"{inp.unit_weight:g} kN/m³"),
                  (TC, f"b = {inp.tc_distance:g} m" if inp.tc_distance is not None else NONE_TEXT()),
                  (_tr("Su", "Water"), water),
                  (_tr("Sismik αh / αv", "Seismic αh / αv"), f"{inp.seismic_h:g} / {inp.seismic_v:g}"),
                  (SUPPORT, f"{inp.support_force:,.0f} kN/m @ {inp.support_angle:g}° ({sup_mode})"),
                  (TARGET_FS, f"{target:g}")]
        key = [(FS_LABEL, f"{fs:.3f}", fs >= target),
               (_tr("Blok ağırlığı", "Block weight"), f"{res.weight:,.0f} kN/m", None),
               (_tr("Çatlak derinliği", "Crack depth"),
                f"{res.tc_depth:.2f} m" if inp.tc_distance is not None else "—", None),
               (_tr("Su kuvvetleri U / V", "Water forces U / V"),
                f"{res.water_U:,.0f} / {res.water_V:,.0f}", None)]
        tables = [(_tr("Kuvvet dengesi (kN/m)", "Force balance (kN/m)"),
                   [[QTY, VAL], [_tr("Blok alanı", "Block area"), f"{res.area:,.2f} m²"],
                    [_tr("Ağırlık W", "Weight W"), f"{res.weight:,.1f}"],
                    [_tr("Kayma düzlemi uzunluğu", "Sliding plane length"), f"{res.plane_length:,.2f} m"],
                    [f"{_tr('Su', 'Water')} U ({_tr('düzlem', 'plane')})", f"{res.water_U:,.1f}"],
                    [f"{_tr('Su', 'Water')} V ({_tr('çatlak', 'crack')})", f"{res.water_V:,.1f}"],
                    [_tr("Sismik αhW", "Seismic αhW"), f"{res.seismic_force:,.1f}"],
                    [_tr("Etkin normal kuvvet", "Effective normal force"), f"{res.normal_force:,.1f}"],
                    [_tr("Kaydırıcı kuvvet", "Driving force"), f"{res.driving:,.1f}"],
                    [_tr("Direnç kuvveti", "Resisting force"), f"{res.resisting:,.1f}"],
                    [FS_LABEL, f"{fs:.3f}"]], [90, 90])]
        return (_tr("Düzlemsel Kayma Analizi", "Planar Sliding Analysis"),
                _tr("Hoek & Bray düzlemsel limit denge çözümü — 1 m şev uzunluğu",
                    "Hoek & Bray planar limit-equilibrium solution — 1 m slope length"),
                key, inputs,
                [(figures[0], _tr("Düzlemsel kayma kesiti, su basıncı dağılımı ve kuvvetler",
                                  "Planar sliding section, water pressure distribution and forces"))],
                tables, list(res.warnings))

    target = float(values.get("t_FS", 1.3))
    inputs = [(_tr("Şev yüzü ψf", "Slope face ψf"), f"{inp.face_angle:g}°"),
              (_tr("Üst şev ψs", "Upper slope ψs"), f"{inp.upper_angle:g}°"),
              (_tr("Süreksizlik eğimi ψd", "Discontinuity dip ψd"),
               f"{inp.disc_dip:g}° (ψp = {90 - inp.disc_dip:g}°)"),
              (_tr("Taban genel eğimi ψb", "Overall base angle ψb"), f"{inp.base_angle:g}°"),
              (_tr("Blok genişliği Δx", "Block width Δx"), f"{inp.block_width:g} m"),
              (_tr("Blok sayısı", "Number of blocks"),
               _tr(f"{inp.n_below} tepe altı + {inp.n_above} tepe üstü",
                   f"{inp.n_below} below crest + {inp.n_above} above crest")),
              (_tr("Sürtünme açısı φ", "Friction angle φ"), f"{inp.friction:g}°"),
              (UNIT_WEIGHT, f"{inp.unit_weight:g} kN/m³"),
              (_tr("Eklem su doluluğu", "Joint water filling"), pct(inp.water_percent, 0)),
              (_tr("Sismik αh", "Seismic αh"), f"{inp.seismic_h:g}"),
              (_tr("Topuk ankrajı", "Toe anchor"),
               f"{inp.support_force:,.0f} kN/m @ {inp.support_angle:g}°"),
              (TARGET_FS, f"{target:g}")]
    key = [(FS_LABEL, f"{res.fs:.3f}", res.fs >= target),
           (_tr("Gerekli φ", "Required φ"), f"{res.phi_required:.2f}°", None),
           (_tr("Topuk ankrajı (φ mevcut)", "Toe anchor (current φ)"), f"{res.T_required:,.0f} kN/m", None),
           (_tr("Şev yüksekliği", "Slope height"), f"{res.slope_height:.1f} m", None)]
    rows = [[_tr("Blok", "Block"), "y (m)", "y/Δx", "W (kN)", "U (kN)", "V (kN)",
             _tr("Mod", "Mode"), "P(n−1) (kN/m)"]]
    for bl in res.blocks:
        rows.append([str(bl["n"]), f"{bl['y']:.2f}", f"{bl['y'] / inp.block_width:.2f}",
                     f"{bl['W']:,.0f}", f"{bl['U']:,.0f}", f"{bl['V']:,.0f}",
                     MODE_TEXT(bl["mode"]), f"{bl['P']:,.1f}"])
    return (_tr("Blok Devrilme Analizi", "Block Toppling Analysis"),
            _tr("Goodman & Bray (1976) blok devrilme limit denge yöntemi — 1 m şev uzunluğu",
                "Goodman & Bray (1976) block toppling limit-equilibrium method — 1 m slope length"),
            key, inputs,
            [(figures[0], _tr("Blok kolonları, göçme modları ve eklem su seviyeleri",
                              "Block columns, failure modes and joint water levels"))],
            [(_tr("Blok bazında sonuçlar", "Per-block results"), rows,
              [14, 20, 16, 26, 22, 22, 24, 36])], list(res.warnings))
