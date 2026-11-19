GÜVENLİ ROTA: GÖREV SIRASI VE CLAUDE CODE PROMPTLARI
(5. görüşme ve dönem sonu teslimleri için, 19.11.2026)

======================================================================
A. GÖREV SIRASI
======================================================================

Ortak kurallar (çakışma olmasın diye):
- Herkes kendi dalında, kendi dosyalarında çalışır. Aynı dosyaya iki kişi dokunmaz:
  routing/astar.py: İkbal | visibility/: Furkan | scene/synthetic.py: İkbal
  scene/converter.py: Feyiz | scene/__init__.py, scene/core.py, .github/: Özkan
- requirements.txt'e yeni paket eklerken sadece kendi satırını ekle, PR açıklamasında yaz.
- Her PR'ı bir kişi daha gözden geçirir, main'e Özkan birleştirir. Birleştirdikten sonra herkes git pull yapar.
- Bir görev başkasının işini bekliyorsa beklerken o işin sahte (elle yazılmış küçük) girdisiyle test yaz, birleşince gerçeğine bağla.

AŞAMA 0 (20-22 Kasım) - hazırlık
  Özkan  : feature/meeting5-plan PR'ını main'e birleştir (CLAUDE.md, scene_format.md, CI). Laptop kurulumu (P0-Ö).
  Herkes : main'i çek, ortamı kur, testleri çalıştır (P0-H).
  Furkan : İş 1, görüş hattı dalını yeniden çalıştır ve PR aç (P1-F).

AŞAMA 1 (22-25 Kasım) - temel
  Özkan  : İş 2, Scene sınıfı (P2-Ö). Diğer işlerin çoğu buna bağlı, önce bu bitmeli.
  İkbal  : İş 3'ün ilk yarısı, arazi ve bina üretimi (Scene'den bağımsız kısım) (P3-İ).
  Feyiz  : İş 5'in ilk yarısı, OSM bina yüksekliklerinin çıkarılması (P5-Fe).
  Furkan : İş 1 birleşince İş 4'e başla (P4-F).

AŞAMA 2 (25-29 Kasım) - parçalar
  İkbal  : İş 3'ü bitir, çıktıyı Scene ile kaydet (P3-İ devamı).
  Feyiz  : İş 5'i bitir, Antalya'nın iki sahnesi (P5-Fe devamı).
  Furkan : İş 4, gözlemci görünürlüğü ve görünürlük maliyeti (P4-F).
  Özkan  : PR'ları gözden geçir, birleştir. Final rapor taslak başlıkları (P9-Ö, ilk kısım).
  -> 29 Kasım: 11. hafta kontrol noktası. Çekirdek bileşenleri danışmana göster (sahne + görünürlük + A*).

AŞAMA 3 (29 Kasım-2 Aralık) - rota
  İkbal  : İş 6, görünürlük maliyetiyle A* (P6-İ).
  Furkan : İş 10 başlangıcı, ışın izlemeyle zemin gerçeği (P10-F). Yetişmezse 5. görüşmede "sıradaki iş" olarak sunulur.
  Feyiz  : Gerçek sahnede yaya/araç ve gündüz/gece görev setinin hazırlanması (P5b-Fe).

AŞAMA 4 (2-6 Aralık) - entegrasyon
  Özkan  : İş 7 uçtan uca demo (P7-Ö), İş 9 CI/README/rapor planı (P9-Ö).
  Özkan + Furkan : İş 8 ilk deney (P8).
  İkbal + Feyiz  : Entegrasyon testleri ve hata düzeltme (P11-İFe).

5. GÖRÜŞME (7-11 Aralık arası bir gün, 12-13. hafta)
  Götürülecekler: demo şekilleri, exp_visibility.csv özeti, CI'ın yeşil olduğu ekran, final rapor ve sunum planı.
  İmzalı formu 1 hafta içinde Teams'e yükle. 13. haftanın sonunda 5 form Teams'te olmalı.

AŞAMA 5 (12-20 Aralık) - 13-14. hafta, test ve belgeler
  Herkes : Kendi bölümünün final rapor taslağı ve README'deki "kim ne yaptı" satırı (P12-H).
  Özkan  : Raporu birleştir, README'yi son haline getir, sürüm etiketi (P13-Ö).

AŞAMA 6 (15. hafta / final dönemi)
  Herkes : Sunum ve demo provası, Senior Design II planı (P14-H).

======================================================================
B. PROMPTLAR
======================================================================
Her promptu ilgili kişi kendi bilgisayarında, repo klasöründe açtığı Claude Code'a yapıştırır.
Hepsi CLAUDE.md'yi okuyarak başlar; proje bağlamı orada.

----------------------------------------------------------------------
P0-Ö  ÖZKAN: LAPTOP KURULUMU (Aşama 0)
----------------------------------------------------------------------
(Önce terminalde:)
  git clone https://github.com/Ozkan177/guvenli-rota.git
  cd guvenli-rota
  git config user.name "Ozkan177"
  git config user.email "<GitHub hesabındaki e-posta>"
  python -m venv .venv
  .venv\Scripts\activate          (macOS/Linux: source .venv/bin/activate)
  pip install -r requirements.txt
  pip install -e .
  copy .env.example .env           (macOS/Linux: cp) ve token'ı .env'e yaz
Eski bilgisayara erişebiliyorsan data/ klasörünü USB ile kopyala. En azından data/raw/opencellid/286.csv.gz dosyasını kopyala: OpenCelliD günde 2 indirme izni veriyor ve yeni indirilen dosya farklı bir anlık görüntü olur.

(Sonra Claude Code'a:)
Bu repoyu yeni bir bilgisayara kurdum ve önceki Claude Code konuşmam diğer bilgisayarda kaldı. CLAUDE.md, README.md, docs/scene_format.md ve reports/veri_fizibilite_raporu.md dosyalarını oku ve projenin nerede olduğunu bana kısaca özetle. Sonra:
1. pytest -q çalıştır.
2. data/ klasöründe hangi dosyalar var, data/data_manifest.csv'deki SHA256 değerleriyle karşılaştır. Eksik ya da farklı olanları tablo halinde göster. Hiçbir şeyi indirme, sadece rapor et.
3. Eksik dosya varsa hangi scripts/ betiğiyle hangi sırayla üretileceğini yaz. OpenCelliD'yi yeniden indirmeden önce bana sor.
4. git branch -a ve son 10 commit'i göster, hangi dalların main'e birleşmediğini söyle.

----------------------------------------------------------------------
P0-H  HERKES: ORTAMI GÜNCELLE (Aşama 0)
----------------------------------------------------------------------
main'e geç ve git pull yap. CLAUDE.md'yi baştan oku, özellikle "Şu anki aşama" bölümündeki iş tablosunu ve docs/scene_format.md'yi. pip install -e . ve pytest -q çalıştır. Bana şunları söyle: tablodaki benim işlerim neler, hangi işi kimden bekliyorum, ilk hangi dalı açmalıyım.

----------------------------------------------------------------------
P1-F  FURKAN: İŞ 1, GÖRÜŞ HATTI DALINI MAIN'E HAZIRLA (Aşama 0, hedef 23 Kasım)
----------------------------------------------------------------------
CLAUDE.md'yi oku. feature/line-of-sight-test dalındayım. Bu dalı main'e PR ile birleştirmeye hazırlamak istiyorum:
1. main'i bu dala merge et, çakışma varsa çöz.
2. data/raw/opencellid/286.csv.gz dosyasının SHA256'sını hesapla. data/data_manifest.csv'deki değerle (80d2456a... ile başlıyor) aynı mı, bana söyle. Aynı değilse dur ve dosyayı Özkan'dan isteyeceğimi not et.
3. Aynıysa scripts/check_opencellid.py, scripts/build_grid.py ve scripts/los_demo.py'yi sırayla yeniden çalıştır. reports/checks/los_antalya.csv eskisiyle aynı mı, farkı tablo olarak göster.
4. data/data_manifest.csv'de main'e göre sadece tekrar eden 4 satırın silinmesi kalsın, satır sonları main'deki gibi olsun. Düz git diff'te sadece 4 satır görünmeli.
5. pytest -q çalıştır, hepsi geçmeli.
Her adımı ayrı commit yap. Push etmeden önce bana sor. Push'tan sonra PR açıklaması için kısa bir İngilizce metin yaz: ne eklendi, testler, Antalya sonucu (görünen/görünmeyen karolarda medyan hız ve p değeri).

----------------------------------------------------------------------
P2-Ö  ÖZKAN: İŞ 2, SCENE SINIFI (Aşama 1, hedef 25 Kasım)
----------------------------------------------------------------------
CLAUDE.md ve docs/scene_format.md'yi oku. main'den feature/scene-format dalını aç.
src/guvenli_rota/scene/ altında docs/scene_format.md'deki Python API'yi yaz (core.py, __init__.py):
- Scene.load(path), Scene.save(path): scene.json, terrain.tif, obstacles.geojson, observers.json, tasks.json, isteğe bağlı landcover.tif.
- Doğrulama: eksik dosya, eksik alan, format_version uyuşmazlığı, raster boyutu ile scene.json'daki width/height uyuşmazlığı, gözlemci ya da görev noktası sahne dışında. Her hata hangi dosyada ve hangi alanda olduğunu söylesin.
- surface(): terrain_is_surface false ise terrain + rasterleştirilmiş engel yükseklikleri (aynı hücrede birden çok engel varsa en yükseği), true ise terrain.
- obstacle_mask(), world_to_cell(x, y), cell_to_world(r, c).
- Engel rasterleştirmede rasterio.features.rasterize kullan, all_touched=False.
Testler (tests/test_scene.py): elle kurulan 20x20 küçük bir sahneyi kaydet-yükle, aynı kalmalı; iki terrain_is_surface durumunda surface() doğru; bozuk sahnede anlaşılır hata; world_to_cell ve cell_to_world birbirinin tersi.
CI'da rasterio ve shapely gerekiyorsa .github/workflows/tests.yml'deki pip install satırına ekle.
Küçük commitler at, pytest geçsin, push etmeden önce bana sor. PR açıklamasında diğerlerinin kullanacağı API'yi 5 satırlık bir örnekle göster.

----------------------------------------------------------------------
P3-İ  İKBAL: İŞ 3, SENTETİK SAHNE ÜRETECİ (Aşama 1-2, hedef 29 Kasım)
----------------------------------------------------------------------
CLAUDE.md ve docs/scene_format.md'yi oku. main'den feature/synthetic-scenes dalını aç.

Birinci kısım (Scene sınıfı main'e girmeden yapılabilir):
src/guvenli_rota/scene/synthetic.py içinde:
- make_terrain(kind, seed, size_m=3000, resolution_m=5): kind "flat" (çok hafif dalgalı ova) ve "hills" (birkaç Gauss tepesi + birkaç katmanlı gürültü, yükseklik farkı 50-150 m). Vakit kalırsa "valley" ve "urban".
- make_obstacles(terrain, seed, building_density, ...): dikdörtgen bina prizmaları (yükseklik 3-30 m), birkaç araç (yaklaşık 2x5 m, 1,5 m), binalar üst üste binmesin. shapely Polygon + height_m + kind.
- make_observers ve make_tasks: noktalar bina içinde olmasın; görevlerin başlangıç ve hedefi sahnenin karşı kenarlarına yakın.
- Aynı seed her zaman aynı sonucu versin (numpy Generator kullan, global random kullanma).
- Çözünürlük: araziyi önce 5 m'de üret, 10 ve 30 m'yi bundan ortalama alarak türet. Böylece aynı seed'in üç çözünürlüğü aynı dünyayı temsil eder.

İkinci kısım (Scene main'e girdikten sonra, git pull):
- make_scene(kind, seed, resolution_m, building_density, n_observers, n_tasks) bir Scene döndürsün.
- scripts/make_synthetic_scenes.py: flat ve hills için seed 0-4, 5/10/30 m sahneleri data/scenes/ altına yazsın; her sahne için yukarıdan bakış görseli (arazi gölgelendirmesi, binalar, gözlemciler, görevler) reports/figures/synthetic/ altına.
Testler (tests/test_synthetic.py): aynı seed iki kez aynı sahneyi veriyor; farklı seed farklı; bina yoğunluğu istenen değerin ±%3'ü içinde; gözlemci ve görev noktaları bina içinde değil; 30 m arazi 5 m arazinin blok ortalaması.
Küçük commitler at, pytest geçsin, push etmeden önce bana sor.

----------------------------------------------------------------------
P4-F  FURKAN: İŞ 4, GÖZLEMCİ GÖRÜNÜRLÜĞÜ (Aşama 1-2, hedef 29 Kasım)
----------------------------------------------------------------------
CLAUDE.md ve docs/scene_format.md'yi oku. İş 1 main'e birleşti, git pull yaptım. main'den feature/observer-visibility dalını aç.
src/guvenli_rota/visibility/observer.py içinde connectivity/line_of_sight.py'deki line_of_sight fonksiyonunu kullanarak (kopyalama, import et) şunları yaz:
- observer_viewshed(surface, observer, cell_size, origin, time="day", target_height=1.7): bir gözlemcinin gördüğü hücreler (bool dizi). Göz yüksekliği, gündüz/gece menzili (range_day_m / range_night_m), görüş açısı fov_deg ve bakış yönü heading_deg (0 = kuzey, saat yönünde) hesaba katılsın.
- visibility_cost(surface, observers, cell_size, origin, time="day", weights=None): her hücreyi gören gözlemcilerin ağırlıklı toplamı (float dizi). Engel hücrelerinin kendisi için değer NaN değil 0 olsun, engel maskesini rota tarafı ayrıca kullanacak.
- Gözlemci kendi hücresi ve hemen yanı her zaman görünür sayılsın.
- Hız: 3 km x 3 km sahne 10 m'de (300x300) 5 gözlemci için kaç saniye sürüyor, ölç ve docstring'e yaz.
Testler (tests/test_observer_visibility.py), elle doğrulanabilir küçük dizilerle:
- Düz zeminde 360° gözlemci menzil içindeki her hücreyi görür, menzil dışını görmez.
- 90° görüş açısında, kuzeye bakan gözlemci güneydeki hücreleri görmez.
- Gözlemciyle hedef arasına yüksek bir duvar koyunca duvarın arkası görünmez.
- Gece menzili kısa olduğunda görünen hücre sayısı azalır.
- İki gözlemcinin görünürlük maliyeti, tek tek maliyetlerin toplamına eşit.
Küçük commitler at, pytest geçsin, push etmeden önce bana sor.

----------------------------------------------------------------------
P5-Fe  FEYİZ: İŞ 5, GERÇEK VERİDEN SAHNE (Aşama 1-2, hedef 29 Kasım)
----------------------------------------------------------------------
CLAUDE.md ve docs/scene_format.md'yi oku. main'den feature/real-scene-converter dalını aç.

Birinci kısım (Scene sınıfı main'e girmeden yapılabilir):
OSM pbf'ten Antalya bölgesi (config/regions.yaml) bina tabanlarını EPSG:32636'da çıkar. Senin yazdığın scripts/build_buildings.py'deki okuma kodunu yeniden kullan, kopyalama. Her bina için yükseklik: height etiketi varsa o; yoksa building:levels x 3 m; ikisi de yoksa varsayılan 6 m. height_source alanını doldur (osm_height, osm_levels, default). Kaç binanın hangi kaynaktan yükseklik aldığını reports/checks/real_scene_antalya.csv'ye yaz.

İkinci kısım (Scene main'e girdikten sonra, git pull):
src/guvenli_rota/scene/converter.py ve scripts/build_real_scene.py ile Antalya için iki sahne üret, data/scenes/ altına:
- antalya_dem: terrain.tif = ortak 30 m ızgaradaki Copernicus DEM, terrain_is_surface = true. obstacles.geojson'a binaları yaz ama surface'a eklenmez (DEM zaten bina tepelerini içeriyor).
- antalya_dem_buildings: bina hücrelerinde DEM'i komşu binasız hücrelerden yumuşat (ya da en düşük komşu değeri kullan), binaları prizma olarak ekle, terrain_is_surface = false. Hangi yöntemi seçtiğini ve nedenini docstring'e yaz.
- landcover.tif: WorldCover sınıfları aynı ızgarada.
- observers.json: elle seçilmiş 3 gözlemci (biri yüksek bir noktada 10 m kule, ikisi yerde 1,7 m). tasks.json: 5 görev. Noktalar bölge içinde ve bina dışında olsun, nasıl seçtiğini yaz.
Testler: iki sahne Scene.load ile yükleniyor; bina hücre oranı reports/checks/buildings.csv'deki değerle uyumlu (farkı yaz); antalya_dem_buildings'in bina dışındaki hücrelerinde surface ile DEM aynı.
Küçük commitler at, pytest geçsin, push etmeden önce bana sor.

----------------------------------------------------------------------
P5b-Fe  FEYİZ: GÖREV SETİ (Aşama 3)
----------------------------------------------------------------------
CLAUDE.md'yi oku. feature/real-scene-tasks dalını aç. Antalya sahneleri için tasks.json'ı genişlet: yaya ve araç modu, gündüz ve gece, toplam 20 görev. Araç görevleri için başlangıç ve hedef bir OSM yolu üzerinde olsun. Görev noktalarını seed ile tekrarlanabilir biçimde üreten bir fonksiyon yaz (elle seçmek yerine), kuralı docstring'e yaz. Test: aynı seed aynı görevleri verir, noktalar bina dışında, araç noktaları yol hücresinde. Push etmeden önce bana sor.

----------------------------------------------------------------------
P6-İ  İKBAL: İŞ 6, GÖRÜNÜRLÜK MALİYETİYLE A* (Aşama 3, hedef 2 Aralık)
----------------------------------------------------------------------
CLAUDE.md'yi oku. main'den feature/astar-visibility dalını aç. src/guvenli_rota/routing/astar.py'yi bozmadan genişlet:
- astar(...)'a isteğe bağlı visibility_cost (float dizi), w_vis (varsayılan 0) ve blocked (bool dizi, bina hücreleri) parametreleri ekle.
- Hücre çarpanı: slope_multiplier + w_vis * visibility_cost. w_vis = 0 ve blocked yokken sonuçlar eskisiyle birebir aynı olmalı, mevcut 34 test hiç değişmeden geçmeli.
- Sezgisel fonksiyonun hâlâ aşırı tahmin etmediğini (admissible) docstring'de açıkla.
- AStarResult'a rota boyunca toplam görünürlük maliyetini ve görünür hücre sayısını ekle.
Testler: tek gözlemcili küçük ızgarada w_vis büyüdükçe rotanın görünür hücre sayısı azalır (artmaz); aynı maliyet ızgarasında NetworkX ile aynı toplam maliyet; blocked hücreye hiç girilmez; tamamen kapalı hedefte "bulunamadı" döner.
Visibility modülü main'de değilse elle yazılmış küçük bir visibility_cost dizisiyle test et.
Küçük commitler at, pytest geçsin, push etmeden önce bana sor.

----------------------------------------------------------------------
P7-Ö  ÖZKAN: İŞ 7, UÇTAN UCA DEMO (Aşama 4, hedef 4 Aralık)
----------------------------------------------------------------------
CLAUDE.md'yi oku. İş 3, 4, 5 ve 6 main'de, git pull yaptım. main'den feature/unseen-route-demo dalını aç.
scripts/demo_unseen_route.py:
- Bir sentetik "hills" sahnesi (seed 0, 10 m) ve antalya_dem_buildings sahnesi için Scene.load, surface, visibility_cost (gündüz).
- Aynı görev için en kısa rota (w_vis = 0) ve görünmeyen rota (w_vis birkaç değer, örneğin 0,5 / 2 / 5).
- Tek bir şekil: arazi gölgelendirmesi, binalar, gözlemciler ve görüş alanları, rotalar. reports/figures/demo_unseen_<sahne>.png.
- Tablo: rota uzunluğu (m), uzunluk artışı (%), görünür kalınan yol oranı (%), hesaplama süresi. reports/checks/demo_unseen.csv.
Bunu tek komutla çalışacak şekilde yaz ve README'ye "Demo" bölümü olarak ekle. Push etmeden önce bana sor.

----------------------------------------------------------------------
P8  ÖZKAN + FURKAN: İŞ 8, İLK DENEY (Aşama 4, hedef 6 Aralık)
----------------------------------------------------------------------
CLAUDE.md'yi oku. main'den feature/exp-visibility dalını aç.
scripts/exp_visibility.py:
- "hills" tipi, seed 0-4, 5/10/30 m. Her sahnede 10 görev.
- Her görev için en kısa rota ve görünmeyen rota (w_vis sabit, değeri argümanla verilsin).
- Görünür kalınan yol oranını iki şekilde ölç: rotanın kendi çözünürlüğündeki görünürlükle (planlayıcının tahmini) ve aynı seed'in 5 m sahnesindeki görünürlükle (referans). İkisi arasındaki farkı yaz; 30 m'nin ne kadar hata yaptığı buradan görülecek.
- Çıktı: reports/checks/exp_visibility.csv (her satır bir görev) ve reports/checks/exp_visibility_summary.csv (çözünürlük başına medyan ve çeyrekler).
- Özet için Spearman korelasyonu (tahmin ile referans) ve eşleştirilmiş Wilcoxon testi (en kısa ile görünmeyen rota) hesapla, p değerlerini yaz. Sonuç zayıf çıkarsa da olduğu gibi yaz.
- Toplam çalışma süresini ölç; 10 dakikayı geçerse görev sayısını argümanla küçültülebilir yap.
Push etmeden önce bana sor.

----------------------------------------------------------------------
P9-Ö  ÖZKAN: İŞ 9, CI, README VE RAPOR PLANI (Aşama 2 ve 4, hedef 6 Aralık)
----------------------------------------------------------------------
CLAUDE.md'yi oku. main'den feature/docs-meeting5 dalını aç.
1. GitHub Actions son çalışmalarının durumunu kontrol etmenin yolunu bana söyle; CI'da kurulmayan bir bağımlılık yüzünden atlanan test var mı, bak.
2. README.md: Status bölümünü güncelle, Demo ve Experiments bölümlerini ekle, "Team and contributions" tablosu ekle (her kişi, sorumlu olduğu modüller, PR numaraları). AI use bölümünü koru.
3. docs/final_report_outline.md: final rapor başlıkları (İngilizce), her başlığın altında 2-3 maddelik içerik notu ve sorumlu kişi. Başlıklar: Abstract, Introduction and problem, Related work, Requirements, System design (scene format, visibility, routing), Data, Experiments and results, Discussion and limitations, Plan for Senior Design II, AI use statement, References.
4. docs/presentation_plan.md: 10-12 dakikalık sunumun akışı, kim hangi kısmı anlatacak, demoda ne gösterilecek.
Push etmeden önce bana sor.

----------------------------------------------------------------------
P10-F  FURKAN: İŞ 10, IŞIN İZLEMEYLE ZEMİN GERÇEĞİ (Aşama 3, yetişirse)
----------------------------------------------------------------------
CLAUDE.md ve docs/scene_format.md'yi oku. main'den feature/ground-truth-raycast dalını aç.
src/guvenli_rota/visibility/ground_truth.py:
- Bir sentetik sahneyi üçgen ağa çevir (arazi ızgarası + bina prizmaları). trimesh kullan; ray hızlandırma için embree kuruluysa onu, değilse trimesh'in varsayılanını kullan.
- point_visible(scene, observer, points): gözlemcinin gözünden her noktaya (yerden 1,7 m) ışın at, arada üçgen varsa görünmez.
- route_visibility(scene, observers, route_xy, step_m=1.0): rota üzerinde 1 m aralıklı noktalarda görünür kalınan yol oranı.
Testler: düz zemin + tek duvar sahnesinde sonucu elle bilinen değerle karşılaştır; ızgara tabanlı observer_viewshed ile 5 m'lik sentetik sahnede çoğu noktada uyuşuyor.
3 km x 3 km sahnede 10 km'lik rota için süreyi ölç. 5. görüşmeye yetişmezse yapılan kısmı ve kalan işi PR açıklamasına yaz. Push etmeden önce bana sor.

----------------------------------------------------------------------
P11-İFe  İKBAL + FEYİZ: ENTEGRASYON TESTLERİ (Aşama 4)
----------------------------------------------------------------------
CLAUDE.md'yi oku. main'den feature/integration-tests dalını aç. tests/test_integration.py: küçük bir sentetik sahne üret (Scene), görünürlük maliyetini hesapla, en kısa ve görünmeyen rotayı bul. Şunları kontrol et: iki rota da başlangıç ve hedefi bağlıyor, bina hücresine girmiyor, görünmeyen rotanın görünür hücre sayısı en kısanınkinden fazla değil; sahne kaydet-yükle sonrası aynı rota çıkıyor. Testin CI'da 30 saniyeden kısa sürmesi için sahneyi küçük tut. Bulduğun hataları ilgili kişinin dalına değil, ayrı bir issue olarak yaz (başlık + nasıl tekrarlanır). Push etmeden önce bana sor.

----------------------------------------------------------------------
P12-H  HERKES: FİNAL RAPOR BÖLÜMÜ (Aşama 5)
----------------------------------------------------------------------
CLAUDE.md ve docs/final_report_outline.md'yi oku. Bana atanmış bölüm(ler): <buraya yaz>. Bu bölümü docs/final_report/<bölüm_adı>.md olarak İngilizce yaz. Sadece repodaki kodda ve reports/ altındaki sonuçlarda olan bilgiyi kullan, sayı uydurma; her sayının hangi dosyadan geldiğini yorum olarak not et. Şekil gerekiyorsa reports/figures/'daki mevcut şekilleri kullan. Abartılı ifadeler kullanma, sonucun zayıf olduğu yerde zayıf olduğunu yaz. Yapay zekâ kullanımını AI use bölümü için bana bir iki cümleyle özetle. Push etmeden önce bana sor.

----------------------------------------------------------------------
P13-Ö  ÖZKAN: RAPORU VE REPOYU TOPARLA (Aşama 5)
----------------------------------------------------------------------
CLAUDE.md'yi oku. docs/final_report/ altındaki bölümleri tek bir docs/final_report.md'de birleştir, tutarsız terimleri ve tekrarları düzelt, her sayının reports/ altındaki dosyalarla aynı olduğunu kontrol et ve farklı olanları listele. README'nin baştan sona güncel olduğunu, kurulum ve demo komutlarının temiz bir klonda çalıştığını kontrol et. Kimsenin token'ı ya da .env dosyası geçmiş commitlerde yok mu, git log ile tara. Sonra v0.1-cse491 etiketi için öneri yap. Push etmeden önce bana sor.

----------------------------------------------------------------------
P14-H  HERKES: SUNUM VE SENIOR DESIGN II PLANI (Aşama 6)
----------------------------------------------------------------------
CLAUDE.md, docs/presentation_plan.md ve docs/final_report.md'yi oku. Benim sunumda anlatacağım kısım: <buraya yaz>. Bu kısım için 3-4 slaytlık içerik (başlık + 3 madde + hangi şekil) ve konuşma notu yaz. Jüri bu kısımla ilgili ne sorabilir, 5 soru ve kısa cevaplarını çıkar. Senior Design II planına benim modülüm için 3 madde öner (NAMOA*, NSGA-II, dil modeliyle gerekçe, arayüz, ışın izleme). Dosyaya yazma, bana göster.
