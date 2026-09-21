"""
lythoskinematic.kinematics.report — kinematik tarama PDF raporu.

Rapor, limit denge modülüyle aynı `rockslope.Report` şablonundan üretilir:
tek bir kurumsal düzen, tek bir künye ve tek bir kaynakça. Masaüstü sürümünde
bu rapor Qt'nin yazıcısıyla basılıyordu; web sürümünde tüm PDF üretimi
reportlab üzerinden gider ve sunucunun bir ekrana ihtiyacı kalmaz.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np
from reportlab.lib.units import mm

from ..i18n import T as _tr
from ..i18n import pct
from ..rockslope.report import Report
from .engine import MonteCarloResult, ScreeningResult, WEDGE
from .i18n import LANG


def build_report(path: str, *, result: ScreeningResult, labels: Sequence[str],
                 joints: Sequence[dict], monte_carlo: Optional[MonteCarloResult],
                 figure, project: dict, note: str = "", lang: str = "TR") -> str:
    """Tarama sonucunu PDF'e yazar ve dosya yolunu döndürür."""
    t = LANG.get(lang, LANG["TR"])
    mode = result.mode

    title = _tr("Kinematik Analiz Raporu", "Kinematic Analysis Report")
    subtitle = _tr("Markland testi — stereografik ve olasılıksal değerlendirme",
                   "Markland test — stereographic and probabilistic assessment")

    inputs = [
        (t["lbl_slope_dip"], f"{result.slope_dip:g}°"),
        (t["lbl_slope_dir"], f"{result.slope_dir:g}°"),
        (t["lbl_frict"], f"{result.friction:g}°"),
        (t["lbl_lat"], f"±{result.lateral_limit:g}°"),
        (t["lbl_type"], t["types"][mode]),
        (_tr("Süreksizlik takımı", "Discontinuity sets"), str(len(labels))),
    ]
    if monte_carlo is not None:
        inputs.append((t["lbl_sim"], f"{monte_carlo.n_trials:,}"))

    n_crit = result.n_critical
    key = [(_tr("Kritik bileşen", "Critical components"),
            f"{n_crit} / {len(result.items)}", n_crit == 0)]
    if monte_carlo is not None:
        level = monte_carlo.risk_level()
        key.append((t["prob_pof"], pct(monte_carlo.pof), monte_carlo.pof < 5))
        key.append((t["prob_eval"].split(". ")[-1], t[f"risk_{level}"][0], level == "low"))
    key.append((_tr("Yenilme mekanizması", "Failure mechanism"),
                t["types"][mode].split(" (")[0], None))

    caption = _tr("Stereonet — kutuplar/kesişimler, kritik bölge ve limit konisi",
                  "Stereonet — poles/intersections, critical zone and limit cone")

    # --- kinematik kontrol tablosu
    head = ([t["col_pair"], t["col_plunge"], t["col_trend"], t["col_status"]] if mode == WEDGE
            else [t["col_label"], t["col_dip"], t["col_dipdir"], t["col_status"]])
    rows: List[List[str]] = [head]
    for it in result.items:
        v1, v2 = ("—", "—") if np.isnan(it.value1) else (f"{it.value1:.1f}", f"{it.value2:.1f}")
        rows.append([it.name, v1, v2, t["status_crit"] if it.critical else t["status_safe"]])
    tables = [(_tr("Kinematik kontrol sonuçları", "Kinematic check results"), rows, [70, 35, 35, 40])]

    # --- girdi olarak verilen süreksizlik takımları
    joint_rows: List[List[str]] = [[t["col_label"], t["col_dip"], t["col_dipdir"], t["col_std"]]]
    for j in joints:
        joint_rows.append([str(j.get("label", "")), f"{float(j.get('dip', 0)):g}",
                           f"{float(j.get('dipdir', 0)):g}", f"{float(j.get('std', 0)):g}"])
    tables.append((_tr("Süreksizlik takımları", "Discontinuity sets"), joint_rows, [70, 35, 35, 40]))

    # --- bileşen bazlı yenilme olasılıkları
    if monte_carlo is not None and len(monte_carlo.item_pof):
        pof_rows: List[List[str]] = [[head[0], t["col_pof"]]]
        entries = []
        for idx, p in zip(monte_carlo.indices, monte_carlo.item_pof):
            name = f"{labels[idx[0]]} × {labels[idx[1]]}" if mode == WEDGE else labels[idx]
            entries.append((name, float(p)))
        for name, p in sorted(entries, key=lambda e: -e[1]):
            pof_rows.append([name, pct(p)])
        tables.append((_tr("Bileşen bazlı yenilme olasılıkları",
                           "Component-wise probabilities of failure"), pof_rows, [110, 70]))

    # --- değerlendirme
    if n_crit:
        assessment = t["summary_crit"].format(n_crit)
    else:
        assessment = t["summary_safe"]
    if monte_carlo is not None:
        assessment += " " + t[f"risk_{monte_carlo.risk_level()}"][1]
    if note:
        assessment = note + "\n\n" + assessment

    return Report(dict(project)).build(
        path, title, subtitle, "screening", key, inputs,
        [(figure, caption)] if figure is not None else [],
        [(name, rws, [w * mm for w in widths]) for name, rws, widths in tables],
        (), assessment, ())
