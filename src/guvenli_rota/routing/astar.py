"""Weighted A* on an 8-connected slope grid (WP2 prototype).

Cost model (kept deliberately simple):

    multiplier(cell) = 1 + slope_deg / SLOPE_SCALE_DEG          # 1.0 on flat ground, 4.0 at 30 deg
    edge_cost(a, b)  = distance(a, b) * (multiplier(a) + multiplier(b)) / 2

    distance = cell_size for orthogonal moves, cell_size * sqrt(2) for diagonal moves.

Cells with slope > max_slope_deg (default 30) or with a non-finite slope (nodata) are impassable.
A diagonal move is not allowed to cut a corner: both orthogonal cells it passes between must be passable.

Heuristic: Euclidean distance * the smallest multiplier among passable cells. Every edge costs at least
its length times that multiplier, and the Euclidean distance is never longer than any grid path, so the
heuristic never overestimates (admissible). It is also consistent, so each cell is expanded at most once.
"""
import heapq
import math
from dataclasses import dataclass, field

import numpy as np

SLOPE_SCALE_DEG = 10.0
DEFAULT_MAX_SLOPE_DEG = 30.0

# (d_row, d_col, length in cells)
_MOVES = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
          (-1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (1, 1, math.sqrt(2))]


def slope_multiplier(slope_deg):
    """Cost multiplier for a cell with the given slope in degrees: 1 + slope / SLOPE_SCALE_DEG."""
    return 1.0 + np.asarray(slope_deg, dtype=float) / SLOPE_SCALE_DEG


def passable_mask(slope_deg, max_slope_deg=DEFAULT_MAX_SLOPE_DEG):
    """True where a cell can be entered: finite slope not above max_slope_deg."""
    slope = np.asarray(slope_deg, dtype=float)
    with np.errstate(invalid="ignore"):
        return np.isfinite(slope) & (slope <= max_slope_deg)


@dataclass
class AStarResult:
    path: list = field(default_factory=list)  # [(row, col), ...] from start to goal; empty if no route
    cost: float = math.inf                    # total edge cost (metres x multiplier); inf if no route
    expanded: int = 0                         # number of cells taken off the open list and expanded

    @property
    def found(self):
        return bool(self.path)


def astar(slope_deg, start, goal, cell_size=30.0, max_slope_deg=DEFAULT_MAX_SLOPE_DEG):
    """Least-cost 8-connected route from start to goal over a slope grid.

    slope_deg: 2D array of slope in degrees (NaN = nodata, treated as impassable).
    start, goal: (row, col) cells.
    Returns AStarResult(path, cost, expanded). If the goal cannot be reached, path is [] and cost is inf.
    Raises ValueError if start or goal is outside the grid or impassable.
    """
    slope = np.asarray(slope_deg, dtype=float)
    if slope.ndim != 2:
        raise ValueError("slope_deg must be a 2D array")
    rows, cols = slope.shape
    ok = passable_mask(slope, max_slope_deg)
    for name, (r, c) in (("start", start), ("goal", goal)):
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError(f"{name} {(r, c)} is outside the {rows}x{cols} grid")
        if not ok[r, c]:
            raise ValueError(f"{name} {(r, c)} is impassable (slope {slope[r, c]:.1f} deg)")

    start, goal = (int(start[0]), int(start[1])), (int(goal[0]), int(goal[1]))
    mult = np.where(ok, slope_multiplier(np.where(ok, slope, 0.0)), np.inf)
    min_mult = float(mult[ok].min())
    gr, gc = goal

    def h(r, c):
        return math.hypot(r - gr, c - gc) * cell_size * min_mult

    g = {start: 0.0}
    parent = {start: None}
    closed = set()
    tie = 0  # FIFO tie-break so equal-f entries pop in insertion order
    open_heap = [(h(*start), tie, start)]
    expanded = 0

    while open_heap:
        _, _, node = heapq.heappop(open_heap)
        if node in closed:
            continue  # stale heap entry
        if node == goal:
            path = []
            while node is not None:
                path.append(node)
                node = parent[node]
            return AStarResult(path[::-1], g[goal], expanded)
        closed.add(node)
        expanded += 1
        r, c = node
        for dr, dc, length in _MOVES:
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols) or not ok[nr, nc]:
                continue
            if dr and dc and not (ok[r + dr, c] and ok[r, c + dc]):
                continue  # no corner cutting
            nxt = (nr, nc)
            if nxt in closed:
                continue
            new_g = g[node] + length * cell_size * (mult[r, c] + mult[nr, nc]) / 2
            if new_g < g.get(nxt, math.inf):
                g[nxt] = new_g
                parent[nxt] = node
                tie += 1
                heapq.heappush(open_heap, (new_g + h(nr, nc), tie, nxt))

    return AStarResult([], math.inf, expanded)
