"""Test that the four grid layers are aligned cell by cell, and measure the DSM effect on slope.

Usage: python scripts/check_grid.py   ->  reports/checks/grid.csv (fails with AssertionError if misaligned)

Alignment is tested against the raw sources: grid values are compared with raw values sampled at the
cell centres, and at centres shifted by one cell. A correct grid matches best with no shift.
"""
import numpy as np
import osmnx as ox
import pandas as pd
import rasterio
from pyproj import Transformer

from guvenli_rota.common import GRID_CRS, GRID_RES, PROCESSED, RAW, REPORTS, grid_spec, load_regions

from check_osm import load_graph

LAYERS = ["dem", "slope", "landcover", "roads"]
SHIFTS = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]  # (row, col) in cells
BUILT = 50
rng = np.random.default_rng(0)


def sample_raw(path, xs, ys):
    lon, lat = Transformer.from_crs(GRID_CRS, "EPSG:4326", always_xy=True).transform(xs, ys)
    with rasterio.open(path) as src:
        return np.array([v[0] for v in src.sample(zip(lon, lat))], dtype="float64")


def shift_scores(grid, raw_path, transform, score):
    """score(grid values, raw values) for each one-cell shift of the sampling points."""
    rows = rng.integers(2, grid.shape[0] - 2, 2000)
    cols = rng.integers(2, grid.shape[1] - 2, 2000)
    out = {}
    for dr, dc in SHIFTS:
        xs, ys = rasterio.transform.xy(transform, rows + dr, cols + dc)
        out[(dr, dc)] = score(grid[rows, cols], sample_raw(raw_path, xs, ys))
    return out


rows = []
for name, r in load_regions().items():
    transform, shape = grid_spec(r)
    arr = {}
    for layer in LAYERS:
        with rasterio.open(PROCESSED / name / f"{layer}.tif") as s:
            assert s.crs == GRID_CRS and s.transform == transform and s.shape == shape, f"{name}/{layer} grid differs"
            arr[layer] = s.read(1)
    assert transform.c % GRID_RES == 0 and transform.f % GRID_RES == 0, "origin not on the 30 m lattice"
    assert np.isfinite(arr["dem"]).all() and (arr["landcover"] > 0).all(), f"{name}: empty cells"

    dem_err = shift_scores(arr["dem"], RAW / name / "dem_glo30.tif", transform,
                           lambda g, w: float(np.median(np.abs(g - w))))
    lc_agree = shift_scores(arr["landcover"], RAW / name / "worldcover_2021_v200.tif", transform,
                            lambda g, w: float(np.mean(g == w)))
    assert min(dem_err, key=dem_err.get) == (0, 0), f"{name}: DEM best at {dem_err}"
    assert max(lc_agree, key=lc_agree.get) == (0, 0), f"{name}: land cover best at {lc_agree}"

    nodes = ox.graph_to_gdfs(load_graph(name, r), edges=False).to_crs(GRID_CRS)
    rr, cc = rasterio.transform.rowcol(transform, nodes.geometry.x, nodes.geometry.y)
    rr, cc = np.array(rr), np.array(cc)
    ok = (rr >= 0) & (rr < shape[0]) & (cc >= 0) & (cc < shape[1])
    node_hit = float(np.mean(arr["roads"][rr[ok], cc[ok]] > 0))
    assert node_hit > 0.95, f"{name}: only {node_hit:.0%} of OSM nodes fall on road cells"

    built = arr["landcover"] == BUILT
    slope = arr["slope"]
    rows.append({
        "region": name, "cells": f"{shape[1]}x{shape[0]}", "crs": GRID_CRS, "res_m": GRID_RES,
        "same_transform_shape_all_layers": True,
        "dem_median_abs_err_m_noshift": round(dem_err[(0, 0)], 2),
        "dem_median_abs_err_m_best_1cell_shift": round(min(v for k, v in dem_err.items() if k != (0, 0)), 2),
        "landcover_agree_pct_noshift": round(lc_agree[(0, 0)] * 100, 1),
        "landcover_agree_pct_best_1cell_shift": round(max(v for k, v in lc_agree.items() if k != (0, 0)) * 100, 1),
        "osm_nodes_on_road_cells_pct": round(node_hit * 100, 1),
        "road_cells_pct": round(float(np.mean(arr["roads"] > 0) * 100), 1),
        "built_cells_pct": round(float(built.mean() * 100), 1),
        "slope_mean_built": round(float(slope[built].mean()), 2) if built.any() else None,
        "slope_mean_nonbuilt": round(float(slope[~built].mean()), 2),
        "slope_mean_crop": round(float(slope[arr["landcover"] == 40].mean()), 2) if (arr["landcover"] == 40).any() else None,
        "slope_p90_built": round(float(np.percentile(slope[built], 90)), 2) if built.any() else None,
    })

df = pd.DataFrame(rows)
df.to_csv(REPORTS / "checks" / "grid.csv", index=False)
print(df.T.to_string(header=False))
print("\nAll alignment assertions passed.")
