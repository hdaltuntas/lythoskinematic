"""rockslope.report — profesyonel PDF rapor (reportlab).

Kullanım:
    rep = Report(project=dict(Proje=..., Konum=..., Hazırlayan=..., Kontrol=..., Doküman_No=..., Revizyon=...))
    rep.build(path, title, subtitle, key_results, inputs, figures, tables, text_blocks, method_text, conclusion)
"""
from __future__ import annotations

import io
import os
import datetime
from typing import Dict, List, Tuple, Optional, Sequence

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
                                Preformatted, KeepTogether, Flowable)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

NAVY = colors.HexColor("#1f3b5a"); ACCENT = colors.HexColor("#2874a6"); GREY = colors.HexColor("#5b6770")
LIGHT = colors.HexColor("#eef1f5"); LINE = colors.HexColor("#c9d1dc"); OK = colors.HexColor("#1e8449"); BAD = colors.HexColor("#c0392b")

METHOD_TEXT = {
    "wedge": ("Analiz, Hoek & Bray (1981) tarafından verilen ve Wyllie & Mah (2004) tarafından geliştirilen tetrahedral kama "
              "limit denge yöntemine dayanır. Kama, iki süreksizlik düzlemi, şev yüzü, üst şev ve isteğe bağlı çekme çatlağı ile "
              "sınırlanır; bileşke kuvvet (ağırlık, su basınçları, sismik yük ve aktif destek) süreksizlik normalleri ve kesişim "
              "çizgisi doğrultusunda çözülerek göçme modu (iki düzlemde kayma, tek düzlemde kayma, düşme) belirlenir. "
              "Güvenlik sayısı, kayma doğrultusundaki direnç kuvvetlerinin kaydırıcı kuvvetlere oranıdır. Su basıncı 'dolu çatlak' "
              "modelinde ortalama u = γw·Hw/6 alınır. Pasif destek yalnızca direnç tarafına eklenir."),
    "planar": ("Analiz, Hoek & Bray (1981) düzlemsel kayma limit denge çözümüne dayanır: FS = [c·A + (W·cosψp − U − V·sinψp + "
               "T·sin(θ+ψp))·tanφ] / [W·sinψp + V·cosψp − T·cos(θ+ψp)]. Çekme çatlağındaki su üçgen dağılımlı (V), kayma "
               "düzlemindeki su çatlak dibinden topuğa doğru lineer azalan (U) kabul edilir. Sismik yük pseudo-statik olarak "
               "blok ağırlık merkezine yatay kuvvet biçiminde uygulanır. Sonuçlar 1 m şev uzunluğu içindir."),
    "toppling": ("Analiz, Goodman & Bray (1976) blok devrilme limit denge yöntemine dayanır (Wyllie & Mah 2004, Bölüm 9). "
                 "Şev, şeve doğru dik/dike yakın süreksizliklerle ayrılmış blok kolonları olarak modellenir; tepeden topuğa her "
                 "blok için devrilme ve kayma dengesi kurularak alt bloğa iletilen kuvvet hesaplanır. Bloklar arası eklemlerde "
                 "üçgen su basıncı, blok tabanında yamuk kaldırma dağılımı kabul edilir. Güvenlik sayısı, mevcut sürtünme "
                 "açısının topuk bloğunu tam dengede tutan sürtünme açısına oranı (tanφ/tanφ_req) olarak tanımlanır."),
}
REFERENCES = [
    "Hoek, E. & Bray, J.W. (1981). Rock Slope Engineering, 3rd ed. IMM, London.",
    "Wyllie, D.C. & Mah, C.W. (2004). Rock Slope Engineering: Civil and Mining, 4th ed. Spon Press.",
    "Goodman, R.E. & Bray, J.W. (1976). Toppling of rock slopes. ASCE Specialty Conf. Rock Eng. for Foundations and Slopes, Boulder.",
    "Rocscience Inc. Swedge / RocPlane / RocTopple Theory Manuals.",
]


def _fonts():
    cands = [("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
             ("Arial", r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\consola.ttf"),
             ("Arial", "/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf", "/System/Library/Fonts/Menlo.ttc")]
    for name, reg, bold, mono in cands:
        if os.path.exists(reg):
            pdfmetrics.registerFont(TTFont(name, reg))
            pdfmetrics.registerFont(TTFont(name + "-Bold", bold if os.path.exists(bold) else reg))
            m = "Courier"
            if os.path.exists(mono):
                try:
                    pdfmetrics.registerFont(TTFont("RSMono", mono)); m = "RSMono"
                except Exception:
                    pass
            return name, name + "-Bold", m
    return "Helvetica", "Helvetica-Bold", "Courier"


class KpiRow(Flowable):
    """Büyük rakamlı özet kutuları (3-4 adet)."""
    def __init__(self, items: Sequence[Tuple[str, str, Optional[bool]]], font, bold, width=180 * mm, height=22 * mm):
        super().__init__(); self.items = list(items); self.font, self.bold = font, bold
        self.width, self.height = width, height

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv; n = len(self.items); gap = 3 * mm; w = (self.width - gap * (n - 1)) / n
        for k, (label, value, ok) in enumerate(self.items):
            x = k * (w + gap)
            c.setFillColor(LIGHT); c.setStrokeColor(LINE); c.roundRect(x, 0, w, self.height, 2 * mm, fill=1, stroke=1)
            c.setFillColor(NAVY if ok is None else (OK if ok else BAD))
            c.rect(x, 0, 2.2 * mm, self.height, fill=1, stroke=0)
            c.setFillColor(GREY); c.setFont(self.font, 7.5); c.drawString(x + 5 * mm, self.height - 6 * mm, label)
            c.setFillColor(NAVY if ok is None else (OK if ok else BAD))
            fs = 13
            while fs > 7.5 and pdfmetrics.stringWidth(value, self.bold, fs) > w - 8 * mm:
                fs -= 0.5
            c.setFont(self.bold, fs); c.drawString(x + 5 * mm, 5 * mm, value)


class Report:
    def __init__(self, project: Dict[str, str], logo_path: Optional[str] = None):
        self.project = dict(project); self.logo = logo_path
        self.font, self.bold, self.mono = _fonts()
        self.st = {
            "title": ParagraphStyle("t", fontName=self.bold, fontSize=20, leading=24, textColor=NAVY),
            "sub": ParagraphStyle("s", fontName=self.font, fontSize=10.5, leading=14, textColor=GREY),
            "h1": ParagraphStyle("h1", fontName=self.bold, fontSize=12.5, leading=16, textColor=NAVY, spaceBefore=12, spaceAfter=5),
            "h2": ParagraphStyle("h2", fontName=self.bold, fontSize=10, leading=13, textColor=ACCENT, spaceBefore=8, spaceAfter=3),
            "body": ParagraphStyle("b", fontName=self.font, fontSize=9.2, leading=13, alignment=TA_LEFT),
            "small": ParagraphStyle("sm", fontName=self.font, fontSize=8, leading=10.5, textColor=GREY),
            "cap": ParagraphStyle("cap", fontName=self.font, fontSize=8.2, leading=11, textColor=GREY, alignment=TA_CENTER, spaceAfter=8),
            "mono": ParagraphStyle("m", fontName=self.mono, fontSize=7.2, leading=9),
            "cell": ParagraphStyle("c", fontName=self.font, fontSize=8.6, leading=11),
            "cellb": ParagraphStyle("cb", fontName=self.bold, fontSize=8.6, leading=11),
        }

    # ------------------------------------------------------------------ yapı taşları
    def _table(self, rows, widths, header=False, zebra=True, align_right_cols=()):
        data = []
        for r, row in enumerate(rows):
            data.append([Paragraph(str(cell), self.st["cellb"] if (header and r == 0) else self.st["cell"]) for cell in row])
        t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
        ts = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
              ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
        if header:
            ts += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
            data[0] = [Paragraph(f"<font color='white'>{c}</font>", self.st["cellb"]) for c in rows[0]]
            t = Table(data, colWidths=widths, repeatRows=1)
        if zebra:
            for r in range(1 if header else 0, len(rows)):
                if r % 2 == (0 if header else 1):
                    ts.append(("BACKGROUND", (0, r), (-1, r), LIGHT))
        for c in align_right_cols:
            ts.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
        t.setStyle(TableStyle(ts)); return t

    def _kv(self, pairs, two_col=True):
        if two_col:
            half = (len(pairs) + 1) // 2; rows = []
            for k in range(half):
                l = pairs[k]; r = pairs[k + half] if k + half < len(pairs) else ("", "")
                rows.append([l[0], l[1], r[0], r[1]])
            t = self._table(rows, [40 * mm, 50 * mm, 40 * mm, 50 * mm], zebra=False)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), LIGHT), ("BACKGROUND", (2, 0), (2, -1), LIGHT)]))
            return t
        t = self._table([[k, v] for k, v in pairs], [50 * mm, 130 * mm], zebra=False)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), LIGHT)])); return t

    def _figure(self, fig, caption, max_h=118 * mm):
        from reportlab.lib.utils import ImageReader
        buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=170, bbox_inches="tight"); buf.seek(0)
        iw, ih = ImageReader(buf).getSize(); buf.seek(0)          # kırpılmış gerçek piksel oranı
        w = 180 * mm; h = w * ih / iw
        if h > max_h:
            h = max_h; w = h * iw / ih
        return KeepTogether([Image(buf, width=w, height=h), Paragraph(caption, self.st["cap"])])

    def _header_footer(self, title):
        proj = self.project
        def cb(canvas, doc):
            canvas.saveState(); w, h = A4
            canvas.setFillColor(NAVY); canvas.rect(0, h - 16 * mm, w, 16 * mm, fill=1, stroke=0)
            canvas.setFillColor(colors.white); canvas.setFont(self.bold, 10.5)
            canvas.drawString(15 * mm, h - 10 * mm, "KAYA ŞEVİ STABİLİTE RAPORU")
            canvas.setFont(self.font, 8.5); canvas.drawRightString(w - 15 * mm, h - 7 * mm, title)
            canvas.drawRightString(w - 15 * mm, h - 12 * mm, f"Doküman: {proj.get('Doküman No', '—')}   Rev: {proj.get('Revizyon', '0')}")
            canvas.setStrokeColor(LINE); canvas.setLineWidth(0.6); canvas.line(15 * mm, 14 * mm, w - 15 * mm, 14 * mm)
            canvas.setFillColor(GREY); canvas.setFont(self.font, 7.5)
            left = f"{proj.get('Proje', '')}  ·  {proj.get('Konum', '')}"
            canvas.drawString(15 * mm, 9.5 * mm, left[:70])
            canvas.drawRightString(w - 15 * mm, 9.5 * mm, f"{proj.get('Tarih', '')}   ·   Sayfa {doc.page}")
            canvas.setFont(self.font, 6.5); canvas.drawString(15 * mm, 5.5 * mm, "Kinematix v2 — limit denge analiz aracı")
            canvas.restoreState()
        return cb

    # ------------------------------------------------------------------ ana
    def build(self, path: str, title: str, subtitle: str, mode: str,
              key_results: Sequence[Tuple[str, str, Optional[bool]]],
              inputs: Sequence[Tuple[str, str]],
              figures: Sequence[Tuple[object, str]] = (),
              tables: Sequence[Tuple[str, List[List[str]], Optional[List[float]]]] = (),
              text_blocks: Sequence[Tuple[str, str]] = (),
              conclusion: str = "", warnings: Sequence[str] = ()):
        st = self.st; proj = self.project
        proj.setdefault("Tarih", datetime.date.today().strftime("%d.%m.%Y"))
        doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=24 * mm,
                                bottomMargin=20 * mm, title=title, author=proj.get("Hazırlayan", ""), subject=subtitle)
        S = []
        # Başlık bloğu
        head = [[Paragraph(title, st["title"])], [Paragraph(subtitle, st["sub"])]]
        if self.logo and os.path.exists(self.logo):
            logo = Image(self.logo, width=28 * mm, height=28 * mm, kind="proportional")
            t = Table([[Table(head), logo]], colWidths=[150 * mm, 30 * mm]); t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            S.append(t)
        else:
            S += [Paragraph(title, st["title"]), Paragraph(subtitle, st["sub"])]
        S.append(Spacer(1, 4))
        info = [(k, v) for k, v in proj.items() if k in ("Proje", "Konum", "Km / Kesit", "Hazırlayan", "Kontrol", "Onay", "Tarih", "Doküman No", "Revizyon")]
        S += [self._kv(info), Spacer(1, 8)]
        # KPI
        S.append(KpiRow(key_results, self.font, self.bold)); S.append(Spacer(1, 4))
        # 1 Yöntem
        S.append(Paragraph("1. Analiz yöntemi", st["h1"]))
        S.append(Paragraph(METHOD_TEXT.get(mode, ""), st["body"]))
        # 2 Girdiler
        S.append(Paragraph("2. Girdi parametreleri", st["h1"]))
        S.append(self._kv(list(inputs)))
        # 3 Şekiller
        if figures:
            for k, (fig, cap) in enumerate(figures, 1):
                f = self._figure(fig, f"Şekil {k}. {cap}")
                S.append(KeepTogether([Paragraph("3. Şekiller", st["h1"]), f]) if k == 1 else f)
        # 4 Sonuç tabloları
        if tables:
            for k, (name, rows, widths) in enumerate(tables, 1):
                tb = self._table(rows, widths or [180 * mm / len(rows[0])] * len(rows[0]), header=True,
                                 align_right_cols=range(1, len(rows[0])))
                parts = ([Paragraph("4. Sonuçlar", st["h1"])] if k == 1 else []) + [Paragraph(f"Tablo {k}. {name}", st["h2"]), tb]
                S.append(KeepTogether(parts) if len(rows) < 25 else parts[0] if k == 1 else parts[1]); 
                if len(rows) >= 25:
                    if k == 1: S.append(Paragraph(f"Tablo {k}. {name}", st["h2"]))
                    S.append(tb)
        # 5 Ayrıntılı çıktı
        if text_blocks:
            S.append(PageBreak())
            S.append(Paragraph("5. Ayrıntılı hesap çıktıları", st["h1"]))
            for name, txt in text_blocks:
                S += [Paragraph(name, st["h2"]), Preformatted(txt, st["mono"])]
        # 6 Uyarılar / Değerlendirme
        if warnings:
            S.append(Paragraph("6. Uyarılar", st["h1"]))
            for w in warnings:
                S.append(Paragraph("• " + w, st["body"]))
        S.append(Paragraph("7. Değerlendirme ve öneriler" if warnings else "6. Değerlendirme ve öneriler", st["h1"]))
        S.append(Paragraph(conclusion or "—", st["body"]))
        # Referanslar + imza
        S.append(Paragraph("Kaynaklar", st["h1"]))
        for r in REFERENCES:
            S.append(Paragraph("• " + r, st["small"]))
        S.append(Spacer(1, 10))
        sig = Table([["Hazırlayan", "Kontrol", "Onay"],
                     [proj.get("Hazırlayan", ""), proj.get("Kontrol", ""), proj.get("Onay", "")],
                     ["", "", ""], ["İmza / Tarih", "İmza / Tarih", "İmza / Tarih"]],
                    colWidths=[60 * mm] * 3, rowHeights=[6 * mm, 6 * mm, 14 * mm, 5 * mm])
        sig.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, 0), self.bold), ("FONTNAME", (0, 1), (-1, -1), self.font),
                                 ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                                 ("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                 ("TEXTCOLOR", (0, -1), (-1, -1), GREY)]))
        S.append(KeepTogether([sig]))
        S.append(Spacer(1, 6))
        S.append(Paragraph("Bu rapor limit denge yöntemleriyle üretilmiştir; sonuçlar girdi parametrelerinin ve saha verisinin "
                           "kalitesine bağlıdır. Tasarım kararları yetkili geoteknik mühendisi tarafından değerlendirilmelidir.", st["small"]))
        doc.build(S, onFirstPage=self._header_footer(title), onLaterPages=self._header_footer(title))
        return path
