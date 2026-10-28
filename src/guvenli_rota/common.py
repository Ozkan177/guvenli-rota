"""Shared helpers for Phase 0 data scripts: paths, regions, download manifest."""
import csv
import hashlib
from datetime import date
from pathlib import Path

import yaml
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
MANIFEST = DATA / "data_manifest.csv"
PROCESSED = DATA / "processed"
REPORTS = ROOT / "reports"
GRID_CRS = "EPSG:32636"
GRID_RES = 30
MANIFEST_FIELDS = ["dataset", "version", "source", "file", "download_date", "size_bytes", "sha256"]


def load_regions():
    """Return {name: region dict} from config/regions.yaml, adding a WGS84 'bbox' (lon/lat)."""
    with open(ROOT / "config" / "regions.yaml", encoding="utf-8") as f:
        regions = yaml.safe_load(f)["regions"]
    to_wgs = Transformer.from_crs(GRID_CRS, "EPSG:4326", always_xy=True)
    for r in regions.values():
        r["bbox"] = to_wgs.transform_bounds(*r["utm_bounds"], densify_pts=21)
    return regions


def grid_spec(region):
    """Affine transform and (rows, cols) of the region's 30 m grid in GRID_CRS."""
    from rasterio.transform import from_origin

    x1, y1, x2, y2 = region["utm_bounds"]
    shape = (round((y2 - y1) / GRID_RES), round((x2 - x1) / GRID_RES))
    return from_origin(x1, y2, GRID_RES, GRID_RES), shape


def to_utm(lon, lat):
    return Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True).transform(lon, lat)


def load_cells(name):
    """OpenCelliD cells clipped to the buffered region, with UTM x/y columns."""
    import pandas as pd

    df = pd.read_csv(RAW / name / "opencellid_cells.csv")
    df["x"], df["y"] = to_utm(df.lon.values, df.lat.values)
    return df


def cluster_sites(cells, dist_m=300):
    """Group cells (antenna sectors) into sites: complete-linkage clusters no wider than dist_m.

    Returns one row per site: x, y (mean of member cells), n_cells, radios.
    """
    import numpy as np
    import pandas as pd
    from scipy.cluster.hierarchy import fcluster, linkage

    if len(cells) == 0:
        return pd.DataFrame(columns=["x", "y", "n_cells", "radios"])
    xy = cells[["x", "y"]].to_numpy()
    labels = np.ones(len(xy), int) if len(xy) == 1 else fcluster(linkage(xy, "complete"), dist_m, "distance")
    g = cells.assign(site=labels).groupby("site")
    return pd.DataFrame({
        "x": g.x.mean(), "y": g.y.mean(), "n_cells": g.size(),
        "radios": g.radio.agg(lambda r: "+".join(sorted(set(r)))),
    }).reset_index(drop=True)


def in_utm_box(x, y, region):
    x1, y1, x2, y2 = region["utm_bounds"]
    return (x >= x1) & (x <= x2) & (y >= y1) & (y <= y2)


def buffered_bbox(bbox, deg):
    return (bbox[0] - deg, bbox[1] - deg, bbox[2] + deg, bbox[3] + deg)


def region_dir(name):
    d = RAW / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def clip_cog(url, bbox, out):
    """Read a lon/lat bbox window from a public COG on the source pixel grid and save it as GeoTIFF."""
    import rasterio
    from rasterio.windows import from_bounds

    env = {"AWS_NO_SIGN_REQUEST": "YES", "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR"}
    with rasterio.Env(**env), rasterio.open("/vsicurl/" + url) as src:
        b = src.bounds
        if not (b.left <= bbox[0] and b.bottom <= bbox[1] and bbox[2] <= b.right and bbox[3] <= b.top):
            # shortcut: one source tile per region, mosaic tiles if a region ever crosses a tile edge
            raise ValueError(f"bbox {bbox} not inside {url} bounds {tuple(b)}")
        win = from_bounds(*bbox, src.transform).round_offsets().round_lengths()
        profile = src.profile | {
            "driver": "GTiff", "width": win.width, "height": win.height,
            "transform": src.window_transform(win), "compress": "deflate",
            "tiled": True, "blockxsize": 256, "blockysize": 256,
        }
        profile.pop("copy_src_overviews", None)
        with rasterio.open(out, "w", **profile) as dst:
            dst.write(src.read(window=win))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def log_download(dataset, version, source, path):
    """Append one row per produced file to data/data_manifest.csv."""
    path = Path(path)
    new = not MANIFEST.exists()
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if new:
            w.writeheader()
        w.writerow({
            "dataset": dataset,
            "version": version,
            "source": source,
            "file": path.relative_to(ROOT).as_posix(),
            "download_date": date.today().isoformat(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
