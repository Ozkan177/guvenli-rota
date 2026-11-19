import json

import numpy as np
import pytest

from guvenli_rota.scene import Scene, SceneError

RES = 10.0
ORIGIN = (0.0, 200.0)


def box(x1, y1, x2, y2):
    return {"type": "Polygon", "coordinates": [[[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]]]}


def obstacle(geometry, kind, height):
    return {"type": "Feature", "geometry": geometry,
            "properties": {"kind": kind, "height_m": height, "height_source": "synthetic"}}


def make_scene(terrain_is_surface=False, landcover=True):
    # building covers cell centres in rows 2-4, cols 2-4; tree covers rows 3-5, cols 4-6.
    # The tree comes after the building so that a plain "last one wins" rasterisation would give 5, not 8.
    return Scene(
        meta={"format_version": "0.1", "name": "test_20x20", "source": "synthetic", "seed": 7,
              "crs": "EPSG:32636", "resolution_m": RES, "width": 20, "height": 20,
              "origin": list(ORIGIN), "terrain_is_surface": terrain_is_surface, "notes": "unit test"},
        terrain=(np.arange(400, dtype=np.float32).reshape(20, 20) * 0.5),
        obstacles=[obstacle(box(20, 150, 50, 180), "building", 8.0),
                   obstacle(box(40, 140, 70, 170), "tree", 5.0)],
        observers=[{"id": "G1", "x": 105.0, "y": 95.0, "eye_height_m": 1.7, "range_day_m": 1500.0,
                    "range_night_m": 300.0, "fov_deg": 360.0, "heading_deg": 0.0}],
        tasks=[{"id": "T1", "start": [5.0, 5.0], "goal": [195.0, 195.0], "mode": "pedestrian", "time": "day"}],
        landcover=np.full((20, 20), 30, dtype=np.uint8) if landcover else None,
    )


BUILDING = {(r, c) for r in range(2, 5) for c in range(2, 5)}
TREE = {(r, c) for r in range(3, 6) for c in range(4, 7)}


def test_save_load_round_trip(tmp_path):
    scene = make_scene()
    scene.save(tmp_path / "s")
    loaded = Scene.load(tmp_path / "s")

    assert loaded.meta == scene.meta
    assert loaded.terrain.dtype == np.float32
    np.testing.assert_array_equal(loaded.terrain, scene.terrain)
    np.testing.assert_array_equal(loaded.landcover, scene.landcover)
    assert loaded.obstacles == scene.obstacles
    assert loaded.observers == scene.observers
    assert loaded.tasks == scene.tasks


def test_landcover_is_optional(tmp_path):
    make_scene(landcover=False).save(tmp_path / "s")
    assert not (tmp_path / "s" / "landcover.tif").exists()
    assert Scene.load(tmp_path / "s").landcover is None


def test_obstacle_mask_uses_cell_centres():
    mask = make_scene().obstacle_mask()
    assert set(zip(*np.nonzero(mask))) == BUILDING | TREE


def test_obstacle_touching_a_cell_without_its_centre_is_not_rasterised():
    scene = make_scene()
    scene.obstacles = [obstacle(box(0, 196, 4, 200), "vehicle", 2.0)]
    assert not scene.obstacle_mask().any()


def test_surface_adds_tallest_obstacle_when_terrain_is_bare_ground():
    scene = make_scene(terrain_is_surface=False)
    added = scene.surface() - scene.terrain
    for r in range(20):
        for c in range(20):
            expected = 8.0 if (r, c) in BUILDING else 5.0 if (r, c) in TREE else 0.0
            assert added[r, c] == expected, (r, c)


def test_surface_is_terrain_when_terrain_is_a_surface_model():
    scene = make_scene(terrain_is_surface=True)
    np.testing.assert_array_equal(scene.surface(), scene.terrain)


def test_world_to_cell_and_cell_to_world_are_inverse():
    scene = make_scene()
    for r in range(20):
        for c in range(20):
            assert scene.world_to_cell(*scene.cell_to_world(r, c)) == (r, c)


def test_world_to_cell_edges():
    scene = make_scene()
    assert scene.world_to_cell(0.0, 200.0) == (0, 0)
    assert scene.world_to_cell(199.99, 0.01) == (19, 19)
    assert scene.cell_to_world(0, 0) == (5.0, 195.0)
    with pytest.raises(ValueError):
        scene.world_to_cell(200.0, 100.0)
    with pytest.raises(ValueError):
        scene.cell_to_world(20, 0)


def edit_json(folder, name, change):
    p = folder / name
    data = json.loads(p.read_text(encoding="utf-8"))
    p.write_text(json.dumps(change(data) or data), encoding="utf-8")


@pytest.mark.parametrize("corrupt, message", [
    (lambda d: (d / "tasks.json").unlink(), r"tasks\.json: file missing"),
    (lambda d: (d / "terrain.tif").unlink(), r"terrain\.tif: file missing"),
    (lambda d: edit_json(d, "scene.json", lambda m: m.pop("crs") and None), r"scene\.json: missing field 'crs'"),
    (lambda d: edit_json(d, "scene.json", lambda m: m.update(format_version="0.2")),
     r"scene\.json: format_version '0\.2' is not supported"),
    (lambda d: edit_json(d, "scene.json", lambda m: m.update(width=21)),
     r"terrain\.tif: raster is 20x20 .* width=21"),
    (lambda d: edit_json(d, "observers.json", lambda o: o[0].pop("eye_height_m") and None),
     r"observers\.json: observer 'G1': missing field 'eye_height_m'"),
    (lambda d: edit_json(d, "observers.json", lambda o: o[0].update(x=500.0)),
     r"observers\.json: observer 'G1': position \(500\.0, 95\.0\) is outside the scene"),
    (lambda d: edit_json(d, "tasks.json", lambda t: t[0].update(goal=[195.0, 250.0])),
     r"tasks\.json: task 'T1': field 'goal' .* is outside the scene"),
    (lambda d: edit_json(d, "tasks.json", lambda t: t[0].update(mode="tank")), r"tasks\.json: task 'T1': field 'mode'"),
    (lambda d: edit_json(d, "tasks.json", lambda t: t.clear()), r"tasks\.json: needs at least one task"),
    (lambda d: edit_json(d, "obstacles.geojson", lambda fc: fc["features"][1]["properties"].pop("height_m") and None),
     r"obstacles\.geojson: feature at index 1: properties: missing field 'height_m'"),
    (lambda d: (d / "observers.json").write_text("[{", encoding="utf-8"), r"observers\.json: invalid JSON"),
])
def test_broken_scene_reports_file_and_field(tmp_path, corrupt, message):
    folder = tmp_path / "s"
    make_scene().save(folder)
    corrupt(folder)
    with pytest.raises(SceneError, match=message):
        Scene.load(folder)
