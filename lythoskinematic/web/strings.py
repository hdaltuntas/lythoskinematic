"""
lythoskinematic.web.strings — arayüz kabuğunun metinleri.

Tarayıcıda hiçbir metin gömülü değildir: JavaScript bu sözlüğü `/api/meta` ile
alır. Böylece dil değişimi tek bir yerden yönetilir ve çeviriler Python
tarafındaki `T()` yardımcısıyla aynı yerde durur.
"""
from __future__ import annotations

from ..i18n import T as _tr
from ..kinematics.i18n import LANG


def shell_strings() -> dict:
    """Seçili dildeki arayüz metinleri."""
    t = LANG[_lang()]
    return {
        # --- kabuk
        "tagline": _tr("kaya şevi kinematiği ve stabilitesi",
                       "rock slope kinematics and stability"),
        "language": _tr("Dil", "Language"),
        "open": _tr("Aç…", "Open…"),
        "save": _tr("Kaydet", "Save"),
        "report": _tr("PDF rapor", "PDF report"),
        "ready": _tr("Hazır.", "Ready."),
        "running": _tr("Hesaplanıyor…", "Computing…"),
        "theme": _tr("Koyu tema", "Dark theme"),
        "theme_light": _tr("Açık tema", "Light theme"),

        # --- sekmeler
        "tab_screening": _tr("1 · Kinematik tarama", "1 · Kinematic screening"),
        "tab_equilibrium": _tr("2 · Limit denge", "2 · Limit equilibrium"),

        # --- tarama
        "joints": _tr("Süreksizlik takımları", "Discontinuity sets"),
        "add_row": _tr("+ Satır ekle", "+ Add row"),
        "del_row": _tr("− Satır sil", "− Remove row"),
        "run_screening": _tr("▶ Taramayı çalıştır", "▶ Run screening"),
        "handoff": _tr("→ Kritik sonucu limit dengeye aktar",
                       "→ Send critical result to limit equilibrium"),
        "handoff_tip": t["handoff_tip"],
        "view_stereonet": t["tab_plot"],
        "view_report": t["tab_rep"],
        "view_probability": t["tab_prob"],
        "critical_of": _tr("kritik / toplam", "critical / total"),
        "waiting_mc": t["prob_running"],

        # --- limit denge
        "mode": _tr("Analiz türü", "Analysis type"),
        "mode_wedge": _tr("Kama (Swedge)", "Wedge (Swedge)"),
        "mode_planar": _tr("Düzlemsel (RocPlane)", "Planar (RocPlane)"),
        "mode_toppling": _tr("Devrilme (RocTopple)", "Toppling (RocTopple)"),
        "run_equilibrium": _tr("▶ Analiz et", "▶ Analyse"),
        "required": _tr("Gerekli destek", "Required support"),
        "bolts": _tr("Bulon önerisi", "Bolt recommendation"),
        "bolt_check": _tr("Bulon kontrol", "Bolt check"),
        "view_results": _tr("Sonuçlar", "Results"),
        "view_plot": _tr("Grafik", "Plot"),
        "view_table": _tr("Tablo", "Table"),
        "view_bolts": _tr("Bulon matrisi", "Bolt matrix"),
        "spacing": _tr("Aralık s (m)", "Spacing s (m)"),
        "length": _tr("Boy L (m)", "Length L (m)"),
        "recommendation": _tr("Öneri", "Recommendation"),
        "target_met": _tr("* hedef FS sağlanıyor", "* target FS met"),
        "warnings": _tr("Uyarılar", "Warnings"),

        # --- genel
        "inputs": _tr("Girdiler", "Inputs"),
        "results": _tr("Sonuçlar", "Results"),
        "no_results": _tr("Analizi çalıştırın.", "Run the analysis."),
        "no_screening": _tr("Kinematik taramayı çalıştırın.", "Run the kinematic screening."),
        "error": _tr("Hata", "Error"),
        "saved": _tr("Kaydedildi", "Saved"),
        "loaded": _tr("Yüklendi", "Loaded"),
        "bad_file": _tr("Bu dosya bir Lythos girdi dosyası değil.",
                        "That file is not a Lythos input file."),
    }


def _lang() -> str:
    from ..i18n import language
    return language()
