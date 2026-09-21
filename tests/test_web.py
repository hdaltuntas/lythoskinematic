"""
Web katmanı (lythoskinematic/web/) için testler.

Oturum nesnesi HTTP'den bağımsız olduğu için arayüzün davranışı soket açmadan
sınanabilir; sunucunun yönlendirmeleri ise geçici bir port üzerinde gerçek bir
HTTP sunucusuyla denetlenir.
"""
import json
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from lythoskinematic import forms, i18n
from lythoskinematic.web import server as web_server
from lythoskinematic.web.session import Session


@pytest.fixture(autouse=True)
def turkish():
    i18n.set_language("TR")
    yield
    i18n.set_language("TR")


@pytest.fixture
def session():
    return Session()


@pytest.fixture
def values():
    return forms.defaults()


def wait_for_job(session, timeout=60.0):
    """Arka plan işinin bitmesini bekler ve son durumu döndürür."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = session.state()
        if state["job"] != "running":
            return state
        time.sleep(0.02)
    raise AssertionError("arka plan işi zamanında bitmedi")


# --------------------------------------------------------------------------- #
#  Kinematik tarama
# --------------------------------------------------------------------------- #

def test_screen_reports_the_critical_set(session, values):
    data = session.screen(values)
    assert data["ok"]
    payload = data["result"]
    assert payload["mode"] == "planar"
    assert payload["n_items"] == 6
    assert payload["n_critical"] == 1
    assert [i["name"] for i in payload["items"] if i["critical"]] == ["E3"]
    assert "<table" in data["report_html"]


def test_screen_without_joints_is_an_error_not_a_crash(session, values):
    values["joints"] = []
    data = session.screen(values)
    assert data["ok"] is False and data["error"]


def test_monte_carlo_finishes_and_fills_the_probability_report(session, values):
    values["trials"] = 1000
    session.screen(values)
    state = wait_for_job(session)
    assert state["job"] == "done"
    assert state["has_monte_carlo"]
    assert "%" in state["probability_html"]


def test_state_is_safe_to_poll_while_a_job_runs(session, values):
    """state() ile arka plan işi aynı kilidi kullanır; yoklama bloke etmemeli."""
    values["trials"] = 50000
    session.screen(values)
    for _ in range(20):
        session.state()                      # kilitlenirse test zaman aşımına uğrar
    wait_for_job(session)


def test_wedge_screening_enumerates_pairs(session, values):
    values["mode"] = "wedge"
    payload = session.screen(values)["result"]
    assert payload["n_items"] == 15          # 6 takımın ikili kombinasyonu
    assert "×" in payload["items"][0]["name"]


def test_screening_payload_is_json_serialisable(session, values):
    """Kama modunda paralel düzlemler NaN üretir; JSON'a null olarak gitmeli."""
    values["mode"] = "wedge"
    values["joints"] = [{"label": "A", "dip": 45, "dipdir": 120, "std": 1},
                        {"label": "B", "dip": 45, "dipdir": 120, "std": 1}]
    payload = session.screen(values)["result"]
    assert payload["items"][0]["v1"] is None
    json.dumps(payload)                      # istisna atmamalı


# --------------------------------------------------------------------------- #
#  Limit denge
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("mode, expected", [
    ("wedge", 1.696), ("planar", 0.891), ("toppling", 1.020),
])
def test_equilibrium_matches_the_validated_results(session, values, mode, expected):
    data = session.equilibrium(mode, values)
    assert data["ok"] and data["mode"] == mode
    assert data["fs"] == pytest.approx(expected, abs=5e-3)
    assert data["summary"].strip()
    assert data["table"]["rows"]


def test_only_the_wedge_offers_a_stereonet(session, values):
    assert session.equilibrium("wedge", values)["figures"] == ["main", "stereonet"]
    assert session.equilibrium("planar", values)["figures"] == ["main"]


def test_toppling_table_keeps_the_mode_colours(session, values):
    table = session.equilibrium("toppling", values)["table"]
    assert table["color_column"] == 6
    modes = {row[6] for row in table["rows"]}
    assert modes <= set(table["colors"])     # her mod adının bir rengi olmalı


def test_required_support_reaches_the_target(session, values):
    data = session.required_support("planar", values)
    assert data["ok"] and data["changed"]
    values.update(data["changed"])
    assert session.equilibrium("planar", values)["fs"] == pytest.approx(
        values["p_FS"], abs=1e-3)


def test_required_support_says_so_when_none_is_needed(session, values):
    values["p_FS"] = 1.0
    values["p_plane"] = 20.0                 # φ = 31°, kuru: zaten stabil
    values["p_tc_on"] = False
    values["p_water"] = "dry"
    data = session.required_support("planar", values)
    assert data["ok"] and data["changed"] == {}
    assert data["message"]


# --------------------------------------------------------------------------- #
#  Bulon tasarımı
# --------------------------------------------------------------------------- #

def test_bolt_design_needs_a_support_force_first(session, values):
    data = session.start_bolts("planar", values)
    assert data["ok"] is False and "T" in data["error"]


def test_bolt_matrix_and_check(session, values):
    values.update(session.required_support("planar", values)["changed"])
    assert session.start_bolts("planar", values)["ok"]
    assert wait_for_job(session, timeout=180)["job"] == "done"

    matrix = session.bolt_matrix_payload()
    assert matrix["lengths"] and matrix["rows"]
    assert len(matrix["rows"][0]["cells"]) == len(matrix["lengths"])
    best = matrix["best"]
    assert best and best["spacing"] > 0

    check = session.bolt_check("planar", values, best["spacing"], best["length"])
    assert check["ok"] and check["adequate"]
    assert check["table"]["rows"]


def test_bolt_design_is_refused_for_toppling(session, values):
    assert session.start_bolts("toppling", values)["ok"] is False
    assert session.bolt_check("toppling", values, 1.5, 6.0)["ok"] is False


# --------------------------------------------------------------------------- #
#  Figürler ve rapor
# --------------------------------------------------------------------------- #

def test_plot_before_analysis_explains_itself(session):
    with pytest.raises(ValueError):
        session.plot("screening")
    with pytest.raises(ValueError):
        session.plot("equilibrium")


def test_plots_are_png(session, values):
    session.screen(values)
    session.equilibrium("wedge", values)
    for target, kind in (("screening", "main"), ("equilibrium", "main"),
                         ("equilibrium", "stereonet")):
        data = session.plot(target, kind)
        assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{target}/{kind} PNG değil"
        assert len(data) > 10000


def test_reports_are_pdf(session, values, tmp_path):
    session.screen(values)
    wait_for_job(session)
    session.equilibrium("planar", values)
    for target in ("screening", "equilibrium"):
        path = session.report(target, str(tmp_path / f"{target}.pdf"))
        with open(path, "rb") as fh:
            assert fh.read(5) == b"%PDF-"


# --------------------------------------------------------------------------- #
#  Köprü
# --------------------------------------------------------------------------- #

def test_handoff_requires_a_critical_result(session, values):
    values["friction"] = 89                  # hiçbir takım kritik olmaz
    session.screen(values)
    assert session.handoff()["ok"] is False


def test_handoff_transfers_the_steepest_critical_item(session, values):
    session.screen(values)
    data = session.handoff()
    assert data["ok"] and data["mode"] == "planar"
    assert data["values"]["p_plane"] == pytest.approx(34.0)
    assert data["values"]["p_phi"] == pytest.approx(values["friction"])
    assert "E3" in data["message"]


# --------------------------------------------------------------------------- #
#  Dil
# --------------------------------------------------------------------------- #

def test_session_follows_the_language(session, values):
    session.set_language("EN")
    payload = session.screen(values)["result"]
    assert payload["mode_label"] == "Planar Sliding"
    assert session.equilibrium("planar", values)["summary"].count("FACTOR OF SAFETY") == 1


# --------------------------------------------------------------------------- #
#  HTTP yönlendirmeleri
# --------------------------------------------------------------------------- #

@pytest.fixture
def http():
    """Geçici bir portta gerçek bir sunucu."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), web_server.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=30) as response:
        return response.status, response.headers.get("Content-Type"), response.read()


def post(base, path, payload):
    request = urllib.request.Request(base + path, method="POST",
                                     data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.status, response.headers.get("Content-Type"), response.read()


def test_index_and_static_files_are_served(http):
    status, kind, body = get(http, "/")
    assert status == 200 and "text/html" in kind
    assert b"Lythos Kinematic" in body
    for name, expected in (("app.js", "javascript"), ("style.css", "css")):
        status, kind, body = get(http, "/static/" + name)
        assert status == 200 and expected in kind and body


def test_meta_carries_everything_the_page_needs(http):
    _, _, body = get(http, "/api/meta")
    meta = json.loads(body)
    assert meta["app"] == "Lythos Kinematic"
    assert set(meta["languages"]) == {"TR", "EN"}
    assert meta["strings"]["run_screening"]
    assert set(meta["schema"]) == {"screening", "equilibrium", "bolts", "report"}
    assert meta["defaults"]["joints"]


def test_unknown_route_is_a_404(http):
    with pytest.raises(urllib.error.HTTPError) as caught:
        get(http, "/api/nonexistent")
    assert caught.value.code == 404


def test_screen_and_plot_over_http(http):
    values = json.loads(get(http, "/api/meta")[2])["defaults"]
    _, _, body = post(http, "/api/screen", {"values": values})
    assert json.loads(body)["ok"]
    status, kind, image = get(http, "/api/plot?target=screening&kind=main")
    assert status == 200 and kind == "image/png" and image[:4] == b"\x89PNG"


def test_report_downloads_a_pdf_over_http(http):
    values = json.loads(get(http, "/api/meta")[2])["defaults"]
    post(http, "/api/equilibrium", {"mode": "planar", "values": values})
    request = urllib.request.Request(http + "/api/report", method="POST",
                                     data=json.dumps({"target": "equilibrium"}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        assert response.headers.get("Content-Type") == "application/pdf"
        assert "attachment" in response.headers.get("Content-Disposition", "")
        assert response.read(5) == b"%PDF-"


def test_bad_input_returns_an_error_not_a_stack_trace(http):
    request = urllib.request.Request(http + "/api/equilibrium", method="POST",
                                     data=json.dumps({"mode": "planar",
                                                      "values": {"p_plane": 80, "p_face": 70}}).encode(),
                                     headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request, timeout=30)
    assert caught.value.code == 400
    payload = json.loads(caught.value.read())
    assert payload["error"] and "Traceback" not in payload["error"]


def test_language_route_switches_and_returns_new_meta(http):
    try:
        _, _, body = post(http, "/api/language", {"lang": "EN"})
        meta = json.loads(body)
        assert meta["language"] == "EN"
        assert meta["strings"]["run_screening"] == "▶ Run screening"
    finally:
        post(http, "/api/language", {"lang": "TR"})
