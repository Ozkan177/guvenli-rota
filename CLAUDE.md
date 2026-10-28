# Güvenli Rota: proje rehberi (Claude Code için)

Bu dosya Claude Code'un projeyi anlaması için yazıldı. Her oturumun başında oku.

## Proje ne?

Akdeniz Üniversitesi Bilgisayar Mühendisliği, CSE 491 Senior Design, Grup 7. Aynı proje TÜBİTAK 2209-A'ya da başvurdu.

Türkçe adı: Görev Kritik Sistemler İçin Güvenli Rota Belirleme ve Rota Tercihinin Gerekçelendirilmesi
İngilizce adı: Safe Route Planning for Mission-Critical Systems and Justification of Route Choice
Danışman: Dr. Öğr. Üyesi Taner Danışman
Ekip: Özkan Damdelen (takım lideri), Muhammed İkbal Ceyhan, Feyiz Ali Bozkurt, Furkan Şenol

Sistemin yapacağı iş: Sahadaki bir ekip ya da araç için birkaç rota önermek. Her rotanın üç maliyeti var: süre, risk ve haberleşme bağlantısının kalitesi. Bu üç ölçüt birbiriyle çeliştiği için tek bir en iyi rota çıkmıyor, birbirine üstün gelmeyen rotalardan oluşan bir Pareto kümesi çıkıyor. Kullanıcı bir rota seçtiğinde bir dil modeli, rotanın neden seçildiğini ve diğerlerinin neden seçilmediğini Türkçe açıklıyor. Açıklamadaki her sayı planlayıcının kendi hesabıyla karşılaştırılıyor, tutmayan açıklama gösterilmiyor.

Ayrıntılı proje metni `docs/` klasöründe. Kararsız kaldığında oraya bak.

## Şu anki aşama: Faz 0, veri fizibilitesi

Danışmana "kullanacağımız açık veriler var" dedik. Şimdi bunun doğru olduğunu kanıtlamamız gerekiyor. Faz 0'ın amacı tek: her veri setinin gerçekten indirilebildiğini, Türkiye'yi kapsadığını, beklenen çözünürlükte olduğunu ve projede işe yarayacağını sayılarla göstermek. Aynı zamanda GitHub reposunu ve proje iskeletini kuruyoruz.

Faz 0'da rota algoritması, dil modeli ya da arayüz yazma. Sadece en sondaki isteğe bağlı küçük A* denemesi istisna.

## Veri setleri

Bağlantılar Ekim 2026'da kontrol edildi. Hepsi ücretsiz. Sadece OpenCelliD hesap ve token istiyor.

### 1. Copernicus DEM GLO-30 (yükseklik ve eğim)
- Erişim: `s3://copernicus-dem-30m/` (bölge eu-central-1, hesap gerekmez, `AWS_NO_SIGN_REQUEST=YES`)
- HTTP: `https://copernicus-dem-30m.s3.amazonaws.com/<KARO>/<KARO>.tif`
- Karo adı: `Copernicus_DSM_COG_10_N36_00_E030_00_DEM` (1°x1°, adı güneybatı köşesini verir). Karo listesi kovadaki `tileList.txt` dosyasında.
- Format: Cloud Optimized GeoTIFF. Tüm karoyu indirmeden sadece bölge penceresini oku.
- Yedek: GLO-90 (`s3://copernicus-dem-90m/`, karo adında `_30_`).
- DOI: 10.5270/ESA-c5d3d65
- Dikkat: Bu bir yüzey modeli (DSM), bina ve ağaç tepeleri de içinde. Kent çevresinde yapay eğimler çıkabilir, raporda bunu not et. AWS'deki kopya 2021 sürümü.

### 2. ESA WorldCover 10 m 2021 v200 (arazi örtüsü)
- Erişim: `s3://esa-worldcover/v200/2021/map/` (eu-central-1, hesap gerekmez)
- Dosya: `ESA_WorldCover_10m_2021_v200_N36E030_Map.tif` (3°x3° karo, adı güneybatı köşesi, 3'ün katı)
- 11 sınıf. Sınıf kodları kullanım kılavuzunda: https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/docs/WorldCover_PUM_V2.0.pdf
- Sadece 2021 v200'ü kullan. 2020 v100 farklı algoritmayla üretildi.
- 30 m'ye indirirken `Resampling.mode` kullan.
- DOI: 10.5281/zenodo.7254221, lisans CC BY 4.0

### 3. OpenStreetMap (yol ağı)
- Faz 0'da da Geofabrik tarihli dosyası kullanılıyor: `https://download.geofabrik.de/europe/turkey-261001.osm.pbf` (yaklaşık 650 MB). Overpass sunucusu yoğunluktan 502 verdiği için OSMnx ile doğrudan çekmekten vazgeçildi. `scripts/download_osm.py` dosyayı indirip `data/raw/<bölge>/osm_roads.osm` olarak bölgelere kırpıyor, OSMnx `graph_from_xml` ile okunuyor.
- Lisans ODbL, atıf: "© OpenStreetMap contributors"

### 4. OpenCelliD (baz istasyonu konumları)
- İndirme sayfası: https://opencellid.org/downloads.php
- Türkiye dosyası (MCC 286): `https://opencellid.org/ocid/downloads?token=<TOKEN>&type=mcc&file=286.csv.gz`
- Token `.env` dosyasında `OPENCELLID_TOKEN` olarak duruyor. Koda gömme, ekrana basma, commit etme.
- Limit: her dosya günde en fazla 2 kez indirilebiliyor. İndirdiğin dosyayı sakla, tekrar tekrar indirme.
- Sütunlar: radio, mcc, net, area, cell, unit, lon, lat, range, samples, changeable, created, updated, averageSignal
- Dikkat:
  - Satırlar baz istasyonu değil, hücre (anten sektörü). Aynı direğin birden fazla satırı olabilir, kapsama hesabından önce yakın noktaları kümele.
  - `changeable=1` olan konumlar ölçümlerin ortalaması, yani tahmin. `changeable=0` operatörden gelen kesin konum.
  - `range` kapsama yarıçapı değil, konumun belirsizlik yarıçapı.
- Lisans CC BY-SA 4.0. Bu veriden türetilen katman paylaşılırsa aynı lisansla paylaşılmalı.

### 5. Ookla Speedtest açık veri (ölçülmüş mobil internet hızı)
- Erişim: `s3://ookla-open-data/parquet/performance/type=mobile/year=2026/quarter=3/2026-07-01_performance_mobile_tiles.parquet` (bölge us-west-2, hesap gerekmez, dosya yaklaşık 190 MB)
- Dosyanın tamamını indirme. DuckDB ile uzaktan oku, Türkiye ya da bölge sınırına göre filtrele:
  ```sql
  INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';
  SELECT * FROM read_parquet('s3://ookla-open-data/parquet/performance/type=mobile/year=2026/quarter=3/*.parquet')
  WHERE tile_x BETWEEN 25.6 AND 44.9 AND tile_y BETWEEN 35.8 AND 42.2;
  ```
- Alanlar: avg_d_kbps, avg_u_kbps, avg_lat_ms, tests, devices, quadkey, tile (WKT geometri), tile_x, tile_y
- Karo zoom 16. Türkiye enleminde kenarı yaklaşık 450-495 m, yani 30 m ızgarada yaklaşık 15x16 hücre ediyor.
- Dikkat: Ookla Nisan 2026'da bazı bölgeleri veriden çıkardı ama hangileri olduğunu yazmadı. Türkiye'nin 2026 Q3 dosyasında olduğunu ilk iş olarak doğrula. Karo yoksa bu "kapsama yok" değil, "veri yok" demek. İkisini ayrı tut.
- Lisans CC BY-NC-SA 4.0 (ticari olmayan). Atıf metni: https://github.com/teamookla/ookla-open-data

### 6. Yedek: SRTM
NASA Earthdata hesabı istiyor. Faz 0'da kullanma. GLO-30 bir bölgede eksikse önce GLO-90'a geç.

## Test bölgeleri (geçici)

Danışmanla henüz kesinleşmedi. Faz 0 için şu üç bölgeyi kullan, her biri yaklaşık 10 km x 10 km:

1. Kent çevresi: Antalya, Konyaaltı/Kepez çevresi
2. Dağlık: Antalya batısı, Saklıkent çevresi (Toros Dağları)
3. Ova: Konya Ovası, Çumra çevresi

Sınır kutularını OSM üzerinden yer adından bul ve `config/regions.yaml` dosyasına yaz. Üç bölge de UTM 36N (EPSG:32636) içinde kalıyor, ortak ızgara için bunu kullan. WorldCover'ın N36E030 karosu üç bölgeyi de kapsamalı, kontrol et.

## Faz 0 adımları

Her adımı bitirince kısa bir commit at. Adım bitmeden diğerine geçme.

1. **Repo iskeleti**
   - Klasörler: `src/guvenli_rota/`, `scripts/`, `notebooks/`, `config/`, `data/raw/`, `data/processed/`, `reports/figures/`, `docs/`
   - `.gitignore`: `data/`, `.env`, `*.tif`, `*.parquet`, `*.csv.gz`, `*.pbf`, sanal ortam klasörü, `__pycache__/`
   - `requirements.txt`: rasterio, geopandas, shapely, pyproj, osmnx, duckdb, pandas, numpy, scipy, matplotlib, python-dotenv, pyyaml
   - `README.md` İngilizce olsun (ders değerlendirmesinde README'ye bakılıyor). Projenin kısa tanımı, kurulum, veri kaynakları ve lisans/atıf bölümü.
   - `.env.example` içinde sadece `OPENCELLID_TOKEN=` satırı olsun.

2. **İndirme ve kırpma betikleri** (`scripts/`): Her veri seti için ayrı betik. Üç bölgeyi kırpıp `data/raw/<bölge>/` altına kaydet. Her indirme için `data/data_manifest.csv` dosyasına bir satır ekle: veri seti, sürüm, kaynak URL/yol, dosya adı, indirme tarihi, boyut, SHA256.

3. **Her veri seti için kontrol** (`scripts/check_*.py` ya da notebook):
   - Dosya açılıyor mu? CRS, çözünürlük ve boyut ne?
   - Bölgeyi tamamen kapsıyor mu? Boş (nodata) piksel oranı ne?
   - Değer aralığı mantıklı mı? Örneğin Antalya kıyısında yükseklik 0'a yakın, Saklıkent'te 1500 m civarında olmalı.
   - Her bölge için bir hızlı bakış görseli `reports/figures/` altına.
   - Sayılar:
     - OpenCelliD: bölge başına hücre sayısı, kümeleme sonrası direk sayısı, `changeable` oranı, radyo türü dağılımı (GSM/UMTS/LTE/NR).
     - Ookla: bölge başına karo sayısı, karoların bölge alanının yüzde kaçını kapladığı, test sayısı dağılımı.
     - OSM: düğüm ve kenar sayısı, yol türü dağılımı.
     - WorldCover: sınıf oranları.

4. **Ortak 30 m ızgara**: Üç bölge için yükseklik, eğim, arazi örtüsü ve yol rasterini aynı ızgaraya (EPSG:32636, 30 m) getir. Hücre hücre hizalandıklarını test et.

5. **H1 ön denemesi (kent çevresi bölgesi)**: Projenin ilk hipotezi şu: baz istasyonu konumlarından hesaplanan bağlantı tahmini, Ookla'nın ölçtüğü hızla pozitif ilişkili. Faz 0'da basit sürümünü dene. Her Ookla karosu için en yakın direğe uzaklığı ve 2 km içindeki direk sayısını hesapla, `avg_d_kbps` ile Spearman korelasyonuna bak. Görüş hattı (DEM üzerinden) hesabı zorunlu değil. Vakit kalırsa tek bir karo için dene. Sonuç zayıf çıksa da yaz, amaç sonucu iyi göstermek değil, verinin bu hesabı mümkün kıldığını görmek.

6. **Rapor**: `reports/veri_fizibilite_raporu.md` dosyasını Türkçe yaz (danışmana gösterilecek). İçinde şunlar olsun:
   - Her veri seti için bir satırlık tablo: indirilebildi mi, Türkiye/bölge kapsaması, çözünürlük, sorunlar, karar (kullanılır / koşullu / kullanılmaz).
   - Görseller.
   - H1 ön deneme sonucu.
   - Sınırlılıklar: DSM, Ookla karo boyutu ve seyrekliği, OpenCelliD konumlarının tahmin olması.
   - Toplantı 3'te konuşulan ihtiyaçlar için verinin yeterli olup olmadığı (aşağıdaki bölüme bak).

7. **İsteğe bağlı**: Dağlık bölgede sadece eğim maliyetiyle iki nokta arasında basit bir A* rotası çiz. Amaç yalnızca ızgaranın rota aramaya hazır olduğunu göstermek.

## Toplantı 3 notları (28.10.2026)

Danışmanla konuşulanlar. Faz 0 raporunda veri bu ihtiyaçları karşılıyor mu, ona bak:
- Kısıtlar sabit olmayacak, kullanıcı her görev için ayarlayabilecek.
- Yaya ve araç modu ayrı olacak. Araç yol ya da geçilebilir arazi ister, eğim sınırı daha düşük. OSM yol türleri ve WorldCover sınıfları bunu ayırmaya yetiyor mu?
- Gündüz/gece seçeneği olacak, görünürlük ve risk değişiyor.
- Güvenlik ile iletişimin kopmaması arasında denge kurulacak.
- Mobil hat kapsaması olmayan yerlerde uydu haberleşmesi bir seçenek olarak konuşuldu. Mobil kapsamanın olmadığı alanları veriden ayırt edebiliyor muyuz?

## Çalışma kuralları

- Büyük dosyaları asla commit etme, `data/` klasörü git dışında kalmalı.
- `.env` dosyasını ve token'ı asla commit etme, loglara da yazma.
- `git push` yapmadan önce sor. Uzak repo adresini kullanıcı verecek.
- Ders kuralı: her öğrenci kendi işini kendi GitHub hesabıyla commit ediyor, commit geçmişi bireysel katkının kanıtı sayılıyor. Commit mesajlarını kısa ve açıklayıcı İngilizce yaz.
- Kod ve yorumlar İngilizce, rapor Türkçe.
- Bir veri kaynağı çalışmazsa sessizce başka bir kaynağa geçme. Durup ne olduğunu yaz, alternatifi öner.
- Ders kuralı: yapay zekâ kullanımı raporda beyan edilecek. README'ye "This repository was set up with assistance from Claude Code" notunu ekle.
