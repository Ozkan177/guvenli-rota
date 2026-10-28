"""Clip ESA WorldCover 10 m 2021 v200 to each region (window read from the public COG).

Usage: python scripts/download_worldcover.py
Output: data/raw/<region>/worldcover_2021_v200.tif (EPSG:4326, 10 m class codes)
"""
import math

from guvenli_rota.common import buffered_bbox, clip_cog, load_regions, log_download, region_dir

BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
BUFFER_DEG = 0.005


def tile_url(lon, lat):
    # 3x3 degree tiles named by their south-west corner
    y, x = math.floor(lat / 3) * 3, math.floor(lon / 3) * 3
    return f"{BASE}/ESA_WorldCover_10m_2021_v200_N{y:02d}E{x:03d}_Map.tif"


if __name__ == "__main__":
    for name, r in load_regions().items():
        bbox = buffered_bbox(r["bbox"], BUFFER_DEG)
        url = tile_url(bbox[0], bbox[1])
        out = region_dir(name) / "worldcover_2021_v200.tif"
        clip_cog(url, bbox, out)
        log_download("ESA WorldCover 10 m", "2021 v200", url, out)
        print(f"{name}: {out}")
