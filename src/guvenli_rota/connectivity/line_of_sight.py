"""Line-of-sight (viewshed) from one antenna to every cell of a DEM grid.

A target cell is visible when no terrain sample between the antenna top and the receiver rises
above the straight line joining them. The terrain profile is sampled once per cell size with
bilinear interpolation, so the result does not depend on the ray direction.

Limits of this model: the DEM is a surface model (DSM), so buildings and trees already block the
line, and only terrain along the profile is considered (no Fresnel zone, no diffraction).
"""
import numpy as np

EARTH_RADIUS_M = 6_371_000.0
REFRACTION_K = 4 / 3  # standard atmosphere: effective earth radius = k * R
CHUNK_CELLS = 1 << 21  # max (targets x samples) held in memory at once


def _bilinear(dem, r, c):
    """Bilinear DEM value at fractional (row, col) positions given in cell-centre coordinates."""
    rows, cols = dem.shape
    r0 = np.clip(np.floor(r).astype(int), 0, max(rows - 2, 0))
    c0 = np.clip(np.floor(c).astype(int), 0, max(cols - 2, 0))
    r1 = np.minimum(r0 + 1, rows - 1)
    c1 = np.minimum(c0 + 1, cols - 1)
    fr = r - r0
    fc = c - c0
    top = dem[r0, c0] * (1 - fc) + dem[r0, c1] * fc
    bottom = dem[r1, c0] * (1 - fc) + dem[r1, c1] * fc
    return top * (1 - fr) + bottom * fr


def line_of_sight(dem, antenna, cell_size=30.0, antenna_height=30.0, receiver_height=1.5,
                  max_range=10_000.0, earth_curvature=False):
    """Boolean visibility map from an antenna to every cell of ``dem``.

    Args:
        dem: 2-D array of elevations in metres (NaN = no data).
        antenna: (row, col) of the antenna cell.
        cell_size: grid spacing in metres.
        antenna_height: antenna height above the ground at its cell, metres.
        receiver_height: receiver height above the ground at each target cell, metres.
        max_range: cells farther than this (metres, centre to centre) are reported as not visible.
        earth_curvature: if True, add earth bulge with standard refraction (k = 4/3).

    Returns:
        Bool array shaped like ``dem``. The antenna cell is visible. Cells beyond ``max_range`` and
        cells with NaN elevation are not. NaN samples along a profile do not block the line.
    """
    dem = np.asarray(dem, dtype="float64")
    if dem.ndim != 2:
        raise ValueError("dem must be 2-D")
    rows, cols = dem.shape
    ar, ac = antenna
    if not (0 <= ar < rows and 0 <= ac < cols):
        raise ValueError(f"antenna {antenna} is outside the {rows}x{cols} grid")
    if np.isnan(dem[ar, ac]):
        raise ValueError("antenna cell has no elevation data")
    z_antenna = dem[ar, ac] + antenna_height

    visible = np.zeros(dem.shape, bool)
    visible[ar, ac] = True

    rr, cc = np.indices(dem.shape)
    dr = (rr - ar).ravel()
    dc = (cc - ac).ravel()
    dist = np.hypot(dr, dc) * cell_size
    idx = np.flatnonzero((dist <= max_range) & ((dr != 0) | (dc != 0)))
    idx = idx[np.argsort(dist[idx], kind="stable")]  # near to far keeps the sample count tight per chunk
    n_steps = np.maximum(np.ceil(dist[idx] / cell_size).astype(int), 1)

    z_target_all = dem.ravel()[idx] + receiver_height
    visible_flat = visible.reshape(-1)  # view: writes below land in `visible`
    start = 0
    while start < len(idx):
        # n_steps is sorted, so the last target of a chunk sets its array width; shrink the chunk
        # until (targets x samples) fits the memory budget
        stop = min(len(idx), start + max(CHUNK_CELLS // int(n_steps[start]), 1))
        while stop - start > 1 and (stop - start) * int(n_steps[stop - 1]) > CHUNK_CELLS:
            stop = start + max(CHUNK_CELLS // int(n_steps[stop - 1]), 1)
        sel = slice(start, stop)
        n = n_steps[sel][:, None]
        k = np.arange(1, int(n_steps[stop - 1]))[None, :]  # intermediate samples only
        frac = k / n
        valid = k < n

        r = ar + dr[idx[sel]][:, None] * frac
        c = ac + dc[idx[sel]][:, None] * frac
        terrain = _bilinear(dem, r, c)
        z_target = z_target_all[sel][:, None]
        line = z_antenna + (z_target - z_antenna) * frac
        if earth_curvature:
            d_total = dist[idx[sel]][:, None]
            d = d_total * frac
            terrain = terrain + d * (d_total - d) / (2 * REFRACTION_K * EARTH_RADIUS_M)

        with np.errstate(invalid="ignore"):  # NaN > x is False: no-data samples never block
            blocked = (valid & (terrain > line)).any(axis=1)
        visible_flat[idx[sel]] = ~blocked & ~np.isnan(z_target[:, 0])
        start = stop
    return visible
