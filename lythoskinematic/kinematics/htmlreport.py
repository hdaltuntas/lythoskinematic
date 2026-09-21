"""
lythoskinematic.kinematics.htmlreport — QTextDocument uyumlu HTML rapor üreticileri.

Qt'nin zengin metin motoru CSS'in yalnızca bir alt kümesini destekler; bu yüzden
tablo/hücre tabanlı, satır içi stilli basit HTML üretilir. Aynı gövde hem ekranda
gösterilir hem de PDF'e basılır.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence, Tuple

import numpy as np

from ..i18n import pct
from .engine import MonteCarloResult, ScreeningResult, WEDGE

# Rapor renk paleti (Lythos kurumsal renkleri)
C_PRIMARY = "#1f3b5a"
C_CRIT, C_CRIT_BG = "#c0392b", "#fdecea"
C_SAFE, C_SAFE_BG = "#1e8449", "#e9f7ef"
C_MOD, C_MOD_BG = "#b9770e", "#fef5e7"
C_GREY = "#f4f6f8"

RISK_COLORS = {"low": (C_SAFE, C_SAFE_BG), "moderate": (C_MOD, C_MOD_BG), "high": (C_CRIT, C_CRIT_BG)}


# --------------------------------------------------------------------------- #
#  Yapı taşları
# --------------------------------------------------------------------------- #

def wrap(body: str) -> str:
    return (f"<html><body style='font-family:Segoe UI, Arial, sans-serif; font-size:10.5pt; color:#222;'>"
            f"{body}</body></html>")


def header(title: str, subtitle: str, date_label: str) -> str:
    return (f"<table width='100%' cellpadding='10' cellspacing='0'><tr>"
            f"<td bgcolor='{C_PRIMARY}'><span style='color:white; font-size:16pt; font-weight:bold;'>{title}</span><br>"
            f"<span style='color:#cfd8e3; font-size:9.5pt;'>{subtitle}</span></td>"
            f"<td bgcolor='{C_PRIMARY}' align='right' valign='bottom'>"
            f"<span style='color:#cfd8e3; font-size:9pt;'>{date_label}: "
            f"{datetime.now().strftime('%d.%m.%Y %H:%M')}</span></td></tr></table>")


def section(title: str) -> str:
    return (f"<br><table width='100%' cellpadding='4' cellspacing='0'><tr>"
            f"<td style='border-bottom:2px solid {C_PRIMARY};'>"
            f"<span style='color:{C_PRIMARY}; font-size:12pt; font-weight:bold;'>{title}</span></td></tr></table>")


def table(headers: Sequence[str], rows: Sequence[Tuple[Sequence[str], Optional[str]]],
          aligns: Optional[Sequence[str]] = None) -> str:
    aligns = aligns or ["left"] * len(headers)
    h = "".join(f"<th align='{a}' bgcolor='{C_PRIMARY}' style='color:white; padding:6px;'>{x}</th>"
                for x, a in zip(headers, aligns))
    body = ""
    for r, (cells, bg) in enumerate(rows):
        bg = bg or (C_GREY if r % 2 else "white")
        body += "<tr>" + "".join(f"<td align='{a}' bgcolor='{bg}' style='padding:5px 8px;'>{c}</td>"
                                 for c, a in zip(cells, aligns)) + "</tr>"
    return f"<table width='100%' cellpadding='4' cellspacing='0'><tr>{h}</tr>{body}</table>"


def badge(text: str, color: str) -> str:
    return (f"<span style='background-color:{color}; color:white; font-weight:bold; "
            f"font-size:8.5pt; padding:2px 6px;'>&nbsp;{text}&nbsp;</span>")


def callout(title: str, text: str, color: str, bg: str) -> str:
    return (f"<table width='100%' cellpadding='10' cellspacing='0'><tr>"
            f"<td width='6' bgcolor='{color}'></td>"
            f"<td bgcolor='{bg}'><span style='color:{color}; font-weight:bold; font-size:11pt;'>{title}</span>"
            f"<br>{text}</td></tr></table>")


def bar(pct: float, color: str) -> str:
    pct = float(np.clip(pct, 0, 100))
    left = f"<td width='{pct:.1f}%' bgcolor='{color}'>&nbsp;</td>" if pct >= 0.5 else ""
    right = f"<td width='{100 - pct:.1f}%' bgcolor='#e3e6ea'>&nbsp;</td>" if pct <= 99.5 else ""
    return f"<table width='100%' cellpadding='0' cellspacing='0'><tr>{left}{right}</tr></table>"


# --------------------------------------------------------------------------- #
#  Rapor gövdeleri
# --------------------------------------------------------------------------- #

def params_table(t: dict, slope_dip, slope_dir, friction, lateral, mode: int) -> str:
    rows = [((t["lbl_slope_dip"], f"{slope_dip}°"), None), ((t["lbl_slope_dir"], f"{slope_dir}°"), None),
            ((t["lbl_frict"], f"{friction}°"), None), ((t["lbl_lat"], f"±{lateral}°"), None),
            ((t["lbl_type"], t["types"][mode]), None)]
    return table([t["par_head"], t["val_head"]], rows)


def kinematic_report(t: dict, result: Optional[ScreeningResult]) -> str:
    """Deterministik kinematik rapor gövdesi (HTML)."""
    body = header(t["rep_title"], t["rep_subtitle"], t["rep_date"])
    if result is None or not result.items:
        return body + callout("!", t["no_data"], C_MOD, C_MOD_BG)

    body += section(t["rep_params"]) + params_table(t, result.slope_dip, result.slope_dir,
                                                    result.friction, result.lateral_limit, result.mode)
    body += section(t["rep_steps"])
    rows = []
    for it in result.items:
        mark = badge(t["status_crit"], C_CRIT) if it.critical else badge(t["status_safe"], C_SAFE)
        v1, v2 = ("—", "—") if np.isnan(it.value1) else (f"{it.value1:.1f}", f"{it.value2:.1f}")
        rows.append(((it.name, v1, v2, mark), C_CRIT_BG if it.critical else None))
    heads = ([t["col_pair"], t["col_plunge"], t["col_trend"], t["col_status"]] if result.mode == WEDGE
             else [t["col_label"], t["col_dip"], t["col_dipdir"], t["col_status"]])
    body += table(heads, rows, ["left", "center", "center", "center"])

    n = result.n_critical
    body += section(t["rep_res"])
    body += (callout(f"{n} × {t['status_crit']}", t["summary_crit"].format(n), C_CRIT, C_CRIT_BG) if n
             else callout(t["status_safe"], t["summary_safe"], C_SAFE, C_SAFE_BG))
    return body


def probabilistic_report(t: dict, mc: MonteCarloResult, labels: Sequence[str], mode: int) -> str:
    """Monte Carlo rapor gövdesi (HTML)."""
    body = header(t["prob_title"], t["prob_subtitle"], t["rep_date"])
    level = mc.risk_level()
    col, bg = RISK_COLORS[level]

    body += (f"<br><table width='100%' cellpadding='12' cellspacing='0'><tr>"
             f"<td bgcolor='{bg}' width='40%' align='center'>"
             f"<span style='font-size:9pt; color:#555;'>{t['prob_pof']}</span><br>"
             f"<span style='font-size:26pt; font-weight:bold; color:{col};'>{pct(mc.pof)}</span></td>"
             f"<td bgcolor='{C_GREY}'>{t['prob_trials']}: <b>{mc.n_trials:,}</b><br>"
             f"{t['prob_fails']}: <b>{mc.n_fail:,}</b><br><br>{bar(mc.pof, col)}</td></tr></table>")

    body += section(t["prob_items"])
    entries = []
    for idx, p in zip(mc.indices, mc.item_pof):
        name = f"{labels[idx[0]]} × {labels[idx[1]]}" if mode == WEDGE else labels[idx]
        entries.append((name, float(p)))
    entries.sort(key=lambda e: -e[1])
    rows = []
    for name, p in entries:
        pc = C_CRIT if p >= 15 else (C_MOD if p >= 5 else C_SAFE)
        rows.append(((name, f"<b>{pct(p)}</b>", bar(p, pc)), None))
    body += table([t["col_pair"] if mode == WEDGE else t["col_label"], t["col_pof"], ""], rows,
                  ["left", "center", "left"])

    body += section(t["prob_eval"]) + callout(*t[f"risk_{level}"], col, bg)
    return body


def waiting_report(t: dict) -> str:
    """Monte Carlo sürerken gösterilecek ara gövde."""
    return header(t["prob_title"], t["prob_subtitle"], t["rep_date"]) + \
        callout("…", t["prob_running"], C_PRIMARY, C_GREY)


def empty_report(t: dict, title_key: str, subtitle_key: str) -> str:
    return header(t[title_key], t[subtitle_key], t["rep_date"]) + callout("!", t["no_data"], C_MOD, C_MOD_BG)
