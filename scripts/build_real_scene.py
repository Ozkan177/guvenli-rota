"""Build the two Antalya real-data scenes and the building height report.

Usage: PYTHONPATH=src python scripts/build_real_scene.py
Inputs:  data/raw/osm/turkey-261001.osm.pbf, data/processed/antalya_periurban/{dem,landcover}.tif
Outputs: data/scenes/antalya_dem/, data/scenes/antalya_dem_buildings/
         reports/checks/real_scene_antalya.csv        (buildings per height source)
         reports/checks/real_scene_antalya_scene.csv  (building cell share, ground estimate)
         reports/figures/real_scene_antalya.png

Observer and task points are hand-picked cells (row, col) on the 30 m grid, chosen by looking at the
DEM, the OSM building mask and the road raster (scripts/build_grid.py). Rules used when picking:
- every point is a non-building cell (checked below, the script stops otherwise);
- the tower stands on the southern tip of the travertine plateau (about 240 m), where it overlooks
  the city below; the two ground observers stand on streets inside the built-up area;
- task start and goal lie near opposite edges of the region, so every route crosses the city.
P5b (feature/real-scene-tasks) replaces the hand-picked tasks with a seeded generator.
"""
import warnings

import numpy as np
import pandas as pd
import rasterio

from guvenli_rota.common import DATA, PROCESSED, RAW, REPORTS, load_regions
from guvenli_rota.scene.converter import (buildings_to_grid, height_source_counts, make_real_scenes,
                                          read_osm_buildings)

REGION = "antalya_periurban"
PREFIX = "antalya"
PBF = RAW / "osm" / "turkey-261001.osm.pbf"
OUT = DATA / "scenes"

# Footprints are already clipped to the grid in buildings_to_grid; Scene's area check still flags
# ~1e-13 m2 of float noise on thousands of them, so that one warning is silenced here.
warnings.filterwarnings("ignore", message=".*footprint extends outside the scene.*")

# id, (row, col), eye height, day range, night range, note
OBSERVERS = [
    ("G1", (185, 170), 10.0, 3000.0, 600.0, "10 m tower on the plateau tip above the city, 243 m DEM"),
    ("G2", (255, 175), 1.7, 1500.0, 300.0, "on a street in the central built-up area"),
    ("G3", (232, 280), 1.7, 1500.0, 300.0, "on a street in the eastern built-up area"),
]
# id, start (row, col), goal (row, col), time
TASKS = [
    ("T1", (290, 10), (290, 323), "day"),     # west -> east across the southern city
    ("T2", (10, 250), (323, 250), "day"),     # north -> south along the eastern part
    ("T3", (60, 60), (300, 200), "day"),      # plateau -> city, down the escarpment
    ("T4", (318, 21), (15, 320), "day"),      # south-west -> north-east diagonal
    ("T5", (150, 5), (200, 325), "night"),    # west -> east below the plateau, at night
]


def cell_xy(transform, rc):
    r, c = rc
    x, y = transform * (c + 0.5, r + 0.5)
    return round(float(x), 2), round(float(y), 2)


def check_points(mask):
    for oid, rc, *_ in OBSERVERS:
        assert not mask[rc], f"observer {oid} at cell {rc} is inside a building"
    for tid, start, goal, _ in TASKS:
        for name, rc in (("start", start), ("goal", goal)):
            assert not mask[rc], f"task {tid} {name} at cell {rc} is inside a building"


def plot(dem_scene, bld_scene, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LightSource

    x0, y0 = dem_scene.meta["origin"]
    h, w = dem_scene.shape
    res = dem_scene.resolution
    extent = (x0, x0 + w * res, y0 - h * res, y0)
    mask = dem_scene.obstacle_mask()
    lowered = dem_scene.terrain - bld_scene.terrain

    fig, axes = plt.subplots(1, 2, figsize=(15, 7))
    ax = axes[0]
    shade = LightSource(azdeg=315, altdeg=45).hillshade(dem_scene.terrain, dx=res, dy=res, vert_exag=2)
    ax.imshow(shade, cmap="gray", extent=extent)
    ax.imshow(np.ma.masked_where(~mask, mask), cmap="autumn", alpha=0.6, extent=extent)
    for o in dem_scene.observers:
        ax.plot(o["x"], o["y"], "^", ms=11, mec="k", mfc="cyan" if o["eye_height_m"] > 2 else "lime")
        ax.annotate(o["id"], (o["x"], o["y"]), xytext=(5, 5), textcoords="offset points", weight="bold")
    for t in dem_scene.tasks:
        (sx, sy), (gx, gy) = t["start"], t["goal"]
        ax.annotate("", (gx, gy), (sx, sy), arrowprops=dict(arrowstyle="->", color="blue",
                                                            ls="--" if t["time"] == "night" else "-"))
        ax.annotate(t["id"], (sx, sy), xytext=(3, 3), textcoords="offset points", color="blue")
    ax.set_title("antalya: DEM hillshade, OSM building cells (orange),\n"
                 "observers (cyan = 10 m tower, green = 1.7 m), tasks (dashed = night)")
    ax = axes[1]
    im = ax.imshow(np.ma.masked_where(~mask, lowered), cmap="viridis", extent=extent)
    fig.colorbar(im, ax=ax, label="DEM - estimated ground (m)")
    ax.set_title("antalya_dem_buildings: terrain lowered under building cells")
    for a in axes:
        a.set_xlabel("x (m, EPSG:32636)")
        a.set_ylabel("y (m)")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    if not PBF.exists():
        raise FileNotFoundError(f"Missing Geofabrik extract: {PBF}. Run scripts/download_osm.py first.")
    region = load_regions()[REGION]

    raw = read_osm_buildings(PBF, {REGION: region})[REGION]
    buildings = buildings_to_grid(raw, region["utm_bounds"])
    print(f"{REGION}: {len(raw)} OSM buildings in the lon/lat box, {len(buildings)} inside the UTM grid")

    heights = pd.DataFrame(height_source_counts(buildings))
    heights.insert(0, "region", REGION)
    (REPORTS / "checks").mkdir(parents=True, exist_ok=True)
    heights.to_csv(REPORTS / "checks" / "real_scene_antalya.csv", index=False)
    print(heights.to_string(index=False))

    with rasterio.open(PROCESSED / REGION / "dem.tif") as src:
        dem, transform = src.read(1), src.transform
    with rasterio.open(PROCESSED / REGION / "landcover.tif") as src:
        assert src.transform == transform and src.shape == dem.shape, "landcover grid differs from DEM grid"
        landcover = src.read(1)
    assert np.isfinite(dem).all(), "DEM has nodata cells"

    observers = []
    for oid, rc, eye, day, night, _ in OBSERVERS:
        x, y = cell_xy(transform, rc)
        observers.append({"id": oid, "x": x, "y": y, "eye_height_m": eye, "range_day_m": day,
                          "range_night_m": night, "fov_deg": 360.0, "heading_deg": 0.0})
    tasks = [{"id": tid, "start": list(cell_xy(transform, s)), "goal": list(cell_xy(transform, g)),
              "mode": "pedestrian", "time": time} for tid, s, g, time in TASKS]

    dem_scene, bld_scene = make_real_scenes(
        PREFIX, REGION, dem, transform, buildings, observers, tasks, landcover=landcover,
        notes="OSM Geofabrik turkey-261001; building height from OSM height, building:levels x 3 m, else 6 m.")
    mask = dem_scene.obstacle_mask()
    check_points(mask)
    for scene in (dem_scene, bld_scene):
        scene.save(OUT / scene.meta["name"])
        print(f"wrote {OUT / scene.meta['name']}")

    ref = pd.read_csv(REPORTS / "checks" / "buildings.csv").set_index("region").loc[REGION]
    lowered = (dem_scene.terrain - bld_scene.terrain)[mask]
    cell_pct = round(100 * float(mask.mean()), 2)
    summary = pd.DataFrame([{
        "region": REGION,
        "n_buildings": len(buildings),
        "building_cell_pct": cell_pct,
        "buildings_csv_area_pct": float(ref.building_area_pct),
        "diff_pct_points": round(cell_pct - float(ref.building_area_pct), 2),
        "ground_lowering_mean_m": round(float(lowered.mean()), 2),
        "ground_lowering_median_m": round(float(np.median(lowered)), 2),
        "ground_lowering_max_m": round(float(lowered.max()), 2),
        "building_cells_unchanged_pct": round(100 * float((lowered == 0).mean()), 2),
    }])
    summary.to_csv(REPORTS / "checks" / "real_scene_antalya_scene.csv", index=False)
    print(summary.T.to_string(header=False))

    plot(dem_scene, bld_scene, REPORTS / "figures" / "real_scene_antalya.png")


if __name__ == "__main__":
    main()
