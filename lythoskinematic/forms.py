"""
lythoskinematic.forms — girdi şeması ve okuyucuları.

Her analiz modunun alanları burada bir kez tanımlanır: anahtar, çift dilli
etiket, birim, aralık ve varsayılan değer. Arayüz formlarını bu şemadan üretir,
sunucu da gelen değerleri buradaki okuyucularla çekirdek veri yapılarına
çevirir. Böylece etiketler ile hesap arasında ikinci bir kopya oluşmaz.

Alan anahtarları (``j1_dip``, ``p_H``, ``t_face``, ``b_cap``, ``rp_project`` …)
kalıcıdır: kaydedilen JSON girdi dosyaları sürümler arasında okunabilir kalır.

Bu modül Qt'den ve HTTP'den bağımsızdır; doğrudan test edilebilir.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .i18n import T as _tr
from .rockslope import (BoltSpec, Joint, Plane, PlanarInput, Seismic, Support, TensionCrack,
                        TopplingInput, Water, WedgeInput)
from .rockslope.report import PROJECT_FIELDS, PROJECT_LABEL

#: Limit denge modlarının anahtarları
MODES = ("wedge", "planar", "toppling")

#: Kinematik tarama mod indeksleri (lythoskinematic.kinematics.engine ile aynı)
SCREENING_MODES = ("planar", "wedge", "toppling")


# --------------------------------------------------------------------------- #
#  Şema veri yapıları
# --------------------------------------------------------------------------- #

@dataclass
class Field:
    """Tek bir girdi alanı."""
    key: str
    label: str
    kind: str = "number"                     # number | text | check | select
    default: Any = 0.0
    unit: str = ""
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    decimals: int = 2
    placeholder: str = ""
    options: List[Dict[str, str]] = field(default_factory=list)
    note: str = ""
    optional: bool = False                   # boş bırakılabilir (boş = otomatik)

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in ("", None, [], 0.0) or k in
                ("key", "label", "kind", "default", "decimals")}


@dataclass
class Group:
    """Başlıklı bir alan kümesi."""
    title: str
    fields: List[Field]
    note: str = ""

    def to_dict(self) -> dict:
        d = {"title": self.title, "fields": [f.to_dict() for f in self.fields]}
        if self.note:
            d["note"] = self.note
        return d


def _num(key, label, default, lo=None, hi=None, unit="", dec=2, step=None, note=""):
    return Field(key, label, "number", default, unit, lo, hi, step, dec, note=note)


def _opt(key, label, placeholder, unit="", note=""):
    return Field(key, label, "number", None, unit, placeholder=placeholder, optional=True, note=note)


def _check(key, label, default=False):
    return Field(key, label, "check", default)


def _select(key, label, default, options):
    return Field(key, label, "select", default,
                 options=[{"value": v, "label": t} for v, t in options])


# --------------------------------------------------------------------------- #
#  Kinematik tarama
# --------------------------------------------------------------------------- #

#: Tabloya ilk açılışta konan örnek süreksizlik takımları
DEFAULT_JOINTS = [
    {"label": "T2", "dip": 73, "dipdir": 152, "std": 2.5},
    {"label": "T1", "dip": 69, "dipdir": 189, "std": 3.0},
    {"label": "E3", "dip": 34, "dipdir": 232, "std": 2.0},
    {"label": "E1", "dip": 28, "dipdir": 104, "std": 2.5},
    {"label": "E2", "dip": 21, "dipdir": 303, "std": 2.0},
    {"label": "J6", "dip": 50, "dipdir": 60, "std": 3.0},
]


def screening_groups() -> List[Group]:
    """Kinematik tarama girdi şeması."""
    return [
        Group(_tr("Şev ve malzeme parametreleri", "Slope and material parameters"), [
            _num("slope_dip", _tr("Şev eğimi (dip)", "Slope dip"), 72, 0, 90, "°", 1),
            _num("slope_dir", _tr("Şev eğim yönü (dip dir)", "Slope dip direction"), 230, 0, 360, "°", 1),
            _num("friction", _tr("Sürtünme açısı φ", "Friction angle φ"), 31, 0, 90, "°", 1),
            _num("lateral", _tr("Yanal sınır limiti", "Lateral limit"), 20, 0, 90, "±°", 1),
            _select("mode", _tr("Analiz türü", "Analysis type"), "planar", [
                ("planar", _tr("Düzlemsel kayma", "Planar sliding")),
                ("wedge", _tr("Kama kayması", "Wedge sliding")),
                ("toppling", _tr("Devrilme (eğilme)", "Flexural toppling")),
            ]),
        ]),
        Group(_tr("Monte Carlo", "Monte Carlo"), [
            _num("trials", _tr("Deneme sayısı", "Number of trials"), 5000, 100, 200000, "", 0, 1000),
            _check("zone", _tr("Kritik bölgeyi stereonette göster", "Show critical zone on the stereonet"), True),
            _check("density", _tr("Kutup yoğunluğu konturu", "Pole density contour"), True),
        ], note=_tr("Std. sapma hem eğime hem eğim yönüne normal dağılım olarak uygulanır.",
                    "Std. dev is applied as a normal distribution to both dip and dip direction.")),
    ]


# --------------------------------------------------------------------------- #
#  Limit denge — kama
# --------------------------------------------------------------------------- #

def _wedge_groups() -> List[Group]:
    groups = []
    for j, (dip, dd, c, phi) in (("j1", (45, 105, 24, 20)), ("j2", (70, 235, 48, 30))):
        groups.append(Group(f"{_tr('Eklem', 'Joint')} {j[-1]}", [
            _num(f"{j}_dip", "Dip", dip, 0, 90, "°", 1),
            _num(f"{j}_dd", "Dip dir", dd, 0, 360, "°", 1),
            _num(f"{j}_c", _tr("Kohezyon c", "Cohesion c"), c, 0, 1e5, "kPa", 1),
            _num(f"{j}_phi", _tr("Sürtünme açısı φ", "Friction angle φ"), phi, 0, 89, "°", 1),
        ]))
    groups += [
        Group(_tr("Şev geometrisi", "Slope geometry"), [
            _num("face_dip", _tr("Şev yüzü dip", "Slope face dip"), 65, 1, 90, "°", 1),
            _num("face_dd", _tr("Şev yüzü dip dir", "Slope face dip dir"), 185, 0, 360, "°", 1),
            _num("up_dip", _tr("Üst şev dip", "Upper slope dip"), 12, 0, 89, "°", 1),
            _num("up_dd", _tr("Üst şev dip dir", "Upper slope dip dir"), 195, 0, 360, "°", 1),
            _num("H", _tr("Şev yüksekliği", "Slope height"), 40, 0.1, 1e4, "m"),
            _num("gamma", _tr("Birim hacim ağırlığı γ", "Unit weight γ"), 25, 1, 40, "kN/m³"),
            _select("scale_mode", _tr("Kamayı ölçekle", "Scale the wedge"), "height", [
                ("height", _tr("Şev yüksekliği (maks. kama)", "Slope height (max. wedge)")),
                ("crest_length", _tr("Tepe uzunluğu", "Crest length")),
                ("bench_width", _tr("Basamak genişliği", "Bench width")),
                ("volume", _tr("Kama hacmi", "Wedge volume")),
                ("weight", _tr("Kama ağırlığı", "Wedge weight")),
            ]),
            _opt("scale_value", _tr("Ölçek değeri", "Scale value"), _tr("kullanılmıyor", "not used")),
        ]),
        Group(_tr("Çekme çatlağı", "Tension crack"), [
            _check("tc_on", _tr("Çekme çatlağı var", "Tension crack present"), False),
            _num("tc_dip", "Dip", 70, 1, 90, "°", 1),
            _num("tc_dd", "Dip dir", 165, 0, 360, "°", 1),
            _num("tc_L", _tr("Tepeden mesafe", "Distance from crest"), 8, 0, 1e4, "m"),
        ]),
        Group(_tr("Su basıncı", "Water pressure"), [
            _select("water_mode", _tr("Model", "Model"), "dry", [
                ("dry", _tr("Kuru", "Dry")),
                ("filled", _tr("Dolu çatlak (Hoek & Bray)", "Filled crack (Hoek & Bray)")),
                ("percent", _tr("Yüzde dolu", "Percent filled")),
                ("custom", _tr("Özel basınç", "Custom pressure")),
            ]),
            _num("gw", "γw", 9.81, 1, 15, "kN/m³"),
            _num("w_pct", _tr("Doluluk", "Filling"), 100, 0, 100, "%", 0),
            _num("u1", "u J1", 0, 0, 1e5, "kPa", 1),
            _num("u2", "u J2", 0, 0, 1e5, "kPa", 1),
            _num("ut", _tr("u çatlak", "u crack"), 0, 0, 1e5, "kPa", 1),
        ]),
        Group(_tr("Sismik yük (pseudo-statik)", "Seismic load (pseudo-static)"), [
            _num("ah", _tr("Katsayı α", "Coefficient α"), 0, 0, 2, "", 3, 0.05),
            _opt("s_trend", "Trend", _tr("şev yönü", "slope direction"), "°"),
            _num("s_plunge", "Plunge", 0, -90, 90, "°", 1),
        ]),
        Group(_tr("Destek (bulon / ankraj)", "Support (bolt / anchor)"), [
            _num("T", _tr("Kuvvet T", "Force T"), 0, 0, 1e9, "kN", 1),
            _num("FS_target", _tr("Hedef FS", "Target FS"), 1.5, 1, 5, "", 2, 0.1),
            _opt("T_trend", "Trend", _tr("optimum", "optimum"), "°"),
            _opt("T_plunge", "Plunge", _tr("optimum", "optimum"), "°"),
            _check("T_passive", _tr("Pasif (varsayılan aktif)", "Passive (active by default)"), False),
        ]),
    ]
    return groups


# --------------------------------------------------------------------------- #
#  Limit denge — düzlemsel
# --------------------------------------------------------------------------- #

def _planar_groups() -> List[Group]:
    return [
        Group(_tr("Şev ve kayma düzlemi (2D kesit, 1 m)", "Slope and sliding plane (2D section, 1 m)"), [
            _num("p_H", _tr("Şev yüksekliği H", "Slope height H"), 20, 0.1, 1e4, "m"),
            _num("p_face", _tr("Şev yüzü ψf", "Slope face ψf"), 72, 1, 89.9, "°", 1),
            _num("p_plane", _tr("Kayma düzlemi ψp", "Sliding plane ψp"), 34, 0.1, 89, "°", 1),
            _num("p_upper", _tr("Üst şev ψs", "Upper slope ψs"), 0, -30, 60, "°", 1),
            _num("p_c", _tr("Kohezyon c", "Cohesion c"), 0, 0, 1e5, "kPa", 1),
            _num("p_phi", _tr("Sürtünme açısı φ", "Friction angle φ"), 31, 0, 89, "°", 1),
            _num("p_gamma", _tr("Birim hacim ağırlığı γ", "Unit weight γ"), 25, 1, 40, "kN/m³"),
        ]),
        Group(_tr("Çekme çatlağı", "Tension crack"), [
            _check("p_tc_on", _tr("Çekme çatlağı var", "Tension crack present"), True),
            _num("p_tc_b", _tr("Tepeden yatay mesafe b", "Horizontal distance from crest b"),
                 6, -1e4, 1e4, "m"),
        ], note=_tr("b &lt; 0: çatlak şev yüzünde", "b &lt; 0: crack on the slope face")),
        Group(_tr("Su basıncı", "Water pressure"), [
            _select("p_water", _tr("Model", "Model"), "dry", [
                ("dry", _tr("Kuru", "Dry")),
                ("percent", _tr("Çatlak % dolu (Hoek & Bray)", "Crack % filled (Hoek & Bray)")),
                ("custom", _tr("Özel basınç", "Custom pressure")),
            ]),
            _num("p_gw", "γw", 9.81, 1, 15, "kN/m³"),
            _num("p_wpct", _tr("Doluluk", "Filling"), 100, 0, 100, "%", 0),
            _num("p_up", _tr("u düzlem", "u plane"), 0, 0, 1e5, "kPa", 1),
            _num("p_ut", _tr("u çatlak", "u crack"), 0, 0, 1e5, "kPa", 1),
        ]),
        Group(_tr("Sismik yük (pseudo-statik)", "Seismic load (pseudo-static)"), [
            _num("p_ah", _tr("αh (yatay)", "αh (horizontal)"), 0, 0, 2, "", 3, 0.05),
            _num("p_av", _tr("αv (aşağı +)", "αv (down +)"), 0, -1, 1, "", 3, 0.05),
        ]),
        Group(_tr("Destek (kN/m)", "Support (kN/m)"), [
            _num("p_T", _tr("Kuvvet T", "Force T"), 0, 0, 1e7, "kN/m", 1),
            _num("p_FS", _tr("Hedef FS", "Target FS"), 1.5, 1, 5, "", 2, 0.1),
            _opt("p_theta", _tr("Açı θ (aşağı +)", "Angle θ (down +)"), _tr("optimum", "optimum"), "°"),
            _check("p_passive", _tr("Pasif", "Passive"), False),
        ], note=_tr("θ boş: optimum açı tan(ψp+θ) = tanφ/FS",
                    "θ empty: optimum angle tan(ψp+θ) = tanφ/FS")),
    ]


# --------------------------------------------------------------------------- #
#  Limit denge — devrilme
# --------------------------------------------------------------------------- #

def _toppling_groups() -> List[Group]:
    return [
        Group(_tr("Blok devrilme geometrisi (Goodman & Bray)",
                  "Block toppling geometry (Goodman & Bray)"), [
            _num("t_face", _tr("Şev yüzü ψf", "Slope face ψf"), 56.6, 1, 89.9, "°", 1),
            _num("t_upper", _tr("Üst şev ψs", "Upper slope ψs"), 4, -30, 60, "°", 1),
            _num("t_disc", _tr("Süreksizlik ψd", "Discontinuity ψd"), 60, 1, 89.9, "°", 1),
            _num("t_base", _tr("Taban genel eğimi ψb", "Overall base angle ψb"), 35.8, 0, 89, "°", 1),
            _num("t_dx", _tr("Blok genişliği Δx", "Block width Δx"), 10, 0.01, 1e3, "m"),
            _num("t_gamma", _tr("Birim hacim ağırlığı γ", "Unit weight γ"), 25, 1, 40, "kN/m³"),
            _num("t_nb", _tr("Blok sayısı (tepe altı)", "Blocks below crest"), 10, 1, 500, "", 0, 1),
            _num("t_na", _tr("Blok sayısı (tepe üstü)", "Blocks above crest"), 6, 0, 500, "", 0, 1),
            _num("t_phi", _tr("Sürtünme açısı φ", "Friction angle φ"), 38.15, 0, 44.9, "°"),
        ], note=_tr("ψp = 90 − ψd (blok tabanı eğimi), ψb ≥ ψp",
                    "ψp = 90 − ψd (block base angle), ψb ≥ ψp")),
        Group(_tr("Su ve sismik yük", "Water and seismic load"), [
            _num("t_water", _tr("Eklem su doluluğu", "Joint water filling"), 0, 0, 100, "%", 0),
            _num("t_gw", "γw", 9.81, 1, 15, "kN/m³"),
            _num("t_ah", _tr("Yatay αh", "Horizontal αh"), 0, 0, 2, "", 3, 0.05),
        ]),
        Group(_tr("Topuk ankrajı (kN/m)", "Toe anchor (kN/m)"), [
            _num("t_T", _tr("Kuvvet T", "Force T"), 0, 0, 1e7, "kN/m", 1),
            _num("t_delta", _tr("Açı δ (aşağı +)", "Angle δ (down +)"), 0, -60, 60, "°", 1),
            _opt("t_hT", _tr("Tabandan yükseklik", "Height above base"), "y1/2", "m"),
            _num("t_FS", _tr("Hedef FS", "Target FS"), 1.3, 1, 5, "", 2, 0.1),
        ]),
    ]


# --------------------------------------------------------------------------- #
#  Bulon tasarımı ve rapor künyesi
# --------------------------------------------------------------------------- #

def bolt_groups() -> List[Group]:
    return [Group(_tr("Bulon karelaj / boy tasarımı", "Bolt spacing / length design"), [
        _num("b_cap", _tr("Bulon kapasitesi", "Bolt capacity"), 150, 1, 1e4, "kN", 0),
        _num("b_dia", _tr("Delik çapı", "Hole diameter"), 76, 20, 300, "mm", 0),
        _num("b_bond", _tr("Aderans τb", "Bond strength τb"), 800, 50, 1e4, "kPa", 0),
        _num("b_fsb", _tr("FS kök", "FS bond"), 2.5, 1, 5, "", 1),
        _num("b_minb", _tr("Min. kök boyu", "Min. bond length"), 2.0, 0, 10, "m"),
        _num("b_extra", _tr("Baş payı", "Head allowance"), 0.5, 0, 3, "m"),
        _num("b_smin", _tr("Aralık s min", "Spacing s min"), 1.0, 0.25, 10, "m"),
        _num("b_smax", _tr("Aralık s maks", "Spacing s max"), 3.0, 0.25, 10, "m"),
    ], note=_tr("Sıra: Gerekli Destek → Bulon Önerisi → seçim → Bulon Kontrol",
                "Order: Required Support → Bolt Recommendation → select → Bolt Check"))]


def report_groups() -> List[Group]:
    fields = [Field("rp_" + key, PROJECT_LABEL(key), "text", "")
              for key in PROJECT_FIELDS if key not in ("date", "revision")]
    fields.append(Field("rp_note", _tr("Değerlendirme notu", "Assessment note"), "text", ""))
    return [Group(_tr("Rapor bilgileri", "Report information"), fields)]


# --------------------------------------------------------------------------- #
#  Şema toplayıcı
# --------------------------------------------------------------------------- #

def equilibrium_groups(mode: str) -> List[Group]:
    """Bir limit denge modunun girdi şeması."""
    builders = {"wedge": _wedge_groups, "planar": _planar_groups, "toppling": _toppling_groups}
    if mode not in builders:
        raise ValueError(f"unknown mode: {mode}")
    return builders[mode]()


def schema() -> dict:
    """Arayüzün form üretmek için kullandığı tam şema (seçili dilde)."""
    return {
        "screening": {
            "groups": [g.to_dict() for g in screening_groups()],
            "joints": DEFAULT_JOINTS,
            "columns": [
                {"key": "label", "label": _tr("Etiket", "Label"), "kind": "text"},
                {"key": "dip", "label": _tr("Dip (°)", "Dip (°)"), "kind": "number"},
                {"key": "dipdir", "label": _tr("Dip dir (°)", "Dip dir (°)"), "kind": "number"},
                {"key": "std", "label": _tr("Std. sapma (°)", "Std. dev (°)"), "kind": "number"},
            ],
        },
        "equilibrium": {
            mode: {"groups": [g.to_dict() for g in equilibrium_groups(mode)]} for mode in MODES
        },
        "bolts": {"groups": [g.to_dict() for g in bolt_groups()]},
        "report": {"groups": [g.to_dict() for g in report_groups()]},
    }


def defaults() -> Dict[str, Any]:
    """Tüm alanların varsayılan değerleri (düz sözlük)."""
    values: Dict[str, Any] = {}
    groups = list(screening_groups()) + list(bolt_groups()) + list(report_groups())
    for mode in MODES:
        groups += equilibrium_groups(mode)
    for group in groups:
        for f in group.fields:
            values[f.key] = f.default
    values["joints"] = [dict(j) for j in DEFAULT_JOINTS]
    return values


# --------------------------------------------------------------------------- #
#  Okuyucular: düz değer sözlüğü -> çekirdek veri yapıları
# --------------------------------------------------------------------------- #

def _f(values: dict, key: str, default: float = 0.0) -> float:
    """Sayısal alan; boş/eksik değer varsayılana düşer."""
    v = values.get(key, default)
    if v is None or v == "":
        return default
    return float(v)


def _maybe(values: dict, key: str) -> Optional[float]:
    """Boş bırakılabilen sayısal alan; boş ise None."""
    v = values.get(key)
    if v is None or v == "":
        return None
    return float(v)


def _b(values: dict, key: str) -> bool:
    return bool(values.get(key, False))


def read_wedge(v: dict) -> WedgeInput:
    """Kama girdisi."""
    tc = TensionCrack(_f(v, "tc_dip"), _f(v, "tc_dd"), _f(v, "tc_L")) if _b(v, "tc_on") else None
    water = Water(v.get("water_mode", "dry"), _f(v, "gw", 9.81), _f(v, "w_pct", 100),
                  _f(v, "u1"), _f(v, "u2"), _f(v, "ut"))
    seismic = Seismic(_f(v, "ah"), _maybe(v, "s_trend"), _f(v, "s_plunge"))
    T = _f(v, "T")
    trend, plunge = _maybe(v, "T_trend"), _maybe(v, "T_plunge")
    if T > 0 and (trend is None or plunge is None):
        raise ValueError(_tr("Destek kuvveti > 0 için trend ve plunge girilmeli "
                             "(veya 'Gerekli Destek' ile otomatik doldurun).",
                             "Trend and plunge are required when the support force is > 0 "
                             "(or let 'Required Support' fill them in)."))
    support = Support(T, trend or 0.0, plunge or 0.0, _b(v, "T_passive"))
    mode = v.get("scale_mode", "height")
    return WedgeInput(
        Joint(_f(v, "j1_dip"), _f(v, "j1_dd"), _f(v, "j1_c"), _f(v, "j1_phi")),
        Joint(_f(v, "j2_dip"), _f(v, "j2_dd"), _f(v, "j2_c"), _f(v, "j2_phi")),
        Plane(_f(v, "face_dip"), _f(v, "face_dd")), Plane(_f(v, "up_dip"), _f(v, "up_dd")),
        _f(v, "H"), _f(v, "gamma"), tc, water, seismic, support,
        scale_mode=mode, scale_value=None if mode == "height" else _maybe(v, "scale_value"))


def read_planar(v: dict) -> PlanarInput:
    """Düzlemsel kayma girdisi."""
    T = _f(v, "p_T")
    theta = _maybe(v, "p_theta")
    if T > 0 and theta is None:
        raise ValueError(_tr("Destek kuvveti > 0 için açı θ girilmeli "
                             "(veya 'Gerekli Destek' ile otomatik doldurun).",
                             "The angle θ is required when the support force is > 0 "
                             "(or let 'Required Support' fill it in)."))
    return PlanarInput(
        _f(v, "p_H"), _f(v, "p_face"), _f(v, "p_plane"), _f(v, "p_upper"),
        _f(v, "p_c"), _f(v, "p_phi"), _f(v, "p_gamma"),
        _f(v, "p_tc_b") if _b(v, "p_tc_on") else None,
        v.get("p_water", "dry"), _f(v, "p_gw", 9.81), _f(v, "p_wpct", 100),
        _f(v, "p_up"), _f(v, "p_ut"), _f(v, "p_ah"), _f(v, "p_av"),
        T, theta or 0.0, _b(v, "p_passive"))


def read_toppling(v: dict) -> TopplingInput:
    """Blok devrilme girdisi."""
    return TopplingInput(
        _f(v, "t_face"), _f(v, "t_upper"), _f(v, "t_disc"), _f(v, "t_base"), _f(v, "t_dx"),
        int(_f(v, "t_nb", 1)), int(_f(v, "t_na")), _f(v, "t_phi"), _f(v, "t_gamma"),
        _f(v, "t_water"), _f(v, "t_gw", 9.81), _f(v, "t_ah"),
        _f(v, "t_T"), _f(v, "t_delta"), _maybe(v, "t_hT"))


def read_bolt_spec(v: dict) -> BoltSpec:
    """Bulon tasarım parametreleri."""
    return BoltSpec(_f(v, "b_cap", 150), _f(v, "b_dia", 76), _f(v, "b_bond", 800),
                    _f(v, "b_fsb", 2.5), _f(v, "b_minb", 2.0), _f(v, "b_extra", 0.5),
                    _f(v, "b_smin", 1.0), _f(v, "b_smax", 3.0))


READERS = {"wedge": read_wedge, "planar": read_planar, "toppling": read_toppling}


def read_input(mode: str, values: dict):
    """Mod adına göre doğru okuyucuyu çağırır."""
    if mode not in READERS:
        raise ValueError(f"unknown mode: {mode}")
    return READERS[mode](values)


def read_joints(values: dict) -> Tuple[List[str], List[float], List[float], List[float]]:
    """Tarama tablosundan (etiketler, dip, dip dir, std); bozuk satırlar atlanır."""
    labels, dips, dirs, stds = [], [], [], []
    for row in values.get("joints", []) or []:
        try:
            dip = float(row.get("dip"))
            dipdir = float(row.get("dipdir"))
            std = float(row.get("std", 0.0))
        except (TypeError, ValueError):
            continue
        label = str(row.get("label", "")).strip()
        if not label:
            continue
        labels.append(label); dips.append(dip); dirs.append(dipdir); stds.append(std)
    return labels, dips, dirs, stds


def project_info(values: dict) -> Dict[str, str]:
    """Rapor künyesi: 'rp_' önekli alanlardan kanonik anahtarlara."""
    return {key: (values.get("rp_" + key) or "—") for key in PROJECT_FIELDS
            if key not in ("date", "revision")}


# --------------------------------------------------------------------------- #
#  Kinematik taramadan limit dengeye aktarım
# --------------------------------------------------------------------------- #

def handoff_values(payload: dict) -> Tuple[str, Dict[str, float]]:
    """Kritik tarama sonucunu limit denge girdilerine çevirir.

    Döndürür: (limit denge modu, atanacak alanlar). Sürtünme açısı her modda
    taramada kullanılan değerle eşitlenir.
    """
    mode = payload["mode"]
    phi = float(payload["friction"])
    face_dip, face_dd = float(payload["slope_dip"]), float(payload["slope_dir"])

    if mode == "wedge":
        (d1, dd1), (d2, dd2) = payload["j1"], payload["j2"]
        return "wedge", {"j1_dip": d1, "j1_dd": dd1, "j1_phi": phi,
                         "j2_dip": d2, "j2_dd": dd2, "j2_phi": phi,
                         "face_dip": face_dip, "face_dd": face_dd}
    if mode == "planar":
        return "planar", {"p_plane": float(payload["dip"]), "p_face": min(face_dip, 89.9),
                          "p_phi": phi}
    return "toppling", {"t_disc": float(payload["dip"]), "t_face": min(face_dip, 89.9),
                        "t_phi": min(phi, 44.9)}
