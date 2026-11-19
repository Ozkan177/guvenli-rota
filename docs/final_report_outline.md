# CSE 491 final report: outline

Working outline for the end-of-semester report. Owners follow the task table in `CLAUDE.md`. Each owner writes
their section as `docs/final_report/<section>.md` (prompt P12-H in `docs/gorev_sirasi_ve_promptlar.md`), and Özkan
merges them into `docs/final_report.md` (P13-Ö).

Rules for every section:
- Use only what is in the repository code and under `reports/`. Do not invent numbers; write **TBD** until a
  result exists, and note which file each number comes from.
- Where a result is weak, say so.
- Files marked *(planned, Task N)* do not exist on `main` yet; *(in review)* means the code is on an open branch.

---

## 1. Abstract
**Owner:** Özkan Damdelen (written last)
- Problem in two sentences: routes that stay hidden from observers, planned on synthetic and real-data scenes.
- What was built: shared scene format, visibility cost layer, A* with visibility cost, evaluation metrics.
- Main result of the first experiment (H5, and H4 if available): **TBD**.

**Sources:** sections 5-8 of this report.

## 2. Introduction and problem
**Owner:** Özkan Damdelen
- Motivation: field teams and vehicles need routes that are short, safe and hard to observe. In the original
  proposal there were three costs (time, risk, connectivity) and a Pareto set.
- Change of focus after meeting 4 (11.11.2026): "reach B from A without being seen by observers". There are now
  two environments, synthetic 3D scenes with known ground truth and real-data scenes in the same format.
  Targeting and fire calculations are out of scope.
- Research questions and hypotheses H1, H4, H5 as defined in `CLAUDE.md`.

**Sources:** `CLAUDE.md` (project summary, meeting 4 notes), CSE 491 proposal (`docs/CSE491_Proposal_P46_Safe_Route_Planning.docx`, local copy, not in git).

## 3. Related work
**Owner:** Muhammed İkbal Ceyhan (routing), Furkan Şenol (visibility and line of sight)
- Grid and graph search: A* (Hart et al., 1968), multi-objective search NAMOA* (Mandow & Pérez de la Cruz, 2005),
  NSGA-II (Deb et al., 2002), A*-based terrain routing for ground vehicles (Taşar & Karakaya, 2025).
- Line of sight and viewshed on elevation models, and the error a coarse grid adds compared with a finer reference
  (background for H4).
- Explainable planning, kept short because it moves to Senior Design II: Krarup et al. (2021), Kambhampati et
  al. (2024), Chakraborti et al. (2020).

**Sources:** reference list of the CSE 491 proposal; new viewshed references collected by Furkan.

## 4. Requirements
**Owner:** Özkan Damdelen
- Functional requirements from the proposal (FR-1 … FR-6), marked as done, changed by the new scope, or moved
  to Senior Design II.
- New requirements from meetings 3 and 4: user-set constraints per mission, pedestrian and vehicle mode,
  day/night, observers with range, field of view and eye height, one scene format for synthetic and real data.
- Non-functional requirements: open data with licences (NFR-3), reproducibility (scripts, `data/data_manifest.csv`,
  seeds), tests on every pull request.

**Sources:** CSE 491 proposal section 5, `CLAUDE.md` (meeting 3 and 4 notes), `docs/scene_format.md`.

## 5. System design
### 5.1 Scene format
**Owner:** Özkan Damdelen
- Folder layout and fields (`scene.json`, `terrain.tif`, `obstacles.geojson`, `observers.json`, `tasks.json`, optional `landcover.tif`).
- `terrain_is_surface` and `surface()`: the Copernicus DEM is a DSM, so obstacles must not be added twice.
- Validation: each error names the file and the field, and raster grids are checked against `scene.json`.

**Sources:** `docs/scene_format.md`, `src/guvenli_rota/scene/core.py`, `tests/test_scene.py`.

### 5.2 Visibility
**Owner:** Furkan Şenol
- Line of sight over the surface raster.
- Observer model: range by day and by night, field of view, heading, eye height.
- Visibility cost layer used by the router.

**Sources:** `src/guvenli_rota/connectivity/line_of_sight.py` *(in review)*, `src/guvenli_rota/visibility/observer.py` *(planned, Task 4)*.

### 5.3 Routing
**Owner:** Muhammed İkbal Ceyhan
- Weighted A* on an 8-connected grid. Cost model: slope multiplier and impassable cells. Admissible heuristic.
- Visibility term with weight `w_vis`: `w_vis = 0` gives the shortest route, `w_vis > 0` the unseen route.
- How synthetic and real scenes go through the same code path.

**Sources:** `src/guvenli_rota/routing/astar.py`, `tests/test_astar.py`, visibility cost in A* *(planned, Task 6)*.

## 6. Data
**Owner:** Feyiz Ali Bozkurt
- Phase 0 summary: five open datasets, three test regions, common 30 m grid and the alignment checks. Decisions
  from the feasibility report (Ookla is the main connectivity source; OpenCelliD is used only in the peri-urban region).
- Synthetic scenes (terrain types, seeds, 5/10/30 m) and the real-data converter for Antalya with two variants
  (DEM only, DEM + OSM buildings).
- Limitations of the data: DSM, Ookla sparseness, OpenCelliD positions are estimates, OSM tags are sparse.

**Sources:** `reports/veri_fizibilite_raporu.md`, `reports/checks/*.csv`, `reports/figures/quicklook_*.png`,
`scripts/build_grid.py`, `scripts/build_buildings.py`, `src/guvenli_rota/scene/synthetic.py` *(planned, Task 3)*,
`src/guvenli_rota/scene/converter.py` *(planned, Task 5)*.

## 7. Implementation
**Owner:** Muhammed İkbal Ceyhan, Feyiz Ali Bozkurt
- Package layout (`scene/`, `routing/`, `visibility/`, `evaluation/`), scripts and configuration.
- Testing: unit tests per module, integration test from scene to visibility to route, and CI on every pull
  request. Give the number of tests from `pytest -q` (**TBD** at the time of writing).
- Reproducibility: download manifest with SHA256, pixel-level data check, synthetic scenes regenerated from seeds.

**Sources:** `src/guvenli_rota/`, `tests/`, `.github/workflows/tests.yml`, `data/data_manifest.csv`,
`scripts/check_data_pixels.py`, `tests/test_integration.py` *(planned, Task 11)*.

## 8. Experiments and results
**Owner:** Özkan Damdelen, Furkan Şenol
- H1 pre-test (Phase 0, Antalya): Spearman correlation between site density and Ookla speed, as reported in the
  feasibility report.
- End-to-end demo: shortest route vs unseen route on a synthetic hills scene and on Antalya. Table of length,
  length increase and visible fraction: **TBD**.
- First experiment: hills scenes, seeds 0-4, 5/10/30 m.
  - H5: Wilcoxon test of the visible fraction, shortest vs unseen route. **TBD**.
  - H4: the planner's estimate vs the 5 m reference, as a Spearman correlation and an error per resolution. **TBD**.

**Sources:** `reports/checks/h1.csv`, `reports/figures/h1_antalya.png`, `src/guvenli_rota/evaluation/metrics.py`,
`scripts/demo_unseen_route.py` and `reports/checks/demo_unseen.csv` *(planned, Task 7)*,
`scripts/exp_visibility.py`, `reports/checks/exp_visibility.csv` and `exp_visibility_summary.csv` *(planned, Task 8)*.

## 9. Discussion and limitations
**Owner:** Furkan Şenol (visibility model), Feyiz Ali Bozkurt (data)
- What the results do and do not show. Synthetic scenes have known ground truth; real scenes do not, so real-data
  visibility cannot be validated with open data.
- Grid effects: a 30 m cell hides small obstacles, and the size of that error is measured by H4.
  Ray-traced ground truth at 1 m: done, or listed as next step (Task 10).
- Data limitations carried over from Phase 0, and the vehicle and night-time assumptions.

**Sources:** sections 6 and 8, `reports/veri_fizibilite_raporu.md` (section 6), `src/guvenli_rota/visibility/ground_truth.py` *(planned, Task 10)*.

## 10. Plan for Senior Design II
**Owner:** all members, merged by Özkan Damdelen
- NAMOA* and NSGA-II on time, risk/visibility and connectivity costs, compared with weighted A* (run time, memory, hypervolume).
- Turkish justification with a language model, checked against planner evidence (evidence schema, verifier,
  contrastive "why not" questions).
- Map interface; ray-traced ground truth if not finished; real-data scenes for the other two regions.

**Sources:** CSE 491 proposal (sections 3 and 7), prompt P14-H output from each member.

## 11. AI use statement
**Owner:** Özkan Damdelen (collects one or two sentences from every member)
- Which tools were used and for what: Claude Code for scripts, tests, report drafts and repository setup.
- What the team decided and checked itself: data sources, regions, method, and every number in the report
  checked against `reports/`.

**Sources:** README "AI use" section, AI statement in `reports/veri_fizibilite_raporu.md`, member notes from P12-H.

## 12. References
**Owner:** each section owner adds their citations; Özkan Damdelen merges and formats them
- Start from the proposal's reference list.
- Add data citations and licences exactly as in the README "Attribution" section.
- Add new viewshed and grid-error references from sections 3 and 9.

**Sources:** CSE 491 proposal references, `README.md` (Data sources, Attribution).
