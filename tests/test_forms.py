"""
Girdi şeması ve okuyucuları (lythoskinematic/forms.py) için testler.

Şema arayüzün tek kaynağıdır: bir alan buradan düşerse form eksilir, anahtarı
değişirse kaydedilmiş girdi dosyaları okunmaz olur. Bu yüzden hem şemanın
bütünlüğü hem de varsayılanların doğrulanmış sonuçları üretmesi sabitlenir.
"""
import pytest

from lythoskinematic import forms, i18n
from lythoskinematic.rockslope import analyze, planar_analyze, toppling_analyze


@pytest.fixture(autouse=True)
def turkish():
    i18n.set_language("TR")
    yield
    i18n.set_language("TR")


# --------------------------------------------------------------------------- #
#  Şema
# --------------------------------------------------------------------------- #

def test_schema_covers_every_mode():
    schema = forms.schema()
    assert set(schema) == {"screening", "equilibrium", "bolts", "report"}
    assert set(schema["equilibrium"]) == set(forms.MODES)
    for mode in forms.MODES:
        groups = schema["equilibrium"][mode]["groups"]
        assert groups and all(g["fields"] for g in groups)


def test_every_field_has_a_label_and_a_unique_key():
    seen = {}
    groups = list(forms.screening_groups()) + list(forms.bolt_groups()) + list(forms.report_groups())
    for mode in forms.MODES:
        groups += forms.equilibrium_groups(mode)
    for group in groups:
        for field in group.fields:
            assert field.label, f"{field.key} etiketsiz"
            # aynı anahtar iki farklı etikete bağlanmamalı
            assert seen.setdefault(field.key, field.label) == field.label, field.key


def test_schema_is_translated():
    tr = forms.schema()["equilibrium"]["planar"]["groups"][0]["title"]
    i18n.set_language("EN")
    en = forms.schema()["equilibrium"]["planar"]["groups"][0]["title"]
    assert tr != en
    assert "Slope" in en


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        forms.equilibrium_groups("spiral")


def test_defaults_contain_every_field():
    values = forms.defaults()
    for mode in forms.MODES:
        for group in forms.equilibrium_groups(mode):
            for field in group.fields:
                assert field.key in values
    assert isinstance(values["joints"], list) and values["joints"]


# --------------------------------------------------------------------------- #
#  Okuyucular
# --------------------------------------------------------------------------- #

def test_defaults_reproduce_the_validated_results():
    """Varsayılan girdiler, doğrulama bölümünde belgelenen sonuçları vermeli."""
    v = forms.defaults()
    assert analyze(forms.read_wedge(v)).factor_of_safety == pytest.approx(1.696, abs=5e-4)
    assert planar_analyze(forms.read_planar(v)).factor_of_safety == pytest.approx(0.891, abs=5e-4)
    assert toppling_analyze(forms.read_toppling(v)).fs == pytest.approx(1.020, abs=5e-3)


def test_missing_and_blank_values_fall_back_to_defaults():
    inp = forms.read_planar({"p_H": 25, "p_face": 70, "p_plane": 35, "p_phi": 30, "p_gw": ""})
    assert inp.slope_height == 25
    assert inp.unit_weight == 0.0          # verilmeyen alan sıfırdır, hata değil
    assert inp.gamma_w == 9.81             # boş bırakılan alan varsayılana düşer


def test_optional_fields_become_none():
    assert forms._maybe({"x": ""}, "x") is None
    assert forms._maybe({}, "x") is None
    assert forms._maybe({"x": "12.5"}, "x") == 12.5


def test_support_force_without_direction_is_rejected():
    v = forms.defaults()
    v["T"] = 500.0
    v["T_trend"] = None
    with pytest.raises(ValueError, match="trend"):
        forms.read_wedge(v)

    v = forms.defaults()
    v["p_T"] = 500.0
    v["p_theta"] = ""
    with pytest.raises(ValueError, match="θ"):
        forms.read_planar(v)


def test_scale_value_is_ignored_in_height_mode():
    v = forms.defaults()
    v["scale_mode"], v["scale_value"] = "height", 1234
    assert forms.read_wedge(v).scale_value is None
    v["scale_mode"] = "volume"
    assert forms.read_wedge(v).scale_value == 1234


def test_read_input_dispatches_by_mode():
    v = forms.defaults()
    assert forms.read_input("wedge", v).slope_height == v["H"]
    assert forms.read_input("planar", v).slope_height == v["p_H"]
    assert forms.read_input("toppling", v).block_width == v["t_dx"]
    with pytest.raises(ValueError):
        forms.read_input("spiral", v)


# --------------------------------------------------------------------------- #
#  Süreksizlik tablosu
# --------------------------------------------------------------------------- #

def test_read_joints_skips_incomplete_rows():
    labels, dips, dirs, stds = forms.read_joints({"joints": [
        {"label": "A", "dip": 40, "dipdir": 200, "std": 2},
        {"label": "", "dip": 40, "dipdir": 200, "std": 2},        # etiketsiz
        {"label": "C", "dip": None, "dipdir": 200, "std": 2},     # eksik
        {"label": "D", "dip": "abc", "dipdir": 200, "std": 2},    # sayı değil
        {"label": "E", "dip": 30, "dipdir": 100, "std": 1},
    ]})
    assert labels == ["A", "E"]
    assert dips == [40.0, 30.0] and dirs == [200.0, 100.0] and stds == [2.0, 1.0]


def test_read_joints_handles_missing_table():
    assert forms.read_joints({}) == ([], [], [], [])


# --------------------------------------------------------------------------- #
#  Taramadan limit dengeye aktarım
# --------------------------------------------------------------------------- #

def test_handoff_planar_sets_plane_face_and_friction():
    mode, values = forms.handoff_values({"mode": "planar", "dip": 34.0, "dipdir": 232.0,
                                         "slope_dip": 72.0, "slope_dir": 230.0, "friction": 31.0})
    assert mode == "planar"
    assert values == {"p_plane": 34.0, "p_face": 72.0, "p_phi": 31.0}


def test_handoff_wedge_sets_both_joints():
    mode, values = forms.handoff_values({"mode": "wedge", "j1": (73.0, 152.0), "j2": (34.0, 232.0),
                                         "slope_dip": 60.0, "slope_dir": 230.0, "friction": 25.0})
    assert mode == "wedge"
    assert values["j1_dip"] == 73.0 and values["j2_dd"] == 232.0
    assert values["j1_phi"] == values["j2_phi"] == 25.0
    assert values["face_dip"] == 60.0


def test_handoff_clamps_angles_to_valid_ranges():
    """Şev yüzü 90° ve φ 45°'nin üstü, ilgili modun geçerli aralığına çekilmeli."""
    _, values = forms.handoff_values({"mode": "toppling", "dip": 70.0, "dipdir": 50.0,
                                      "slope_dip": 90.0, "slope_dir": 230.0, "friction": 50.0})
    assert values["t_face"] == 89.9
    assert values["t_phi"] == 44.9

    _, values = forms.handoff_values({"mode": "planar", "dip": 40.0, "dipdir": 230.0,
                                      "slope_dip": 90.0, "slope_dir": 230.0, "friction": 31.0})
    assert values["p_face"] == 89.9


def test_handoff_result_is_a_usable_input():
    """Aktarılan değerler doğrudan analiz edilebilmeli."""
    v = forms.defaults()
    _, changed = forms.handoff_values({"mode": "wedge", "j1": (45.0, 105.0), "j2": (70.0, 235.0),
                                       "slope_dip": 65.0, "slope_dir": 185.0, "friction": 30.0})
    v.update(changed)
    result = analyze(forms.read_wedge(v))
    assert result.factor_of_safety > 0


def test_project_info_maps_prefixed_fields():
    info = forms.project_info({"rp_project": "A", "rp_location": "", "rp_doc_no": "X-1"})
    assert info["project"] == "A"
    assert info["location"] == "—"            # boş alan tire olur
    assert info["doc_no"] == "X-1"
    assert "date" not in info                 # tarih rapor sırasında konur
