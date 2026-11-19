"""Route evaluation metrics.

Routes are handled as (N, 2) arrays of world coordinates (x, y) in metres, not as cell indices, so a route
planned on one scene can be measured on another scene with the same origin but a different resolution.
Inputs are only a Scene, numpy arrays and the [(row, col), ...] path returned by A*.
"""
import numpy as np


def path_to_xy(scene, path):
    """(N, 2) array of the centres of the cells in an A* path [(row, col), ...]."""
    return np.array([scene.cell_to_world(r, c) for r, c in path], dtype=float).reshape(-1, 2)


def route_length_m(xy):
    """Length of the polyline through the points xy, in metres."""
    xy = np.asarray(xy, dtype=float)
    return float(np.hypot(*np.diff(xy, axis=0).T).sum())


def resample_route(xy, step_m=1.0):
    """Points every step_m metres along the polyline xy, from its first point to its last one.

    The last interval is shorter when the length is not a multiple of step_m.
    """
    if step_m <= 0:
        raise ValueError("step_m must be positive")
    xy = np.asarray(xy, dtype=float)
    seg = np.hypot(*np.diff(xy, axis=0).T)
    keep = np.concatenate([[True], seg > 0])
    xy, dist = xy[keep], np.concatenate([[0.0], np.cumsum(seg[seg > 0])])
    if len(xy) == 1:
        return xy.copy()
    d = np.append(np.arange(0.0, dist[-1], step_m), dist[-1])
    return np.column_stack([np.interp(d, dist, xy[:, 0]), np.interp(d, dist, xy[:, 1])])


def length_increase(route_xy, baseline_xy):
    """How much longer route_xy is than baseline_xy, in percent of the baseline length."""
    base = route_length_m(baseline_xy)
    if base == 0:
        raise ValueError("baseline route has zero length")
    return 100.0 * (route_length_m(route_xy) - base) / base
