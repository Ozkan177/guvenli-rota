"""Scene folder format v0.1 (see docs/scene_format.md): load, save, validate, surface."""
import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import box, shape

FORMAT_VERSION = "0.1"

SCENE_FIELDS = ("format_version", "name", "source", "seed", "crs", "resolution_m",
                "width", "height", "origin", "terrain_is_surface")
OBSERVER_FIELDS = ("id", "x", "y", "eye_height_m", "range_day_m", "range_night_m", "fov_deg", "heading_deg")
TASK_FIELDS = ("id", "start", "goal", "mode", "time")
OBSTACLE_FIELDS = ("kind", "height_m", "height_source")

SOURCES = {"synthetic", "real"}
KINDS = {"building", "vehicle", "tree"}
HEIGHT_SOURCES = {"synthetic", "osm_levels", "osm_height", "default"}
MODES = {"pedestrian", "vehicle"}
TIMES = {"day", "night"}


class SceneError(ValueError):
    """A scene folder or Scene object does not follow the format. The message names the file and field."""


@dataclass(eq=False)
class Scene:
    meta: dict
    terrain: np.ndarray
    obstacles: list
    observers: list
    tasks: list
    landcover: np.ndarray | None = None

    def __post_init__(self):
        self.terrain = np.asarray(self.terrain, dtype=np.float32)
        _validate(self)

    @property
    def resolution(self):
        return float(self.meta["resolution_m"])

    @property
    def shape(self):
        return self.meta["height"], self.meta["width"]

    @property
    def transform(self):
        x0, y0 = self.meta["origin"]
        return from_origin(x0, y0, self.resolution, self.resolution)

    @classmethod
    def load(cls, path):
        path = Path(path)
        meta = _read_json(path, "scene.json")
        rasters = {"terrain.tif": _read_raster(path, "terrain.tif")}
        if (path / "landcover.tif").exists():
            rasters["landcover.tif"] = _read_raster(path, "landcover.tif")
        fc = _read_json(path, "obstacles.geojson")
        if not isinstance(fc, dict) or fc.get("type") != "FeatureCollection" or not isinstance(fc.get("features"), list):
            raise SceneError("obstacles.geojson: must be a FeatureCollection with a 'features' list")
        scene = cls(
            meta=meta,
            terrain=rasters["terrain.tif"][0],
            obstacles=fc["features"],
            observers=_read_json(path, "observers.json"),
            tasks=_read_json(path, "tasks.json"),
            landcover=rasters["landcover.tif"][0] if "landcover.tif" in rasters else None,
        )
        for name, (_, crs, transform) in rasters.items():
            scene._check_grid(name, crs, transform)
        return scene

    def _check_grid(self, name, crs, transform):
        if crs != CRS.from_user_input(self.meta["crs"]):
            raise SceneError(f"{name}: CRS {crs} does not match scene.json crs {self.meta['crs']!r}")
        if not transform.almost_equals(self.transform, precision=1e-6):
            raise SceneError(f"{name}: origin ({transform.c}, {transform.f}) and pixel size "
                             f"({transform.a}, {-transform.e}) do not match scene.json "
                             f"origin {self.meta['origin']} and resolution_m {self.meta['resolution_m']}")

    def save(self, path):
        _validate(self)
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        _write_json(path / "scene.json", self.meta)
        _write_json(path / "obstacles.geojson", {"type": "FeatureCollection", "features": self.obstacles})
        _write_json(path / "observers.json", self.observers)
        _write_json(path / "tasks.json", self.tasks)
        self._write_raster(path / "terrain.tif", self.terrain)
        if self.landcover is not None:
            self._write_raster(path / "landcover.tif", self.landcover)

    def obstacle_heights(self):
        """(H, W) float32 obstacle height per cell, 0 where there is none; the tallest obstacle wins."""
        shapes = [(f["geometry"], float(f["properties"]["height_m"]))
                  for f in sorted(self.obstacles, key=lambda f: f["properties"]["height_m"])]
        if not shapes:
            return np.zeros(self.shape, dtype=np.float32)
        # rasterize writes shapes in order, so sorting by height leaves the tallest value in each cell
        return rasterize(shapes, out_shape=self.shape, transform=self.transform,
                         fill=0.0, all_touched=False, dtype="float32")

    def obstacle_mask(self):
        """(H, W) bool, True for cells whose centre lies inside an obstacle footprint."""
        if not self.obstacles:
            return np.zeros(self.shape, dtype=bool)
        return rasterize([(f["geometry"], 1) for f in self.obstacles], out_shape=self.shape,
                         transform=self.transform, fill=0, all_touched=False, dtype="uint8").astype(bool)

    def surface(self):
        """Elevation that blocks sight: terrain alone if it is already a surface model, else terrain + obstacles."""
        if self.meta["terrain_is_surface"]:
            return self.terrain.copy()
        return self.terrain + self.obstacle_heights()

    def contains(self, x, y):
        x0, y0 = self.meta["origin"]
        h, w = self.shape
        return x0 <= x < x0 + w * self.resolution and y0 - h * self.resolution < y <= y0

    def world_to_cell(self, x, y):
        """(row, col) of the cell that contains the point (x, y)."""
        if not self.contains(x, y):
            raise ValueError(f"point ({x}, {y}) is outside the scene")
        x0, y0 = self.meta["origin"]
        h, w = self.shape
        row = min(math.floor((y0 - y) / self.resolution), h - 1)
        col = min(math.floor((x - x0) / self.resolution), w - 1)
        return row, col

    def cell_to_world(self, row, col):
        """(x, y) of the centre of cell (row, col)."""
        h, w = self.shape
        if not (0 <= row < h and 0 <= col < w):
            raise ValueError(f"cell ({row}, {col}) is outside the {h}x{w} scene")
        x0, y0 = self.meta["origin"]
        return x0 + (col + 0.5) * self.resolution, y0 - (row + 0.5) * self.resolution

    def _write_raster(self, path, array):
        h, w = array.shape
        with rasterio.open(path, "w", driver="GTiff", width=w, height=h, count=1, dtype=array.dtype,
                           crs=self.meta["crs"], transform=self.transform, compress="deflate") as dst:
            dst.write(array, 1)


def _read_json(folder, name):
    p = folder / name
    if not p.exists():
        raise SceneError(f"{name}: file missing in {folder}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SceneError(f"{name}: invalid JSON ({e})") from None


def _read_raster(folder, name):
    p = folder / name
    if not p.exists():
        raise SceneError(f"{name}: file missing in {folder}")
    with rasterio.open(p) as src:
        return src.read(1), src.crs, src.transform


def _write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _require(item, fields, where):
    if not isinstance(item, dict):
        raise SceneError(f"{where}: must be an object")
    missing = [f for f in fields if f not in item]
    if missing:
        raise SceneError(f"{where}: missing field '{missing[0]}'")


def _check_choice(value, allowed, where, field):
    if value not in allowed:
        raise SceneError(f"{where}: field '{field}' is {value!r}, expected one of {sorted(allowed)}")


def _label(kind, i, item):
    return f"{kind} {item['id']!r}" if isinstance(item, dict) and "id" in item else f"{kind} at index {i}"


def _validate(scene):
    meta = scene.meta
    _require(meta, SCENE_FIELDS, "scene.json")
    if meta["format_version"] != FORMAT_VERSION:
        raise SceneError(f"scene.json: format_version {meta['format_version']!r} is not supported "
                         f"(expected {FORMAT_VERSION!r})")
    _check_choice(meta["source"], SOURCES, "scene.json", "source")
    if meta["source"] == "real" and "region" not in meta:
        raise SceneError("scene.json: missing field 'region' (required for real scenes)")
    if meta["source"] == "synthetic" and meta["seed"] is None:
        raise SceneError("scene.json: field 'seed' must not be null for synthetic scenes")

    expected = (meta["height"], meta["width"])
    for name, array in (("terrain.tif", scene.terrain), ("landcover.tif", scene.landcover)):
        if array is not None and array.shape != expected:
            raise SceneError(f"{name}: raster is {array.shape[0]}x{array.shape[1]} (height x width) "
                             f"but scene.json gives height={expected[0]}, width={expected[1]}")

    x0, y0 = meta["origin"]
    extent = box(x0, y0 - expected[0] * scene.resolution, x0 + expected[1] * scene.resolution, y0)
    for i, f in enumerate(scene.obstacles):
        where = f"obstacles.geojson: feature at index {i}"
        _require(f, ("geometry", "properties"), where)
        if not isinstance(f["geometry"], dict) or f["geometry"].get("type") not in ("Polygon", "MultiPolygon"):
            raise SceneError(f"{where}: field 'geometry' must be a Polygon or MultiPolygon")
        _require(f["properties"], OBSTACLE_FIELDS, f"{where}: properties")
        _check_choice(f["properties"]["kind"], KINDS, where, "kind")
        _check_choice(f["properties"]["height_source"], HEIGHT_SOURCES, where, "height_source")
        footprint = shape(f["geometry"])
        inside = footprint.intersection(extent).area
        if inside == 0:
            raise SceneError(f"{where}: footprint lies entirely outside the scene")
        if inside < footprint.area:
            warnings.warn(f"{where}: footprint extends outside the scene, only the part inside is used",
                          stacklevel=3)

    for i, o in enumerate(scene.observers):
        where = f"observers.json: {_label('observer', i, o)}"
        _require(o, OBSERVER_FIELDS, where)
        if not scene.contains(o["x"], o["y"]):
            raise SceneError(f"{where}: position ({o['x']}, {o['y']}) is outside the scene")

    if not scene.tasks:
        raise SceneError("tasks.json: needs at least one task")
    for i, t in enumerate(scene.tasks):
        where = f"tasks.json: {_label('task', i, t)}"
        _require(t, TASK_FIELDS, where)
        _check_choice(t["mode"], MODES, where, "mode")
        _check_choice(t["time"], TIMES, where, "time")
        for end in ("start", "goal"):
            x, y = t[end]
            if not scene.contains(x, y):
                raise SceneError(f"{where}: field '{end}' ({x}, {y}) is outside the scene")
