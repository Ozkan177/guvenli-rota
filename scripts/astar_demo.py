"""A* demo on the Saklıkent slope grid: route between two points at least 5 km apart.

Usage: python scripts/astar_demo.py [--start ROW COL] [--goal ROW COL] [--max-slope DEG]
Needs: data/processed/saklikent_mountain/slope.tif (python scripts/build_grid.py)
Output: reports/figures/astar_saklikent.png, summary printed to stdout.

Without --start/--goal, the start is the passable cell nearest to 15% / 85% of the grid (south-west)
and the goal the one nearest to 85% / 15% (north-east), both inside the largest connected passable area.
"""
import argparse
import math
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import ListedColormap
from pyproj import Transformer
from scipy import ndimage

from guvenli_rota.common import GRID_CRS, PROCESSED, REPORTS
from guvenli_rota.routing.astar import DEFAULT_MAX_SLOPE_DEG, astar, passable_mask

REGION = "saklikent_mountain"
MIN_DISTANCE_M = 5000
INK, MUTED, ROUTE = "#1f2328", "#8c959f", "#0969da"
SLOPE_CMAP = ListedColormap(plt.cm.Oranges(np.linspace(0.05, 0.85, 256)))


def pick_endpoints(ok, start_frac=(0.85, 0.15), goal_frac=(0.15, 0.85)):
    """Passable cells nearest to the given (row, col) fractions, inside the largest connected passable area."""
    labels, n = ndimage.label(ok, structure=np.ones((3, 3)))
    if n == 0:
        raise SystemExit("no passable cells in the grid")
    largest = np.argmax(np.bincount(labels.ravel())[1:]) + 1
    cells = np.argwhere(labels == largest)
    rows, cols = ok.shape

    def nearest(frac):
        target = np.array([frac[0] * (rows - 1), frac[1] * (cols - 1)])
        return tuple(int(v) for v in cells[np.argmin(((cells - target) ** 2).sum(axis=1))])

    return nearest(start_frac), nearest(goal_frac)


def cell_xy(transform, cell):
    """UTM x, y of a cell centre."""
    return transform * (cell[1] + 0.5, cell[0] + 0.5)


def path_length_m(path, cell_size):
    return sum(math.hypot(r2 - r1, c2 - c1) for (r1, c1), (r2, c2) in zip(path, path[1:])) * cell_size


def plot_route(slope, ok, bounds, transform, res, start, goal, max_slope, out):
    left, bottom, right, top = (v / 1000 for v in bounds)
    fig, ax = plt.subplots(figsize=(8.5, 7.5), constrained_layout=True)
    im = ax.imshow(np.where(ok, slope, np.nan), cmap=SLOPE_CMAP, vmin=0, vmax=max_slope,
                   extent=(left, right, bottom, top), interpolation="nearest")
    ax.imshow(np.where(ok, np.nan, 1.0), cmap=ListedColormap(["#57606a"]), alpha=0.85,
              extent=(left, right, bottom, top), interpolation="nearest")
    fig.colorbar(im, ax=ax, shrink=0.8, label="slope (degrees)")

    halo = [pe.Stroke(linewidth=4, foreground="white"), pe.Normal()]
    if res.found:
        xy = np.array([cell_xy(transform, c) for c in res.path]) / 1000
        ax.plot(xy[:, 0], xy[:, 1], color=ROUTE, lw=2, path_effects=halo, label="A* route")
    for cell, name in ((start, "start"), (goal, "goal")):
        x, y = (v / 1000 for v in cell_xy(transform, cell))
        ax.plot(x, y, "o", ms=9, color=ROUTE, mec="white", mew=2, zorder=5)
        ax.annotate(name, (x, y), xytext=(7, 7), textcoords="offset points", fontsize=9, color=INK,
                    path_effects=[pe.withStroke(linewidth=3, foreground="white")])

    ax.plot([], [], "s", color="#57606a", ms=9, label=f"impassable (> {max_slope:g} deg or nodata)")
    ax.legend(loc="lower right", fontsize=8, framealpha=0.9)
    ax.set_xlabel("UTM 36N easting (km)", color=MUTED)
    ax.set_ylabel("UTM 36N northing (km)", color=MUTED)
    ax.tick_params(labelsize=8, colors=MUTED)
    summary = (f"length {path_length_m(res.path, transform.a) / 1000:.2f} km, cost {res.cost:,.0f}, "
               f"{res.expanded:,} cells expanded" if res.found else "no route found")
    ax.set_title(f"Saklıkent: slope-weighted A* ({summary})", fontsize=10, loc="left", color=INK)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--start", nargs=2, type=int, metavar=("ROW", "COL"))
    p.add_argument("--goal", nargs=2, type=int, metavar=("ROW", "COL"))
    p.add_argument("--max-slope", type=float, default=DEFAULT_MAX_SLOPE_DEG)
    args = p.parse_args()

    with rasterio.open(PROCESSED / REGION / "slope.tif") as src:
        slope = src.read(1).astype(float)
        if src.nodata is not None:
            slope[slope == src.nodata] = np.nan
        transform, bounds = src.transform, tuple(src.bounds)
    cell_size = transform.a
    ok = passable_mask(slope, args.max_slope)

    auto_start, auto_goal = pick_endpoints(ok)
    start = tuple(args.start) if args.start else auto_start
    goal = tuple(args.goal) if args.goal else auto_goal
    (x1, y1), (x2, y2) = cell_xy(transform, start), cell_xy(transform, goal)
    straight = math.hypot(x2 - x1, y2 - y1)
    if straight < MIN_DISTANCE_M:
        raise SystemExit(f"start and goal are {straight:.0f} m apart, need at least {MIN_DISTANCE_M} m")

    t0 = time.perf_counter()
    res = astar(slope, start, goal, cell_size=cell_size, max_slope_deg=args.max_slope)
    elapsed = time.perf_counter() - t0

    to_wgs = Transformer.from_crs(GRID_CRS, "EPSG:4326", always_xy=True)
    print(f"grid {slope.shape[0]}x{slope.shape[1]} cells of {cell_size:g} m, "
          f"impassable {100 * (1 - ok.mean()):.1f}% (slope > {args.max_slope:g} deg or nodata)")
    for name, cell, (x, y) in (("start", start, (x1, y1)), ("goal", goal, (x2, y2))):
        lon, lat = to_wgs.transform(x, y)
        print(f"{name}: cell {cell}, UTM ({x:.0f}, {y:.0f}), lon/lat ({lon:.5f}, {lat:.5f})")
    print(f"straight-line distance: {straight / 1000:.2f} km")
    if res.found:
        on_route = slope[tuple(np.array(res.path).T)]
        print(f"route: {len(res.path)} cells, length {path_length_m(res.path, cell_size) / 1000:.2f} km, "
              f"cost {res.cost:,.0f}, max slope on route {on_route.max():.1f} deg")
    else:
        print("route: none (goal not reachable)")
    print(f"cells expanded: {res.expanded:,}")
    print(f"A* time: {elapsed:.3f} s")

    out = REPORTS / "figures" / "astar_saklikent.png"
    plot_route(slope, ok, bounds, transform, res, start, goal, args.max_slope, out)
    print(f"figure: {out.relative_to(REPORTS.parent)}")


if __name__ == "__main__":
    main()
