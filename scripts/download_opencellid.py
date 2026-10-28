"""Download the OpenCelliD Turkey file (MCC 286) once and clip cells to each region.

Usage: python scripts/download_opencellid.py   (needs OPENCELLID_TOKEN in .env)
Output: data/raw/opencellid/286.csv.gz, data/raw/<region>/opencellid_cells.csv

The national file can be downloaded at most twice a day, so it is never re-downloaded if present.
Rows are cells (antenna sectors), not towers; clustering into towers happens in the check step.
"""
import os
import urllib.request

import pandas as pd
from dotenv import load_dotenv

from guvenli_rota.common import MANIFEST, RAW, ROOT, buffered_bbox, load_regions, log_download, region_dir

GZ = RAW / "opencellid" / "286.csv.gz"
SOURCE = "https://opencellid.org/ocid/downloads?token=<TOKEN>&type=mcc&file=286.csv.gz"
COLUMNS = ["radio", "mcc", "net", "area", "cell", "unit", "lon", "lat", "range",
           "samples", "changeable", "created", "updated", "averageSignal"]
BUFFER_DEG = 0.05  # ~5 km: towers outside the box still serve cells inside it


def download():
    if GZ.exists():
        # file placed by hand (browser download): log it once
        if GZ.relative_to(ROOT).as_posix() not in MANIFEST.read_text(encoding="utf-8"):
            log_download("OpenCelliD (MCC 286)", "snapshot (manual download)", SOURCE, GZ)
        return
    load_dotenv(ROOT / ".env")
    token = os.environ.get("OPENCELLID_TOKEN")
    if not token:
        raise SystemExit("OPENCELLID_TOKEN missing in .env")
    GZ.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(SOURCE.replace("<TOKEN>", token), timeout=600) as r:
        body = r.read()
    if body[:2] != b"\x1f\x8b":  # API errors come back as HTTP 200 with a text body
        raise SystemExit("OpenCelliD did not return a gzip file: " + body[:200].decode(errors="replace").replace(token, "<TOKEN>"))
    GZ.write_bytes(body)
    log_download("OpenCelliD (MCC 286)", "snapshot", SOURCE, GZ)


def clip(regions):
    with pd.io.common.get_handle(GZ, "r", compression="gzip") as h:
        has_header = h.handle.readline().startswith("radio")
    df = pd.read_csv(GZ, header=0 if has_header else None, names=None if has_header else COLUMNS)
    print(f"Turkey file: {len(df)} cells")
    for name, r in regions.items():
        x1, y1, x2, y2 = buffered_bbox(r["bbox"], BUFFER_DEG)
        sub = df[df.lon.between(x1, x2) & df.lat.between(y1, y2)]
        out = region_dir(name) / "opencellid_cells.csv"
        sub.to_csv(out, index=False)
        log_download("OpenCelliD cells (clipped)", "snapshot", f"{GZ.name} bbox+{BUFFER_DEG}deg", out)
        print(f"{name}: {len(sub)} cells (box + {BUFFER_DEG} deg)")


if __name__ == "__main__":
    download()
    clip(load_regions())
