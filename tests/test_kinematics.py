"""
Kinematik tarama çekirdeği (lythos/kinematics/) için testler.

Markland kriterleri elle doğrulanabilir sınır durumlarına, kesişim çizgisi ise
limit denge çekirdeğinin (lythos/rockslope/) bağımsız vektör uygulamasına karşı
sınanır — iki ayrı uygulamanın aynı geometriyi vermesi gerekir.
"""
import numpy as np
import pytest

from lythos.kinematics import engine as eng
from lythos.rockslope.core import plane_normal, unit, vector_to_trend_plunge

SLOPE_DIP, SLOPE_DIR, PHI, LATERAL = 72.0, 230.0, 31.0, 20.0


# --------------------------------------------------------------------------- #
#  Düzlemsel kayma (Markland)
# --------------------------------------------------------------------------- #

def test_planar_critical_daylights_and_exceeds_friction():
    # φ < ψp < ψf ve eğim yönü şevle aynı -> kritik
    assert bool(eng.is_planar_critical(45, 230, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))


@pytest.mark.parametrize("dip, dipdir, why", [
    (25, 230, "ψp < φ: sürtünme yeterli"),
    (80, 230, "ψp > ψf: günışığı görmez"),
    (45, 300, "yanal limit dışında"),
])
def test_planar_not_critical(dip, dipdir, why):
    assert not bool(eng.is_planar_critical(dip, dipdir, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL)), why


def test_planar_boundaries_are_inclusive():
    # ψp = φ ve ψp = ψf sınırları kriterin içinde sayılır
    assert bool(eng.is_planar_critical(PHI, SLOPE_DIR, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))
    assert bool(eng.is_planar_critical(SLOPE_DIP, SLOPE_DIR, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))
    assert bool(eng.is_planar_critical(45, SLOPE_DIR + LATERAL, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))
    assert not bool(eng.is_planar_critical(45, SLOPE_DIR + LATERAL + 1, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))


# --------------------------------------------------------------------------- #
#  Kesişim çizgisi — rockslope çekirdeğine karşı çapraz doğrulama
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("d1, dd1, d2, dd2", [
    (45, 105, 70, 235),
    (73, 152, 34, 232),
    (60, 10, 50, 300),
])
def test_intersection_matches_rockslope_core(d1, dd1, d2, dd2):
    plunge, trend = eng.intersection_line(d1, dd1, d2, dd2)

    # bağımsız yol: iki düzlem normalinin vektörel çarpımı (rockslope.core)
    v = np.cross(plane_normal(d1, dd1), plane_normal(d2, dd2))
    if v[2] > 0:
        v = -v
    trend_ref, plunge_ref = vector_to_trend_plunge(unit(v))

    assert plunge == pytest.approx(plunge_ref, abs=1e-9)
    assert trend == pytest.approx(trend_ref, abs=1e-9)


def test_parallel_planes_give_nan_not_crash():
    plunge, trend = eng.intersection_line(45, 120, 45, 120)
    assert np.isnan(plunge) and np.isnan(trend)
    # NaN kesişim kinematik olarak kritik sayılmamalı
    assert not bool(eng.is_wedge_critical(plunge, trend, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))


# --------------------------------------------------------------------------- #
#  Kama ve devrilme kriterleri
# --------------------------------------------------------------------------- #

def test_wedge_critical_requires_daylighting():
    # Şev yönünde, φ'den dik ama görünür şev eğiminden yatık kesişim -> kritik
    assert bool(eng.is_wedge_critical(50, SLOPE_DIR, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))
    # Şev yüzünden dik kesişim günışığı görmez
    assert not bool(eng.is_wedge_critical(85, SLOPE_DIR, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))
    # φ'den yatık kesişim kaymaz
    assert not bool(eng.is_wedge_critical(20, SLOPE_DIR, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))


def test_toppling_goodman_bray_criterion():
    # Kutup plunge'ı = 90 − dip; kriter: 90 − dip <= ψf − φ  => dip >= 90 − (72 − 31) = 49
    back_dir = (SLOPE_DIR + 180.0) % 360.0
    assert bool(eng.is_toppling_critical(70, back_dir, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))
    assert not bool(eng.is_toppling_critical(40, back_dir, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))
    # Şevle aynı yöne eğimli süreksizlik devrilmez (kutbu ters yöne bakar)
    assert not bool(eng.is_toppling_critical(70, SLOPE_DIR, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL))


def test_friction_cone_angle_per_mode():
    assert eng.friction_cone_angle(eng.PLANAR, SLOPE_DIP, PHI) == pytest.approx(PHI)
    assert eng.friction_cone_angle(eng.WEDGE, SLOPE_DIP, PHI) == pytest.approx(90 - PHI)
    assert eng.friction_cone_angle(eng.TOPPLING, SLOPE_DIP, PHI) == pytest.approx(90 - (SLOPE_DIP - PHI))


# --------------------------------------------------------------------------- #
#  Tarama ve kritik bölge
# --------------------------------------------------------------------------- #

LABELS = ["T2", "T1", "E3", "E1", "E2", "J6"]
DIPS = np.array([73.0, 69.0, 34.0, 28.0, 21.0, 50.0])
DIP_DIRS = np.array([152.0, 189.0, 232.0, 104.0, 303.0, 60.0])


def test_screen_planar_flags_expected_set():
    res = eng.screen(LABELS, DIPS, DIP_DIRS, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL, eng.PLANAR)
    assert len(res.items) == len(LABELS)
    names = {it.name for it in res.critical_items}
    # E3 (34/232): φ=31 ≤ 34 ≤ 72 ve |232−230| = 2 ≤ 20  -> tek kritik takım
    assert names == {"E3"}
    assert res.n_critical == 1


def test_screen_wedge_enumerates_all_pairs():
    res = eng.screen(LABELS, DIPS, DIP_DIRS, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL, eng.WEDGE)
    n = len(LABELS)
    assert len(res.items) == n * (n - 1) // 2
    assert all(it.is_pair for it in res.items)


def test_critical_zone_grid_contains_critical_items():
    """Stereonet'te taranan kritik bölge, kritik bulunan kutupları kapsamalı."""
    res = eng.screen(LABELS, DIPS, DIP_DIRS, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL, eng.PLANAR)
    zp, zt = eng.critical_zone_grid(eng.PLANAR, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL, step=1.0)
    for it in res.critical_items:
        pole_plunge, pole_trend = 90.0 - it.value1, (it.value2 + 180.0) % 360.0
        d = np.hypot(zp - pole_plunge, eng.angular_difference(zt, pole_trend))
        assert d.min() < 2.0, f"{it.name} kritik bölge bulutunun dışında kaldı"


# --------------------------------------------------------------------------- #
#  Monte Carlo
# --------------------------------------------------------------------------- #

def test_monte_carlo_without_uncertainty_matches_deterministic():
    """Std.sapma = 0 iken olasılık, deterministik sonucun 0/100 karşılığı olmalı."""
    zeros = np.zeros_like(DIPS)
    det = eng.screen(LABELS, DIPS, DIP_DIRS, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL, eng.PLANAR)
    mc = eng.run_monte_carlo(DIPS, DIP_DIRS, zeros, SLOPE_DIP, SLOPE_DIR, PHI, LATERAL,
                             eng.PLANAR, n_trials=500)
    assert mc.pof == pytest.approx(100.0 if det.n_critical else 0.0)
    for it, p in zip(det.items, mc.item_pof):
        assert p == pytest.approx(100.0 if it.critical else 0.0)


def test_monte_carlo_is_reproducible_and_bounded():
    a = eng.run_monte_carlo(DIPS, DIP_DIRS, np.full_like(DIPS, 3.0), SLOPE_DIP, SLOPE_DIR, PHI,
                            LATERAL, eng.WEDGE, n_trials=2000, seed=7)
    b = eng.run_monte_carlo(DIPS, DIP_DIRS, np.full_like(DIPS, 3.0), SLOPE_DIP, SLOPE_DIR, PHI,
                            LATERAL, eng.WEDGE, n_trials=2000, seed=7)
    assert a.pof == pytest.approx(b.pof)
    assert 0.0 <= a.pof <= 100.0
    assert a.n_fail == b.n_fail <= a.n_trials
    assert np.all((a.item_pof >= 0) & (a.item_pof <= 100))
    # toplam PoF, en yüksek bileşen PoF'undan küçük olamaz (birleşim kuralı)
    assert a.pof >= a.item_pof.max() - 1e-9


def test_monte_carlo_uncertainty_raises_probability():
    """Sınırda duran bir takımda belirsizlik, PoF'u 0 ile 100 arasına taşımalı."""
    dips, dirs = np.array([PHI]), np.array([SLOPE_DIR])      # tam sürtünme sınırında
    mc = eng.run_monte_carlo(dips, dirs, np.array([5.0]), SLOPE_DIP, SLOPE_DIR, PHI, LATERAL,
                             eng.PLANAR, n_trials=4000, seed=3)
    assert 20.0 < mc.pof < 80.0


def test_risk_levels():
    def pof(p):
        return eng.MonteCarloResult(pof=p, n_fail=0, n_trials=1).risk_level()
    assert pof(2.0) == "low"
    assert pof(9.0) == "moderate"
    assert pof(30.0) == "high"
