"""Copernicus DEM, ESA WorldCover ve OpenStreetMap test bölgelerinde çalışıyor mu?

Kurulum:  pip install rasterio numpy osmnx
Çalıştır: python veri_kontrol.py

Raster dosyalar indirilmez, sadece bölge penceresi internetten okunur.
OSM yol ağı Overpass üzerinden çekilir (Konya bölgesi 1-2 dakika sürebilir).
"""
import os
from collections import Counter

import numpy as np
import rasterio
from rasterio.windows import from_bounds

os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
os.environ["AWS_NO_SIGN_REQUEST"] = "YES"

# ad: (min_boylam, min_enlem, max_boylam, max_enlem, DEM karosu)
BOLGELER = {
    "Antalya kent cevresi": (30.55, 36.83, 30.85, 36.95, "N36_00_E030_00"),
    "Saklikent (dagik)":    (30.20, 36.80, 30.45, 36.95, "N36_00_E030_00"),
    "Konya - Cumra (ova)":  (32.60, 37.45, 32.90, 37.65, "N37_00_E032_00"),
}

WORLDCOVER = ("/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/"
              "v200/2021/map/ESA_WorldCover_10m_2021_v200_N36E030_Map.tif")
SINIF = {10: "Agac", 20: "Cali", 30: "Cayir", 40: "Tarim", 50: "Yerlesim",
         60: "Ciplak/seyrek", 70: "Kar/buz", 80: "Su", 90: "Sulak alan",
         95: "Mangrov", 100: "Yosun/liken"}


def oku(yol, b):
    with rasterio.open(yol) as src:
        pencere = from_bounds(b[0], b[1], b[2], b[3], src.transform)
        dizi = src.read(1, window=pencere)
        return dizi, src.nodata, src.res


for ad, (x1, y1, x2, y2, karo) in BOLGELER.items():
    print(f"\n=== {ad} ===")
    b = (x1, y1, x2, y2)

    # 1) Copernicus DEM
    try:
        t = f"Copernicus_DSM_COG_10_{karo}_DEM"
        dem, nd, res = oku(f"/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/{t}/{t}.tif", b)
        dem = dem.astype("float32")
        bos = np.mean(dem == nd) * 100 if nd is not None else 0.0
        # eğim (derece), piksel boyutu metreye kabaca çevrilir
        dy = res[1] * 111_320
        dx = res[0] * 111_320 * np.cos(np.radians((y1 + y2) / 2))
        gy, gx = np.gradient(dem, dy, dx)
        egim = np.degrees(np.arctan(np.hypot(gx, gy)))
        print(f"DEM     : {dem.shape[1]}x{dem.shape[0]} piksel, bos %{bos:.1f}, "
              f"yukseklik {dem.min():.0f}-{dem.max():.0f} m (ort. {dem.mean():.0f}), "
              f"ort. egim {egim.mean():.1f} derece, egim>20 derece %{np.mean(egim > 20) * 100:.0f}")
    except Exception as e:
        print(f"DEM     : HATA -> {e}")

    # 2) ESA WorldCover
    try:
        wc, _, _ = oku(WORLDCOVER, b)
        sayac = Counter(wc.ravel().tolist())
        toplam = wc.size
        en_cok = ", ".join(f"{SINIF.get(k, k)} %{v / toplam * 100:.0f}"
                           for k, v in sayac.most_common(5))
        print(f"Arazi   : {wc.shape[1]}x{wc.shape[0]} piksel -> {en_cok}")
    except Exception as e:
        print(f"Arazi   : HATA -> {e}")

    # 3) OpenStreetMap
    try:
        import osmnx as ox
        G = ox.graph_from_bbox(bbox=(x1, y1, x2, y2), network_type="all")
        turler = Counter()
        for _, _, d in G.edges(data=True):
            h = d.get("highway", "?")
            turler.update(h if isinstance(h, list) else [h])
        en_cok = ", ".join(f"{k} {v}" for k, v in turler.most_common(6))
        print(f"OSM     : {G.number_of_nodes()} dugum, {G.number_of_edges()} kenar -> {en_cok}")
    except Exception as e:
        print(f"OSM     : HATA -> {e}")
