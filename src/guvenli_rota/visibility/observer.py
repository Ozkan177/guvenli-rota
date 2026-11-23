"""Observer viewshed and aggregated visibility cost on a 2-D surface grid.

Delegates ray-profile obstruction checks to ``guvenli_rota.connectivity.line_of_sight.line_of_sight``
and layers observer-specific parameters from the shared scene format (``docs/scene_format.md``):
eye height, day/night detection range, horizontal field of view, and compass heading.
"""
import math

import numpy as np

from guvenli_rota.connectivity.line_of_sight import line_of_sight

VALID_TIMES = ("day", "night")


def _validate_grid_args(surface, cell_size, origin, time):
    surface = np.asarray(surface, dtype="float64")
    if surface.ndim != 2:
        raise ValueError("surface must be 2-D")
    cell_size = float(cell_size)
    if not (math.isfinite(cell_size) and cell_size > 0):
        raise ValueError(f"cell_size must be positive and finite, got {cell_size!r}")
    if len(origin) != 2:
        raise ValueError(f"origin must be a (x0, y0) pair, got {origin!r}")
    origin = (float(origin[0]), float(origin[1]))
    if time not in VALID_TIMES:
        raise ValueError(f"time must be one of {VALID_TIMES}, got {time!r}")
    return surface, cell_size, origin


def _world_to_cell(x, y, origin, cell_size, shape):
    """Return (row, col) of the cell containing world point (x, y), matching Scene.world_to_cell."""
    x0, y0 = origin
    h, w = shape
    if not (x0 <= x < x0 + w * cell_size and y0 - h * cell_size < y <= y0):
        raise ValueError(f"observer position ({x}, {y}) is outside the {h}x{w} grid")
    row = min(math.floor((y0 - y) / cell_size), h - 1)
    col = min(math.floor((x - x0) / cell_size), w - 1)
    return row, col


def observer_viewshed(surface, observer, cell_size, origin, time="day", target_height=1.7):
    """Boolean visibility map for a single observer on ``surface``.

    Args:
        surface: 2-D array of surface elevations in metres (terrain + obstacles when applicable;
            NaN = no data).
        observer: Mapping matching an entry in ``observers.json`` with ``x``, ``y``,
            ``eye_height_m``, ``range_day_m``, ``range_night_m``, ``fov_deg``, and
            ``heading_deg`` (0 = north, clockwise; ignored when ``fov_deg`` is 360).
        cell_size: Grid spacing in metres.
        origin: ``(x0, y0)`` world coordinates of the top-left corner of cell ``(0, 0)``.
        time: ``"day"`` or ``"night"``, selecting ``range_day_m`` or ``range_night_m``.
        target_height: Target height above the surface at each cell, in metres.

    Returns:
        Bool array with the same shape as ``surface``. Cells beyond the active range, outside the
        field of view, occluded by ``surface``, or with NaN elevation are ``False``. The observer's
        own cell and its 8 immediate neighbours (where elevation is not NaN) are always ``True``.
    """
    surface, cell_size, origin = _validate_grid_args(surface, cell_size, origin, time)
    h, w = surface.shape

    ox, oy = float(observer["x"]), float(observer["y"])
    ar, ac = _world_to_cell(ox, oy, origin, cell_size, (h, w))

    range_key = "range_day_m" if time == "day" else "range_night_m"
    max_range = float(observer[range_key])
    if max_range < 0:
        raise ValueError(f"{range_key} must be non-negative, got {max_range!r}")

    fov_deg = float(observer["fov_deg"])
    if not (0.0 <= fov_deg <= 360.0):
        raise ValueError(f"fov_deg must be in [0, 360], got {fov_deg!r}")

    visible = line_of_sight(
        surface,
        (ar, ac),
        cell_size=cell_size,
        antenna_height=float(observer["eye_height_m"]),
        receiver_height=float(target_height),
        max_range=max_range,
    )

    if fov_deg < 360.0:
        heading = float(observer["heading_deg"])
        rr = np.arange(h)[:, None]
        cc = np.arange(w)[None, :]
        dx = cc - ac  # east
        dy = ar - rr  # north (row 0 is at the top / north edge)
        bearing = np.degrees(np.arctan2(dx, dy)) % 360.0
        diff = (bearing - heading + 180.0) % 360.0 - 180.0
        visible &= np.abs(diff) <= fov_deg / 2.0 + 1e-9

    # The observer's own cell and its 8 immediate neighbours are always visible when valid.
    r0, r1 = max(ar - 1, 0), min(ar + 2, h)
    c0, c1 = max(ac - 1, 0), min(ac + 2, w)
    visible[r0:r1, c0:c1] = ~np.isnan(surface[r0:r1, c0:c1])
    return visible


def visibility_cost(surface, observers, cell_size, origin, time="day", weights=None,
                    target_height=1.7, obstacle_mask=None):
    """Weighted sum of observer viewsheds on ``surface``.

    Args:
        surface: 2-D array of surface elevations in metres.
        observers: Sequence of observer mappings (same schema as ``observers.json``).
        cell_size: Grid spacing in metres.
        origin: ``(x0, y0)`` world coordinates of the top-left corner of cell ``(0, 0)``.
        time: ``"day"`` or ``"night"``.
        weights: Optional sequence of non-negative float weights, one per observer (default: 1.0
            for every observer).
        target_height: Target height above the surface at each cell, in metres.
        obstacle_mask: Optional 2-D bool array of obstacle cells. When provided, obstacle cells are
            zeroed (never NaN); the router separately blocks them via its own obstacle mask.

    Returns:
        Float64 array with the same shape as ``surface``. Values are non-negative and finite
        (no NaN); obstacle cells (when ``obstacle_mask`` is given) and cells with NaN elevation
        have value ``0.0``.
    """
    surface, cell_size, origin = _validate_grid_args(surface, cell_size, origin, time)
    observers = list(observers)

    if weights is None:
        w_arr = np.ones(len(observers), dtype="float64")
    else:
        w_arr = np.asarray(weights, dtype="float64")
        if w_arr.ndim != 1 or len(w_arr) != len(observers):
            raise ValueError(f"weights length {len(w_arr)} does not match observers length {len(observers)}")
        if not np.all(np.isfinite(w_arr)) or np.any(w_arr < 0):
            raise ValueError("weights must be finite and non-negative")

    if obstacle_mask is not None:
        obstacle_mask = np.asarray(obstacle_mask, dtype=bool)
        if obstacle_mask.shape != surface.shape:
            raise ValueError(f"obstacle_mask has shape {obstacle_mask.shape}, expected {surface.shape}")

    cost = np.zeros(surface.shape, dtype="float64")
    for obs, w in zip(observers, w_arr):
        if w == 0.0:
            continue
        vis = observer_viewshed(surface, obs, cell_size, origin, time=time, target_height=target_height)
        cost += w * vis

    if obstacle_mask is not None:
        cost[obstacle_mask] = 0.0
    return cost
