"""Build real-data scenes (docs/scene_format.md) from the common 30 m grid and OSM buildings.

Two variants per region:

- ``<prefix>_dem``: terrain.tif is the Copernicus DEM, which is a surface model (DSM) and already
  contains roofs and tree tops, so ``terrain_is_surface = true``. OSM buildings are written to
  obstacles.geojson (the planner uses them as blocked cells) but are not added to the surface.
- ``<prefix>_dem_buildings``: the DEM is replaced by an estimate of the ground under building cells
  (see :func:`ground_under_buildings`) and the OSM buildings are added back as prisms,
  ``terrain_is_surface = false``.

The OSM reader needs ``osmium`` and is imported lazily, so the rest of this module (height rules,
ground estimate, scene assembly) can be tested without it.
"""
import re

import numpy as np
from pyproj import Transformer
from shapely import set_precision, transform as transform_coords
from shapely.geometry import Polygon, box, mapping

from guvenli_rota.scene.core import FORMAT_VERSION, Scene

LEVEL_HEIGHT_M = 3.0
DEFAULT_HEIGHT_M = 6.0
MAX_HEIGHT_M = 300.0  # anything taller in this region is a tagging error
FEET_TO_M = 0.3048
HEIGHT_TAGS = ("height", "building:levels")

_NUMBER = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _first_number(text):
    m = _NUMBER.search(text)
    return float(m.group().replace(",", ".")) if m else None


def parse_height(value):
    """Metres from an OSM ``height`` tag ("12", "12 m", "12,5", "40 ft", "40'"), or None if unusable."""
    if value is None:
        return None
    text = str(value).strip().lower()
    h = _first_number(text)
    if h is None:
        return None
    if "ft" in text or "'" in text or "feet" in text:
        h *= FEET_TO_M
    return h if 0 < h <= MAX_HEIGHT_M else None


def parse_levels(value):
    """Number of floors from ``building:levels`` ("3", "3.5", "2;3" -> 3), or None if unusable."""
    if value is None:
        return None
    numbers = [_first_number(part) for part in str(value).split(";")]
    numbers = [n for n in numbers if n is not None]
    if not numbers:
        return None
    levels = max(numbers)
    return levels if 0 < levels <= MAX_HEIGHT_M / LEVEL_HEIGHT_M else None


def building_height(tags):
    """(height_m, height_source) for one building from its OSM tags.

    Rule: a valid ``height`` tag wins (``osm_height``); else ``building:levels`` x 3 m (``osm_levels``);
    else 6 m (``default``). Values that cannot be parsed or are outside (0, 300] m are ignored.
    """
    h = parse_height(tags.get("height"))
    if h is not None:
        return h, "osm_height"
    levels = parse_levels(tags.get("building:levels"))
    if levels is not None:
        return levels * LEVEL_HEIGHT_M, "osm_levels"
    return DEFAULT_HEIGHT_M, "default"


def _osm_handler_class():
    import osmium

    class BuildingHandler(osmium.SimpleHandler):
        """Closed OSM ways tagged ``building`` that intersect one of the lon/lat boxes."""

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
            tags = {k: way.tags.get(k) for k in HEIGHT_TAGS if k in way.tags}
            for name, region_box in self.boxes.items():
                if geometry.intersects(region_box):
                    self.buildings[name].append((geometry, tags))

    return BuildingHandler


def read_osm_buildings(pbf, regions):
    """{region name: [(lon/lat Polygon, height tags dict), ...]} from an OSM pbf (one pass for all regions)."""
    handler = _osm_handler_class()({name: box(*r["bbox"]) for name, r in regions.items()})
    handler.apply_file(str(pbf), locations=True)
    return handler.buildings


def buildings_to_grid(buildings, utm_bounds, crs="EPSG:32636"):
    """Project (lon/lat polygon, tags) pairs to ``crs``, clip to ``utm_bounds`` and add heights.

    Returns a list of dicts with ``geometry`` (shapely, in ``crs``), ``height_m`` and ``height_source``.
    Footprints that fall outside the box after projection are dropped.
    """
    to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    grid_box = box(*utm_bounds)
    out = []
    for geometry, tags in buildings:
        g = transform_coords(geometry, to_utm, interleaved=False).intersection(grid_box)
        if g.geom_type == "GeometryCollection":
            polys = [p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
            g = polys[0] if len(polys) == 1 else None
        if g is None or g.is_empty or g.geom_type not in ("Polygon", "MultiPolygon") or g.area <= 0:
            continue
        height, source = building_height(tags)
        out.append({"geometry": g, "height_m": round(height, 2), "height_source": source})
    return out


def height_source_counts(buildings):
    """Rows (height_source, n_buildings, pct, median/min/max height) for the height source report."""
    rows = []
    n = len(buildings)
    for source in ("osm_height", "osm_levels", "default"):
        h = np.array([b["height_m"] for b in buildings if b["height_source"] == source])
        rows.append({
            "height_source": source,
            "n_buildings": int(h.size),
            "pct": round(100 * h.size / n, 2) if n else 0.0,
            "height_median_m": float(np.median(h)) if h.size else None,
            "height_min_m": float(h.min()) if h.size else None,
            "height_max_m": float(h.max()) if h.size else None,
        })
    return rows


def obstacle_features(buildings, precision_m=0.01):
    """GeoJSON features (kind=building) for Scene.obstacles, coordinates rounded to ``precision_m``."""
    return [{
        "type": "Feature",
        "geometry": mapping(set_precision(b["geometry"], precision_m)),
        "properties": {"kind": "building", "height_m": b["height_m"], "height_source": b["height_source"]},
    } for b in buildings]


def ground_under_buildings(dsm, building_mask, max_search_cells=100):
    """Estimate bare ground in building cells from the surrounding non-building DSM cells.

    Method: inverse-distance interpolation from the nearest non-building cells
    (``rasterio.fill.fillnodata``, the GDAL FillNodata algorithm), then capped at the original DSM
    so the ground is never above the surface. Non-building cells are returned unchanged.

    Why this and not "lowest neighbour": in Antalya the building cells form large connected blocks,
    so many building cells have no non-building neighbour at all, and on a slope the lowest neighbour
    puts the ground below the downhill edge of the block. Interpolation from the block's edge follows
    the slope across the block. Its limitation: the open cells next to buildings still hold some
    roof and tree height in a 30 m DSM, so the estimated ground can stay a few metres too high.
    """
    from rasterio.fill import fillnodata

    dsm = np.asarray(dsm, dtype=np.float32)
    building_mask = np.asarray(building_mask, dtype=bool)
    if not building_mask.any():
        return dsm.copy()
    if building_mask.all():
        raise ValueError("every cell is a building cell, there is no ground to interpolate from")
    filled = fillnodata(dsm.copy(), mask=(~building_mask).astype("uint8"),
                        max_search_distance=max_search_cells, smoothing_iterations=0)
    ground = np.where(building_mask, np.minimum(filled, dsm), dsm).astype(np.float32)
    return ground


def make_real_scenes(name_prefix, region_key, dem, transform, buildings, observers, tasks,
                     landcover=None, crs="EPSG:32636", notes=""):
    """The two real-scene variants as Scene objects: (``<prefix>_dem``, ``<prefix>_dem_buildings``).

    ``dem`` is the DSM on the grid given by the rasterio ``transform`` (square cells, north up),
    ``buildings`` the output of :func:`buildings_to_grid`.
    """
    res = float(transform.a)
    if not np.isclose(-transform.e, res):
        raise ValueError("grid cells must be square and north up")
    h, w = dem.shape
    meta = {
        "format_version": FORMAT_VERSION, "source": "real", "region": region_key, "seed": None,
        "crs": crs, "resolution_m": res, "width": w, "height": h,
        "origin": [float(transform.c), float(transform.f)],
    }
    obstacles = obstacle_features(buildings)
    dem_scene = Scene(
        meta=meta | {"name": f"{name_prefix}_dem", "terrain_is_surface": True,
                     "notes": f"Copernicus DEM GLO-30 as surface; OSM buildings as obstacles only. {notes}".strip()},
        terrain=dem, obstacles=obstacles, observers=observers, tasks=tasks, landcover=landcover)
    ground = ground_under_buildings(dem, dem_scene.obstacle_mask())
    bld_scene = Scene(
        meta=meta | {"name": f"{name_prefix}_dem_buildings", "terrain_is_surface": False,
                     "notes": ("Copernicus DEM with building cells replaced by an interpolated ground "
                               f"estimate; OSM buildings added as prisms. {notes}").strip()},
        terrain=ground, obstacles=obstacles, observers=observers, tasks=tasks, landcover=landcover)
    return dem_scene, bld_scene
