import numpy as np
import pytest

from guvenli_rota.evaluation.metrics import (agreement, length_increase, paired_summary, path_to_xy, resample_route,
                                             route_length_m, visible_fraction, visible_length_m)
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


def left_half_visible(scene):
    """Cells with centre x < 150 m are visible: the left half of a 300 m x 300 m scene."""
    h, w = scene.shape
    centres_x = np.array([scene.cell_to_world(0, c)[0] for c in range(w)])
    return np.broadcast_to(centres_x < 150.0, (h, w)).copy()


def test_straight_route_across_half_visible_grid():
    scene = make_scene(30.0, 10)
    route = path_to_xy(scene, [(5, c) for c in range(10)])     # x from 15 to 285 m along row 5
    pts = resample_route(route, step_m=1.0)                     # 271 points, x = 15, 16, ..., 285
    frac = visible_fraction(pts, scene, left_half_visible(scene))
    assert frac == pytest.approx(135 / 271)                     # x = 15..149 are visible
    assert frac == pytest.approx(0.5, abs=0.01)
    assert visible_length_m(route, scene, left_half_visible(scene)) == pytest.approx(135.0, abs=0.5)


def test_same_route_gives_same_fraction_at_30m_and_5m():
    coarse, fine = make_scene(30.0, 10), make_scene(5.0, 60)
    route = path_to_xy(coarse, [(9 - i, i) for i in range(10)])  # diagonal (15, 15) -> (285, 285)
    pts = resample_route(route, step_m=1.0)
    f30 = visible_fraction(pts, coarse, left_half_visible(coarse))
    f5 = visible_fraction(pts, fine, left_half_visible(fine))
    assert f30 == pytest.approx(0.5, abs=0.01)
    assert f5 == pytest.approx(f30, abs=0.01)                   # only samples next to x = 150 may differ


def test_visible_fraction_rejects_points_outside_the_scene():
    scene = make_scene(30.0, 10)
    with pytest.raises(ValueError, match="outside the scene"):
        visible_fraction([[15.0, 285.0], [310.0, 285.0]], scene, left_half_visible(scene))


def test_visible_fraction_rejects_mask_of_another_grid():
    coarse, fine = make_scene(30.0, 10), make_scene(5.0, 60)
    with pytest.raises(ValueError, match="shape"):
        visible_fraction([[15.0, 285.0]], fine, left_half_visible(coarse))


def test_paired_summary_all_differences_positive():
    a = np.arange(1.0, 9.0)
    s = paired_summary(a, a + 1)
    assert (s["n"], s["n_positive"], s["n_negative"], s["n_zero"]) == (8, 8, 0, 0)
    assert s["median_diff"] == s["q1_diff"] == s["q3_diff"] == 1.0
    assert s["median_a"] == 4.5 and s["median_b"] == 5.5
    assert s["rank_biserial"] == 1.0
    assert s["p_value"] == pytest.approx(2 / 2**8)             # exact test: only 1 of 256 sign patterns is as extreme, both tails


def test_paired_summary_reversed_gives_negative_effect():
    a = np.arange(1.0, 9.0)
    assert paired_summary(a + 1, a)["rank_biserial"] == -1.0


def test_paired_summary_identical_arrays():
    s = paired_summary([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert (s["n_zero"], s["p_value"], s["rank_biserial"]) == (3, 1.0, 0.0)


def test_agreement_identical_arrays():
    v = [0.1, 0.4, 0.2, 0.9, 0.5]
    r = agreement(v, v)
    assert r["spearman_rho"] == pytest.approx(1.0)
    assert r["mean_abs_diff"] == 0.0


def test_agreement_monotone_but_shifted():
    r = agreement([1.0, 2.0, 3.0, 4.0], [11.0, 12.0, 13.0, 14.0])
    assert r["spearman_rho"] == pytest.approx(1.0)
    assert r["mean_abs_diff"] == 10.0


def test_paired_summary_rank_biserial_with_mixed_signs():
    # differences 1, -2, 3 -> ranks 1, 2, 3 -> T+ = 4, T- = 2 -> (4 - 2) / 6
    s = paired_summary([0.0, 0.0, 0.0], [1.0, -2.0, 3.0])
    assert s["rank_biserial"] == pytest.approx(1 / 3)
    assert (s["n_positive"], s["n_negative"]) == (2, 1)
