"""
İki dilli metin katmanı (lythos/i18n.py) ve limit denge çekirdeğinin çevirileri.

Hesap sonuçlarının dilden bağımsız olması, buna karşılık kullanıcıya görünen her
metnin dili izlemesi gerekir. Blok modu gibi iç anahtarlar (renk eşlemesinde
kullanılır) hiçbir dilde değişmemelidir.
"""
import numpy as np
import pytest

from lythos import i18n
from lythos.rockslope import text as rtext
from lythos.rockslope.bolts import BoltSpec, bolt_check_planar
from lythos.rockslope.planar import PlanarInput, planar_analyze, planar_required_support
from lythos.rockslope.report import METHOD, PROJECT_FIELDS, PROJECT_LABEL
from lythos.rockslope.toppling import TopplingInput, toppling_analyze
from lythos.rockslope.wedge import Joint, Plane, Seismic, Support, Water, WedgeInput, analyze


@pytest.fixture(autouse=True)
def restore_language():
    """Her test Türkçe başlar ve dili geri bırakır."""
    i18n.set_language("TR")
    yield
    i18n.set_language("TR")


PLANAR = PlanarInput(20, 72, 34, 0, 0, 31, 25, 6, "percent", 9.81, 100, 0, 0, 0, 0, 0, 0, False)
TOPPLING = TopplingInput(56.6, 4, 60, 35.8, 10, 10, 6, 38.15, 25, 0, 9.81, 0, 0, 0, None)
WEDGE = WedgeInput(Joint(45, 105, 24, 20), Joint(70, 235, 48, 30), Plane(65, 185), Plane(12, 195),
                   40, 25, None, Water("dry"), Seismic(0), Support(0, 0, 0))


# --------------------------------------------------------------------------- #
#  Dil anahtarı
# --------------------------------------------------------------------------- #

def test_set_language_reports_change_only_once():
    assert i18n.language() == "TR"
    assert i18n.set_language("EN") is True
    assert i18n.set_language("EN") is False          # değişiklik yok
    assert i18n.language() == "EN"


def test_unknown_language_is_ignored():
    assert i18n.set_language("DE") is False
    assert i18n.set_language("") is False
    assert i18n.language() == "TR"


def test_language_code_is_case_insensitive():
    assert i18n.set_language("en") is True
    assert i18n.language() == "EN"


def test_T_follows_the_selected_language():
    assert i18n.T("kuru", "dry") == "kuru"
    i18n.set_language("EN")
    assert i18n.T("kuru", "dry") == "dry"


def test_listeners_are_notified():
    seen = []
    i18n.on_change(seen.append)
    i18n.set_language("EN")
    assert seen == ["EN"]


# --------------------------------------------------------------------------- #
#  Sonuç metinleri
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("build, tr_word, en_word", [
    (lambda: planar_analyze(PLANAR).summary(), "GÜVENLİK SAYISI", "FACTOR OF SAFETY"),
    (lambda: toppling_analyze(TOPPLING).summary(), "BLOK DEVRİLME", "BLOCK TOPPLING"),
    (lambda: analyze(WEDGE).summary(), "KAMA STABİLİTE", "WEDGE STABILITY"),
])
def test_summaries_switch_language(build, tr_word, en_word):
    tr = build()
    assert tr_word in tr and en_word not in tr
    i18n.set_language("EN")
    en = build()
    assert en_word in en and tr_word not in en


def test_summary_layout_is_identical_in_both_languages():
    """Çeviri hizalamayı bozmamalı: satır sayısı ve etiket sütunu aynı kalır."""
    tr = planar_analyze(PLANAR).summary().splitlines()
    i18n.set_language("EN")
    en = planar_analyze(PLANAR).summary().splitlines()
    assert len(tr) == len(en)

    width = rtext.LABEL_WIDTH
    checked = 0
    for a, b in zip(tr, en):
        if len(a) > width and a[width] == ":":       # hizalanmış etiket satırı
            assert b[width] == ":", f"hizalama bozuk:\n{a!r}\n{b!r}"
            checked += 1
    assert checked >= 10, "hizalanmış satır bulunamadı; özet biçimi değişmiş olabilir"


def test_numbers_are_language_independent():
    """Dil yalnızca metni değiştirir; sayısal sonuçlar aynı kalır."""
    tr = planar_analyze(PLANAR)
    i18n.set_language("EN")
    en = planar_analyze(PLANAR)
    assert tr.factor_of_safety == pytest.approx(en.factor_of_safety)
    assert tr.weight == pytest.approx(en.weight)
    assert analyze(WEDGE).factor_of_safety == pytest.approx(1.696, abs=5e-4)


def test_round_trip_restores_turkish_text():
    tr_before = planar_analyze(PLANAR).summary()
    i18n.set_language("EN")
    planar_analyze(PLANAR).summary()
    i18n.set_language("TR")
    assert planar_analyze(PLANAR).summary() == tr_before


# --------------------------------------------------------------------------- #
#  İç anahtarlar dilden bağımsız olmalı
# --------------------------------------------------------------------------- #

def test_block_mode_keys_never_change():
    """Blok modu anahtarı renk eşlemesinde kullanılır; çevrilmemelidir."""
    for lang in ("TR", "EN"):
        i18n.set_language(lang)
        res = toppling_analyze(TOPPLING)
        modes = {bl["mode"] for bl in res.blocks}
        assert modes <= set(rtext.BLOCK_MODES), modes


def test_mode_text_translates_but_keys_stay():
    assert rtext.MODE_TEXT("devrilme") == "devrilme"
    i18n.set_language("EN")
    assert rtext.MODE_TEXT("devrilme") == "toppling"
    assert rtext.MODE_TEXT("kayma") == "sliding"
    assert rtext.MODE_TEXT("stabil") == "stable"
    # bilinmeyen anahtar olduğu gibi geri döner
    assert rtext.MODE_TEXT("bilinmeyen") == "bilinmeyen"


def test_failure_mode_text_follows_language():
    assert "İki düzlemde kayma" in analyze(WEDGE).mode
    i18n.set_language("EN")
    assert "Sliding on two planes" in analyze(WEDGE).mode


def test_water_mode_labels():
    assert rtext.WATER_MODE("dry") == "kuru"
    i18n.set_language("EN")
    assert rtext.WATER_MODE("dry") == "dry"
    assert rtext.WATER_MODE("filled") == "filled crack (H&B)"


# --------------------------------------------------------------------------- #
#  Hata ve uyarı metinleri
# --------------------------------------------------------------------------- #

def test_error_messages_are_translated():
    bad = PlanarInput(20, 72, 80, 0, 0, 31, 25, None, "dry", 9.81, 0, 0, 0, 0, 0, 0, 0, False)
    with pytest.raises(ValueError, match="olmalı"):
        planar_analyze(bad)
    i18n.set_language("EN")
    with pytest.raises(ValueError, match="is required"):
        planar_analyze(bad)


def test_warning_prefix_is_translated():
    # yüksek su + güçlü sismik yük: etkin normal kuvvet ≤ 0 uyarısını tetikler
    flooded = PlanarInput(20, 72, 34, 0, 0, 31, 25, 12, "percent", 9.81, 100, 0, 0, 1.5, 0, 0, 0, False)
    res = planar_analyze(flooded)
    assert res.warnings, "bu girdi bir uyarı üretmeli"
    assert res.summary().count("UYARI: ") == len(res.warnings)
    i18n.set_language("EN")
    assert planar_analyze(flooded).summary().count("WARNING: ") == len(res.warnings)


def test_bolt_check_verdict_is_translated():
    T, ang, _ = planar_required_support(PLANAR, 1.5, None, False)
    inp = PlanarInput(20, 72, 34, 0, 0, 31, 25, 6, "percent", 9.81, 100, 0, 0, 0, 0, T, ang, False)
    spec = BoltSpec(150, 76, 800, 2.5, 2.0, 0.5, 1.0, 3.0)
    chk = bolt_check_planar(inp, 1.5, 9.0, ang, spec, 1.5, False)
    assert ("UYGUN" in chk.summary()) or ("YETERSİZ" in chk.summary())
    i18n.set_language("EN")
    assert ("ADEQUATE" in chk.summary()) or ("INADEQUATE" in chk.summary())


# --------------------------------------------------------------------------- #
#  Rapor metinleri
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("mode", ["wedge", "planar", "toppling"])
def test_method_text_exists_in_both_languages(mode):
    tr = METHOD(mode)
    i18n.set_language("EN")
    en = METHOD(mode)
    assert tr and en and tr != en
    assert "Hoek" in tr or "Goodman" in tr
    assert "Hoek" in en or "Goodman" in en


def test_unknown_mode_gives_empty_method_text():
    assert METHOD("nonexistent") == ""


def test_project_labels_cover_every_field():
    for lang in ("TR", "EN"):
        i18n.set_language(lang)
        labels = [PROJECT_LABEL(k) for k in PROJECT_FIELDS]
        assert all(labels), "her alanın bir başlığı olmalı"
        assert len(set(labels)) == len(labels), "başlıklar benzersiz olmalı"
    i18n.set_language("EN")
    assert PROJECT_LABEL("prepared_by") == "Prepared by"
    assert PROJECT_LABEL("doc_no") == "Document No"


def test_percent_format_follows_language():
    assert i18n.pct(93.1) == "%93.10"
    assert i18n.pct(100, 0) == "%100"
    i18n.set_language("EN")
    assert i18n.pct(93.1) == "93.10%"
    assert i18n.pct(100, 0) == "100%"
