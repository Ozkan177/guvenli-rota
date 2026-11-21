"""Write the synthetic test scenes and a top view of each to disk.

Usage: python scripts/make_synthetic_scenes.py [--kinds flat hills] [--seeds 0 1 2 3 4]
                                               [--resolutions 5 10 30] [--density 0.10] [--no-figures]
Output: data/scenes/synthetic_<kind>_s<seed>_<res>m/ (scene format, not committed) and
        reports/figures/synthetic/synthetic_<kind>_s<seed>.png, one figure per kind and seed with one
        panel per resolution, so the three resolutions of the same world can be compared side by side.
"""
import argparse
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Wedge

from guvenli_rota.common import DATA, REPORTS
from guvenli_rota.scene.synthetic import SIZE_M, building_density, make_scene

INK, MUTED = "#1f2328", "#8c959f"
OBSERVER, START, GOAL = "#cf222e", "#0969da", "#0969da"
OBSTACLE_CMAP = ListedColormap([INK])


def hillshade(z, resolution_m, azimuth_deg=315, altitude_deg=45, vert_exag=3.0):
    """Absolute hillshade in [0, 1], not stretched per image, so a flat plain stays an even grey."""
    gy, gx = np.gradient(z.astype(np.float64) * vert_exag, resolution_m)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)  # downslope direction, clockwise from north (rows run south)
    az, zen = np.radians(azimuth_deg), np.radians(90 - altitude_deg)
    return np.clip(np.cos(zen) * np.cos(slope) + np.sin(zen) * np.sin(slope) * np.cos(az - aspect), 0, 1)


def plot_panel(ax, scene, title):
    x0, y0 = scene.meta["origin"]
    h, w = scene.shape
    extent = (x0, x0 + w * scene.resolution, y0 - h * scene.resolution, y0)
    shade = hillshade(scene.terrain, scene.resolution)
    ax.imshow(shade, cmap="Greys_r", vmin=0, vmax=1, extent=extent, interpolation="nearest")
    mask = scene.obstacle_mask()
    ax.imshow(np.where(mask, 1.0, np.nan), cmap=OBSTACLE_CMAP, extent=extent, interpolation="nearest")

    for o in scene.observers:
        if o["fov_deg"] < 360:  # field of view wedge, drawn short; heading 0 = north, clockwise
            centre = 90 - o["heading_deg"]
            ax.add_patch(Wedge((o["x"], o["y"]), 0.08 * extent[1], centre - o["fov_deg"] / 2,
                               centre + o["fov_deg"] / 2, color=OBSERVER, alpha=0.25, lw=0))
        ax.plot(o["x"], o["y"], "^", ms=9, color=OBSERVER, mec="white", mew=1.2)
    for t in scene.tasks:
        (sx, sy), (gx, gy) = t["start"], t["goal"]
        ax.plot([sx, gx], [sy, gy], color=START, lw=0.8, alpha=0.5, ls="--")
        ax.plot(sx, sy, "o", ms=8, mfc="white", mec=START, mew=1.8)
        ax.plot(gx, gy, "o", ms=8, color=GOAL, mec="white", mew=1)

    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_title(f"{title}: {w}x{h} cells, obstacle cells {mask.mean() * 100:.1f}%",
                 fontsize=9, loc="left", color=INK)
    ax.tick_params(labelsize=7, colors=MUTED)


def figure(scenes, out):
    first = scenes[0]
    fig, axs = plt.subplots(1, len(scenes), figsize=(5.2 * len(scenes), 5.6), constrained_layout=True,
                            squeeze=False)
    for ax, scene in zip(axs[0], scenes):
        plot_panel(ax, scene, f"{scene.resolution:g} m")
    kind = first.meta["name"].split("_")[1]
    n_buildings = sum(f["properties"]["kind"] == "building" for f in first.obstacles)
    fig.suptitle(f"{kind}, seed {first.meta['seed']}: relief {np.ptp(first.terrain):.0f} m, "
                 f"{n_buildings} buildings ({building_density(first.obstacles, _size(first)) * 100:.1f}% "
                 f"of the area), {len(first.observers)} observers, {len(first.tasks)} tasks",
                 fontsize=11, color=INK)
    fig.legend(handles=[Patch(color=INK, label="obstacle cells (building or vehicle)"),
                        Line2D([], [], marker="^", ls="", ms=9, color=OBSERVER, mec="white",
                               label="observer (wedge: field of view)"),
                        Line2D([], [], marker="o", ls="", ms=8, mfc="white", mec=START, mew=1.8,
                               label="task start"),
                        Line2D([], [], marker="o", ls="", ms=8, color=GOAL, mec="white", label="task goal")],
               loc="lower center", ncol=4, fontsize=8, frameon=False, bbox_to_anchor=(0.5, -0.06))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=100, bbox_inches="tight")
    plt.close(fig)


def _size(scene):
    return scene.shape[1] * scene.resolution


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--kinds", nargs="+", default=["flat", "hills"])
    p.add_argument("--seeds", nargs="+", type=int, default=list(range(5)))
    p.add_argument("--resolutions", nargs="+", type=int, default=[5, 10, 30])
    p.add_argument("--density", type=float, default=0.10, help="building footprint share of the area")
    p.add_argument("--observers", type=int, default=3)
    p.add_argument("--tasks", type=int, default=10)
    p.add_argument("--size-m", type=int, default=SIZE_M)
    p.add_argument("--no-figures", action="store_true")
    args = p.parse_args()

    out_dir = DATA / "scenes"
    for kind in args.kinds:
        for seed in args.seeds:
            scenes = []
            for res in args.resolutions:
                t0 = time.perf_counter()
                scene = make_scene(kind, seed, res, args.density, args.observers, args.tasks, args.size_m)
                scene.save(out_dir / scene.meta["name"])
                scenes.append(scene)
                print(f"{scene.meta['name']}: {scene.shape[1]}x{scene.shape[0]} cells, "
                      f"relief {np.ptp(scene.terrain):.1f} m, {len(scene.obstacles)} obstacles, "
                      f"{time.perf_counter() - t0:.1f} s")
            if not args.no_figures:
                out = REPORTS / "figures" / "synthetic" / f"synthetic_{kind}_s{seed}.png"
                figure(scenes, out)
                print(f"  figure: {out.relative_to(REPORTS.parent)}")


if __name__ == "__main__":
    main()
