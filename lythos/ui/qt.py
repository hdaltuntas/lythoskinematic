"""
lythos.ui.qt — Qt bağlamasının tek noktadan sabitlenmesi.

Qt bağlaması matplotlib'den ÖNCE ve tek başına yüklenmelidir. Aksi hâlde
matplotlib makinede PyQt5/PyQt6 bulursa önce onu yükler; ikinci bir Qt kitaplığı
aynı işleme girince Windows'ta "DLL load failed / belirtilen yordam bulunamadı"
hatası verir. `lythos.ui` içindeki her modül matplotlib'i içe aktarmadan önce
bu modülü içe aktarır.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_API", "pyside6")

import PySide6  # noqa: E402,F401  (bağlamayı erkenden yükle)

QT_API = "pyside6"
