"""Check the clipped Copernicus DEM: CRS, resolution, coverage, voids, value range.

Usage: python scripts/check_dem.py   ->  reports/checks/dem.csv
"""
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds

from guvenli_rota.common import RAW, REPORTS, load_regions

rows = []
for name, r in load_regions().items():
    with rasterio.open(RAW / name / "dem_glo30.tif") as src:
        b = src.bounds
        bbox = r["bbox"]
        covers = b.left <= bbox[0] and b.bottom <= bbox[1] and b.right >= bbox[2] and b.top >= bbox[3]
        z = src.read(1, window=from_bounds(*bbox, src.transform).round_offsets().round_lengths())
        void = ~np.isfinite(z) | (z < -1000) | ((z == src.nodata) if src.nodata is not None else False)
        lat = (bbox[1] + bbox[3]) / 2
        rows.append({
            "region": name, "crs": str(src.crs), "res_deg": src.res[0],
            "res_m_x": round(src.res[0] * 111_320 * np.cos(np.radians(lat)), 1),
            "res_m_y": round(src.res[1] * 110_574, 1), "shape": f"{src.width}x{src.height}",
            "covers_region": covers, "void_pct": round(void.mean() * 100, 3),
            "z_min": round(float(z.min())), "z_p01": round(float(np.percentile(z, 1))),
            "z_mean": round(float(z.mean())), "z_p99": round(float(np.percentile(z, 99))),
            "z_max": round(float(z.max())),
        })

df = pd.DataFrame(rows)
(REPORTS / "checks").mkdir(parents=True, exist_ok=True)
df.to_csv(REPORTS / "checks" / "dem.csv", index=False)
print(df.to_string(index=False))
