"""Synthetic test scenes: terrain, buildings, vehicles, observers and tasks from a seed.

Every scene lives in a local frame of the scene CRS (EPSG:32636) whose top-left corner is (0, size_m),
so x runs 0..size_m to the east and y runs 0..size_m to the north, all in metres.

Reproducibility: each part draws from its own numpy Generator seeded with (seed, part), so the same seed
always gives the same scene, and changing for example the building density does not move the hills.
No global random state is used.

Resolutions: the terrain is always generated at BASE_RESOLUTION_M (5 m) and coarser grids (10, 30 m) are
block means of it, so the three resolutions of one seed describe the same world. Obstacles, observers and
tasks are generated in world coordinates from the 5 m terrain and are identical at every resolution.

Obstacles are axis-aligned rectangles (GeoJSON features in the scene format). Observers and task points are
placed so that the whole CLEAR_CELL_M x CLEAR_CELL_M (30 m) grid cell around them is free of obstacles.
Since 5, 10 and 30 m cells nest, their cell is then free of obstacles at every supported resolution.
"""
import math

import numpy as np
from scipy import ndimage

BASE_RESOLUTION_M = 5
SIZE_M = 3000
CLEAR_CELL_M = 30
KINDS = ("flat", "hills")
CRS = "EPSG:32636"

# independent random streams per scene part
_TERRAIN, _OBSTACLES, _OBSERVERS, _TASKS = range(4)


def _rng(seed, part):
    if not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError(f"seed must be a non-negative integer, got {seed!r}")
    return np.random.default_rng([int(seed), part])


def _grid_size(size_m, resolution_m):
    if size_m % BASE_RESOLUTION_M or resolution_m % BASE_RESOLUTION_M or size_m % resolution_m:
        raise ValueError(f"size_m ({size_m}) and resolution_m ({resolution_m}) must be multiples of "
                         f"{BASE_RESOLUTION_M} m and resolution_m must divide size_m")
    return int(size_m // resolution_m)


def block_mean(array, factor):
    """Mean over non-overlapping factor x factor blocks (shape must be divisible by factor)."""
    h, w = array.shape
    if h % factor or w % factor:
        raise ValueError(f"shape {array.shape} is not divisible by {factor}")
    return array.astype(np.float64).reshape(h // factor, factor, w // factor, factor).mean(axis=(1, 3))


def _smooth_noise(rng, shape, scale_m):
    """Unit-std Gaussian noise smoothed at a length scale of scale_m metres (on the 5 m base grid)."""
    noise = ndimage.gaussian_filter(rng.standard_normal(shape), scale_m / BASE_RESOLUTION_M, mode="reflect")
    return noise / noise.std()


def make_terrain(kind, seed, size_m=SIZE_M, resolution_m=BASE_RESOLUTION_M):
    """(H, W) float32 ground elevation in metres. Row 0 is the northern edge.

    kind "flat":  plain at ~1000 m with very gentle undulation, relief (max - min) 1-4 m.
    kind "hills": 4-7 Gaussian hills plus three octaves of smoothed noise (300, 100, 30 m), rescaled so
                  the relief is 50-150 m (drawn from the seed), base elevation 500 m.
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    n = _grid_size(size_m, BASE_RESOLUTION_M)
    factor = _grid_size(resolution_m, BASE_RESOLUTION_M)
    _grid_size(size_m, resolution_m)
    rng = _rng(seed, _TERRAIN)
    coords = (np.arange(n) + 0.5) * BASE_RESOLUTION_M
    x, y = np.meshgrid(coords, size_m - coords)  # cell centres, y decreasing with row

    if kind == "flat":
        z = _smooth_noise(rng, (n, n), 400) + 0.3 * _smooth_noise(rng, (n, n), 100)
        relief, base = rng.uniform(1.0, 4.0), 1000.0
    else:
        z = np.zeros((n, n))
        for _ in range(rng.integers(4, 8)):
            cx, cy = rng.uniform(0, size_m, 2)
            sigma = rng.uniform(0.07, 0.2) * size_m
            z += rng.uniform(0.4, 1.0) * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2))
        z = z / z.max()
        for scale_m, amp in ((300, 0.15), (100, 0.05), (30, 0.01)):
            z += amp * _smooth_noise(rng, (n, n), scale_m)
        relief, base = rng.uniform(50.0, 150.0), 500.0

    z = (base + (z - z.min()) / (z.max() - z.min()) * relief).astype(np.float32)
    # coarser grids are block means of the float32 5 m grid, exactly as make_scene derives them
    return block_mean(z, factor).astype(np.float32)


def slope_deg(terrain, resolution_m):
    """Slope in degrees from central differences (same formula as scripts/build_grid.py)."""
    gy, gx = np.gradient(terrain.astype(np.float64), resolution_m)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def _rect_feature(x1, y1, x2, y2, kind, height_m):
    """Axis-aligned rectangle as a scene-format obstacle feature (exterior ring counter-clockwise)."""
    ring = [[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]]
    return {"type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[float(a), float(b)] for a, b in ring]]},
            "properties": {"kind": kind, "height_m": float(height_m), "height_source": "synthetic"}}


def rect_bounds(feature):
    """(x1, y1, x2, y2) of an axis-aligned rectangle feature."""
    ring = np.asarray(feature["geometry"]["coordinates"][0], dtype=float)
    return ring[:, 0].min(), ring[:, 1].min(), ring[:, 0].max(), ring[:, 1].max()


class _Occupancy:
    """1 m occupancy grid of the scene, row 0 = northern edge, used to keep rectangles apart."""

    def __init__(self, size_m):
        self.size = int(size_m)
        self.grid = np.zeros((self.size, self.size), dtype=bool)

    def _window(self, x1, y1, x2, y2):
        r1, r2 = max(0, math.floor(self.size - y2)), min(self.size, math.ceil(self.size - y1))
        c1, c2 = max(0, math.floor(x1)), min(self.size, math.ceil(x2))
        return slice(r1, r2), slice(c1, c2)

    def free(self, x1, y1, x2, y2, gap=0.0):
        return not self.grid[self._window(x1 - gap, y1 - gap, x2 + gap, y2 + gap)].any()

    def add(self, x1, y1, x2, y2):
        self.grid[self._window(x1, y1, x2, y2)] = True


def _occupancy(obstacles, size_m):
    occ = _Occupancy(size_m)
    for f in obstacles:
        occ.add(*rect_bounds(f))
    return occ


def make_obstacles(terrain, seed, building_density=0.10, n_vehicles=10, resolution_m=BASE_RESOLUTION_M,
                   building_size_m=(8, 30), building_height_m=(3, 30), vehicle_size_m=(2, 5),
                   vehicle_height_m=1.5, gap_m=3, max_slope_deg=20.0, max_attempts=200_000):
    """Buildings and vehicles as scene-format obstacle features (GeoJSON Feature dicts).

    building_density: share of the scene area covered by building footprints (vehicles not counted).
    Buildings are axis-aligned rectangles with sides in building_size_m and heights in building_height_m,
    corners on whole metres, at least gap_m apart, and only where the terrain slope at the footprint centre
    is at most max_slope_deg. Buildings are added until their total footprint reaches the target area.
    Vehicles are 2 x 5 m (either orientation), 1.5 m high, placed on free ground after the buildings.
    """
    if not 0 <= building_density < 0.5:
        raise ValueError("building_density must be in [0, 0.5)")
    size_m = terrain.shape[0] * resolution_m
    slope = slope_deg(terrain, resolution_m)
    rng = _rng(seed, _OBSTACLES)
    occ = _Occupancy(size_m)
    features = []

    def place(w, h, kind, height):
        x1 = int(rng.integers(0, size_m - w + 1))
        y1 = int(rng.integers(0, size_m - h + 1))
        x2, y2 = x1 + w, y1 + h
        r = min(int((size_m - (y1 + y2) / 2) // resolution_m), terrain.shape[0] - 1)
        c = min(int(((x1 + x2) / 2) // resolution_m), terrain.shape[1] - 1)
        if slope[r, c] > max_slope_deg or not occ.free(x1, y1, x2, y2, gap_m):
            return 0
        occ.add(x1, y1, x2, y2)
        features.append(_rect_feature(x1, y1, x2, y2, kind, height))
        return w * h

    target, area, attempts = building_density * size_m ** 2, 0, 0
    lo, hi = building_size_m
    while area < target:
        attempts += 1
        if attempts > max_attempts:
            raise RuntimeError(f"could only reach building density {area / size_m ** 2:.3f} of "
                               f"{building_density} after {max_attempts} attempts")
        w, h = (int(v) for v in rng.integers(lo, hi + 1, 2))
        area += place(w, h, "building", round(float(rng.uniform(*building_height_m)), 1))

    placed, attempts = 0, 0
    while placed < n_vehicles:
        attempts += 1
        if attempts > max_attempts:
            raise RuntimeError(f"could only place {placed} of {n_vehicles} vehicles")
        w, h = vehicle_size_m if rng.random() < 0.5 else vehicle_size_m[::-1]
        placed += place(int(w), int(h), "vehicle", vehicle_height_m) > 0
    return features


def building_density(obstacles, size_m=SIZE_M):
    """Share of the scene area covered by building footprints."""
    area = sum((x2 - x1) * (y2 - y1) for x1, y1, x2, y2 in
               (rect_bounds(f) for f in obstacles if f["properties"]["kind"] == "building"))
    return area / size_m ** 2


def _free_point(rng, occ, slope, x_range, y_range, max_slope_deg, max_attempts=10_000):
    """Random point inside x_range x y_range whose whole CLEAR_CELL_M cell is free and not too steep."""
    size_m = occ.size
    for _ in range(max_attempts):
        x, y = rng.uniform(*x_range), rng.uniform(*y_range)
        cx1 = math.floor(x / CLEAR_CELL_M) * CLEAR_CELL_M
        cy1 = math.floor(y / CLEAR_CELL_M) * CLEAR_CELL_M
        if not occ.free(cx1, cy1, cx1 + CLEAR_CELL_M, cy1 + CLEAR_CELL_M):
            continue
        r = min(int((size_m - y) // BASE_RESOLUTION_M), slope.shape[0] - 1)
        c = min(int(x // BASE_RESOLUTION_M), slope.shape[1] - 1)
        if slope[r, c] <= max_slope_deg:
            return round(float(x), 1), round(float(y), 1)
    raise RuntimeError(f"no free point found in x {x_range}, y {y_range}")


def _base_terrain(terrain, resolution_m):
    if resolution_m != BASE_RESOLUTION_M:
        raise ValueError(f"pass the {BASE_RESOLUTION_M} m terrain so points do not depend on the resolution")
    return slope_deg(terrain, resolution_m)


def make_observers(terrain, obstacles, seed, n=3, resolution_m=BASE_RESOLUTION_M, eye_height_m=1.7,
                   range_day_m=1500.0, range_night_m=300.0, fov_choices=(360.0, 180.0, 120.0)):
    """n observers at free points (not in or next to an obstacle), ids G1..Gn.

    Field of view is drawn from fov_choices and heading (0 = north, clockwise) uniformly, both from the seed.
    """
    slope = _base_terrain(terrain, resolution_m)
    size_m = terrain.shape[0] * resolution_m
    rng = _rng(seed, _OBSERVERS)
    occ = _occupancy(obstacles, size_m)
    margin = 0.05 * size_m
    observers = []
    for i in range(n):
        x, y = _free_point(rng, occ, slope, (margin, size_m - margin), (margin, size_m - margin), 30.0)
        observers.append({"id": f"G{i + 1}", "x": x, "y": y, "eye_height_m": eye_height_m,
                          "range_day_m": range_day_m, "range_night_m": range_night_m,
                          "fov_deg": float(fov_choices[rng.integers(len(fov_choices))]),
                          "heading_deg": round(float(rng.uniform(0, 360)), 1)})
    return observers


def make_tasks(terrain, obstacles, seed, n=10, resolution_m=BASE_RESOLUTION_M, mode="pedestrian", time="day",
               edge_band=(0.03, 0.12), max_slope_deg=25.0):
    """n start/goal pairs near opposite edges of the scene, ids T1..Tn.

    Each task picks west-east or south-north (and its direction) from the seed. The start lies in a band
    edge_band (as a share of the scene size) from one edge, the goal in the same band from the opposite edge,
    and the other coordinate is anywhere in the middle 80%. Points are on free, gentle ground.
    """
    slope = _base_terrain(terrain, resolution_m)
    size_m = terrain.shape[0] * resolution_m
    rng = _rng(seed, _TASKS)
    occ = _occupancy(obstacles, size_m)
    near = (edge_band[0] * size_m, edge_band[1] * size_m)
    far = (size_m - near[1], size_m - near[0])
    middle = (0.1 * size_m, 0.9 * size_m)
    tasks = []
    for i in range(n):
        a, b = (near, far) if rng.random() < 0.5 else (far, near)
        if rng.random() < 0.5:  # west-east
            start = _free_point(rng, occ, slope, a, middle, max_slope_deg)
            goal = _free_point(rng, occ, slope, b, middle, max_slope_deg)
        else:  # south-north
            start = _free_point(rng, occ, slope, middle, a, max_slope_deg)
            goal = _free_point(rng, occ, slope, middle, b, max_slope_deg)
        tasks.append({"id": f"T{i + 1}", "start": list(start), "goal": list(goal), "mode": mode, "time": time})
    return tasks


def scene_name(kind, seed, resolution_m):
    return f"synthetic_{kind}_s{seed}_{int(resolution_m)}m"


def make_scene(kind, seed, resolution_m=10, building_density=0.10, n_observers=3, n_tasks=10, size_m=SIZE_M):
    """A Scene (docs/scene_format.md) for the given kind, seed and resolution.

    Obstacles, observers and tasks are generated on the 5 m terrain, so they are the same at every resolution.
    """
    from guvenli_rota.scene.core import FORMAT_VERSION, Scene

    base = make_terrain(kind, seed, size_m, BASE_RESOLUTION_M)
    terrain = block_mean(base, _grid_size(resolution_m, BASE_RESOLUTION_M)).astype(np.float32)
    obstacles = make_obstacles(base, seed, building_density)
    n = _grid_size(size_m, resolution_m)
    return Scene(
        meta={"format_version": FORMAT_VERSION, "name": scene_name(kind, seed, resolution_m),
              "source": "synthetic", "seed": int(seed), "crs": CRS, "resolution_m": float(resolution_m),
              "width": n, "height": n, "origin": [0.0, float(size_m)], "terrain_is_surface": False,
              "notes": f"{kind} scene, {n_observers} observers, building density {building_density:.0%}"},
        terrain=terrain,
        obstacles=obstacles,
        observers=make_observers(base, obstacles, seed, n_observers),
        tasks=make_tasks(base, obstacles, seed, n_tasks),
    )
