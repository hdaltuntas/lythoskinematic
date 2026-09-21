"""
Çekirdek hesap modüllerinin (lythoskinematic/rockslope/) bağımsız kapalı-form çözümlere karşı
regresyon testleri. Bunlar README'deki "Doğrulama" bölümünde belgelenen
referans değerlerdir; wedge/planar/toppling üzerinde yapılacak bir değişiklik
bu değerleri bozarsa test burada yakalar.
"""
import numpy as np
import pytest

from lythoskinematic.rockslope.planar import PlanarInput, planar_analyze
from lythoskinematic.rockslope.wedge import WedgeInput, Joint, Plane, Water, analyze, hoek_bray_short
from lythoskinematic.rockslope.toppling import TopplingInput, toppling_analyze


def test_planar_dry_cohesionless_matches_closed_form():
    """c=0, kuru: FS = tanφ / tanψp (Hoek & Bray kapalı-form)."""
    i = PlanarInput(slope_height=30, face_angle=60, plane_angle=35, upper_angle=10,
                     cohesion=0, friction=30, unit_weight=25)
    r = planar_analyze(i)
    expected = np.tan(np.radians(30)) / np.tan(np.radians(35))
    assert r.factor_of_safety == pytest.approx(expected, rel=1e-9)


def test_planar_with_cohesion_and_water_is_finite_and_positive():
    i = PlanarInput(slope_height=20, face_angle=72, plane_angle=34, upper_angle=0,
                     cohesion=25, friction=31, unit_weight=25, tc_distance=6,
                     water_mode="percent", water_percent=50)
    r = planar_analyze(i)
    assert np.isfinite(r.factor_of_safety)
    assert r.factor_of_safety > 0
    assert not r.warnings


@pytest.fixture
def classic_wedge():
    j1 = Joint(dip=45, dipdir=105, friction=35)
    j2 = Joint(dip=70, dipdir=235, friction=35)
    face = Plane(dip=65, dipdir=185)
    upper = Plane(dip=12, dipdir=195)
    return dict(joint1=j1, joint2=j2, slope_face=face, upper_slope=upper,
                slope_height=40, unit_weight=25)


def test_wedge_vector_method_matches_closed_form_dry(classic_wedge):
    inp = WedgeInput(**classic_wedge)
    r = analyze(inp)
    assert r.mode.startswith("İki düzlemde kayma")
    assert r.factor_of_safety == pytest.approx(hoek_bray_short(inp), rel=1e-9)
    # regresyon: bu geometri için bilinen sayısal değer
    assert r.factor_of_safety == pytest.approx(1.7407205230520555, rel=1e-9)


def test_wedge_vector_method_matches_closed_form_filled_water(classic_wedge):
    inp = WedgeInput(**classic_wedge, water=Water(mode="filled"))
    r = analyze(inp)
    assert r.factor_of_safety == pytest.approx(hoek_bray_short(inp), rel=1e-9)
    assert r.factor_of_safety == pytest.approx(0.8024581439219098, rel=1e-9)


def test_toppling_wyllie_mah_chapter9_benchmark():
    """Wyllie & Mah (2004) Böl. 9 örneği: limit dengede gerekli sürtünme açısı φ ≈ 38°."""
    i = TopplingInput(face_angle=56.6, upper_angle=4, disc_dip=60, base_angle=35.8,
                       block_width=10, n_below=10, n_above=6, friction=38.15, unit_weight=25)
    r = toppling_analyze(i)
    assert r.phi_required == pytest.approx(37.6, abs=0.5)
    assert r.fs == pytest.approx(1.0, abs=0.1)
