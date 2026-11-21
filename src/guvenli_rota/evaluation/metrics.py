"""Route evaluation metrics.

Routes are handled as (N, 2) arrays of world coordinates (x, y) in metres, not as cell indices, so a route
planned on one scene can be measured on another scene with the same origin but a different resolution.
Inputs are only a Scene, numpy arrays and the [(row, col), ...] path returned by A*.
"""
import numpy as np
from scipy import stats


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


def _visible_at(points_xy, scene, visible):
    """Bool per point: is the cell of `scene` that contains the point marked in `visible`."""
    visible = np.asarray(visible, dtype=bool)
    if visible.shape != tuple(scene.shape):
        raise ValueError(f"visible has shape {visible.shape} but the scene grid is {tuple(scene.shape)}")
    points_xy = np.asarray(points_xy, dtype=float).reshape(-1, 2)
    if len(points_xy) == 0:
        raise ValueError("no points given")
    # world_to_cell raises ValueError for a point outside the scene
    return np.array([visible[scene.world_to_cell(x, y)] for x, y in points_xy])


def visible_fraction(points_xy, scene, visible):
    """Share of the points that fall in a cell marked True in `visible` (an (H, W) bool array of `scene`).

    Raises ValueError if a point lies outside the scene or `visible` does not match the scene grid.

    The points are world coordinates, so a route planned on a coarse scene can be measured against a finer
    reference scene with the same origin. Pass the reference scene with its own visibility array:

        coarse = Scene.load("data/scenes/hills_s42_30m")
        fine = Scene.load("data/scenes/hills_s42_5m")            # same origin, 6x more cells per side
        route = path_to_xy(coarse, astar(...).path)               # planned on the 30 m grid
        pts = resample_route(route, step_m=1.0)
        visible_fraction(pts, coarse, visible_30m)                # what the planner believed
        visible_fraction(pts, fine, visible_5m)                   # measured on the 5 m reference
    """
    return float(_visible_at(points_xy, scene, visible).mean())


def visible_length_m(points_xy, scene, visible, step_m=1.0):
    """Length in metres of the polyline points_xy that runs through cells marked True in `visible`.

    The polyline is resampled every step_m metres (a no-op for points that already come from
    resample_route with the same step). Each piece between two samples counts with the mean visibility of
    its two ends, so a crossing between visible and hidden cells is off by at most step_m / 2.
    """
    pts = resample_route(points_xy, step_m)
    vis = _visible_at(pts, scene, visible).astype(float)
    seg = np.hypot(*np.diff(pts, axis=0).T)
    return float((seg * (vis[:-1] + vis[1:]) / 2).sum())


def length_increase(route_xy, baseline_xy):
    """How much longer route_xy is than baseline_xy, in percent of the baseline length."""
    base = route_length_m(baseline_xy)
    if base == 0:
        raise ValueError("baseline route has zero length")
    return 100.0 * (route_length_m(route_xy) - base) / base


def _quartiles(v):
    q1, med, q3 = np.percentile(v, [25, 50, 75])
    return float(q1), float(med), float(q3)


def paired_summary(a, b):
    """Compare paired measurements a[i], b[i] (e.g. shortest vs unseen route in the same scene).

    Differences are b - a. Returns a dict with:
      n; median, q1, q3 of a, b and the differences;
      n_positive, n_negative, n_zero: sign counts of the differences;
      p_value: two-sided Wilcoxon signed-rank test (zero differences dropped);
      rank_biserial: matched-pairs rank-biserial correlation (T+ - T-) / (T+ + T-) over the nonzero
        differences, from -1 (b always smaller) to 1 (b always larger).
    If every difference is zero, p_value is 1.0 and rank_biserial is 0.0.
    """
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.shape != b.shape or a.ndim != 1 or len(a) == 0:
        raise ValueError("a and b must be non-empty 1D arrays of the same length")
    d = b - a
    out = {"n": len(d)}
    for name, v in (("a", a), ("b", b), ("diff", d)):
        out[f"q1_{name}"], out[f"median_{name}"], out[f"q3_{name}"] = _quartiles(v)
    out["n_positive"], out["n_negative"] = int((d > 0).sum()), int((d < 0).sum())
    out["n_zero"] = int((d == 0).sum())

    nz = d[d != 0]
    if len(nz) == 0:
        out["p_value"], out["rank_biserial"] = 1.0, 0.0
        return out
    ranks = stats.rankdata(np.abs(nz))
    t_pos, t_neg = ranks[nz > 0].sum(), ranks[nz < 0].sum()
    out["p_value"] = float(stats.wilcoxon(nz).pvalue)
    out["rank_biserial"] = float((t_pos - t_neg) / (t_pos + t_neg))
    return out


def agreement(estimate, reference):
    """How well an estimate follows a reference (e.g. grid visibility vs ray-traced ground truth).

    Returns a dict with spearman_rho, p_value and mean_abs_diff (mean of |estimate - reference|).
    """
    estimate, reference = np.asarray(estimate, dtype=float), np.asarray(reference, dtype=float)
    if estimate.shape != reference.shape or estimate.ndim != 1 or len(estimate) < 2:
        raise ValueError("estimate and reference must be 1D arrays of the same length, at least 2 values")
    res = stats.spearmanr(estimate, reference)
    return {"spearman_rho": float(res.statistic), "p_value": float(res.pvalue),
            "mean_abs_diff": float(np.abs(estimate - reference).mean())}
