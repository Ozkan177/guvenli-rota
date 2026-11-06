"""Line-of-sight demo (Antalya): viewshed of the site with the most cells, compared with Ookla speeds.

Usage: python scripts/los_demo.py   (run download_opencellid.py, check_opencellid.py and build_grid.py first)
Output: reports/figures/los_antalya.png, reports/checks/los_antalya.csv

The site is the one with the most OpenCelliD cells among sites whose centre lies inside the region box.
Each 2026Q3 Ookla tile is classified by the visibility of its centre cell. Tiles outside the 30 m grid
or beyond the maximum range are left out of the comparison: they are "not evaluated", not "not visible".
"""
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol
from scipy.stats import mannwhitneyu

from guvenli_rota.common import PROCESSED, REPORTS, in_utm_box, load_regions, to_utm
from guvenli_rota.connectivity.line_of_sight import line_of_sight

from check_ookla import load_tiles

REGION = "antalya_periurban"
ANTENNA_H, RECEIVER_H, MAX_RANGE = 30.0, 1.5, 10_000.0


def tile_cells(tiles, transform, shape):
    """Row/col of each tile centre on the grid; rows/cols are -1 when the centre is off-grid."""
    x, y = to_utm(tiles.tile_x.to_numpy(), tiles.tile_y.to_numpy())
    rows, cols = rowcol(transform, x, y)
    rows, cols = np.asarray(rows), np.asarray(cols)
    ok = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
    return np.where(ok, rows, -1), np.where(ok, cols, -1), x, y


if __name__ == "__main__":
    region = load_regions()[REGION]
    sites = pd.read_csv(PROCESSED / REGION / "sites.csv")
    inside = sites[in_utm_box(sites.x, sites.y, region)]
    if inside.empty:
        raise SystemExit(f"no OpenCelliD site inside {REGION}; run check_opencellid.py first")
    site = inside.sort_values(["n_cells", "x"], ascending=[False, True]).iloc[0]
    print(f"site: x={site.x:.0f} y={site.y:.0f} cells={site.n_cells} radios={site.radios} "
          f"(of {len(inside)} sites in box)")

    with rasterio.open(PROCESSED / REGION / "dem.tif") as src:
        dem = src.read(1).astype("float64")
        transform = src.transform
    r0, c0 = rowcol(transform, site.x, site.y)
    r0, c0 = int(r0), int(c0)

    t0 = time.perf_counter()
    visible = line_of_sight(dem, (r0, c0), cell_size=30.0, antenna_height=ANTENNA_H,
                            receiver_height=RECEIVER_H, max_range=MAX_RANGE)
    seconds = time.perf_counter() - t0
    rr, cc = np.indices(dem.shape)
    in_range = np.hypot(rr - r0, cc - c0) * 30.0 <= MAX_RANGE
    print(f"viewshed: {dem.shape[1]}x{dem.shape[0]} cells in {seconds:.1f} s, "
          f"visible {visible.mean() * 100:.1f}% of grid, {visible[in_range].mean() * 100:.1f}% of cells in range")

    # Ookla comparison
    tiles = load_tiles(REGION)
    tiles = tiles[(tiles.year == 2026) & (tiles.quarter == 3)].reset_index(drop=True)
    rows, cols, tx, ty = tile_cells(tiles, transform, dem.shape)
    on_grid = rows >= 0
    tiles["visible"] = False
    tiles.loc[on_grid, "visible"] = visible[rows[on_grid], cols[on_grid]]
    dist = np.hypot(tx - site.x, ty - site.y)
    evaluated = on_grid & (dist <= MAX_RANGE)
    ev = tiles[evaluated]

    def stats(label, t):
        return {"group": label, "n_tiles": len(t), "tests_total": int(t.tests.sum()),
                "mean_download_mbps": round(t.avg_d_kbps.mean() / 1000, 2) if len(t) else None,
                "median_download_mbps": round(t.avg_d_kbps.median() / 1000, 2) if len(t) else None,
                "test_weighted_mean_download_mbps":
                    round((t.avg_d_kbps * t.tests).sum() / t.tests.sum() / 1000, 2) if len(t) else None}

    vis, hid = ev[ev.visible], ev[~ev.visible]
    rows_out = [stats("visible", vis), stats("not_visible", hid), stats("all_evaluated", ev),
                stats("not_evaluated_off_grid_or_out_of_range", tiles[~evaluated])]
    df = pd.DataFrame(rows_out)
    if len(vis) and len(hid):
        u = mannwhitneyu(vis.avg_d_kbps, hid.avg_d_kbps, alternative="two-sided")
        df["mannwhitney_p"] = [float(f"{u.pvalue:.2g}")] + [None] * (len(df) - 1)
    df["site_x"], df["site_y"], df["site_cells"] = site.x, site.y, int(site.n_cells)
    df["antenna_height_m"], df["receiver_height_m"], df["max_range_m"] = ANTENNA_H, RECEIVER_H, MAX_RANGE
    df["compute_seconds"] = round(seconds, 2)
    (REPORTS / "checks").mkdir(parents=True, exist_ok=True)
    df.to_csv(REPORTS / "checks" / "los_antalya.csv", index=False)
    print(df.drop(columns=["site_x", "site_y", "antenna_height_m", "receiver_height_m", "max_range_m"]).to_string(index=False))

    # Figure
    ink = "#1f2328"
    extent = [transform.c, transform.c + transform.a * dem.shape[1],
              transform.f + transform.e * dem.shape[0], transform.f]
    fig, ax = plt.subplots(figsize=(8, 7.4), constrained_layout=True)
    ax.imshow(dem, cmap="Greys", extent=extent, alpha=0.55)
    overlay = np.ma.masked_where(~visible, np.ones(dem.shape))
    ax.imshow(overlay, cmap="Blues", vmin=0, vmax=1.6, extent=extent, alpha=0.55)
    ex, ey, ev_vis = tx[evaluated], ty[evaluated], ev.visible.to_numpy()
    ax.scatter(ex[ev_vis], ey[ev_vis], s=18, c="#1b7837", ec="white", lw=0.4,
               label=f"Ookla tile, visible (n={len(vis)})")
    ax.scatter(ex[~ev_vis], ey[~ev_vis], s=18, c="#c2410c", ec="white", lw=0.4,
               label=f"Ookla tile, not visible (n={len(hid)})")
    ax.scatter([site.x], [site.y], marker="*", s=220, c="#d4a017", ec=ink, lw=0.8, label="OpenCelliD site", zorder=5)
    ax.ticklabel_format(style="plain", useOffset=False)
    ax.set_xlabel("UTM 36N easting (m)")
    ax.set_ylabel("UTM 36N northing (m)")
    ax.legend(loc="lower left", fontsize=8, framealpha=0.9)
    ax.set_title(f"Line of sight from one site ({int(site.n_cells)} cells), antenna {ANTENNA_H:.0f} m, "
                 f"receiver {RECEIVER_H} m\nvisible {visible[in_range].mean() * 100:.0f}% of cells within "
                 f"{MAX_RANGE / 1000:.0f} km, computed in {seconds:.1f} s", fontsize=10, loc="left", color=ink)
    (REPORTS / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(REPORTS / "figures" / "los_antalya.png", dpi=110)
