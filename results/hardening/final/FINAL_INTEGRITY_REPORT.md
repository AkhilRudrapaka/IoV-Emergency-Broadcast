# Final integrity report (Block G, 2026-11-21)

## Snapshots

- **`pre_final_manifest_sha256.txt`:** sha256 of all 19,822 files under `results/`. Taken before any final-stage run:
  after the Phase 1 code change, before the baseline checks and G4.
- **`results_manifest_sha256.txt`:** sha256 of all 23,160 files under `results/` after G4, the final checks and the
  documentation updates. It excludes `results/hardening/final/` itself.

## Comparison

| Set | Result |
|---|---|
| Block F (`results/adversarial/`) | unchanged (all files hash-identical) |
| G1, G2, G3a, G3b, G3b_gate, G3b_k0_check (`results/hardening/<sweep>/` and the top-level CSVs and JSONs) | unchanged |
| Historical selections (`G2_selection.json` etc.) and `PREREGISTERED_RULES.json` | unchanged |
| `results/incident/`, `results/incident_routing/` | unchanged |
| Tracked `results/urban/` | unchanged; `git status` clean |
| `results/hardening/BLOCK_G_TABLES.md` | regenerated. With its G4 completion row and G4 section removed, it is byte-identical to the pre-G4 file: only G4 content was added. |
| `results/hardening/sweep_log.txt` | appended only (the earlier content is an exact prefix) |

**Added since the snapshot: 3,338 files.**
- `results/hardening/G4/`: 25 settings, 2,250 raw records.
- `results/hardening/G4_*.csv`.
- `results/hardening/final_checks/`: baseline and new-default reproductions, the post-G4 re-run, and the incident demo.
- Analysis scripts and their outputs, and reports.

**Earlier stage snapshots** (all verified at the time):
- pre-G3a: 12,271 files;
- pre-G3b: 14,226 files.

## Code state during the runs

No Python module changed between the first baseline check and the end of G4. This was checked by modification time
against `final_checks/baseline_off`.

Edits after G4:
- test fixtures;
- documentation;
- generated portal copies;
- analysis scripts under `results/hardening/analysis/`.

The final test run covers the final tree.

## Final cleanup check (against `results_manifest_sha256.txt`, taken after G4)

- All 23,160 files in the post-G4 manifest are unchanged, except `sweep_log.txt`, which is append-only (verified).
- This covers Block F, G1, G2, G3a, G3b, G3b_gate, G3b_k0_check, G4, `results/incident`, `results/incident_routing`,
  `results/urban`, the earlier `final_checks/` runs, and every report, CSV and JSON under `results/`. The manifest
  excludes `results/hardening/final/`, which holds the records themselves.
- Added since then:
  - `final_checks/cleanup/` (448 files);
  - `final_checks/incident_demo_cleanup/` (5 files);
  - `analysis/final_baseline_check_cleanup_output.txt`.
- `results/urban`: `git status` clean.
- Nothing staged, committed or pushed (HEAD `107f1b4`).
