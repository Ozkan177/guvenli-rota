"""Real-data scene converter: height rules, ground estimate, scene assembly, and the built Antalya scenes."""
import csv
import warnings

import numpy as np
import pytest
from rasterio.transform import from_origin
from shapely.geometry import box

from guvenli_rota.common import DATA, REPORTS
from guvenli_rota.scene import Scene
from guvenli_rota.scene.converter import (building_height, buildings_to_grid, ground_under_buildings,
                                          height_source_counts, make_real_scenes, parse_height, parse_levels)

SCENES = DATA / "scenes"


@pytest.mark.parametrize("tags, expected", [
    ({"height": "12"}, (12.0, "osm_height")),
    ({"height": "12.5 m", "building:levels": "10"}, (12.5, "osm_height")),
    ({"height": "7,5"}, (7.5, "osm_height")),
    ({"height": "100 ft"}, (30.48, "osm_height")),
    ({"building:levels": "4"}, (12.0, "osm_levels")),
    ({"height": "yes", "building:levels": "2"}, (6.0, "osm_levels")),
    ({"height": "0", "building:levels": "2;3"}, (9.0, "osm_levels")),
    ({"building:levels": "-1"}, (6.0, "default")),
    ({}, (6.0, "default")),
])
def test_building_height_rules(tags, expected):
    h, source = building_height(tags)
    assert source == expected[1]
    assert h == pytest.approx(expected[0])


def test_parsers_reject_nonsense():
    assert parse_height(None) is None
    assert parse_height("tall") is None
    assert parse_height("5000") is None
    assert parse_levels("many") is None
    assert parse_levels("3.5") == 3.5


def test_buildings_to_grid_projects_clips_and_counts():
    # two lon/lat squares near (30.68 E, 36.94 N), one far outside the UTM box
    inside = box(30.680, 36.940, 30.6802, 36.9402)
    outside = box(31.5, 37.5, 31.5002, 37.5002)
    out = buildings_to_grid([(inside, {"building:levels": "2"}), (outside, {})],
                            (288390, 4085730, 298410, 4095750))
    assert len(out) == 1
    assert out[0]["height_source"] == "osm_levels" and out[0]["height_m"] == 6.0
    assert 300 < out[0]["geometry"].area < 500  # about 18 m x 22 m
    rows = {r["height_source"]: r for r in height_source_counts(out)}
    assert rows["osm_levels"]["n_buildings"] == 1 and rows["default"]["n_buildings"] == 0


def test_ground_under_buildings_follows_slope_and_never_rises():
    # plane rising 1 m per column, a 3x3 "building" 20 m high in the middle
    dsm = np.tile(np.arange(10, dtype=np.float32), (10, 1))
    mask = np.zeros((10, 10), bool)
    mask[4:7, 4:7] = True
    dsm[mask] += 20
    ground = ground_under_buildings(dsm, mask)
    assert np.array_equal(ground[~mask], dsm[~mask])
    assert np.all(ground <= dsm)
    plane = np.tile(np.arange(10, dtype=np.float32), (10, 1))
    assert np.abs(ground[mask] - plane[mask]).max() < 1.5
    assert ground[5, 4] < ground[5, 6]  # still rises west -> east across the block


def test_ground_under_buildings_without_buildings_is_a_copy():
    dsm = np.ones((4, 4), np.float32)
    ground = ground_under_buildings(dsm, np.zeros((4, 4), bool))
    assert np.array_equal(ground, dsm) and ground is not dsm


def _small_scenes():
    res = 10.0
    transform = from_origin(1000.0, 2200.0, res, res)
    dsm = np.full((20, 20), 50.0, np.float32)
    dsm[5:10, 5:10] = 62.0  # a roof in the DSM
    buildings = [{"geometry": box(1050, 2100, 1100, 2150), "height_m": 12.0, "height_source": "osm_height"}]
    observers = [{"id": "G1", "x": 1015.0, "y": 2185.0, "eye_height_m": 10.0, "range_day_m": 300.0,
                  "range_night_m": 100.0, "fov_deg": 360.0, "heading_deg": 0.0}]
    tasks = [{"id": "T1", "start": [1005.0, 2005.0], "goal": [1195.0, 2195.0],
              "mode": "pedestrian", "time": "day"}]
    landcover = np.full((20, 20), 50, np.uint8)
    return dsm, make_real_scenes("tiny", "antalya_periurban", dsm, transform, buildings, observers, tasks,
                                 landcover=landcover)


def test_make_real_scenes_two_variants(tmp_path):
    dsm, (dem_scene, bld_scene) = _small_scenes()
    assert dem_scene.meta["name"] == "tiny_dem" and dem_scene.meta["terrain_is_surface"] is True
    assert bld_scene.meta["name"] == "tiny_dem_buildings" and bld_scene.meta["terrain_is_surface"] is False
    mask = dem_scene.obstacle_mask()
    assert mask.sum() == 25
    assert np.array_equal(dem_scene.surface(), dsm)
    surface = bld_scene.surface()
    assert np.array_equal(surface[~mask], dsm[~mask])
    assert np.allclose(bld_scene.terrain[mask], 50.0)
    assert np.allclose(surface[mask], 62.0)
    for scene in (dem_scene, bld_scene):
        scene.save(tmp_path / scene.meta["name"])
        loaded = Scene.load(tmp_path / scene.meta["name"])
        assert np.array_equal(loaded.surface(), scene.surface())
        assert np.array_equal(loaded.landcover, scene.landcover)


# ---- the built Antalya scenes (need data/, skipped in CI) ----

def _load(name):
    path = SCENES / name
    if not (path / "scene.json").exists():
        pytest.skip(f"{path} not built, run scripts/build_real_scene.py")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Scene.load(path)


@pytest.fixture(scope="module")
def antalya():
    return _load("antalya_dem"), _load("antalya_dem_buildings")


def test_antalya_scenes_load(antalya):
    dem_scene, bld_scene = antalya
    for s in antalya:
        assert s.meta["region"] == "antalya_periurban" and s.shape == (334, 334)
        assert s.landcover is not None and len(s.observers) == 3 and len(s.tasks) == 5
    assert dem_scene.meta["terrain_is_surface"] and not bld_scene.meta["terrain_is_surface"]


def test_antalya_building_cell_share_matches_buildings_csv(antalya):
    dem_scene, _ = antalya
    with open(REPORTS / "checks" / "buildings.csv", newline="", encoding="utf-8") as f:
        ref = next(r for r in csv.DictReader(f) if r["region"] == "antalya_periurban")
    cell_pct = 100 * dem_scene.obstacle_mask().mean()
    # buildings.csv gives the area fraction (10x10 subpixels), the scene counts cell centres
    assert abs(cell_pct - float(ref["building_area_pct"])) < 0.5


def test_antalya_surface_equals_dem_outside_buildings(antalya):
    dem_scene, bld_scene = antalya
    mask = dem_scene.obstacle_mask()
    assert np.array_equal(bld_scene.surface()[~mask], dem_scene.terrain[~mask])
    assert np.all(bld_scene.terrain <= dem_scene.terrain)


def test_antalya_points_outside_buildings(antalya):
    dem_scene, _ = antalya
    mask = dem_scene.obstacle_mask()
    for o in dem_scene.observers:
        assert not mask[dem_scene.world_to_cell(o["x"], o["y"])], o["id"]
    for t in dem_scene.tasks:
        for end in ("start", "goal"):
            assert not mask[dem_scene.world_to_cell(*t[end])], (t["id"], end)
