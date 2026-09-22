[English](CHANGELOG.md) | **Türkçe**

# Değişiklik günlüğü

Kayda değer değişiklikler, en yenisi önce. Sürüm numaraları
[anlamsal sürümleme](https://semver.org) kuralını izler.

## 0.1.0 — 22.09.2026

İlk sürüm. [PyPI](https://pypi.org/project/lythoskinematic/0.1.0/)

Lythos Kinematic, daha önce ayrı iki masaüstü programı olan **SlopeKinematics**
(kinematik ve olasılık, PyQt5) ile **Kinematix** (limit denge, bulon ve rapor, PySide6)
projelerini tarayıcıdan sürülen tek bir uygulamada birleştirir ve onların geçmişini
sürdürür.

### Eklenenler

- **Kinematik tarama** — eşit alan stereonetinde Markland testi, Kamb sayım konisiyle
  kutup yoğunluğu konturu, kritik bölge taraması ve süreksizlik yönelim belirsizliğini
  hesaba katan Monte Carlo yenilme olasılığı.
- **Limit denge** — kama (Hoek & Bray vektörel yöntem), düzlemsel kayma ve Goodman & Bray
  blok devrilmesi; hedef FS için gerekli destek kuvveti, tıklanabilir bulon aralık × boy
  matrisi ve seçilen tasarım için kapasite/FS kontrolü.
- **Köprü** — taramada bulunan en kritik süreksizlik veya kesişim, tek tuşla limit denge
  girdilerine yazılır.
- **Web arayüzü** — yalnızca standart kütüphaneye dayanan yerel bir HTTP sunucusu; uzak
  oturumda ya da masaüstü araç takımının ekran isteyeceği bir kapsayıcı içinde de çalışır.
  Grafikler sunucuda üretilir; ekranda görülen ile rapora giren birebir aynıdır.
- **Baştan sona çift dilli** — etiketler, sonuç metinleri, uyarılar, hata iletileri,
  grafik etiketleri ve PDF raporları Türkçe ve İngilizce; dil çalışırken değiştirilir.
  Dil değişimi formları girdileri koruyarak yeniden kurar ve hiçbir sayıyı değiştirmez.
- **PDF raporları** — her iki modül için tek bir reportlab şablonu: proje künyesi, girdi
  tabloları, şekiller, kuvvet dengesi tabloları, kaynakça ve imza bloğu.
- **Komut satırı** — `web`, `screen`, `run`, `example`. `screen` ve `run`, arayüzün
  kaydettiği JSON'u okur; tarayıcıda kurulan bir vaka gözetimsiz yeniden çalıştırılabilir.
- **Girdi şeması** (`forms.py`) — bir alanın anahtarı, etiketi, birimi, aralığı ve
  varsayılanı Python tarafında bir kez yazılır; sayfa sunucunun gönderdiğini çizer,
  böylece JavaScript'te etiketlerin ikinci bir kopyası oluşmaz.
- `tools/upload_to_pypi.py` — sürümü derleyip yükler, PyPI'da zaten var olan bir sürümü
  reddeder ve reddedilen bir yüklemenin nedenini açıklar.

### Önceki programlara göre değişenler

- **Tek arayüz.** İki Qt bağlaması aynı işlemi paylaşamaz ve masaüstü araç takımı bir
  ekran ister. Her iki masaüstü arayüz de tarayıcıdan sürülen arayüzle değiştirildi; bu
  aynı zamanda iki programın iş akışını tek bir girdi kümesi arkasında birleştirdi.
- **`mplstereonet` kaldırıldı.** Stereonet çizimi artık `stereonet.py` içindeki tek ortak
  uygulamadan gelir (eşit alan/eşit açı projeksiyonu, büyük ve küçük daireler, Kamb sayım
  konisiyle kutup yoğunluğu). İki modül birebir aynı geometriyi kullanır ve güncel Python
  sürümlerinde kurulumu bozulan bir bağımlılık ortadan kalkar.
- **Tek rapor yolu.** Tarama raporu eskiden Qt'nin yazıcısıyla basılıyordu; artık her şey
  aynı reportlab şablonundan geçer, PDF için ekrana gerek yoktur.
- **PySide6 artık bir bağımlılık değil.** Paket yalnızca NumPy, SciPy, Matplotlib ve
  reportlab ister.

### Düzeltilenler

- **Eşit alan projeksiyonunda yarıçap normalizasyonu.** Yatay çizgiler (plunge = 0) dış
  çember yerine yarıçapın %70,7'sine düşüyor, yani tüm veri ağın iç kısmına sıkışıyordu.
  Kinematix'in kama stereonetinde de vardı; `tests/test_stereonet.py` ile sabitlendi.

### Doğrulama

111 test. Hesap çekirdekleri kapalı-form çözümlere karşı sabitlenmiştir: kama, Hoek & Bray
kısa çözümüne karşı 1.696 kuru / 1.065 su dolu; düzlemsel, c = 0 kuru durumda
tanφ/tanψp; devrilme, Wyllie & Mah 9. bölüm örneğine karşı. Kinematik kesişim çizgisi,
limit denge çekirdeğinin bağımsız vektör uygulamasına karşı çapraz doğrulanır; belirsizlik
sıfırken Monte Carlo sonucu deterministik 0/100 cevabına iner.

### Bilinen sorunlar

- Komut satırı çıktısını boruyu erken kapatan bir komuta bağlamak (`lythos-kinematic
  screen girdi.json | head`) sessizce çıkmak yerine `BrokenPipeError` yığın izi bırakır.
