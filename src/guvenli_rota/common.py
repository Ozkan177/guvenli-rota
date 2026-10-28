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
GRID_CRS = "EPSG:32636"
MANIFEST_FIELDS = ["dataset", "version", "source", "file", "download_date", "size_bytes", "sha256"]


def load_regions():
    """Return {name: region dict} from config/regions.yaml, adding a WGS84 'bbox' (lon/lat)."""
    with open(ROOT / "config" / "regions.yaml", encoding="utf-8") as f:
        regions = yaml.safe_load(f)["regions"]
    to_wgs = Transformer.from_crs(GRID_CRS, "EPSG:4326", always_xy=True)
    for r in regions.values():
        r["bbox"] = to_wgs.transform_bounds(*r["utm_bounds"], densify_pts=21)
    return regions


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
