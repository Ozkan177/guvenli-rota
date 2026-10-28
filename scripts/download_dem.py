"""Clip Copernicus DEM GLO-30 to each region (window read from the public COG, no full tile download).

Usage: python scripts/download_dem.py
Output: data/raw/<region>/dem_glo30.tif (EPSG:4326, 1 arcsec)
"""
import math

from guvenli_rota.common import buffered_bbox, clip_cog, load_regions, log_download, region_dir

BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
BUFFER_DEG = 0.005  # margin so the later UTM reprojection has full coverage


def tile_url(lon, lat):
    t = f"Copernicus_DSM_COG_10_N{math.floor(lat):02d}_00_E{math.floor(lon):03d}_00_DEM"
    return f"{BASE}/{t}/{t}.tif"


if __name__ == "__main__":
    for name, r in load_regions().items():
        bbox = buffered_bbox(r["bbox"], BUFFER_DEG)
        url = tile_url(bbox[0], bbox[1])
        out = region_dir(name) / "dem_glo30.tif"
        clip_cog(url, bbox, out)
        log_download("Copernicus DEM GLO-30", "2021 (AWS open data)", url, out)
        print(f"{name}: {out}")
