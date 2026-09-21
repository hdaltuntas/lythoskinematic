"""
Ortak stereonet projeksiyonu (lythos/stereonet.py) için testler.

Bu modül mplstereonet'in yerini aldığı için, projeksiyonun bilinen analitik
değerleri ve limit denge çekirdeğinin vektör yardımcılarıyla tutarlılığı sınanır.
"""
import numpy as np
import pytest

from lythos import stereonet as st
from lythos.rockslope.core import down_dip_vector, plane_normal, trend_plunge_vector


def test_vertical_line_projects_to_centre():
    x, y = st.line_xy(123.0, 90.0)
    assert x == pytest.approx(0.0, abs=1e-12)
    assert y == pytest.approx(0.0, abs=1e-12)


def test_horizontal_line_projects_to_primitive_circle():
    for trend in (0.0, 45.0, 180.0, 359.0):
        x, y = st.line_xy(trend, 0.0)
        assert np.hypot(x, y) == pytest.approx(1.0, abs=1e-12)
    # kuzey yukarı, doğu sağda
    assert st.line_xy(0.0, 0.0) == pytest.approx((0.0, 1.0), abs=1e-12)
    assert st.line_xy(90.0, 0.0) == pytest.approx((1.0, 0.0), abs=1e-12)


def test_equal_area_radius_is_lambert():
    """Schmidt ağı: r = √2·sin((90−plunge)/2), birim daireye ölçeklenmiş."""
    for plunge in (0.0, 15.0, 45.0, 75.0, 90.0):
        r_ref = np.sqrt(2.0) * np.sin(np.radians(90.0 - plunge) / 2.0)
        x, y = st.line_xy(0.0, plunge)
        assert np.hypot(x, y) == pytest.approx(r_ref, abs=1e-12)


def test_equal_angle_radius_is_wulff():
    for plunge in (0.0, 30.0, 60.0, 90.0):
        r_ref = np.tan(np.radians(90.0 - plunge) / 2.0)
        x, y = st.line_xy(0.0, plunge, equal_area=False)
        assert np.hypot(x, y) == pytest.approx(r_ref, abs=1e-12)


def test_pole_of_horizontal_plane_is_centre():
    x, y = st.pole_xy(0.0, 0.0)
    assert np.hypot(x, y) == pytest.approx(0.0, abs=1e-12)


def test_pole_is_90_degrees_from_dip_vector():
    for dip, dipdir in [(34.0, 232.0), (73.0, 152.0), (5.0, 10.0)]:
        n = -plane_normal(dip, dipdir)          # aşağı bakan kutup
        d = down_dip_vector(dip, dipdir)
        assert float(n @ d) == pytest.approx(0.0, abs=1e-12)
        # kutbun plunge'ı 90 − dip olmalı
        _, plunge = st.vector_to_trend_plunge(n)
        assert float(plunge) == pytest.approx(90.0 - dip, abs=1e-9)


def test_great_circle_lies_within_primitive_circle():
    for dip, dipdir in [(0.0, 0.0), (34.0, 232.0), (89.0, 100.0)]:
        xs, ys = st.great_circle(dip, dipdir)
        r = np.hypot(xs, ys)
        assert np.nanmax(r) <= 1.0 + 1e-9
        # eğim vektörü büyük dairenin üzerinde olmalı
        dx, dy = st.stereo_xy(down_dip_vector(dip, dipdir))
        assert np.min(np.hypot(xs - dx, ys - dy)) < 1e-6


def test_great_circle_of_vertical_plane_is_a_diameter():
    xs, ys = st.great_circle(90.0, 90.0)        # doğuya dik eğimli düzlem
    # Doğrultusu kuzey-güney olduğundan izi, x = 0 ekseni üzerindeki çaptır
    assert np.allclose(xs, 0.0, atol=1e-9)
    assert np.nanmax(np.abs(ys)) == pytest.approx(1.0, abs=1e-9)


def test_small_circle_about_vertical_is_a_circle():
    """Düşey eksen etrafında 30°'lik koni, sabit yarıçaplı bir daire vermeli."""
    xs, ys = st.small_circle(0.0, 90.0, 30.0)
    r = np.hypot(xs, ys)
    r = r[np.isfinite(r)]
    expected = np.hypot(*st.line_xy(0.0, 60.0))   # koni yüzeyi plunge = 90 − 30
    assert np.allclose(r, expected, atol=1e-9)


def test_small_circle_clips_upper_hemisphere():
    """Yatay eksen etrafındaki koninin üst yarımküreye taşan kolu NaN olmalı."""
    xs, ys = st.small_circle(0.0, 0.0, 30.0)
    assert np.isnan(xs).any()
    assert np.nanmax(np.hypot(xs, ys)) <= 1.0 + 1e-9


def test_vector_to_trend_plunge_flips_upward_vectors():
    up = trend_plunge_vector(40.0, -20.0)        # yukarı bakan vektör
    trend, plunge = st.vector_to_trend_plunge(up)
    assert float(plunge) == pytest.approx(20.0, abs=1e-9)
    assert float(trend) == pytest.approx(220.0, abs=1e-9)


def test_density_grid_peaks_at_the_cluster():
    """Yoğunluk kümenin merkezinde doruğa çıkmalı, karşı tarafta sıfır olmalı."""
    rng = np.random.default_rng(0)
    trend = rng.normal(120.0, 3.0, 200)
    plunge = rng.normal(40.0, 3.0, 200)
    X, Y, Z = st.density_grid(trend, plunge, gridsize=101)

    cx, cy = st.line_xy(120.0, 40.0)
    centre = np.nanargmin(np.hypot(X - cx, Y - cy))
    peak = np.nanmax(Z)
    assert peak > 50.0                                  # kümenin yarısından fazlası tek koninin içinde
    assert Z.flat[centre] >= 0.98 * peak                # küme merkezi doruğun içinde

    # kürenin karşı tarafında ölçüm yok
    ox, oy = st.line_xy(300.0, 40.0)
    opposite = np.nanargmin(np.hypot(X - ox, Y - oy))
    assert Z.flat[opposite] == 0.0

    # doruk, sayım konisinin yarıçapı kadar bir bölgede kalmalı
    k = np.nanargmax(Z)
    assert np.hypot(float(X.flat[k]) - cx, float(Y.flat[k]) - cy) < 0.25


def test_density_grid_is_nan_outside_primitive_circle():
    X, Y, Z = st.density_grid(np.array([10.0]), np.array([45.0]), gridsize=41)
    outside = np.hypot(X, Y) > 1.0
    assert np.all(np.isnan(Z[outside]))


def test_density_grid_handles_empty_input():
    assert st.density_grid([], []) is None
