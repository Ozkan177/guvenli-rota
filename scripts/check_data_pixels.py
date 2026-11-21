"""Fingerprint the pixel content of the raw DEM and WorldCover rasters.

The file SHA256 in data/data_manifest.csv changes with compression and GDAL version even when the
pixels are identical. This script hashes the decoded pixel array instead, so two downloads can be
compared across machines.

Usage: python scripts/check_data_pixels.py   ->  reports/checks/data_pixels.csv
"""
import hashlib

import pandas as pd
import rasterio

from guvenli_rota.common import RAW, REPORTS, ROOT, load_regions

FILES = ["dem_glo30.tif", "worldcover_2021_v200.tif"]

rows = []
for name in load_regions():
    for fname in FILES:
        path = RAW / name / fname
        with rasterio.open(path) as src:
            pixels = src.read()
            rows.append({
                "file": path.relative_to(ROOT).as_posix(),
                "width": src.width,
                "height": src.height,
                "bands": src.count,
                "dtype": str(pixels.dtype),
                "crs": str(src.crs),
                "nodata": str(src.nodata),
                "transform": ",".join(repr(v) for v in tuple(src.transform)[:6]),
                "pixel_sha256": hashlib.sha256(pixels.tobytes()).hexdigest(),
            })

df = pd.DataFrame(rows)
(REPORTS / "checks").mkdir(parents=True, exist_ok=True)
df.to_csv(REPORTS / "checks" / "data_pixels.csv", index=False)
print(df.drop(columns="transform").to_string(index=False))
