"""A* on scenes with the real visibility layer (visibility/observer.py) and obstacle mask."""
import numpy as np
import pytest

from guvenli_rota.routing.astar import astar
from guvenli_rota.routing.scene_route import plan_route, plan_task, scene_visibility, terrain_slope_deg
from guvenli_rota.scene import Scene
from guvenli_rota.scene.synthetic import make_scene


def box(x1, y1, x2, y2):
    return {"type": "Polygon", "coordinates": [[[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]]]}


def wall_scene():
    """Flat 20x30 grid of 10 m cells. One observer at the north (cell 1, 15) looks over an east-west wall,
    10 m high, in rows 9-10 and columns 4-25. Everything south of the wall is hidden from the observer."""
    return Scene(
        meta={"format_version": "0.1", "name": "wall_20x30", "source": "synthetic", "seed": 0,
              "crs": "EPSG:32636", "resolution_m": 10.0, "width": 30, "height": 20, "origin": [0.0, 200.0],
              "terrain_is_surface": False, "notes": "unit test"},
        terrain=np.zeros((20, 30)),
        obstacles=[{"type": "Feature", "geometry": box(40, 90, 260, 110),
                    "properties": {"kind": "building", "height_m": 10.0, "height_source": "synthetic"}}],
        observers=[{"id": "G1", "x": 155.0, "y": 185.0, "eye_height_m": 1.7, "range_day_m": 1000.0,
                    "range_night_m": 300.0, "fov_deg": 360.0, "heading_deg": 0.0}],
        tasks=[{"id": "T1", "start": [5.0, 145.0], "goal": [295.0, 145.0], "mode": "pedestrian", "time": "day"}],
    )


def test_scene_visibility_on_the_wall_scene():
    scene = wall_scene()
    vis = scene_visibility(scene)
    mask = scene.obstacle_mask()
    assert mask.sum() == 2 * 22
    assert (vis[mask] == 0).all()
    assert (vis[:9] == 1).all()       # open ground north of the wall is seen
    assert (vis[11:] == 0).all()      # the wall hides everything south of it


def test_shortest_route_is_seen_and_hidden_route_goes_behind_the_wall():
    scene = wall_scene()
    vis = scene_visibility(scene)
    shortest = plan_task(scene, scene.tasks[0], w_vis=0, visibility=vis)
    assert shortest.path == [(5, c) for c in range(30)]  # straight along row 5, all in sight
    assert shortest.visible_cells == 30
    assert shortest.visibility_cost == pytest.approx(290)

    hidden = plan_task(scene, scene.tasks[0], w_vis=1, visibility=vis)
    assert hidden.path[0] == (5, 0) and hidden.path[-1] == (5, 29)
    assert max(r for r, _ in hidden.path) >= 11            # goes round to the far side of the wall
    assert not any(scene.obstacle_mask()[p] for p in hidden.path)
    assert hidden.visible_cells < shortest.visible_cells
    assert hidden.visibility_cost < shortest.visibility_cost


def test_visibility_is_computed_when_not_given():
    scene = wall_scene()
    given = plan_task(scene, scene.tasks[0], w_vis=1, visibility=scene_visibility(scene))
    computed = plan_task(scene, scene.tasks[0], w_vis=1)
    assert computed.path == given.path and computed.cost == given.cost
    assert plan_task(scene, scene.tasks[0]).visible_cells == 30  # reported for w_vis = 0 too


@pytest.fixture(scope="module")
def hills():
    scene = make_scene("hills", 0, 10, size_m=600, n_tasks=4)
    return scene, scene_visibility(scene)


def test_w_vis_zero_is_plain_astar_on_terrain_slope_with_obstacles_blocked(hills):
    scene, vis = hills
    for task in scene.tasks:
        res = plan_task(scene, task, visibility=vis)
        direct = astar(terrain_slope_deg(scene), scene.world_to_cell(*task["start"]),
                       scene.world_to_cell(*task["goal"]), cell_size=10, blocked=scene.obstacle_mask())
        assert res.path == direct.path and res.cost == direct.cost


def test_synthetic_tasks_route_around_obstacles_and_visibility_does_not_increase(hills):
    scene, vis = hills
    mask = scene.obstacle_mask()
    for task in scene.tasks:
        routes = [plan_task(scene, task, w_vis=w, visibility=vis) for w in (0, 0.5, 2)]
        for res in routes:
            assert res.found
            assert res.path[0] == scene.world_to_cell(*task["start"])
            assert res.path[-1] == scene.world_to_cell(*task["goal"])
            assert not any(mask[p] for p in res.path)
        totals = [res.visibility_cost for res in routes]
        assert all(b <= a + 1e-9 for a, b in zip(totals, totals[1:]))


def test_terrain_slope_ignores_buildings():
    scene = wall_scene()
    np.testing.assert_array_equal(terrain_slope_deg(scene), 0)  # flat terrain, 10 m wall not a cliff
