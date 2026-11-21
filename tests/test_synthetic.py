import numpy as np
import pytest

from guvenli_rota.scene import Scene
from guvenli_rota.scene.synthetic import (
    CLEAR_CELL_M, block_mean, building_density, make_obstacles, make_observers, make_scene, make_tasks,
    make_terrain, rect_bounds,
)

SIZE = 600  # small scenes keep the tests fast; the full 3000 m scenes are built by the script


def parts(kind, seed, density=0.10, size=SIZE):
    terrain = make_terrain(kind, seed, size)
    obstacles = make_obstacles(terrain, seed, density)
    return terrain, obstacles, make_observers(terrain, obstacles, seed), make_tasks(terrain, obstacles, seed)


def points(observers, tasks):
    return [(o["x"], o["y"]) for o in observers] + [tuple(t[end]) for t in tasks for end in ("start", "goal")]


@pytest.mark.parametrize("kind", ["flat", "hills"])
def test_same_seed_gives_same_scene(kind):
    a, b = parts(kind, 3), parts(kind, 3)
    np.testing.assert_array_equal(a[0], b[0])
    assert a[1:] == b[1:]


@pytest.mark.parametrize("kind", ["flat", "hills"])
def test_different_seed_gives_different_scene(kind):
    a, b = parts(kind, 3), parts(kind, 4)
    assert not np.array_equal(a[0], b[0])
    for part_a, part_b in zip(a[1:], b[1:]):
        assert part_a != part_b


def test_terrain_relief_by_kind():
    for seed in range(5):
        flat = make_terrain("flat", seed, SIZE)
        hills = make_terrain("hills", seed, SIZE)
        assert 1.0 <= np.ptp(flat) <= 4.0 + 1e-3
        assert 50.0 - 1e-3 <= np.ptp(hills) <= 150.0 + 1e-3
        assert flat.dtype == hills.dtype == np.float32


@pytest.mark.parametrize("kind", ["flat", "hills"])
@pytest.mark.parametrize("resolution", [10, 30])
def test_coarse_terrain_is_block_mean_of_5m(kind, resolution):
    fine = make_terrain(kind, 1, SIZE, 5)
    coarse = make_terrain(kind, 1, SIZE, resolution)
    assert coarse.shape == (SIZE // resolution, SIZE // resolution)
    np.testing.assert_array_equal(coarse, block_mean(fine, resolution // 5).astype(np.float32))


@pytest.mark.parametrize("density", [0.05, 0.10, 0.20])
def test_building_density_within_3_percent(density):
    terrain = make_terrain("hills", 2, SIZE)
    got = building_density(make_obstacles(terrain, 2, density), SIZE)
    assert got == pytest.approx(density, rel=0.03)


def test_obstacles_do_not_overlap_and_follow_the_spec():
    _, obstacles, _, _ = parts("hills", 5)
    occ = np.zeros((SIZE, SIZE), dtype=np.uint8)
    for f in obstacles:
        x1, y1, x2, y2 = rect_bounds(f)
        p = f["properties"]
        if p["kind"] == "building":
            assert 3 <= p["height_m"] <= 30
        else:
            assert p["kind"] == "vehicle" and p["height_m"] == 1.5
            assert sorted((x2 - x1, y2 - y1)) == [2, 5]
        assert 0 <= x1 < x2 <= SIZE and 0 <= y1 < y2 <= SIZE
        occ[int(SIZE - y2):int(SIZE - y1), int(x1):int(x2)] += 1
    assert occ.max() == 1


@pytest.mark.parametrize("kind", ["flat", "hills"])
def test_points_are_outside_obstacles_with_a_free_30m_cell(kind):
    _, obstacles, observers, tasks = parts(kind, 6)
    rects = [rect_bounds(f) for f in obstacles]
    for x, y in points(observers, tasks):
        cx1, cy1 = x // CLEAR_CELL_M * CLEAR_CELL_M, y // CLEAR_CELL_M * CLEAR_CELL_M
        for x1, y1, x2, y2 in rects:
            assert not (x1 <= x <= x2 and y1 <= y <= y2)
            # the 30 m cell around the point does not overlap the obstacle
            assert x2 <= cx1 or x1 >= cx1 + CLEAR_CELL_M or y2 <= cy1 or y1 >= cy1 + CLEAR_CELL_M


def test_tasks_run_between_opposite_edges():
    _, _, _, tasks = parts("hills", 7)
    near, far = 0.12 * SIZE, 0.88 * SIZE
    for t in tasks:
        (sx, sy), (gx, gy) = t["start"], t["goal"]
        west_east = (sx <= near and gx >= far) or (sx >= far and gx <= near)
        south_north = (sy <= near and gy >= far) or (sy >= far and gy <= near)
        assert west_east or south_north


def test_invalid_arguments():
    with pytest.raises(ValueError, match="kind"):
        make_terrain("mountains", 0, SIZE)
    with pytest.raises(ValueError, match="resolution"):
        make_terrain("flat", 0, SIZE, 7)
    with pytest.raises(ValueError, match="seed"):
        make_terrain("flat", -1, SIZE)


@pytest.fixture(scope="module")
def scenes():
    return {res: make_scene("hills", 0, res, size_m=SIZE, n_tasks=4) for res in (5, 10, 30)}


def test_make_scene_is_the_same_world_at_every_resolution(scenes):
    fine = scenes[5]
    for res, scene in scenes.items():
        assert isinstance(scene, Scene)
        assert scene.meta["name"] == f"synthetic_hills_s0_{res}m"
        assert scene.shape == (SIZE // res, SIZE // res)
        assert scene.obstacles == fine.obstacles
        assert scene.observers == fine.observers
        assert scene.tasks == fine.tasks
        np.testing.assert_array_equal(scene.terrain, block_mean(fine.terrain, res // 5).astype(np.float32))


def test_points_are_not_in_obstacle_cells_at_any_resolution(scenes):
    for scene in scenes.values():
        mask = scene.obstacle_mask()
        assert mask.any()
        for x, y in points(scene.observers, scene.tasks):
            assert not mask[scene.world_to_cell(x, y)]


def test_scene_save_load_round_trip(scenes, tmp_path):
    scene = scenes[30]
    scene.save(tmp_path / "s")
    loaded = Scene.load(tmp_path / "s")
    assert loaded.meta == scene.meta
    np.testing.assert_array_equal(loaded.terrain, scene.terrain)
    assert loaded.obstacles == scene.obstacles
    assert loaded.observers == scene.observers
    assert loaded.tasks == scene.tasks
