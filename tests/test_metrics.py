import numpy as np
import pytest

from guvenli_rota.evaluation.metrics import length_increase, path_to_xy, resample_route, route_length_m
from guvenli_rota.scene import Scene


def make_scene(res, n, origin=(0.0, 300.0)):
    """n x n flat scene with one task, no obstacles or observers."""
    size = n * res
    x0, y0 = origin
    return Scene(
        meta={"format_version": "0.1", "name": f"test_{res:g}m", "source": "synthetic", "seed": 0,
              "crs": "EPSG:32636", "resolution_m": res, "width": n, "height": n,
              "origin": list(origin), "terrain_is_surface": False},
        terrain=np.zeros((n, n), dtype=np.float32), obstacles=[], observers=[],
        tasks=[{"id": "T1", "start": [x0 + 1, y0 - 1], "goal": [x0 + size - 1, y0 - size + 1],
                "mode": "pedestrian", "time": "day"}],
    )


def test_path_to_xy_gives_cell_centres():
    scene = make_scene(30.0, 10)
    np.testing.assert_array_equal(path_to_xy(scene, [(0, 0), (1, 1), (9, 9)]),
                                  [[15.0, 285.0], [45.0, 255.0], [285.0, 15.0]])


def test_straight_line_length():
    assert route_length_m([[0, 0], [10, 0], [30, 0]]) == 30.0


def test_3_4_5_triangle():
    assert route_length_m([[0, 0], [3, 4]]) == 5.0
    assert route_length_m([[0, 0], [3, 0], [3, 4]]) == 7.0
    assert route_length_m([[0, 0], [3, 0], [3, 4], [0, 0]]) == 12.0


def test_single_point_route_has_zero_length():
    assert route_length_m([[5, 5]]) == 0.0


def test_resample_includes_both_ends_and_follows_corners():
    pts = resample_route([[0, 0], [3, 0], [3, 4]], step_m=1.0)
    assert len(pts) == 8
    np.testing.assert_allclose(pts[0], [0, 0])
    np.testing.assert_allclose(pts[4], [3, 1])
    np.testing.assert_allclose(pts[-1], [3, 4])
    np.testing.assert_allclose(np.hypot(*np.diff(pts, axis=0).T), 1.0)


def test_resample_shorter_last_step():
    pts = resample_route([[0, 0], [10.5, 0]], step_m=1.0)
    assert len(pts) == 12
    np.testing.assert_allclose(pts[-2:], [[10, 0], [10.5, 0]])


def test_resample_skips_repeated_points():
    pts = resample_route([[0, 0], [0, 0], [2, 0], [2, 0]], step_m=1.0)
    np.testing.assert_allclose(pts, [[0, 0], [1, 0], [2, 0]])


def test_length_increase_in_percent():
    assert length_increase([[0, 0], [3, 0], [3, 4]], [[0, 0], [3, 4]]) == pytest.approx(40.0)
