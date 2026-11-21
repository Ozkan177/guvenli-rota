# Scene format (v0.1)

The planner reads every test case through one format, whether the scene is synthetic or built from
real data. The synthetic generator and the real-data converter both write this format, so the planner,
the visibility module and the evaluation scripts never need to know where a scene came from.

## Folder layout

One folder per scene:

```
<scene>/
  scene.json          metadata (required)
  terrain.tif         ground elevation in metres, float32 GeoTIFF (required)
  obstacles.geojson   buildings, vehicles, trees as footprint polygons with a height (required, may be empty)
  observers.json      observer list (required, may be empty)
  tasks.json          start/goal pairs (required, at least one)
  landcover.tif       ESA WorldCover class codes on the same grid (optional, real scenes only)
```

Synthetic scenes are regenerated from their seed and are not committed. They live under
`data/scenes/` like all other data.

## scene.json

```json
{
  "format_version": "0.1",
  "name": "synthetic_hills_s42_10m",
  "source": "synthetic",
  "seed": 42,
  "crs": "EPSG:32636",
  "resolution_m": 10.0,
  "width": 300,
  "height": 300,
  "origin": [0.0, 3000.0],
  "terrain_is_surface": false,
  "notes": "hills scene, 3 observers, building density 10%"
}
```

- `source`: `"synthetic"` or `"real"`. Real scenes also give `"region"` (a key of `config/regions.yaml`).
- `seed`: required for synthetic scenes, `null` for real ones.
- `crs`: real scenes use EPSG:32636 (UTM 36N). Synthetic scenes use the same CRS with a local origin, so
  all distances are in metres.
- `origin`: x, y of the top-left corner of the top-left cell (same convention as a rasterio transform).
- `terrain_is_surface`: `true` when `terrain.tif` already contains buildings and trees, which is the case
  for the Copernicus DEM (a DSM). Then obstacle heights must not be added on top a second time
  (see "Surface" below).

## obstacles.geojson

A GeoJSON FeatureCollection in the scene CRS. Each feature is a Polygon footprint with:

| property | type | meaning |
|---|---|---|
| `kind` | string | `building`, `vehicle` or `tree` |
| `height_m` | number | height above the ground |
| `height_source` | string | `synthetic`, `osm_levels`, `osm_height` or `default` |

## observers.json

```json
[
  {"id": "G1", "x": 1250.0, "y": 1800.0, "eye_height_m": 1.7,
   "range_day_m": 1500.0, "range_night_m": 300.0, "fov_deg": 360.0, "heading_deg": 0.0}
]
```

- `eye_height_m`: 1.7 for a person on the ground, 10.0 for a tower.
- `fov_deg`: horizontal field of view; 360 means the observer looks all around.
- `heading_deg`: centre of the field of view, 0 = north, clockwise. Ignored when `fov_deg` is 360.

## tasks.json

```json
[{"id": "T1", "start": [150.0, 150.0], "goal": [2850.0, 2850.0], "mode": "pedestrian", "time": "day"}]
```

`mode` is `pedestrian` or `vehicle`, `time` is `day` or `night`.

## Surface

Visibility is computed on the surface, not on the bare terrain:

- `terrain_is_surface = false` (synthetic scenes): surface = terrain + rasterised obstacle heights.
- `terrain_is_surface = true` (Copernicus DEM): surface = terrain. The real-data converter writes two
  variants of each region, one with the DEM only and one with OSM buildings added on a smoothed
  terrain, and we compare both.

## Python API (to be implemented in `src/guvenli_rota/scene/`)

```python
scene = Scene.load(path)       # reads and validates the folder
scene.terrain                  # (H, W) float array
scene.surface()                # terrain + obstacle heights, following terrain_is_surface
scene.obstacle_mask()          # (H, W) bool, cells covered by an obstacle
scene.world_to_cell(x, y)      # -> (row, col) of the cell containing the point
scene.cell_to_world(row, col)  # -> (x, y) of the cell centre
scene.save(path)
```

Changes to this format go through a pull request that updates this file and `format_version`.
