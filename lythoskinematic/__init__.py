"""
Lythos Kinematic — kaya şevi kinematiği ve stabilitesi (web tabanlı).

İki adımlı bir iş akışı sunar:

    1. Kinematik tarama  — Markland testi, stereonet, kutup yoğunluğu ve
                           Monte Carlo olasılık analizi
    2. Limit denge       — kama / düzlemsel / devrilme analizi, bulon karelaj ve
                           boy tasarımı, PDF rapor

Arayüz, tarayıcıdan sürülen yerel bir web sunucusudur (yalnızca standart
kütüphane); bu sayede uzak oturumda veya kapsayıcı içinde de çalışır.

Paket düzeni
------------
    lythoskinematic.i18n        dil anahtarı; çift dilli metin yardımcısı
    lythoskinematic.stereonet   ortak alt yarımküre stereonet projeksiyonu
    lythoskinematic.kinematics  kinematik tarama çekirdeği (Markland + Monte Carlo)
    lythoskinematic.rockslope   limit denge çekirdeği (Hoek & Bray, Goodman & Bray)
    lythoskinematic.forms       girdi şeması ve okuyucuları (arayüzden bağımsız)
    lythoskinematic.web         yerel web sunucusu ve tarayıcı arayüzü

Çalıştırma:  lythos-kinematic        (veya  python -m lythoskinematic)
"""

__version__ = "0.1.0"

APP_NAME = "Lythos Kinematic"
ORG = "Lythos"

__all__ = ["__version__", "APP_NAME", "ORG"]
