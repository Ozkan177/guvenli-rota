"""Download the dated Geofabrik Turkey extract and clip the road network to each region.

Usage: python scripts/download_osm.py

Output per region: data/raw/<region>/osm_roads.osm (all highway=* ways touching the
buffered region box, with all their nodes, so ways crossing the border stay whole).
"""
import hashlib
import urllib.request

import osmium

from guvenli_rota.common import RAW, buffered_bbox, load_regions, log_download, region_dir

VERSION = "261001"
URL = f"https://download.geofabrik.de/europe/turkey-{VERSION}.osm.pbf"
PBF = RAW / "osm" / f"turkey-{VERSION}.osm.pbf"
BUFFER_DEG = 0.01  # ~1 km, so the 30 m grid edges get their roads


def download():
    if PBF.exists():
        return
    PBF.parent.mkdir(parents=True, exist_ok=True)
    expected = urllib.request.urlopen(URL + ".md5").read().decode().split()[0]
    tmp = PBF.with_suffix(".part")
    md5 = hashlib.md5()
    with urllib.request.urlopen(URL) as r, open(tmp, "wb") as f:
        for chunk in iter(lambda: r.read(1 << 20), b""):
            f.write(chunk)
            md5.update(chunk)
    if md5.hexdigest() != expected:
        raise RuntimeError(f"MD5 mismatch for {URL}: got {md5.hexdigest()}, expected {expected}")
    tmp.rename(PBF)
    log_download("OpenStreetMap (Geofabrik Turkey)", VERSION, URL, PBF)


def extract(regions):
    boxes = {name: buffered_bbox(r["bbox"], BUFFER_DEG) for name, r in regions.items()}

    def inside(loc):
        return [n for n, (x1, y1, x2, y2) in boxes.items() if x1 <= loc.lon <= x2 and y1 <= loc.lat <= y2]

    # Pass 1: node ids inside each box (nodes precede ways in a sorted PBF).
    node_region = {}
    way_nodes = {n: set() for n in boxes}
    way_ids = {n: set() for n in boxes}
    for obj in osmium.FileProcessor(str(PBF), osmium.osm.NODE | osmium.osm.WAY):
        if obj.is_node():
            hits = inside(obj.location)
            if hits:
                node_region[obj.id] = hits
        elif "highway" in obj.tags:
            refs = [nd.ref for nd in obj.nodes]
            for name in {h for ref in refs for h in node_region.get(ref, ())}:
                way_ids[name].add(obj.id)
                way_nodes[name].update(refs)

    # Pass 2: write the selected nodes and ways per region.
    writers = {}
    for name in boxes:
        out = region_dir(name) / "osm_roads.osm"
        out.unlink(missing_ok=True)
        writers[name] = (osmium.SimpleWriter(str(out)), out)
    for obj in osmium.FileProcessor(str(PBF), osmium.osm.NODE | osmium.osm.WAY):
        for name, (w, _) in writers.items():
            if (obj.is_node() and obj.id in way_nodes[name]) or (obj.is_way() and obj.id in way_ids[name]):
                w.add(obj)
    for name, (w, out) in writers.items():
        w.close()
        print(f"{name}: {len(way_ids[name])} highway ways, {len(way_nodes[name])} nodes -> {out.name}")
        log_download("OpenStreetMap roads (clipped)", VERSION, f"{PBF.name} bbox+{BUFFER_DEG}deg", out)


if __name__ == "__main__":
    download()
    extract(load_regions())
