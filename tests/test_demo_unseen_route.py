import importlib.util
from pathlib import Path

import pytest

from guvenli_rota.scene.synthetic import make_scene

_spec = importlib.util.spec_from_file_location(
    "demo_unseen_route", Path(__file__).resolve().parents[1] / "scripts" / "demo_unseen_route.py")
demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo)


@pytest.fixture(scope="module")
def small_scene():
    scene = make_scene("hills", 0, 10, building_density=0.02, n_observers=2, n_tasks=3, size_m=600)
    return scene, demo.scene_layers(scene)


def test_route_pair_connects_task_and_avoids_buildings(small_scene):
    scene, layers = small_scene
    task = scene.tasks[0]
    pair = demo.route_pair(scene, layers, task)
    assert pair is not None
    for route in pair.values():
        assert route["path"][0] == scene.world_to_cell(*task["start"])
        assert route["path"][-1] == scene.world_to_cell(*task["goal"])
        assert not any(layers["mask"][p] for p in route["path"])
        assert 0.0 <= route["visible_pct"] <= 100.0


def test_unseen_route_trades_length_for_visibility(small_scene):
    scene, layers = small_scene
    for task in scene.tasks:
        pair = demo.route_pair(scene, layers, task)
        shortest, unseen = pair["shortest"], pair["unseen"]
        assert unseen["vis_cost"] <= shortest["vis_cost"] + 1e-9
        assert unseen["length_increase_pct"] == pytest.approx(100 * (unseen["length_m"] / shortest["length_m"] - 1))
        assert shortest["length_increase_pct"] == 0.0


def candidate(shortest_visible, increase):
    return {"pair": {"shortest": {"visible_pct": shortest_visible},
                     "unseen": {"length_increase_pct": increase}}}


def test_pick_most_visible_shortest_within_detour_limit():
    a, b, c = candidate(90.0, 45.0), candidate(70.0, 20.0), candidate(60.0, 5.0)
    assert demo.pick([a, b, c], max_increase_pct=30.0) is b
    assert demo.pick([a, b, c]) is a


def test_pick_stops_when_no_task_fits_the_limit():
    with pytest.raises(SystemExit, match="at most 30"):
        demo.pick([candidate(90.0, 45.0)], max_increase_pct=30.0)
