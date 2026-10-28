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

Phase 0: data feasibility. We verify that each open dataset can be downloaded, covers Turkey and the
three test regions (peri-urban Antalya, mountainous Saklıkent, Konya Plain), has the expected resolution,
and is usable for the project. No routing, LLM, or UI code yet.

## Repository layout

```
src/guvenli_rota/   Python package
scripts/            download, clip and check scripts
notebooks/          exploratory notebooks
config/             region definitions and settings
data/raw/           downloaded data per region (not in git)
data/processed/     aligned 30 m grids (not in git)
reports/            feasibility report and figures
docs/               project proposal documents
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .               # makes src/guvenli_rota importable
cp .env.example .env             # then put your OpenCelliD token in .env
```

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

## AI use

This repository was set up with assistance from Claude Code.
