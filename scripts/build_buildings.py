"""Extract OSM building footprints and rasterize their 30 m coverage fraction.

Usage: PYTHONPATH=src python scripts/build_buildings.py
Output: data/processed/<region>/buildings.tif
"""
from pathlib import Path

import numpy as np
import osmium
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import Polygon, box
from shapely.ops import transform as transform_geometry

from guvenli_rota.common import GRID_CRS, GRID_RES, PROCESSED, RAW, grid_spec, load_regions

PBF = RAW / "osm" / "turkey-261001.osm.pbf"
SUBPIXELS = 10


class BuildingHandler(osmium.SimpleHandler):
    def __init__(self, boxes):
        super().__init__()
        self.boxes = boxes
        self.buildings = {name: [] for name in boxes}

    def way(self, way):
        if "building" not in way.tags or not way.is_closed():
            return
        points = [(node.lon, node.lat) for node in way.nodes if node.location.valid()]
        if len(points) < 4:
            return
        geometry = Polygon(points)
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        if geometry.is_empty:
            return
        for name, region_box in self.boxes.items():
            if geometry.intersects(region_box):
                self.buildings[name].append(geometry)


def extract_buildings(regions):
    boxes = {
        name: box(*r["bbox"])
        for name, r in regions.items()
    }
    handler = BuildingHandler(boxes)
    handler.apply_file(str(PBF), locations=True)
    return handler.buildings


def to_grid_geometries(geometries, region):
    to_utm = Transformer.from_crs("EPSG:4326", GRID_CRS, always_xy=True).transform
    x1, y1, x2, y2 = region["utm_bounds"]
    grid_box = box(x1, y1, x2, y2)
    return [
        transform_geometry(to_utm, geometry).intersection(grid_box)
        for geometry in geometries
    ]


def rasterize_fraction(geometries, transform, shape):
    fine_shape = (shape[0] * SUBPIXELS, shape[1] * SUBPIXELS)
    fine_transform = from_origin(
        transform.c, transform.f, GRID_RES / SUBPIXELS, GRID_RES / SUBPIXELS
    )
    mask = rasterize(
        ((geometry, 1) for geometry in geometries if not geometry.is_empty),
        out_shape=fine_shape,
        transform=fine_transform,
        fill=0,
        dtype="uint8",
    )
    return mask.reshape(shape[0], SUBPIXELS, shape[1], SUBPIXELS).mean(axis=(1, 3)).astype("float32")


def write_buildings(path, values, transform, building_count):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=values.shape[1],
        height=values.shape[0],
        count=1,
        dtype="float32",
        crs=GRID_CRS,
        transform=transform,
        nodata=0,
        compress="deflate",
    ) as dst:
        dst.write(values, 1)
        dst.update_tags(building_count=building_count, subpixels=SUBPIXELS)


if __name__ == "__main__":
    if not PBF.exists():
        raise FileNotFoundError(f"Missing Geofabrik extract: {PBF}. Run scripts/download_osm.py first.")

    regions = load_regions()
    buildings = extract_buildings(regions)
    for name, region in regions.items():
        transform, shape = grid_spec(region)
        values = rasterize_fraction(to_grid_geometries(buildings[name], region), transform, shape)
        output = PROCESSED / name / "buildings.tif"
        output.parent.mkdir(parents=True, exist_ok=True)
        write_buildings(output, values, transform, len(buildings[name]))
        print(f"{name}: {len(buildings[name])} buildings -> {output}")
