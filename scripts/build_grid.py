"""Put elevation, slope, land cover and roads on one 30 m grid per region (EPSG:32636).

Usage: python scripts/build_grid.py
Output: data/processed/<region>/{dem,slope,landcover,roads}.tif, all with the same transform and shape.
"""
import numpy as np
import osmnx as ox
import rasterio
from rasterio.features import rasterize
from rasterio.warp import Resampling, reproject

from guvenli_rota.common import GRID_CRS, GRID_RES, PROCESSED, RAW, grid_spec, load_regions

from check_osm import load_graph

# road raster codes; lower = bigger road, drawn last so it wins shared cells. 0 = no road.
ROAD_CLASS = {
    "motorway": 1, "trunk": 1, "primary": 2, "secondary": 3, "tertiary": 4,
    "residential": 5, "unclassified": 5, "living_street": 5, "service": 5, "road": 5,
    "track": 6, "path": 7, "footway": 7, "pedestrian": 7, "steps": 7, "cycleway": 7, "bridleway": 7,
}
OTHER_ROAD = 8  # construction, proposed, busway, ...


def road_code(h):
    h = h[0] if isinstance(h, list) else h
    return ROAD_CLASS.get(h.removesuffix("_link"), OTHER_ROAD)


def warp(src_path, transform, shape, resampling, dtype):
    out = np.zeros(shape, dtype)
    with rasterio.open(src_path) as src:
        reproject(rasterio.band(src, 1), out, dst_transform=transform, dst_crs=GRID_CRS, resampling=resampling)
    return out


def write(path, arr, transform, nodata=None):
    with rasterio.open(path, "w", driver="GTiff", width=arr.shape[1], height=arr.shape[0], count=1,
                       dtype=arr.dtype, crs=GRID_CRS, transform=transform, nodata=nodata, compress="deflate") as dst:
        dst.write(arr, 1)


def slope_deg(dem):
    gy, gx = np.gradient(dem, GRID_RES)
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype("float32")


if __name__ == "__main__":
    for name, r in load_regions().items():
        transform, shape = grid_spec(r)
        out = PROCESSED / name
        out.mkdir(parents=True, exist_ok=True)

        dem = warp(RAW / name / "dem_glo30.tif", transform, shape, Resampling.bilinear, "float32")
        write(out / "dem.tif", dem, transform)
        write(out / "slope.tif", slope_deg(dem), transform)
        write(out / "landcover.tif",
              warp(RAW / name / "worldcover_2021_v200.tif", transform, shape, Resampling.mode, "uint8"),
              transform, nodata=0)

        edges = ox.graph_to_gdfs(ox.convert.to_undirected(load_graph(name, r)), nodes=False).to_crs(GRID_CRS)
        codes = edges.highway.map(road_code)
        order = codes.sort_values(ascending=False).index
        roads = rasterize(zip(edges.geometry[order], codes[order]), out_shape=shape, transform=transform,
                          fill=0, dtype="uint8")
        write(out / "roads.tif", roads, transform)
        print(f"{name}: {shape[1]}x{shape[0]} cells, road cells {np.mean(roads > 0) * 100:.1f}%")
