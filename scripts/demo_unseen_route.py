"""End-to-end demo: scene -> observer visibility -> shortest route and unseen route -> figure and table.

Usage: python scripts/demo_unseen_route.py
Inputs:  synthetic "hills" scenes generated in memory (seeds 0-4, 10 m, building density 0.02, 4 observers),
         data/scenes/antalya_dem_buildings/ (built by scripts/build_real_scene.py)
Outputs: reports/figures/demo_unseen_synthetic.png, reports/figures/demo_unseen_antalya.png,
         reports/checks/demo_unseen.csv

For every task the shortest route (w_vis = 0) and the unseen route (w_vis = 5) are planned with A* on the
ground slope, with buildings blocked and the day-time visibility cost of all observers as the visibility term.
Visible fraction = share of 1 m samples along the route that fall in a cell seen by at least one observer.
Task shown per scene:
- synthetic: over seeds 0-4, the task whose shortest route is the most visible, among tasks where the unseen
  route is at most 30 % longer than the shortest one;
- Antalya: of the 5 tasks in tasks.json, the one whose shortest route is the most visible.
All tasks are evaluated with day-time visibility, including tasks marked "night".
"Shortest" means least slope-weighted cost (w_vis = 0), not least length, so on uneven ground the unseen route
can come out slightly shorter in metres.
"""
import time

from guvenli_rota.common import DATA, REPORTS
from guvenli_rota.evaluation.metrics import path_to_xy, resample_route, route_length_m, visible_fraction
from guvenli_rota.routing.astar import astar
from guvenli_rota.scene import Scene
from guvenli_rota.scene.synthetic import make_scene, slope_deg
from guvenli_rota.visibility import visibility_cost

W_UNSEEN = 5.0
SEEDS = range(5)
BUILDING_DENSITY = 0.02
N_OBSERVERS = 4
MAX_LENGTH_INCREASE_PCT = 30.0
ANTALYA = DATA / "scenes" / "antalya_dem_buildings"


def scene_layers(scene, time_of_day="day"):
    """Visibility cost, obstacle mask and ground slope of a scene, plus the visibility run time in seconds."""
    mask = scene.obstacle_mask()
    x0, y0 = scene.meta["origin"]
    t0 = time.perf_counter()
    vis = visibility_cost(scene.surface(), scene.observers, scene.resolution, (x0, y0),
                          time=time_of_day, obstacle_mask=mask)
    vis_s = time.perf_counter() - t0
    return {"vis": vis, "mask": mask, "slope": slope_deg(scene.terrain, scene.resolution), "vis_s": vis_s}


def plan(scene, layers, task, w_vis):
    """A* route for one task; dict with path, xy, length_m, visible_pct, vis_cost and astar_s, or None if
    unreachable. vis_cost is A*'s own route visibility cost (metres x observers), which never grows with w_vis."""
    start, goal = scene.world_to_cell(*task["start"]), scene.world_to_cell(*task["goal"])
    t0 = time.perf_counter()
    res = astar(layers["slope"], start, goal, cell_size=scene.resolution, visibility_cost=layers["vis"],
                w_vis=w_vis, blocked=layers["mask"])
    astar_s = time.perf_counter() - t0
    if not res.found:
        return None
    xy = path_to_xy(scene, res.path)
    visible = 100 * visible_fraction(resample_route(xy, 1.0), scene, layers["vis"] > 0)
    return {"path": res.path, "xy": xy, "length_m": route_length_m(xy), "visible_pct": visible,
            "vis_cost": res.visibility_cost, "astar_s": astar_s}


def route_pair(scene, layers, task):
    """Shortest and unseen route for a task, or None if either cannot be planned."""
    shortest, unseen = plan(scene, layers, task, 0.0), plan(scene, layers, task, W_UNSEEN)
    if shortest is None or unseen is None:
        return None
    unseen["length_increase_pct"] = 100 * (unseen["length_m"] / shortest["length_m"] - 1)
    shortest["length_increase_pct"] = 0.0
    return {"shortest": shortest, "unseen": unseen}


def pick(candidates, max_increase_pct=None):
    """Candidate whose shortest route is the most visible, optionally only those with a bounded detour."""
    ok = [c for c in candidates
          if max_increase_pct is None or c["pair"]["unseen"]["length_increase_pct"] <= max_increase_pct]
    if not ok:
        raise SystemExit(f"no task where the unseen route is at most {max_increase_pct} % longer")
    return max(ok, key=lambda c: c["pair"]["shortest"]["visible_pct"])


def evaluate(scene, layers):
    """One candidate per task that can be routed."""
    out = []
    for task in scene.tasks:
        pair = route_pair(scene, layers, task)
        if pair is not None:
            out.append({"scene": scene, "layers": layers, "task": task, "pair": pair})
    return out


def table_rows(c):
    rows = []
    for name, w_vis in (("shortest", 0.0), ("unseen", W_UNSEEN)):
        r = c["pair"][name]
        rows.append({
            "scene": c["scene"].meta["name"], "task": c["task"]["id"], "route": name, "w_vis": w_vis,
            "length_m": round(r["length_m"], 1), "length_increase_pct": round(r["length_increase_pct"], 1),
            "visible_pct": round(r["visible_pct"], 1), "astar_s": round(r["astar_s"], 3),
            "visibility_s": round(c["layers"]["vis_s"], 3),
        })
    return rows


def plot(c, out):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import LightSource

    scene, layers, task = c["scene"], c["layers"], c["task"]
    h, w = scene.shape
    x0, y0 = scene.meta["origin"]
    extent = (x0, x0 + w * scene.resolution, y0 - h * scene.resolution, y0)

    fig, ax = plt.subplots(figsize=(8, 8))
    shade = LightSource(azdeg=315, altdeg=45).hillshade(scene.terrain, dx=scene.resolution, dy=scene.resolution)
    ax.imshow(shade, cmap="gray", extent=extent, vmin=0, vmax=1)
    seen = np.zeros((h, w, 4))
    seen[layers["vis"] > 0] = (0.85, 0.1, 0.1, 0.35)
    ax.imshow(seen, extent=extent)
    blocks = np.zeros((h, w, 4))
    blocks[layers["mask"]] = (0, 0, 0, 1)
    ax.imshow(blocks, extent=extent)

    for name, color in (("shortest", "tab:orange"), ("unseen", "tab:blue")):
        r = c["pair"][name]
        label = (f"{name} (w_vis={0 if name == 'shortest' else W_UNSEEN:g}): "
                 f"{r['length_m']:.0f} m, {r['visible_pct']:.0f}% visible")
        ax.plot(r["xy"][:, 0], r["xy"][:, 1], color=color, lw=2.2, label=label)
    ax.plot(*task["start"], "o", color="white", mec="black", ms=9, label="start")
    ax.plot(*task["goal"], "s", color="white", mec="black", ms=9, label="goal")
    ax.plot([o["x"] for o in scene.observers], [o["y"] for o in scene.observers], "^", color="red",
            mec="black", ms=11, label="observers")
    ax.plot([], [], "s", color=(0.85, 0.1, 0.1, 0.35), ms=10, label="seen by an observer (day)")
    ax.plot([], [], "s", color="black", ms=10, label="buildings")

    ax.set_title(f"{scene.meta['name']}, task {task['id']}")
    ax.set_xlabel("Easting (m, EPSG:32636)")
    ax.set_ylabel("Northing (m)")
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main():
    import pandas as pd

    if not (ANTALYA / "scene.json").exists():
        raise SystemExit(f"{ANTALYA} not found, run: PYTHONPATH=src python scripts/build_real_scene.py")

    synthetic = []
    for seed in SEEDS:
        scene = make_scene("hills", seed, 10, building_density=BUILDING_DENSITY, n_observers=N_OBSERVERS)
        synthetic += evaluate(scene, scene_layers(scene))
    chosen_syn = pick(synthetic, MAX_LENGTH_INCREASE_PCT)

    antalya = Scene.load(ANTALYA)
    chosen_ant = pick(evaluate(antalya, scene_layers(antalya)))

    (REPORTS / "figures").mkdir(parents=True, exist_ok=True)
    (REPORTS / "checks").mkdir(parents=True, exist_ok=True)
    plot(chosen_syn, REPORTS / "figures" / "demo_unseen_synthetic.png")
    plot(chosen_ant, REPORTS / "figures" / "demo_unseen_antalya.png")
    df = pd.DataFrame(table_rows(chosen_syn) + table_rows(chosen_ant))
    df.to_csv(REPORTS / "checks" / "demo_unseen.csv", index=False, lineterminator="\n")
    print(f"synthetic: {len(synthetic)} tasks evaluated over seeds {list(SEEDS)}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
