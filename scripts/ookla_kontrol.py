"""Ookla 2026 Q3 mobil verisinde Türkiye ve test bölgeleri var mı?

Kurulum:  pip install duckdb
Çalıştır: python ookla_kontrol.py

190 MB'lık dosyanın tamamı indirilmez, DuckDB sadece gereken kısımları okur.
Bölge kutuları yaklaşıktır, sadece kontrol amaçlı.
"""
import duckdb

URL = ("https://ookla-open-data.s3.amazonaws.com/parquet/performance/"
       "type=mobile/year=2026/quarter=3/2026-07-01_performance_mobile_tiles.parquet")

BOLGELER = {
    # ad: (min_boylam, max_boylam, min_enlem, max_enlem)
    "Turkiye (kaba kutu)":       (25.6, 44.9, 35.8, 42.2),
    "Antalya kent cevresi":      (30.55, 30.85, 36.83, 36.95),
    "Saklikent (dagik)":         (30.20, 30.45, 36.80, 36.95),
    "Konya Ovasi - Cumra (ova)": (32.60, 32.90, 37.45, 37.65),
}

con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")

for ad, (x1, x2, y1, y2) in BOLGELER.items():
    karo, test, mbps = con.execute(f"""
        SELECT COUNT(*), SUM(tests), ROUND(AVG(avg_d_kbps) / 1000, 1)
        FROM read_parquet('{URL}')
        WHERE tile_x BETWEEN {x1} AND {x2} AND tile_y BETWEEN {y1} AND {y2}
    """).fetchone()
    print(f"{ad:28s} karo: {karo:>7}  test: {test or 0:>8}  ort. indirme: {mbps} Mbps")
