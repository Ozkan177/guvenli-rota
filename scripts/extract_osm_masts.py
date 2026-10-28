"""Extract mast/tower nodes from the Geofabrik Turkey extract, as a possible cell site layer.

Usage: python scripts/extract_osm_masts.py   (run download_osm.py first)
Output: data/raw/osm/turkey_masts.csv, data/raw/<region>/osm_masts.csv

'is_comm' marks towers tagged as communication (tower:type=communication,
man_made=communications_tower or any communication:* key). Untagged masts may also be cell sites.
"""
import csv

import osmium

from guvenli_rota.common import RAW, buffered_bbox, load_regions, log_download, region_dir

PBF = RAW / "osm" / "turkey-261001.osm.pbf"
TYPES = {"mast", "tower", "communications_tower"}
FIELDS = ["osm_id", "lon", "lat", "man_made", "tower_type", "operator", "is_comm"]
BUFFER_DEG = 0.05  # same as OpenCelliD clip


def scan():
    rows = []
    # shortcut: nodes only; towers mapped as building outlines (ways) are skipped, add with_locations if they matter
    for n in osmium.FileProcessor(str(PBF), osmium.osm.NODE).with_filter(osmium.filter.KeyFilter("man_made")):
        mm = n.tags.get("man_made")
        if mm not in TYPES:
            continue
        tt = n.tags.get("tower:type", "")
        rows.append({
            "osm_id": n.id, "lon": n.location.lon, "lat": n.location.lat, "man_made": mm, "tower_type": tt,
            "operator": n.tags.get("operator", ""),
            "is_comm": int(tt == "communication" or mm == "communications_tower"
                           or any(t.k.startswith("communication:") for t in n.tags)),
        })
    return rows


def write(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    rows = scan()
    out = RAW / "osm" / "turkey_masts.csv"
    write(rows, out)
    log_download("OpenStreetMap masts", "261001", f"{PBF.name} man_made=mast|tower|communications_tower", out)
    print(f"Turkey: {len(rows)} masts/towers, {sum(r['is_comm'] for r in rows)} tagged as communication")
    for name, r in load_regions().items():
        x1, y1, x2, y2 = buffered_bbox(r["bbox"], BUFFER_DEG)
        sub = [m for m in rows if x1 <= m["lon"] <= x2 and y1 <= m["lat"] <= y2]
        out = region_dir(name) / "osm_masts.csv"
        write(sub, out)
        log_download("OpenStreetMap masts (clipped)", "261001", f"turkey_masts.csv bbox+{BUFFER_DEG}deg", out)
        print(f"{name}: {len(sub)} masts/towers, {sum(m['is_comm'] for m in sub)} communication")
