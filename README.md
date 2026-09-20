# Kinematix v1.0 — Kaya Şevi Stabilite Analizi (PySide6)

Hoek & Bray limit denge yöntemleriyle **kama (Swedge)**, **düzlemsel (RocPlane)** ve **blok devrilme (RocTopple)**
analizi; bulon karelaj/boy tasarımı; profesyonel PDF raporlama.

## Kurulum ve çalıştırma
```
pip install -r requirements.txt
python kinematix.py          # açık/koyu tema, F5-F8 kısayolları
```

## Yapı
```
rockslope/            hesap çekirdeği (arayüzden bağımsız)
  core.py             vektör/geometri yardımcıları
  style.py            ortak çizim stili
  wedge.py            kama: geometri, analiz, destek, H&B doğrulama, 3D, stereonet
  planar.py           düzlemsel kayma: analiz, destek, 2D kesit
  toppling.py         blok devrilme: su + sismik + topuk ankrajı, kesit
  bolts.py            karelaj/boy önerisi, seçilen tasarımın kapasite kontrolü
  report.py           PDF rapor (reportlab)
kinematix.py          PySide6 arayüzü: dock girdi paneli, sekmeli sonuç/grafik/tablo, arka planda öneri matrisi,
                      açık/koyu tema (QSettings ile hatırlanır), son girdiler, JSON kaydet/yükle, PDF
tests/                pytest doğrulama paketi (kapalı-form çözümlerle karşılaştırma)
```

## Kısayollar
F5 Analiz · F6 Gerekli destek · F7 Bulon önerisi · F8 Bulon kontrol · Ctrl+P PDF · Ctrl+S / Ctrl+O kaydet / yükle

## Tek dosya exe (isteğe bağlı)
```
pip install pyinstaller
pyinstaller --noconfirm --windowed --name Kinematix --collect-all reportlab kinematix.py
```
Windows'ta Türkçe karakterler için rapor Arial (C:\Windows\Fonts) kullanır; Linux'ta DejaVu Sans.

## Doğrulama
kama — Hoek & Bray kapalı-form kısa çözümle birebir (kuru 1.696 / dolu 1.065);
düzlemsel — c=0 kuru: tanφ/tanψp; devrilme — Wyllie & Mah Bölüm 9 örneği (blok yükseklikleri, modlar, limit denge φ≈38°).

Bu değerler `tests/` altında pytest ile sabitlenmiştir; çekirdek modüllerde (`rockslope/`) değişiklik
yapıldığında regresyonu yakalamak için çalıştırın:
```
pip install -r requirements-dev.txt
pytest
```

## Lisans
MIT — bkz. [LICENSE](LICENSE). Bağımlılıklardan PySide6 LGPL'dir; kurum içi dağıtım için ek lisans gerekmez.

## Sorun giderme (Windows)
**`ImportError: DLL load failed while importing QtCore`** → iki farklı Qt aynı anda yüklenmiş ya da PySide6/shiboken6 sürümleri uyumsuz.
1. Teşhis: `python check_env.py` (PySide6 ve shiboken6 sürümleri aynı olmalı; PyQt5/PyQt6 varsa çakışma kaynağıdır).
2. Temiz kurulum: `pip uninstall -y PySide6 PySide6-Essentials PySide6-Addons shiboken6` → `pip install PySide6`
3. En sağlam yol, ayrı sanal ortam:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   python kinematix.py
   ```
4. Anaconda kullanıyorsanız: `conda create -n kinematix python=3.11` → `conda activate kinematix` → `pip install -r requirements.txt`.
   (Anaconda base ortamındaki PyQt5/qt paketleri ile pip PySide6 karışmasın.)
5. Hâlâ hata varsa Microsoft Visual C++ 2015–2022 Redistributable (x64) kurulu olmalı.
