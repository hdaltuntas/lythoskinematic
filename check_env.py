"""Lythos Suite ortam teşhisi — `python check_env.py` ile çalıştırın, çıktıyı paylaşın."""
import sys, os, importlib, subprocess
print("Python :", sys.version.split()[0], "|", sys.executable)
print("Conda  :", "evet" if "conda" in sys.version.lower() or os.path.exists(os.path.join(sys.prefix, "conda-meta")) else "hayır")
for m in ("PySide6", "shiboken6", "PyQt6", "PyQt5", "matplotlib", "numpy", "scipy", "reportlab"):
    try:
        mod = importlib.import_module(m); print(f"{m:10s}: {getattr(mod, '__version__', '?')}   ({os.path.dirname(mod.__file__)})")
    except Exception as e:
        print(f"{m:10s}: yok  ({type(e).__name__}: {str(e)[:70]})")
try:
    from PySide6.QtCore import qVersion; print("Qt      :", qVersion())
except Exception as e:
    print("PySide6.QtCore yüklenemedi:", e)
if sys.platform.startswith("win"):
    out = subprocess.run("where Qt6Core.dll", shell=True, capture_output=True, text=True).stdout.strip()
    print("PATH üzerindeki Qt6Core.dll:", out or "yok (iyi)")

print()
for m in ("lythos", "lythos.stereonet", "lythos.kinematics", "lythos.rockslope"):
    try:
        mod = importlib.import_module(m); print(f"{m:20s}: tamam")
    except Exception as e:
        print(f"{m:20s}: HATA  ({type(e).__name__}: {str(e)[:70]})")
