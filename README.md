# Güvenli Rota: Safe Route Planning for Mission-Critical Systems

CSE 491 Senior Design, Group 7, Akdeniz University, Department of Computer Engineering.
Advisor: Asst. Prof. Dr. Taner Danışman.
Team: Özkan Damdelen (lead), Muhammed İkbal Ceyhan, Feyiz Ali Bozkurt, Furkan Şenol.

The system proposes several routes for a field team or vehicle. Each route has three costs: travel time,
risk, and quality of the communication link. Because these objectives conflict, the planner returns a
Pareto set of non-dominated routes instead of a single best one. When the user picks a route, a language
model explains in Turkish why it was chosen and why the others were not. Every number in the explanation
is checked against the planner's own computation, and explanations that do not match are not shown.

## Status

- Phase 0 (data feasibility) is done: five open datasets are downloaded for three test regions and
  aligned on a common 30 m grid. See `reports/veri_fizibilite_raporu.md`.
- Working code: weighted A* on a slope grid (`src/guvenli_rota/routing/astar.py`) and a line-of-sight
  module on the DEM (in review).
- Next (Dec 2026): the planner runs in two environments, synthetic 3D scenes where the ground truth is
  known and scenes built from real open data, both in one scene format (`docs/scene_format.md`).
  The first target is a route that observers cannot see, compared with the shortest route.

Tests run on every pull request (`.github/workflows/tests.yml`):

```bash
pip install -e . && pytest -q
```

## Repository layout

```
src/guvenli_rota/   Python package
scripts/            download, clip and check scripts
notebooks/          exploratory notebooks
config/             region definitions and settings
data/raw/           downloaded data per region (not in git)
data/processed/     aligned 30 m grids (not in git)
reports/            feasibility report and figures
docs/               scene format and project documents
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .               # makes src/guvenli_rota importable
cp .env.example .env             # then put your OpenCelliD token in .env
```

## Reproducing Phase 0

```bash
python scripts/download_dem.py
python scripts/download_worldcover.py
python scripts/download_osm.py          # ~650 MB Geofabrik extract
python scripts/download_ookla.py
python scripts/download_opencellid.py   # or place 286.csv.gz in data/raw/opencellid/ by hand
python scripts/extract_osm_masts.py
python scripts/check_dem.py; python scripts/check_worldcover.py; python scripts/check_osm.py
python scripts/check_ookla.py; python scripts/check_opencellid.py; python scripts/plot_quicklook.py
python scripts/build_grid.py; python scripts/check_grid.py
PYTHONPATH=src python scripts/build_buildings.py
PYTHONPATH=src python scripts/check_buildings.py
python scripts/h1_antalya.py; python scripts/check_needs.py
```

Results: `reports/veri_fizibilite_raporu.md` (feasibility report, Turkish), tables in `reports/checks/`, figures in `reports/figures/`.
The building layer is stored as `data/processed/<region>/buildings.tif`, where each cell
contains the estimated building footprint fraction from 0 to 1. Its alignment and
WorldCover/slope checks are written to `reports/checks/buildings.csv`.

## Demo

End-to-end run: scene, then observer visibility, then the shortest route (`w_vis = 0`) and the unseen route
(`w_vis = 5`), then a figure and a table. It runs on a synthetic hills scene and on the Antalya real-data scene.

```bash
PYTHONPATH=src python scripts/build_real_scene.py   # once, builds data/scenes/antalya_dem_buildings (~8 min)
python scripts/demo_unseen_route.py                 # ~1.5 min
```

Outputs: `reports/figures/demo_unseen_synthetic.png`, `reports/figures/demo_unseen_antalya.png` and
`reports/checks/demo_unseen.csv`.

How the task in each figure is chosen:
- **Synthetic** (seeds 0-4, 10 m, building density 0.02, 4 observers): the task whose shortest route is the
  most visible, among tasks where the unseen route is at most 30 % longer.
- **Antalya**: of the 5 tasks in `tasks.json`, the one whose shortest route is the most visible.

Visibility is day-time for every task. "Shortest" means least slope-weighted cost, not least length.

Current result (`reports/checks/demo_unseen.csv`):

| Scene | Task | Route | Length (m) | Length increase | Visible |
|---|---|---|---|---|---|
| synthetic_hills_s4_10m | T3 | shortest | 2503 | 0.0 % | 83.0 % |
| synthetic_hills_s4_10m | T3 | unseen | 2943 | 17.6 % | 9.8 % |
| antalya_dem_buildings | T2 | shortest | 9987 | 0.0 % | 3.1 % |
| antalya_dem_buildings | T2 | unseen | 9915 | -0.7 % | 0.0 % |

In the Antalya scene the three observers see only 3.2 % of the cells, so no task has a strongly visible
shortest route. The cause is the terrain, not the visibility code: on a flat surface the tower observer G1
sees its whole 3 km range (28 % of the scene), but on the scene terrain, even without buildings, it sees
2.9 %. The plateau top around G1 hides the city below.

## Data sources

| Dataset | Use | Access | License |
|---|---|---|---|
| Copernicus DEM GLO-30 (2021) | elevation, slope | `s3://copernicus-dem-30m/` (public) | Copernicus DEM licence, DOI 10.5270/ESA-c5d3d65 |
| ESA WorldCover 10 m 2021 v200 | land cover | `s3://esa-worldcover/v200/2021/map/` (public) | CC BY 4.0, DOI 10.5281/zenodo.7254221 |
| OpenStreetMap | road network | Geofabrik `turkey-261001.osm.pbf` | ODbL |
| OpenCelliD (MCC 286) | cell tower locations | opencellid.org, token required | CC BY-SA 4.0 |
| Ookla Speedtest open data | measured mobile speed | `s3://ookla-open-data/parquet/performance/type=mobile/` (public) | CC BY-NC-SA 4.0 |

Raw data is not stored in this repository. Each download is logged in `data/data_manifest.csv`
(source, version, date, size, SHA256) so the inputs can be reproduced.

## Attribution

- Contains modified Copernicus DEM data © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018,
  provided under COPERNICUS by the European Union and ESA.
- © ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by the
  ESA WorldCover consortium.
- © OpenStreetMap contributors.
- OpenCelliD Project, licensed under CC BY-SA 4.0. Layers derived from it are shared under the same license.
- Speedtest® by Ookla® Global Fixed and Mobile Network Performance Maps, licensed under CC BY-NC-SA 4.0.
  https://github.com/teamookla/ookla-open-data

## Team and contributions

| Member | GitHub username | Responsible for | Pull requests |
|---|---|---|---|
| Özkan Damdelen (lead) | Ozkan177 | Phase 0 data pipeline and feasibility report (`scripts/download_*.py`, `scripts/check_*.py`, `scripts/build_grid.py`, `scripts/h1_antalya.py`; committed before the PR workflow started), scene format (`src/guvenli_rota/scene/`), evaluation metrics (`src/guvenli_rota/evaluation/`), CI and project documents | #1, #4, #5, #6, #7 |
| Muhammed İkbal Ceyhan | muhammedceyhan | Weighted A* (`src/guvenli_rota/routing/`), synthetic scene generator (planned) | #3 |
| Feyiz Ali Bozkurt | Bozkurt-FeyizAli | OSM building layer (`scripts/build_buildings.py`, `scripts/check_buildings.py`), real-data scene converter (planned) | #2 |
| Furkan Şenol | Nightwolf37 | Line of sight (`src/guvenli_rota/connectivity/`), observer visibility (planned) | Line-of-sight module: in review |

## AI use

This repository was set up with assistance from Claude Code.
