"""Unit tests for observer_viewshed and visibility_cost on small hand-checkable grids."""
import numpy as np
import pytest

from guvenli_rota.scene.synthetic import make_scene
from guvenli_rota.visibility.observer import observer_viewshed, visibility_cost

CELL = 10.0


def _cell_center(row, col, origin, cell_size=CELL):
    x0, y0 = origin
    return x0 + (col + 0.5) * cell_size, y0 - (row + 0.5) * cell_size


def _make_observer(row, col, origin, *, cell_size=CELL, eye_height_m=1.7,
                   range_day_m=100.0, range_night_m=30.0, fov_deg=360.0, heading_deg=0.0, obs_id="G1"):
    x, y = _cell_center(row, col, origin, cell_size)
    return {
        "id": obs_id,
        "x": x,
        "y": y,
        "eye_height_m": eye_height_m,
        "range_day_m": range_day_m,
        "range_night_m": range_night_m,
        "fov_deg": fov_deg,
        "heading_deg": heading_deg,
    }


def test_flat_360_observer_sees_within_range_and_not_beyond():
    shape = (21, 21)
    origin = (0.0, shape[0] * CELL)
    surface = np.zeros(shape)
    obs = _make_observer(10, 10, origin, range_day_m=50.0, fov_deg=360.0)

    vis = observer_viewshed(surface, obs, cell_size=CELL, origin=origin, time="day")

    rr, cc = np.indices(shape)
    expected = np.hypot(rr - 10, cc - 10) * CELL <= 50.0
    assert (vis == expected).all()
    assert vis[10, 15]       # exactly 50 m east: inside range
    assert not vis[10, 16]   # 60 m east: outside range


def test_90_deg_fov_facing_north_hides_south_and_sides():
    shape = (21, 21)
    origin = (0.0, shape[0] * CELL)
    surface = np.zeros(shape)
    obs = _make_observer(10, 10, origin, range_day_m=200.0, fov_deg=90.0, heading_deg=0.0)

    vis = observer_viewshed(surface, obs, cell_size=CELL, origin=origin, time="day")

    assert vis[:10, 10].all()           # directly north is visible
    assert vis[5, 15] and vis[5, 5]     # NE (45 deg) and NW (315 deg) edges are visible
    assert not vis[12:, 10].any()       # south (beyond immediate neighbour) is hidden
    assert not vis[10, 12:].any()       # east is hidden
    assert not vis[10, :9].any()        # west is hidden
    assert vis[9:12, 9:12].all()        # observer cell and immediate 8-neighbours stay visible


def test_fov_heading_wraps_across_north_and_supports_other_directions():
    shape = (21, 21)
    origin = (0.0, shape[0] * CELL)
    surface = np.zeros(shape)

    # Heading 350 deg with 40 deg FOV covers [330, 360) U [0, 10]
    wrap_obs = _make_observer(10, 10, origin, range_day_m=200.0, fov_deg=40.0, heading_deg=350.0)
    vis_wrap = observer_viewshed(surface, wrap_obs, cell_size=CELL, origin=origin)
    assert vis_wrap[0, 10]              # bearing 0 deg is inside [330, 10]
    assert vis_wrap[2, 7]               # bearing ~339 deg is inside [330, 10]
    assert not vis_wrap[18, 10]         # bearing 180 deg is outside

    # Heading 90 deg (east) with 90 deg FOV
    east_obs = _make_observer(10, 10, origin, range_day_m=200.0, fov_deg=90.0, heading_deg=90.0)
    vis_east = observer_viewshed(surface, east_obs, cell_size=CELL, origin=origin)
    assert vis_east[10, 18]             # east is visible
    assert not vis_east[2, 10]          # north is hidden
    assert not vis_east[10, 2]          # west is hidden


def test_high_wall_hides_cells_behind_it():
    shape = (11, 21)
    origin = (1000.0, 2000.0 + shape[0] * CELL)
    surface = np.zeros(shape)
    surface[:, 8] = 30.0  # tall building/wall across column 8
    obs = _make_observer(5, 2, origin, eye_height_m=1.7, range_day_m=250.0, fov_deg=360.0)

    vis = observer_viewshed(surface, obs, cell_size=CELL, origin=origin, time="day", target_height=1.7)

    assert vis[5, 2:8].all()            # observer and cells in front of the wall are visible
    assert vis[5, 8]                    # wall top itself is hit by the ray
    assert not vis[5, 9:].any()         # everything behind the wall is hidden


def test_night_shorter_range_reduces_visible_cells():
    shape = (25, 25)
    origin = (0.0, shape[0] * CELL)
    surface = np.zeros(shape)
    obs = _make_observer(12, 12, origin, range_day_m=100.0, range_night_m=30.0, fov_deg=360.0)

    day_vis = observer_viewshed(surface, obs, cell_size=CELL, origin=origin, time="day")
    night_vis = observer_viewshed(surface, obs, cell_size=CELL, origin=origin, time="night")

    assert night_vis.sum() < day_vis.sum()
    assert (day_vis | ~night_vis).all()  # night viewshed is a subset of day viewshed
    assert day_vis[12, 20] and not night_vis[12, 20]


def test_observer_cell_and_immediate_neighbours_always_visible():
    shape = (9, 9)
    origin = (0.0, shape[0] * CELL)
    surface = np.zeros(shape)
    surface[3, 3] = np.nan  # NaN neighbour remains False
    obs = _make_observer(4, 4, origin, range_day_m=0.0, fov_deg=30.0, heading_deg=0.0)

    vis = observer_viewshed(surface, obs, cell_size=CELL, origin=origin)

    expected_patch = np.ones((3, 3), dtype=bool)
    expected_patch[0, 0] = False  # cell (3, 3) is NaN
    assert (vis[3:6, 3:6] == expected_patch).all()


def test_two_observers_visibility_cost_equals_sum_of_individual_costs():
    shape = (15, 15)
    origin = (500.0, 1500.0)
    surface = np.zeros(shape)
    surface[7, 4:11] = 20.0  # central barrier
    obs1 = _make_observer(2, 2, origin, range_day_m=100.0, obs_id="G1")
    obs2 = _make_observer(12, 12, origin, range_day_m=100.0, obs_id="G2")

    c1 = visibility_cost(surface, [obs1], cell_size=CELL, origin=origin)
    c2 = visibility_cost(surface, [obs2], cell_size=CELL, origin=origin)
    c_both = visibility_cost(surface, [obs1, obs2], cell_size=CELL, origin=origin)
    assert np.array_equal(c_both, c1 + c2)
    assert c_both.dtype == np.float64
    assert not np.isnan(c_both).any()

    # Weighted sum matches weighted individuals
    c_weighted = visibility_cost(surface, [obs1, obs2], cell_size=CELL, origin=origin, weights=[2.5, 0.5])
    assert np.allclose(c_weighted, 2.5 * c1 + 0.5 * c2)


def test_visibility_cost_obstacle_cells_zero_and_no_nan():
    shape = (11, 11)
    origin = (0.0, shape[0] * CELL)
    surface = np.zeros(shape)
    surface[0, 0] = np.nan
    obstacle_mask = np.zeros(shape, dtype=bool)
    obstacle_mask[5, 5:8] = True
    surface[obstacle_mask] = 15.0
    obs = _make_observer(5, 2, origin, range_day_m=100.0)

    cost = visibility_cost(surface, [obs], cell_size=CELL, origin=origin, obstacle_mask=obstacle_mask)

    assert not np.isnan(cost).any()
    assert cost[0, 0] == 0.0
    assert (cost[obstacle_mask] == 0.0).all()
    assert cost[5, 2] == 1.0

    # Empty observer list produces an all-zero float grid
    empty = visibility_cost(surface, [], cell_size=CELL, origin=origin)
    assert empty.shape == shape and (empty == 0.0).all()


def test_validation_errors():
    shape = (5, 5)
    origin = (0.0, 50.0)
    surface = np.zeros(shape)
    valid_obs = _make_observer(2, 2, origin)
    outside_obs = {**valid_obs, "x": -1.0}

    with pytest.raises(ValueError, match="outside"):
        observer_viewshed(surface, outside_obs, cell_size=CELL, origin=origin)
    with pytest.raises(ValueError, match="time"):
        observer_viewshed(surface, valid_obs, cell_size=CELL, origin=origin, time="dusk")
    with pytest.raises(ValueError, match="fov_deg"):
        observer_viewshed(surface, {**valid_obs, "fov_deg": 400.0}, cell_size=CELL, origin=origin)
    with pytest.raises(ValueError, match="weights"):
        visibility_cost(surface, [valid_obs], cell_size=CELL, origin=origin, weights=[1.0, 2.0])
    with pytest.raises(ValueError, match="weights"):
        visibility_cost(surface, [valid_obs], cell_size=CELL, origin=origin, weights=[-1.0])
    with pytest.raises(ValueError, match="obstacle_mask"):
        visibility_cost(surface, [valid_obs], cell_size=CELL, origin=origin,
                        obstacle_mask=np.zeros((4, 5), dtype=bool))


def test_works_with_synthetic_scene():
    scene = make_scene("flat", seed=0, resolution_m=30.0, size_m=600.0, building_density=0.05,
                       n_observers=2, n_tasks=1)
    cost = visibility_cost(
        scene.surface(),
        scene.observers,
        cell_size=scene.resolution,
        origin=scene.meta["origin"],
        time="day",
        obstacle_mask=scene.obstacle_mask(),
    )
    assert cost.shape == scene.shape
    assert not np.isnan(cost).any()
    assert (cost >= 0.0).all()
    assert (cost[scene.obstacle_mask()] == 0.0).all()
