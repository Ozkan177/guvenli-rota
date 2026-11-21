# CSE 491 final presentation plan

Target length: 11:30 (allowed 10-12 minutes), then questions. Each member presents at least one part. Slide
content and speaker notes for each part come from prompt P14-H in `docs/gorev_sirasi_ve_promptlar.md`.

Rules:
- Show only results that exist in `reports/`. Until they exist, the slide says **TBD**, and we do not quote numbers
  from memory.
- Every figure on a slide names its file, so it can be regenerated.

## Flow

| # | Part | Time | Presenter | What is shown |
|---|---|---|---|---|
| 1 | Problem and motivation | 1:00 | Özkan Damdelen | A field team must reach B without being seen. Why the shortest route is not enough. |
| 2 | Scope and approach | 1:00 | Özkan Damdelen | Change after meeting 4: synthetic scenes with known ground truth and real-data scenes, one scene format (`docs/scene_format.md`). |
| 3 | Data and real-data scenes | 1:30 | Feyiz Ali Bozkurt | Phase 0 in one slide (five datasets, three regions, common 30 m grid). Antalya scene in two variants, DEM only and DEM + buildings. Figure: `reports/figures/quicklook_antalya_periurban.png`. |
| 4 | Synthetic scenes | 1:00 | Muhammed İkbal Ceyhan | Terrain types, buildings and vehicles, seeds, 5/10/30 m. Figure of one generated scene **TBD** (Task 3). |
| 5 | Visibility | 1:30 | Furkan Şenol | Line of sight on the surface, observer range, field of view, day/night. Figure: viewshed of one scene **TBD** (Tasks 1 and 4). |
| 6 | Routing | 1:00 | Muhammed İkbal Ceyhan | A* with slope and visibility cost. Shortest route (`w_vis = 0`) vs unseen route. |
| 7 | Demo | 2:00 | Özkan Damdelen | See "Demo" below. |
| 8 | First experiment | 1:30 | Furkan Şenol | H5: visible fraction, shortest vs unseen route, with p value. H4: planner estimate vs 5 m reference per resolution. Values **TBD** (Task 8, `reports/checks/exp_visibility_summary.csv`). |
| 9 | Limitations and Senior Design II | 1:00 | Feyiz Ali Bozkurt | Data and grid limitations. Plan: NAMOA*, NSGA-II, Turkish justification with a verifier, map interface, ray-traced ground truth. |
|   | **Total** | **11:30** | | |

Time per member: Özkan 4:00, Feyiz 2:30, İkbal 2:00, Furkan 3:00.

## Demo (part 7)

- **Run:** `scripts/demo_unseen_route.py` *(planned, Task 7)* on a synthetic hills scene (seed 0, 10 m) and on the
  Antalya DEM + buildings scene.
- **Show:** one figure per scene with terrain, buildings, observers and their visible area, the shortest route and
  the unseen route (`reports/figures/demo_unseen_<scene>.png`). Then the table from `reports/checks/demo_unseen.csv`:
  length, length increase, visible fraction, run time. Values **TBD**.
- **Live or recorded:** run live only if it finishes in under 30 seconds on the presentation laptop. Otherwise show
  the saved figures. Either way, keep the PNGs ready as a fallback.
- **If time allows:** the GitHub Actions page with green tests.

## Before the presentation

- [ ] Dry run with a timer; cut any part that runs over its time.
- [ ] Every number on the slides checked against `reports/checks/`.
- [ ] Demo run on the presentation laptop from a clean clone.
- [ ] Each presenter prepares answers to likely questions on their part (P14-H).
