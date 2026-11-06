import numpy as np
import pytest

from guvenli_rota.connectivity.line_of_sight import line_of_sight

CELL = 30.0


def test_flat_terrain_everything_visible():
    dem = np.full((41, 41), 100.0)
    vis = line_of_sight(dem, (20, 20), cell_size=CELL)
    assert vis.all()


def test_hill_hides_cells_behind_it():
    # antenna at column 0, a 200 m wall-like hill at column 10 across all rows
    dem = np.zeros((21, 41))
    dem[:, 10] = 200.0
    vis = line_of_sight(dem, (10, 0), cell_size=CELL, antenna_height=30.0, receiver_height=1.5)
    assert vis[10, 1:10].all()        # in front of the hill
    assert vis[10, 10]                # the hill top itself is hit by the line
    assert not vis[10, 11:].any()     # everything behind it is hidden along the same row


def test_single_peak_casts_a_shadow_only_behind_it():
    dem = np.zeros((41, 41))
    dem[20, 25] = 300.0               # one tall peak east of the antenna
    vis = line_of_sight(dem, (20, 20), cell_size=CELL)
    assert not vis[20, 30]            # directly behind the peak
    assert vis[20, 10]                # opposite direction is open
    assert vis[5, 30]                 # off to the side is open


def test_low_bump_does_not_block_a_high_antenna():
    dem = np.zeros((1, 41))
    # 3 m bump, antenna 30 m up. The line to the cell right behind the bump (col 11) passes at
    # ~4.1 m above the bump column, so a 5 m bump would correctly hide that one cell.
    dem[0, 10] = 3.0
    vis = line_of_sight(dem, (0, 0), cell_size=CELL, antenna_height=30.0)
    assert vis.all()


def test_max_range_cuts_off_far_cells():
    dem = np.zeros((1, 101))
    vis = line_of_sight(dem, (0, 0), cell_size=CELL, max_range=300.0)
    assert vis[0, :11].all()          # 10 cells = 300 m, inclusive
    assert not vis[0, 11:].any()


def test_antenna_height_changes_result():
    dem = np.zeros((1, 41))
    dem[0, 10] = 40.0
    low = line_of_sight(dem, (0, 0), cell_size=CELL, antenna_height=5.0)
    high = line_of_sight(dem, (0, 0), cell_size=CELL, antenna_height=100.0)
    assert not low[0, 20]
    assert high[0, 20]


def test_receiver_height_changes_result():
    dem = np.zeros((1, 41))
    dem[0, 10] = 20.0
    ground = line_of_sight(dem, (0, 0), cell_size=CELL, antenna_height=30.0, receiver_height=0.0)
    tall = line_of_sight(dem, (0, 0), cell_size=CELL, antenna_height=30.0, receiver_height=30.0)
    assert not ground[0, 12]          # grazing line too low just behind the bump
    assert tall[0, 12]


def test_antenna_cell_visible_and_nan_target_not_visible():
    dem = np.zeros((5, 5))
    dem[0, 4] = np.nan
    vis = line_of_sight(dem, (2, 2), cell_size=CELL)
    assert vis[2, 2]
    assert not vis[0, 4]
    assert vis.sum() == 24


def test_earth_curvature_hides_far_flat_cells():
    dem = np.zeros((1, 334))
    # antenna 2 m high: the radio horizon is ~ sqrt(2 * 8.5e6 * 2) = 5.8 km
    flat = line_of_sight(dem, (0, 0), cell_size=CELL, antenna_height=2.0, receiver_height=0.0)
    curved = line_of_sight(dem, (0, 0), cell_size=CELL, antenna_height=2.0, receiver_height=0.0,
                           earth_curvature=True)
    assert flat[0, 300]
    assert curved[0, 50]
    assert not curved[0, 300]


def test_antenna_outside_grid_raises():
    with pytest.raises(ValueError):
        line_of_sight(np.zeros((5, 5)), (5, 0))


def test_chunking_gives_same_result(monkeypatch):
    rng = np.random.default_rng(0)
    dem = rng.normal(0, 15, (31, 31)).cumsum(axis=0).cumsum(axis=1) / 10
    full = line_of_sight(dem, (15, 15), cell_size=CELL)
    import guvenli_rota.connectivity.line_of_sight as los

    monkeypatch.setattr(los, "CHUNK_CELLS", 50)
    small = line_of_sight(dem, (15, 15), cell_size=CELL)
    assert (full == small).all()
