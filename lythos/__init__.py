"""
Lythos Suite — geoteknik analiz uygulama takımı.

Modüller
--------
Lythos Kinematic : kaya şevi kinematiği ve stabilitesi
    • Kinematik tarama  — Markland testi, stereonet, Monte Carlo olasılık analizi
                          (eski SlopeKinematics)
    • Limit denge       — kama / düzlemsel / devrilme analizi, bulon tasarımı, PDF rapor
                          (eski Kinematix)

Paket düzeni
------------
    lythos.stereonet   ortak alt yarımküre stereonet projeksiyonu (dış bağımlılıksız)
    lythos.kinematics  kinematik tarama çekirdeği (Markland + Monte Carlo)
    lythos.rockslope   limit denge çekirdeği (Hoek & Bray, Goodman & Bray)
    lythos.ui          PySide6 arayüzü (suite kabuğu + modül panelleri)

Çalıştırma:  python lythos_suite.py   (veya  python -m lythos)
"""

__version__ = "1.0.0"

APP_NAME = "Lythos Suite"
ORG = "Lythos"
MODULE_KINEMATIC = "Lythos Kinematic"

__all__ = ["__version__", "APP_NAME", "ORG", "MODULE_KINEMATIC"]
