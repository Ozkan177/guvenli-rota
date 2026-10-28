"""Check the clipped ESA WorldCover 2021 v200: CRS, resolution, coverage, nodata, class shares.

Usage: python scripts/check_worldcover.py   ->  reports/checks/worldcover.csv
"""
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import from_bounds

from guvenli_rota.common import RAW, REPORTS, load_regions

# class codes from the WorldCover v2.0 product user manual
CLASSES = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built", 60: "bare",
           70: "snow_ice", 80: "water", 90: "wetland", 95: "mangrove", 100: "moss_lichen"}

rows = []
for name, r in load_regions().items():
    with rasterio.open(RAW / name / "worldcover_2021_v200.tif") as src:
        b, bbox = src.bounds, r["bbox"]
        covers = b.left <= bbox[0] and b.bottom <= bbox[1] and b.right >= bbox[2] and b.top >= bbox[3]
        lc = src.read(1, window=from_bounds(*bbox, src.transform).round_offsets().round_lengths())
        row = {"region": name, "crs": str(src.crs), "res_deg": src.res[0], "shape": f"{src.width}x{src.height}",
               "covers_region": covers, "nodata_pct": round(float(np.mean(lc == src.nodata)) * 100, 3)}
        unknown = set(np.unique(lc).tolist()) - set(CLASSES) - {src.nodata}
        assert not unknown, f"{name}: unexpected class codes {unknown}"
        row |= {f"pct_{v}": round(float(np.mean(lc == k)) * 100, 2) for k, v in CLASSES.items()}
        rows.append(row)

df = pd.DataFrame(rows)
(REPORTS / "checks").mkdir(parents=True, exist_ok=True)
df.to_csv(REPORTS / "checks" / "worldcover.csv", index=False)
print(df.T.to_string(header=False))
