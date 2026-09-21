"""
lythos.rockslope — kaya şevi limit denge çekirdeği (Hoek & Bray, Goodman & Bray)

Lythos Kinematic modülünün limit denge hesaplarını yapar; arayüzden bağımsızdır.

Modüller:
  core      : ortak vektör/geometri yardımcıları
  style     : ortak matplotlib stili
  wedge     : tetrahedral kama analizi (Swedge karşılığı) + stereonet
  planar    : düzlemsel kayma (RocPlane karşılığı)
  toppling  : blok devrilmesi, su dahil (RocTopple karşılığı)
  bolts     : bulon karelaj/boy tasarımı ve kapasite kontrolü
  report    : profesyonel PDF rapor
"""
from .core import (unit, plane_normal, down_dip_vector, trend_plunge_vector, vector_to_trend_plunge,
                   intersect_3_planes, polygon_area)
from .wedge import (Joint, Plane, TensionCrack, Water, Seismic, Support, WedgeInput, WedgeGeometry, WedgeResult,
                    SupportResult, build_wedge, analyze, required_support, optimum_support_direction,
                    hoek_bray_short, plot_wedge, plot_stereonet)
from .planar import PlanarInput, PlanarResult, planar_analyze, planar_required_support, plot_planar
from .toppling import TopplingInput, TopplingResult, toppling_analyze, toppling_required_support, plot_toppling
from .bolts import (BoltSpec, BoltPattern, BoltCheck, bolt_pattern_planar, bolt_pattern_wedge,
                    bolt_check_planar, bolt_check_wedge, bolt_options_table, STANDARD_LENGTHS)
from .report import Report, METHOD_TEXT

__version__ = "1.0.0"
