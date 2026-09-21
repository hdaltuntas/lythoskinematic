"""
lythoskinematic.web.server — arayüzü sunan yerel HTTP sunucusu.

Arayüz, başlatıldığı makinede küçük bir HTTP sunucusu olarak çalışır ve
tarayıcıdan sürülür. Bu seçim programı uzak oturumda ya da kapsayıcı içinde de
kullanılabilir kılar (masaüstü araç takımının isteyeceği bir ekran gerekmez) ve
standart kütüphane dışında hiçbir bağımlılık getirmez.

Sunucu, host açıkça değiştirilmedikçe geri döngü adresinin dışına çıkmaz;
uzun hesaplar bir iş parçacığında koşar, böylece Monte Carlo ya da bulon öneri
matrisi dönerken arayüz yanıt vermeye devam eder.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import APP_NAME, __version__, forms
from ..i18n import LANGS, T as _tr, language
from .session import Session
from .strings import shell_strings

STATIC = os.path.join(os.path.dirname(__file__), "static")

#: Tarayıcı sekmesi için küçük bir işaret: şev üzerinde süreksizlik düzlemi
_FAVICON = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    b'<rect width="32" height="32" rx="6" fill="#1f3b5a"/>'
    b'<path d="M4 26h24L17 7z" fill="#d8cfbf"/>'
    b'<path d="M10 26 21 11" stroke="#c0392b" stroke-width="2.2" stroke-linecap="round"/>'
    b'<circle cx="17" cy="7" r="2" fill="#5aa9d6"/></svg>'
)

SESSION = Session()


def _meta() -> dict:
    """Arayüzün açılışta okuduğu her şey: sürüm, diller, metinler, form şeması."""
    return {
        "app": APP_NAME,
        "version": __version__,
        "language": language(),
        "languages": list(LANGS),
        "strings": shell_strings(),
        "schema": forms.schema(),
        "defaults": forms.defaults(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LythosKinematic"

    def log_message(self, fmt, *args):        # konsolu hesap çıktısına bırak
        pass

    # ---------------------------------------------------------------- yardımcılar
    def _send(self, code: int, body: bytes, content_type: str, extra: dict = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, code: int = 200) -> None:
        self._send(code, json.dumps(payload, default=float).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _static(self, name: str) -> None:
        path = os.path.join(STATIC, os.path.basename(name))
        if not os.path.isfile(path):
            return self._json({"error": "not found"}, 404)
        kinds = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}
        with open(path, "rb") as fh:
            self._send(200, fh.read(), kinds.get(os.path.splitext(path)[1],
                                                 "application/octet-stream"))

    # --------------------------------------------------------------------- GET
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route, query = parsed.path, parse_qs(parsed.query)
        try:
            if route in ("/", "/index.html"):
                return self._static("index.html")
            if route.startswith("/static/"):
                return self._static(route)
            if route == "/favicon.ico":
                return self._send(200, _FAVICON, "image/svg+xml")
            if route == "/api/meta":
                return self._json(_meta())
            if route == "/api/state":
                return self._json(SESSION.state())
            if route == "/api/bolts":
                return self._json(SESSION.bolt_matrix_payload())
            if route == "/api/plot":
                target = query.get("target", ["screening"])[0]
                kind = query.get("kind", ["main"])[0]
                return self._send(200, SESSION.plot(target, kind), "image/png")
            self._json({"error": "not found"}, 404)
        except Exception as exc:
            self._json({"error": f"{exc}"}, 400)

    # -------------------------------------------------------------------- POST
    def do_POST(self) -> None:
        route = urlparse(self.path).path
        try:
            data = self._body()
            if route == "/api/language":
                SESSION.set_language(str(data.get("lang", "TR")))
                return self._json(_meta())
            if route == "/api/screen":
                return self._json(SESSION.screen(data.get("values", {})))
            if route == "/api/handoff":
                return self._json(SESSION.handoff())
            if route == "/api/equilibrium":
                return self._json(SESSION.equilibrium(data.get("mode", "wedge"),
                                                      data.get("values", {})))
            if route == "/api/required":
                return self._json(SESSION.required_support(data.get("mode", "wedge"),
                                                           data.get("values", {})))
            if route == "/api/bolts":
                return self._json(SESSION.start_bolts(data.get("mode", "wedge"),
                                                      data.get("values", {})))
            if route == "/api/bolt-check":
                return self._json(SESSION.bolt_check(
                    data.get("mode", "wedge"), data.get("values", {}),
                    float(data.get("spacing", 1.0)), float(data.get("length", 6.0))))
            if route == "/api/report":
                return self._report(data)
            self._json({"error": "not found"}, 404)
        except Exception as exc:
            self._json({"error": f"{exc}"}, 400)

    def _report(self, data: dict) -> None:
        """PDF'i geçici bir dosyaya yazıp indirme olarak gönderir."""
        target = data.get("target", "screening")
        name = f"lythos_{target}.pdf"
        with tempfile.TemporaryDirectory() as tmp:
            path = SESSION.report(target, os.path.join(tmp, name))
            with open(path, "rb") as fh:
                body = fh.read()
        self._send(200, body, "application/pdf",
                   {"Content-Disposition": f'attachment; filename="{name}"'})


def serve(host: str = "127.0.0.1", port: int = 8778, open_browser: bool = True,
          lang: str = "TR") -> None:
    """Arayüzü başlatır ve Ctrl+C gelene kadar çalıştırır."""
    SESSION.set_language(lang)
    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"{APP_NAME} {__version__} — {url}")
    print(_tr("Durdurmak için Ctrl+C.", "Press Ctrl+C to stop."))
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n" + _tr("durduruldu", "stopped"))
    finally:
        server.server_close()
