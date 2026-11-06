import math

import networkx as nx
import numpy as np
import pytest

from guvenli_rota.routing.astar import astar, passable_mask, slope_multiplier

SQ2 = math.sqrt(2)


def test_multiplier_values():
    assert slope_multiplier(0) == pytest.approx(1.0)
    assert slope_multiplier(10) == pytest.approx(2.0)
    assert slope_multiplier(30) == pytest.approx(4.0)


def test_flat_grid_goes_straight_diagonal():
    res = astar(np.zeros((3, 3)), (0, 0), (2, 2), cell_size=30)
    assert res.path == [(0, 0), (1, 1), (2, 2)]
    assert res.cost == pytest.approx(2 * SQ2 * 30)
    assert res.expanded >= 2


def test_avoids_steep_but_passable_cell():
    # straight through the 25 deg centre: 2 * (1 + 3.5) / 2 = 4.5
    # over the top row diagonally:          2 * sqrt(2) * 1   = 2.83  <- best
    # under the bottom row (5 deg cell):    2 * sqrt(2) * 1.25 = 3.54
    slope = np.array([[0, 0, 0],
                      [0, 25, 0],
                      [0, 5, 0]], float)
    res = astar(slope, (1, 0), (1, 2), cell_size=1)
    assert res.path == [(1, 0), (0, 1), (1, 2)]
    assert res.cost == pytest.approx(2 * SQ2)


def test_impassable_wall_forces_route_through_gap():
    slope = np.zeros((3, 5))
    slope[1:, 2] = 45  # wall in column 2, open only at row 0
    res = astar(slope, (2, 0), (2, 4), cell_size=1)
    assert (0, 2) in res.path
    assert all(slope[r, c] <= 30 for r, c in res.path)
    # (2,0)->(0,1): 1 + sqrt(2); (0,1)->(0,3): 2; (0,3)->(2,4): 1 + sqrt(2). No corner cutting at the wall.
    assert res.cost == pytest.approx(2 * (1 + SQ2) + 2)


def test_slope_threshold_is_configurable():
    slope = np.array([[0, 31, 0]], float)
    assert not astar(slope, (0, 0), (0, 2)).found
    res = astar(slope, (0, 0), (0, 2), cell_size=1, max_slope_deg=35)
    assert res.path == [(0, 0), (0, 1), (0, 2)]
    assert res.cost == pytest.approx((1 + 4.1) / 2 * 2)


def test_no_route():
    slope = np.zeros((3, 3))
    slope[:, 1] = 45
    res = astar(slope, (0, 0), (2, 2))
    assert not res.found
    assert res.path == []
    assert res.cost == math.inf
    assert res.expanded == 3  # only the left column is reachable


def test_no_corner_cutting_between_impassable_cells():
    slope = np.array([[0, 45],
                      [45, 0]], float)
    assert not astar(slope, (0, 0), (1, 1)).found


def test_nodata_is_impassable():
    slope = np.array([[0, np.nan, 0]])
    assert not astar(slope, (0, 0), (0, 2)).found


def test_invalid_start_or_goal():
    slope = np.zeros((3, 3))
    slope[0, 0] = 40
    with pytest.raises(ValueError, match="start"):
        astar(slope, (0, 0), (2, 2))
    with pytest.raises(ValueError, match="goal"):
        astar(slope, (2, 2), (3, 0))


def grid_graph(slope, cell_size, max_slope):
    """Independent 8-connected NetworkX graph with the same cost model, for cross-checking."""
    ok = passable_mask(slope, max_slope)
    rows, cols = slope.shape
    graph = nx.Graph()
    for r in range(rows):
        for c in range(cols):
            if not ok[r, c]:
                continue
            graph.add_node((r, c))
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols and ok[nr, nc]):
                    continue
                if dr and dc and not (ok[r + dr, c] and ok[r, c + dc]):
                    continue
                dist = math.hypot(dr, dc) * cell_size
                w = dist * (slope_multiplier(slope[r, c]) + slope_multiplier(slope[nr, nc])) / 2
                graph.add_edge((r, c), (nr, nc), weight=float(w))
    return graph


@pytest.mark.parametrize("seed", range(25))
def test_matches_networkx_astar(seed):
    rng = np.random.default_rng(seed)
    slope = rng.uniform(0, 40, size=(20, 25))  # ~25% of cells above 30 deg
    slope[rng.random(slope.shape) < 0.03] = np.nan
    ok = passable_mask(slope)
    cells = np.argwhere(ok)
    start, goal = (tuple(int(v) for v in cells[i]) for i in rng.choice(len(cells), 2, replace=False))

    res = astar(slope, start, goal, cell_size=30)
    graph = grid_graph(slope, 30, 30)
    min_mult = slope_multiplier(slope[ok]).min()

    def h(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1]) * 30 * min_mult

    try:
        nx_path = nx.astar_path(graph, start, goal, heuristic=h, weight="weight")
    except nx.NetworkXNoPath:
        assert not res.found
        return
    assert res.cost == pytest.approx(nx.path_weight(graph, nx_path, "weight"))
    assert res.cost == pytest.approx(nx.path_weight(graph, res.path, "weight"))  # path is valid and costs that
    assert res.path[0] == start and res.path[-1] == goal
    assert h(start, goal) <= res.cost + 1e-9  # heuristic never overestimates
