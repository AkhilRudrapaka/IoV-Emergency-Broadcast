# Final test report (Block G, 2026-11-21)

## Final run (final working tree)

| Suite | Command | Result |
|---|---|---|
| Project validation | `python -m pytest validation -q` | **166 passed**, 0 failed (173 s) |
| VeReMi ML | `python -m pytest veremi -q` | **26 passed** |
| Portal build and check | `python build_portal_assets.py`, then `node check.mjs` in `portal/` | passed (JavaScript syntax, assets, 78 saved comparison rows, SUMO snapshots) |
| Portal served | `python run.py web --port 8791` | `/`, `/app.js`, `/data.js`, `/styles.css`, `/assets/summary.csv`, `/simulation`, `/downloads/RESULTS.md` all HTTP 200 |

**Validation tests by file:**

| File | Tests |
|---|---|
| test_adversarial | 9 |
| test_channel | 5 |
| test_corroboration | 8 |
| test_demo_pairs | 29 |
| test_hardening (committee enforcement and burst detector) | 21 |
| test_incident_response (incident detection) | 11 |
| test_incident_routing | 11 |
| test_infrastructure | 7 |
| test_ml_trust | 9 |
| test_pipeline | 10 |
| test_portal_downloads | 3 |
| test_protocols | 17 |
| test_rsu | 12 |
| test_web_results | 14 |

## Behaviour checks

| Check | Evidence | Result |
|---|---|---|
| Baseline reproduction with enforcement off, burst detector off | `analysis/final_baseline_check_output.txt` (before G4), `final_baseline_check_post_g4_output.txt` (fresh, after G4) | default matrix (180 runs) and on-off set (30 runs): all 5 processed CSVs byte-identical to `results/urban`, both times |
| New default (enforcement on, detector off): genuine alerts not suppressed | same files | `runs.csv`, `summary.csv`, `paired.csv` byte-identical; only forgery CSVs change |
| Forged alerts fail the committee check | same files; `test_every_check_site_rejects_outsider_signers_by_default` | voting-only registered 134/180 → 1/180; on-off full level 25/30 → 0/30; outsider signers rejected at release, RSU batch authentication and incident re-verification |
| k = 0 reproduces Block F | `results/hardening/G3b_k0_check/` | byte-identical (2 settings) |
| Incident chain with the new defaults | `results/hardening/final_checks/incident_demo/d200_r02.json` | see below |

**Incident chain on d200_r02:**
1. Staged stop of v164 at 114 s.
2. Detected from live telemetry at 115 s (speed drop 11.53 > 9.5).
3. Alert released; certificate re-verified (BLS valid, 3 committee endorsers).
4. V2V dissemination reaches 200/200 vehicles.
5. RSU registers the event.
6. 49 vehicles rerouted (3 have no alternative, 1 cannot avoid the edge); every acceptance criterion is true.
7. The forged alert is rejected ("0 committee endorsers") and changes 0 routes.

## Failures found during this stage, and how each was resolved

All of them were reported when they occurred. None was skipped or bypassed.

| Failure | Cause | Resolution |
|---|---|---|
| `test_incident_response::test_the_stop_is_detected...` | It asserted that the live run equals the published d200_r02 record. That record predates enforcement; only its forgery section differs (its voting-only forgery was accepted). | The test now checks that the genuine parts are identical and that the forgery is now rejected. New `test_with_enforcement_off_the_published_record_is_reproduced_exactly` keeps the exact-reproduction check with enforcement off. |
| `test_incident_response::test_only_vehicles_that_accepted...` | The 4-argument accept stub, and a fixture record without `committee`. | The stub takes the committee argument; the fixture carries `committee`. |
| `test_incident_response::test_a_rejected_forged_alert_changes_no_route` | It asserted that the voting-only counterfactual would accept the forgery (the Block F gap). | It now asserts False (the gap is closed). The Block F value stays covered by the tracked-record assertion. |
| 3 tests in `test_adversarial` | Block F characterisation tests (they assert the pre-enforcement behaviour). | `_block_f()` pins `ENFORCE_COMMITTEE=0`; the assertions are unchanged. |
| `test_incident_routing::test_only_a_vehicle_that_accepted_the_alert_is_detoured` | The fixture record had no `committee` key (`KeyError`). | The fixture carries `committee`, as every real record does. |
| `test_portal_downloads` (twice) | Stale generated copies after source or doc edits. | `python build_portal_assets.py`, and a copy of `PROJECT_GUIDE.md` into `documentation_website/portal/downloads/`. |

## Open items (not changed; need approval)

**Proposed `portal/app.js` corrections.** The portal does not yet:
1. state that the VeReMi ML detector is shadow-only, or mention the burst detector;
2. describe forged-alert rejection by committee membership. It says only "endorsers are not reputable".
3. note that the saved `results/urban` snapshot predates enforcement. Its genuine results are unchanged under the new
   default; its voting-only forgery figures are not.
4. describe the live incident detection (kinematic threshold on a staged stop) and the rerouting stage.

It also contradicts itself on sample size: the Limitations page says "only two independent scenarios per density", the
Results page says 30.

**Other:**
- `documentation_website/portal` is a standalone presentation snapshot. Only its required download copy was refreshed.
- `protocols.py:111` has a stale comment ("opt-in level"). It does not affect behaviour.

## Final cleanup run (after the portal corrections and the protocols.py comment fix)

| Check | Result |
|---|---|
| `python -m pytest validation -q` | **166 passed**, 0 failed (170 s) |
| `python -m pytest veremi -q` | **26 passed** |
| `python build_portal_assets.py`, then `node check.mjs` in `portal/` | passed |
| `python run.py web --port 8792` | `/`, `/app.js`, `/data.js`, `/styles.css`, `/assets/summary.csv`, `/simulation`, `/downloads/{RESULTS.md, config.py, PROJECT_GUIDE.md, source.zip}` all HTTP 200. The served `app.js` contains the corrected text, and the served `config.py` has `ENFORCE_COMMITTEE = 1`, `TRUST_BURST_K = 0`. |
| Baseline, `EXP_ENFORCE_COMMITTEE=0 EXP_TRUST_BURST_K=0` (`final_checks/cleanup/`) | default matrix and on-off set: all 5 CSVs byte-identical to `results/urban` |
| New defaults (`final_checks/cleanup/default_on`, `onoff09_on`) | genuine CSVs byte-identical. Forged alerts registered: voting-only 134/180 → 1/180; on-off full level 25/30 → 0/30; on-off voting-only 26/30 → 0/30. |
| End-to-end incident demo (`final_checks/incident_demo_cleanup/`) | see below |

**Incident demo steps:**
1. Staged stop of v164 at 114 s.
2. Kinematic detection at 115 s (11.53 > 9.5).
3. Certificate re-verified (BLS valid, 3 committee endorsers).
4. V2V dissemination reaches 200/200 vehicles.
5. RSU registers the event.
6. 49 vehicles rerouted.
7. The forged alert is accepted by 0 vehicles and changes 0 routes ("only 0 reputable committee endorsers").

Every acceptance criterion is true.

**Open items from the earlier run:**
- Resolved: the portal corrections (`PORTAL_CORRECTIONS.md`) and the `protocols.py` comment.
- Remaining: the downloadable `.docx`, which needs `python-docx`; see `PORTAL_CORRECTIONS.md`.

## Pre-commit run (after the portability fix)

| Check | Result |
|---|---|
| `veremi/test_preprocess.py`, verbose | 13 passed, including the real-dataset test, which ran (not skipped) on the relative path |
| VeReMi | **26 passed** |
| Validation | **166 passed** |
| Baseline, `EXP_ENFORCE_COMMITTEE=0 EXP_TRUST_BURST_K=0` (`final_checks/precommit/`) | byte-identical to `results/urban`; new defaults leave genuine CSVs unchanged |
| Bundle (`portal/downloads/source.zip`) | all 70 entries equal the current files; it contains the relative-path test |
