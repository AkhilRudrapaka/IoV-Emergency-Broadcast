# Files changed in Block G (nothing committed)

Branch `akhil`, based on `107f1b4`. Several tracked files were already modified by Blocks A–F before Block G started:
`build_portal_assets.py`, `corroboration.py`, `demo.py`, `experiment.py`, `figures.py`, `infrastructure.py`,
`protocols.py`, `run.py`, `scenario.py` and `portal/downloads/*`. Block G changes in those files are listed below.
`git diff` shows the combined state.

## Final stage (Phases 1–6, 2026-11-21)

**Source:**

| File | Change |
|---|---|
| `config.py` | `ENFORCE_COMMITTEE = 1` (was 0); comments for the enforcement default and for k = 4 as opt-in. |
| `adversarial.py` | G4 settings de-duplicated by folder name (34 listed → 25 unique; prevents double collection). |

**Tests** (updated for the new default):

| File | Change |
|---|---|
| `validation/test_hardening.py` | The default test now asserts enforcement on, 5/3, k = 0, no CH-route quorum, ML off. New tests: `test_enforcement_can_be_switched_off_to_reproduce_block_f`, `test_every_check_site_rejects_outsider_signers_by_default`, `test_the_k4_opt_in_and_the_g4_settings_are_preserved`. The off-vs-on comparisons now switch enforcement off explicitly. |
| `validation/test_adversarial.py` | `_block_f()` pins `ENFORCE_COMMITTEE=0` in the 3 Block F characterisation tests. Their assertions are unchanged. |
| `validation/test_incident_response.py` | The accept stub takes the committee argument, and the fixture record carries `committee`. Showcase: the genuine dissemination must equal the published record, and the voting-only forgery must now be rejected. New `test_with_enforcement_off_the_published_record_is_reproduced_exactly`. |
| `validation/test_incident_routing.py` | The fixture record carries `committee`, as every real record does. |

**Documentation:**

| File | Change |
|---|---|
| `CLAUDE.md` | Verified facts corrected; new "Block G final configuration" section. |
| `README.md`, `PROJECT_GUIDE.md`, `docs/SYSTEM_DESIGN.md` | One sentence each on the security defaults. |

**Generated copies:**
- `portal/downloads/{PROJECT_GUIDE.md, SNAPSHOT.txt, config.py, source.zip}`, produced by `python build_portal_assets.py`;
- `documentation_website/portal/downloads/PROJECT_GUIDE.md`, an exact copy of `PROJECT_GUIDE.md`, as
  `test_portal_downloads` requires.

**New reports:**
- `BLOCK_G_FINAL_REPORT.md`;
- `results/hardening/G4_CONFIRMATION_REPORT.md`;
- `results/hardening/final/{FINAL_CONFIGURATION,FINAL_TEST_REPORT,FINAL_INTEGRITY_REPORT,CHANGED_FILES}.md`.

**New analysis:**
- `results/hardening/analysis/final_baseline_check.py`, with `final_baseline_check_output.txt` and
  `final_baseline_check_post_g4_output.txt`;
- `results/hardening/analysis/g4_confirmation.py`, with `g4_confirmation_output.txt`.

**New results:**
- `results/hardening/G4/` (25 settings, 2250 raw records) and `results/hardening/G4_{genuine,trust,forgery}_{runs,summary}.csv`;
- `results/hardening/final_checks/` (`baseline_off`, `onoff09_off`, `default_on`, `onoff09_on`, `post_g4/`,
  `incident_demo/`);
- `results/hardening/final/results_manifest_sha256.txt` and `pre_final_manifest_sha256.txt`.

**Regenerated or appended:**
- `results/hardening/BLOCK_G_TABLES.md` (G4 section added; nothing removed);
- `results/hardening/sweep_log.txt` (appended; the old content is an exact prefix).

## Earlier Block G stages (G1–G4 preparation)

**Source:**
- `corroboration.py`: the committee argument to `accept`, and `require_committee`;
- `protocols.py`: committee at release and in CH-route rounds;
- `infrastructure.py`: committee in `cluster_votes` and `batch_authenticate`;
- `experiment.py`: decision trust and certificate committees;
- `scenario.py`: burst detector, `decision_trust` (capped at 0.5);
- `incident_response.py`: enforced re-verification;
- `run.py`: adversarial G1–G4 and `G3b_gate`;
- `figures.py`: colour entry;
- `adversarial.py`: G sweeps, `calibrate_burst`, corrected `select_committee`, `COMMITTEE_CANDIDATES`, `ADOPTION_RULE`,
  the `G3B_COMPARISON_GATE` arm.

**Tests:** `validation/test_hardening.py` (new).

**Reports:**
- `BLOCK_G_SECURITY_HARDENING_PLAN.md`;
- `results/hardening/{G2_RESULTS_REPORT, G3A_CALIBRATION_REPORT, G3B_EVALUATION_REPORT, G4_PREPARATION_REPORT}.md`;
- `results/hardening/PREREGISTERED_RULES.json`.

**Results:**
- `results/hardening/{G1, G2, G3a, G3b, G3b_gate, G3b_k0_check}/` with their CSVs;
- `G2_selection.json` (historical, unchanged), `G2_selection_corrected.json`, `G3a_calibration_choice.json`;
- `results/hardening/analysis/*` (`g2_paired`, `g3a_calibration`, `g3b_evaluation`, `g4_ch_route`, `blockg_tables`).

## Not changed

**Kept:**
- `results/urban` (tracked; verified clean);
- all Block F, G1, G2, G3a and G3b outputs (hash-verified);
- `results/incident`, `results/incident_routing`;
- VeReMi data;
- every historical report.

**Not regenerated:**
- `Project_Website_Documentation_Portal.docx`: its generator needs `python-docx`, which is not installed. See
  `PORTAL_CORRECTIONS.md`.
- `documentation_website/portal` content beyond the required download copy.

## Final cleanup (2026-11-21, after approval)

| File | Change |
|---|---|
| `portal/app.js` | 7 text corrections (`PORTAL_CORRECTIONS.md`). |
| `protocols.py` | The stale "opt-in level" comment on line 111 was replaced by a trailing comment on line 110 ("members: the rebuilt committee, enforced by default"). Comment only; line numbers unchanged. |
| `portal/downloads/{source.zip, SNAPSHOT.txt}` | Regenerated by `python build_portal_assets.py`. `config.py` and `PROJECT_GUIDE.md` copies already current. |
| `results/hardening/final/{PORTAL_CORRECTIONS,GIT_DIFF_SUMMARY}.md` | New. |
| `results/hardening/final/{FINAL_TEST_REPORT,FINAL_INTEGRITY_REPORT,CHANGED_FILES}.md` | Cleanup sections added. |
| `results/hardening/final_checks/{cleanup, incident_demo_cleanup}/` | New: the final baseline, new-default and incident-demo runs. |
| `results/hardening/analysis/final_baseline_check_cleanup_output.txt` | New. |
| `results/hardening/sweep_log.txt` | Appended. |
| `BLOCK_G_FINAL_REPORT.md` | One limitation added (the stale `.docx` download) and the evidence table extended. |

## Pre-commit portability fix (approved option 1)

| File | Change |
|---|---|
| `veremi/test_preprocess.py` | The absolute dataset path was replaced by `Path(__file__).resolve().parents[3] / "data/veremi_nextgen/InTAS_highway_2"`, the same `<repo>/../../data` root as `config.ML_MODEL_DIR`. The real-dataset test's skip reason now names the expected location when the data is missing. |
| `DATASET_ACQUISITION_REPORT.md` | Absolute data and repository paths replaced by the `<data>` and `<repo>` placeholders, now defined relative to the repository. |
| `PREPROCESSING_REPORT.md` | The output path is written as `<data>/processed/v2/`; the command example uses `D="../../data/veremi_nextgen/InTAS_highway_2"`. Facts, measurements and commands are unchanged. |
| `portal/downloads/source.zip`, `SNAPSHOT.txt` | Rebuilt with `python build_portal_assets.py`. |
