"""Validate the building grid and calculate building/WorldCover/slope statistics.

Usage: PYTHONPATH=src python scripts/check_buildings.py
Output: reports/checks/buildings.csv
"""
import numpy as np
import pandas as pd
import rasterio

from guvenli_rota.common import GRID_CRS, GRID_RES, PROCESSED, REPORTS, grid_spec, load_regions

BUILT_CLASS = 50

rows = []
for name, region in load_regions().items():
    transform, shape = grid_spec(region)
    paths = {
        layer: PROCESSED / name / f"{layer}.tif"
        for layer in ("buildings", "slope", "landcover")
    }
    with rasterio.open(paths["buildings"]) as buildings_src, \
            rasterio.open(paths["slope"]) as slope_src, \
            rasterio.open(paths["landcover"]) as landcover_src:
        assert buildings_src.crs == GRID_CRS, f"{name}: building CRS differs"
        assert buildings_src.shape == shape, f"{name}: building shape differs"
        assert buildings_src.transform == transform, f"{name}: building transform differs"
        for layer, source in (("slope", slope_src), ("landcover", landcover_src)):
            assert source.crs == buildings_src.crs, f"{name}: {layer} CRS differs"
            assert source.shape == buildings_src.shape, f"{name}: {layer} shape differs"
            assert source.transform == buildings_src.transform, f"{name}: {layer} transform differs"
        assert transform.c % GRID_RES == 0 and transform.f % GRID_RES == 0, \
            f"{name}: origin not on the 30 m lattice"

        buildings = buildings_src.read(1)
        building_count = int(buildings_src.tags().get("building_count", 0))
        slope = slope_src.read(1)
        landcover = landcover_src.read(1)

    assert np.isfinite(buildings).all() and ((buildings >= 0) & (buildings <= 1)).all(), \
        f"{name}: building fractions outside [0, 1]"
    building_cells = buildings > 0
    worldcover_built = landcover == BUILT_CLASS
    building_area = float(buildings.mean())
    overlap_area = float((buildings * worldcover_built).mean())
    worldcover_built_area = float(worldcover_built.mean())
    rows.append({
        "region": name,
        "building_count": building_count,
        "building_area_pct": round(building_area * 100, 2),
        "worldcover_built_area_pct": round(worldcover_built_area * 100, 2),
        "building_area_in_worldcover_built_pct": round(
            overlap_area / building_area * 100, 2
        ) if building_area else 0,
        "worldcover_built_area_covered_by_buildings_pct": round(
            overlap_area / worldcover_built_area * 100, 2
        ) if worldcover_built_area else 0,
        "slope_mean_building_cells": round(float(slope[building_cells].mean()), 2)
        if building_cells.any() else None,
        "slope_mean_nonbuilding_cells": round(float(slope[~building_cells].mean()), 2),
        "crs": GRID_CRS,
        "res_m": GRID_RES,
        "same_transform_shape_as_other_layers": True,
    })

df = pd.DataFrame(rows)
(REPORTS / "checks").mkdir(parents=True, exist_ok=True)
df.to_csv(REPORTS / "checks" / "buildings.csv", index=False)
print(df.to_string(index=False))
print("\nAll building-grid alignment assertions passed.")
