"""Check Ookla mobile tiles: tiles per quarter, share of region area covered, test counts.

Usage: python scripts/check_ookla.py   ->  reports/checks/ookla.csv, reports/checks/ookla_quarters.csv
A missing tile means "no measurements", not "no coverage".
"""
import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import box, wkt

from guvenli_rota.common import GRID_CRS, RAW, REPORTS, load_regions

LATEST = (2026, 3)


def load_tiles(name):
    path = (RAW / name / "ookla_mobile_2024q1_2026q3.parquet").as_posix()
    df = duckdb.sql(f"SELECT * FROM '{path}'").df()
    return gpd.GeoDataFrame(df, geometry=df.tile.map(wkt.loads), crs="EPSG:4326")


def area_pct(tiles, region_poly):
    return tiles.to_crs(GRID_CRS).union_all().intersection(region_poly).area / region_poly.area * 100


if __name__ == "__main__":
    rows, quarters = [], []
    for name, r in load_regions().items():
        t = load_tiles(name)
        b = t.geometry.bounds
        assert np.allclose((b.minx + b.maxx) / 2, t.tile_x, atol=1e-5), "tile_x is not the tile centre"
        assert np.allclose((b.miny + b.maxy) / 2, t.tile_y, atol=1e-3), "tile_y is not the tile centre"
        x1, y1, x2, y2 = r["bbox"]
        t = t[t.tile_x.between(x1, x2) & t.tile_y.between(y1, y2)]
        poly = box(*r["utm_bounds"])
        latest = t[(t.year == LATEST[0]) & (t.quarter == LATEST[1])]
        pooled = t.drop_duplicates("quadkey")
        for (y, q), g in t.groupby(["year", "quarter"]):
            quarters.append({"region": name, "quarter": f"{y}Q{q}", "tiles": len(g), "tests": int(g.tests.sum())})
        rows.append({
            "region": name,
            "tiles_latest": len(latest), "area_pct_latest": round(area_pct(latest, poly), 1),
            "tiles_pooled_2024q1_2026q3": len(pooled), "area_pct_pooled": round(area_pct(pooled, poly), 1),
            "tests_latest_total": int(latest.tests.sum()),
            "tests_per_tile_median": float(latest.tests.median()), "tests_per_tile_p90": float(latest.tests.quantile(.9)),
            "pct_tiles_lt5_tests": round(float((latest.tests < 5).mean() * 100), 1),
            "down_mbps_median": round(latest.avg_d_kbps.median() / 1000, 1),
            "latency_ms_median": float(latest.avg_lat_ms.median()),
        })

    (REPORTS / "checks").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(REPORTS / "checks" / "ookla.csv", index=False)
    pd.DataFrame(quarters).to_csv(REPORTS / "checks" / "ookla_quarters.csv", index=False)
    print(pd.DataFrame(rows).T.to_string(header=False))
