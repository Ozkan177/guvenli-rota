"""A* with a visibility cost layer and blocked (building) cells.

The visibility module is not on main yet, so these tests use small hand-written visibility_cost arrays.
"""
import math

import networkx as nx
import numpy as np
import pytest

from guvenli_rota.routing.astar import astar, passable_mask, slope_multiplier

SQ2 = math.sqrt(2)


def north_observer_grid():
    """5x9 flat grid; one observer north of it sees rows 0-2 (cost 1), rows 3-4 are hidden (cost 0)."""
    slope = np.zeros((5, 9))
    vis = np.zeros((5, 9))
    vis[:3] = 1.0
    return slope, vis


def test_visibility_fields_on_a_hand_solved_route():
    slope, vis = north_observer_grid()
    res = astar(slope, (2, 0), (2, 8), cell_size=10, visibility_cost=vis, w_vis=0.0)
    assert res.path == [(2, c) for c in range(9)]  # w_vis = 0: straight along the visible row
    assert res.cost == pytest.approx(80)
    assert res.visible_cells == 9
    assert res.visibility_cost == pytest.approx(80)  # 8 edges x 10 m x mean visibility 1


def test_large_w_vis_hides_the_route():
    slope, vis = north_observer_grid()
    res = astar(slope, (2, 0), (2, 8), cell_size=10, visibility_cost=vis, w_vis=10.0)
    # only start and goal are visible; everything in between runs through hidden row 3
    assert res.visible_cells == 2
    assert all(r >= 3 for r, _ in res.path[1:-1])
    # straight down into hidden row 3 and straight back up at the end: two 10 m steps, each half in sight.
    # (At w_vis = 0.2 it still steps in diagonally, 2 * sqrt(2) * 10 * 0.5 = 14.1; only a larger w_vis makes
    # the extra length of the orthogonal steps worth it.)
    assert res.path[:2] == [(2, 0), (3, 0)] and res.path[-2:] == [(3, 8), (2, 8)]
    assert res.visibility_cost == pytest.approx(10.0)


def test_visible_cells_do_not_increase_with_w_vis():
    slope, vis = north_observer_grid()
    counts = [astar(slope, (2, 0), (2, 8), cell_size=10, visibility_cost=vis, w_vis=w).visible_cells
              for w in (0, 0.05, 0.2, 0.5, 1, 2, 5, 20)]
    assert counts == sorted(counts, reverse=True)
    assert counts[0] > counts[-1]


@pytest.mark.parametrize("seed", range(10))
def test_route_visibility_does_not_increase_with_w_vis(seed):
    # cost = length + w * visibility, so for w1 < w2 optimality gives (w2 - w1)(V2 - V1) <= 0
    rng = np.random.default_rng(seed)
    slope = rng.uniform(0, 25, size=(15, 20))
    vis = (rng.random((15, 20)) < 0.5).astype(float)
    totals = [astar(slope, (0, 0), (14, 19), visibility_cost=vis, w_vis=w).visibility_cost
              for w in (0, 0.1, 0.3, 1, 3, 10)]
    assert all(b <= a + 1e-9 for a, b in zip(totals, totals[1:]))


@pytest.mark.parametrize("seed", range(10))
def test_w_vis_zero_and_no_blocked_is_slope_only(seed):
    rng = np.random.default_rng(seed)
    slope = rng.uniform(0, 40, size=(20, 25))
    cells = np.argwhere(passable_mask(slope))
    start, goal = (tuple(int(v) for v in cells[i]) for i in rng.choice(len(cells), 2, replace=False))
    base = astar(slope, start, goal)
    for kwargs in ({"visibility_cost": rng.random(slope.shape), "w_vis": 0.0},
                   {"blocked": np.zeros(slope.shape, dtype=bool)}):
        res = astar(slope, start, goal, **kwargs)
        assert res.path == base.path
        assert res.cost == base.cost  # bit for bit
        assert res.expanded == base.expanded


def test_blocked_cells_are_never_entered():
    slope = np.zeros((5, 7))
    blocked = np.zeros((5, 7), dtype=bool)
    blocked[:4, 3] = True  # building wall, open only at the bottom row
    res = astar(slope, (0, 0), (0, 6), cell_size=1, blocked=blocked)
    assert (4, 3) in res.path
    assert not any(blocked[p] for p in res.path)


def test_fully_enclosed_goal_is_not_found():
    slope = np.zeros((7, 7))
    blocked = np.zeros((7, 7), dtype=bool)
    blocked[2:5, 2:5] = True
    blocked[3, 3] = False  # goal cell is free but every neighbour is a building
    res = astar(slope, (0, 0), (3, 3), blocked=blocked)
    assert not res.found
    assert res.path == [] and res.cost == math.inf


def test_blocked_start_or_goal_raises():
    blocked = np.zeros((3, 3), dtype=bool)
    blocked[0, 0] = True
    with pytest.raises(ValueError, match="start .*blocked"):
        astar(np.zeros((3, 3)), (0, 0), (2, 2), blocked=blocked)
    with pytest.raises(ValueError, match="goal .*blocked"):
        astar(np.zeros((3, 3)), (2, 2), (0, 0), blocked=blocked)


@pytest.mark.parametrize("kwargs, match", [
    ({"visibility_cost": -np.ones((3, 3)), "w_vis": 1}, "visibility_cost"),
    ({"visibility_cost": np.ones((2, 3)), "w_vis": 1}, "visibility_cost has shape"),
    ({"visibility_cost": np.ones((3, 3)), "w_vis": -1}, "w_vis"),
    ({"blocked": np.zeros((3, 2), dtype=bool)}, "blocked has shape"),
])
def test_invalid_inputs(kwargs, match):
    with pytest.raises(ValueError, match=match):
        astar(np.zeros((3, 3)), (0, 0), (2, 2), **kwargs)


def cost_graph(slope, vis, w_vis, blocked, cell_size, max_slope=30):
    """Independent NetworkX graph with multiplier = slope_multiplier + w_vis * visibility_cost."""
    ok = passable_mask(slope, max_slope) & ~blocked
    mult = slope_multiplier(np.where(ok, slope, 0)) + w_vis * vis
    rows, cols = slope.shape
    graph = nx.Graph()
    for r, c in np.argwhere(ok):
        graph.add_node((r, c))
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols and ok[nr, nc]):
                continue
            if dr and dc and not (ok[r + dr, c] and ok[r, c + dc]):
                continue
            w = math.hypot(dr, dc) * cell_size * (mult[r, c] + mult[nr, nc]) / 2
            graph.add_edge((int(r), int(c)), (int(nr), int(nc)), weight=float(w))
    return graph, mult[ok].min()


@pytest.mark.parametrize("seed", range(20))
def test_matches_networkx_with_visibility_and_blocked(seed):
    rng = np.random.default_rng(seed)
    slope = rng.uniform(0, 35, size=(18, 22))
    vis = rng.integers(0, 4, size=slope.shape).astype(float)  # 0-3 observers see each cell
    blocked = rng.random(slope.shape) < 0.1
    w_vis = float(rng.choice([0.0, 0.5, 2.0]))
    ok = passable_mask(slope) & ~blocked
    cells = np.argwhere(ok)
    start, goal = (tuple(int(v) for v in cells[i]) for i in rng.choice(len(cells), 2, replace=False))

    res = astar(slope, start, goal, cell_size=10, visibility_cost=vis, w_vis=w_vis, blocked=blocked)
    graph, min_mult = cost_graph(slope, vis, w_vis, blocked, 10)

    def h(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1]) * 10 * min_mult

    try:
        nx_path = nx.astar_path(graph, start, goal, heuristic=h, weight="weight")
    except nx.NetworkXNoPath:
        assert not res.found
        return
    assert res.cost == pytest.approx(nx.path_weight(graph, nx_path, "weight"))
    assert res.cost == pytest.approx(nx.path_weight(graph, res.path, "weight"))
    assert not any(blocked[p] for p in res.path)
    assert h(start, goal) <= res.cost + 1e-9  # heuristic still admissible with the visibility term
    assert res.visible_cells == sum(vis[p] > 0 for p in res.path)
