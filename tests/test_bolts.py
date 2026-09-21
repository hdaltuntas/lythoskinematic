"""bolts.py için testler.

bolt_check_wedge içindeki üçgen-içi (nokta-üçgen) testi eskiden `sgn()` kapanışının
ilk parametresini görmezden gelip dıştaki `p` değişkenini kullanması ve bunun bir
`and` ifadesiyle telafi edilmeye çalışılması nedeniyle kırılgandı (bkz. bolts.py
geçmişi). Bu test, düzeltilmiş üçgen-içi testinin kama yüzeyindeki karelaj
noktalarını doğru sınıflandırdığını ve fonksiyonun hatasız çalıştığını doğrular.
"""
import numpy as np
import pytest

from lythoskinematic.rockslope.wedge import WedgeInput, Joint, Plane, required_support
from lythoskinematic.rockslope.bolts import BoltSpec, bolt_check_wedge


@pytest.fixture
def classic_wedge():
    j1 = Joint(dip=45, dipdir=105, friction=35)
    j2 = Joint(dip=70, dipdir=235, friction=35)
    face = Plane(dip=65, dipdir=185)
    upper = Plane(dip=12, dipdir=195)
    return WedgeInput(joint1=j1, joint2=j2, slope_face=face, upper_slope=upper,
                      slope_height=40, unit_weight=25)


def test_bolt_check_wedge_runs_and_classifies_rows(classic_wedge):
    sr = required_support(classic_wedge, target_fs=1.5)
    spec = BoltSpec()
    chk = bolt_check_wedge(classic_wedge, s=2.0, L=8.0, trend=sr.trend, plunge=sr.plunge,
                           spec=spec, target_fs=1.5)
    # yüzeye en az bir bulon sığmalı ve etkin sayı toplam sayıyı aşamaz
    assert chk.n_bolts > 0
    assert 0 <= chk.n_effective <= chk.n_bolts
    # regresyon: bilinen geometri için sabit karelaj sayısı
    assert chk.n_bolts == 211
    assert chk.n_effective == 54
    assert chk.fs > 0 and np.isfinite(chk.fs)


def test_bolt_check_wedge_denser_spacing_fits_more_bolts(classic_wedge):
    spec = BoltSpec()
    sr = required_support(classic_wedge, target_fs=1.5)
    coarse = bolt_check_wedge(classic_wedge, s=3.0, L=8.0, trend=sr.trend, plunge=sr.plunge,
                              spec=spec, target_fs=1.5)
    fine = bolt_check_wedge(classic_wedge, s=1.0, L=8.0, trend=sr.trend, plunge=sr.plunge,
                            spec=spec, target_fs=1.5)
    assert fine.n_bolts > coarse.n_bolts
