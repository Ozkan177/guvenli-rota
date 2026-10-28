"""Numbers for the meeting 3 needs: vehicle vs pedestrian, day/night, coverage gaps.

Usage: python scripts/check_needs.py   ->  reports/checks/needs.csv
Slope thresholds are illustrative, not project decisions.
"""
import numpy as np
import osmium
import pandas as pd
import rasterio

from guvenli_rota.common import PROCESSED, RAW, REPORTS, load_regions

TAGS = ["surface", "tracktype", "access", "smoothness", "lit", "maxspeed"]
OFFROAD_VEHICLE = [30, 40, 60]  # grass, crop, bare: open land a vehicle may cross
NO_GO = [80, 90]  # water, wetland

rows = []
for name, r in load_regions().items():
    lay = {}
    for layer in ["slope", "landcover", "roads"]:
        with rasterio.open(PROCESSED / name / f"{layer}.tif") as s:
            lay[layer] = s.read(1)
    slope, lc, roads = lay["slope"], lay["landcover"], lay["roads"]
    row = {"region": name}
    row |= {f"slope_gt{t}_pct": round(float(np.mean(slope > t) * 100), 1) for t in [10, 15, 20, 30]}
    row["vehicle_road_cells_pct"] = round(float(np.mean((roads >= 1) & (roads <= 6)) * 100), 1)
    row["foot_only_road_cells_pct"] = round(float(np.mean(roads == 7) * 100), 1)
    row["offroad_open_land_pct"] = round(float(np.isin(lc, OFFROAD_VEHICLE).mean() * 100), 1)
    row["offroad_open_land_slope_le15_pct"] = round(float((np.isin(lc, OFFROAD_VEHICLE) & (slope <= 15)).mean() * 100), 1)
    row["tree_pct"] = round(float(np.mean(lc == 10) * 100), 1)
    row["no_go_water_pct"] = round(float(np.isin(lc, NO_GO).mean() * 100), 2)

    ways, tagged, tracks, track_typed = 0, dict.fromkeys(TAGS, 0), 0, 0
    for w in osmium.FileProcessor(str(RAW / name / "osm_roads.osm"), osmium.osm.WAY):
        ways += 1
        for t in TAGS:
            tagged[t] += t in w.tags
        if w.tags.get("highway") == "track":
            tracks += 1
            track_typed += "tracktype" in w.tags
    row["osm_ways"] = ways
    row |= {f"osm_{t}_tag_pct": round(tagged[t] / ways * 100, 1) for t in TAGS}
    row["osm_track_with_tracktype_pct"] = round(track_typed / tracks * 100, 1) if tracks else None
    rows.append(row)

df = pd.DataFrame(rows)
df.to_csv(REPORTS / "checks" / "needs.csv", index=False)
print(df.T.to_string(header=False))
