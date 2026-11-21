# Block D: integration of the ML detector with temporal trust (shadow mode)

**Date:** 18 November 2026.

**Status:** integrated in **shadow mode only**. In this mode the detector scores CAMs and logs a what-if trust; no
existing decision changes. **Enforcement stays disabled, and it should**: in this simulator the detector produces
**16–27 % false flags on honest CAMs** and carries **no information about which vehicles misbehave**. The evidence is
in §6.

- **Tests:** 114/114 project tests (the original 105 unchanged, plus 9 new) and 26/26 ML pipeline tests pass.
- **Not changed:** the Block C model, the VeReMi labels and the processed data. Nothing was committed.

## 1. Integration map (verified in the code)

| Concern | Where | What Block D does there |
|---|---|---|
| Beta trust | `clustering.py:21` `beta_trust(s, f)` | Reused unchanged |
| Behaviour history | `scenario.py` `build`, per-second watchdog loop: each second, every vehicle with a neighbour is observed relaying or not (`ok`/`bad` counts) | **The integration point**: the same loop also builds and scores each observed vehicle's CAM |
| Trust used by every decision | `sc["trust"]` → clustering, committee, certificate acceptance, CH route, RSU (`experiment.py:50,55,59,66,127,138`) | Never written by Block D |
| DBSCAN, cluster heads | `clustering.py:25` `elect_roles` | Called read-only for the what-if log |
| Committee | `corroboration.py:72` `committee` | Called read-only for the what-if log |
| BLS12-381 | `corroboration.py:59` `verify_aggregate`, `:95` `accept` | Untouched, and checked by a test |
| RSU and emergency messages | `rsu.py:43` `validate`, `:67` `register`; `protocols.py` | Untouched |
| Post-event trust update | `infrastructure.py:104` `trust_after_event` (stored in SQLite, never fed back) | Untouched |
| CAMs | **None exist.** `channel.py:14`: "no background (beacon) traffic" | Built from SUMO state, in shadow mode only |

**How a received message affects trust today:** it doesn't. Trust comes from the simulated per-second watchdog
observation, an abstraction of routine relaying. The only messages actually simulated are the one alert and its votes.

**Why no major redesign is needed:** the trust system is a Beta reputation over per-second observations, so ML flags
fit in as one more bounded per-second observation type. The only missing piece is the CAM. It is built from the SUMO
positions, speeds and headings that the watchdog loop already reads.

## 2. Trust flow before and after

```
BEFORE (and AFTER with ML_TRUST_MODE="off", the default: identical code path)
  SUMO FCD, each second -> watchdog draw per observed vehicle -> ok/bad counts -> beta_trust -> sc["trust"]
        -> CH election, committee, certificate acceptance (BLS first, then reputation), forwarding, CH route, RSU

AFTER, ML_TRUST_MODE="shadow"
  SUMO FCD, each second -> watchdog draw (unchanged) -> ok/bad -> beta_trust -> sc["trust"] -> every decision, unchanged
                        \-> CamObserver: one CAM per observed vehicle (SUMO state, as heard by its nearest neighbour)
                              -> veremi.features.ReceiverStreams -> 24 features -> Detector (frozen Block C model)
                              -> per-vehicle ML evidence {cams, scored, flagged, invalid, errors, max_score}
                              -> what-if trust (s+1)/(s+f+2+w*min(flags, cap)) -> sc["ml_shadow"]  (never read by a decision)
  experiment.run_one, after every decision -> ml_trust.shadow_record -> raw["ml_shadow"]:
        what-if trusted status, cluster heads and genuine-alert committee, and whether its quorum would hold
```

## 3. Changes

| File | Change | Why |
|---|---|---|
| `ml_trust.py` (new, 192 lines) | Detector adapter, CAM observer, bounded what-if trust, shadow log | The whole integration in one module |
| `config.py` (+7 lines) | `ML_TRUST_MODE="off"`, `ML_MODEL_DIR`, `ML_EVIDENCE_WEIGHT=0.25`, `ML_EVIDENCE_CAP=40`, `ML_CAM_DELAY_MS=1.44` | Every outcome-relevant parameter lives in `config.py`. Overridable with `EXP_<NAME>` |
| `scenario.py` (+11 / −2) | Imports `ML_TRUST_MODE`; creates the observer when the mode isn't off; one `observer.observe(...)` call in the watchdog loop; `return {...}` became `sc = {...}` plus `sc["ml_shadow"]` | The narrowest point where per-second vehicle states exist. The call draws no random numbers, so seeded runs are unchanged |
| `experiment.py` (+3) | `raw["ml_shadow"] = ml_trust.shadow_record(...)` only if `sc` has `ml_shadow`, placed after all decisions | Records what would have changed |
| `build_portal_assets.py` (+1) | Bundles `veremi/*.py` | The published `source.zip` must contain what `ml_trust.py` imports |
| `portal/downloads/{source.zip, config.py, SNAPSHOT.txt}` | Regenerated with `python build_portal_assets.py` | Required by the existing bundle test after any source change |
| `validation/test_ml_trust.py` (new) | 9 tests (§7) | |

Unchanged: `clustering.py`, `corroboration.py`, `protocols.py`, `channel.py`, `rsu.py`, `infrastructure.py`, `demo.py`,
every existing test, and everything in `veremi/`.

## 4. The ML adapter (`ml_trust.Detector`)

- **Loading:**
  1. Reads `selection.json` next to the model.
  2. Requires it to be frozen.
  3. Requires its feature list to equal the approved 24-feature schema (`veremi/features.py`, the same order as training).
  4. Checks the artifact's MD5 against the frozen selection **before** unpickling it.

  It never fits or writes anything; a test confirms the artifact's MD5 is unchanged after loading. Any failure leaves the detector `unavailable` with a reason.
- **`score(X)`:** `X` is an (n, 24) array in schema order. It returns per-row `score` (the model's probability), `flag` (score ≥ the frozen Block C threshold 0.9439), `status` and `model_version` (`hist_gradient_boosting:c16d73f8db22`). The possible statuses are:
  - `ok`
  - `invalid_features`: wrong width, ±inf, or NaN in one of the 9 never-missing features
  - `model_unavailable`
  - `inference_error`

  **Any failure yields `flag=False`. A failure is never treated as malicious.**
- **Model location:** `config.ML_MODEL_DIR` points at `…/processed/v2/models/block_c` outside the repo. Without it, shadow mode still runs and logs `model_unavailable`.

## 5. How ML evidence enters trust

- **What a CAM is here:** each second, every vehicle the watchdog observes (it has at least one neighbour) broadcasts one CAM built from its SUMO state.
  - Position, speed and heading come from SUMO.
  - Acceleration is the 1-second speed change, which is how SUMO itself defines it at 1-second steps; it is 0 in a vehicle's first second.
  - The receive delay is 1.44 ms, the median genuine delay in the VeReMi Train data.
- **One reception per transmission:** the CAM is scored **once**, as received by the sender's nearest neighbour, so repeated receptions never count as independent evidence (test `test_each_transmitted_cam_is_one_observation…`). History features use the sender's previous CAMs.
- **What-if trust:** `(s+1)/(s+f+2+w·min(flags, cap))`, where `s` and `f` are the existing watchdog counts.
  - **Without flags it equals `beta_trust(s, f)` exactly.**
  - A flag counts as `w = 0.25` of a watchdog failure, and at most `cap = 40` flags count, i.e. at most 10 equivalent failures.
  - One flag moves a typical honest vehicle (s = 66, f = 8) by less than 0.003.
  - Even unlimited flags cannot push that vehicle below the 0.7 gate (both are tested).
  - The effect builds over repeated observations.
- **Clean CAMs add nothing**, which makes the coupling penalty-only. The detector judges CAM *content*. A plausible CAM says nothing about relaying, so it must not raise the trust of a vehicle that drops relays.
- **Cryptography is independent.** `accept()` checks the BLS aggregate before reputation; ML never reaches it. A forged certificate is rejected under watchdog and what-if trust alike, and no protocol, corroboration, RSU, channel, clustering or infrastructure module references `ml_trust` (tested).
- **Emergency messages:** in shadow mode nothing changes, so no alert can be suppressed (tested on a full run). The shadow log also records whether the genuine alert's committee would still reach quorum under the what-if trust: it did in all 40 shadow runs.
- **Scope:** the detector says nothing about relay dropping or forged accident alerts, and is not used for them.
- **Modes:**
  - `off`: the default; nothing runs.
  - `shadow`.
  - `enforce`: **reserved and refused** with an explanation, for the reasons in §6.

## 6. Shadow-mode results

Commands: `EXP_ML_TRUST_MODE=shadow EXP_RESULTS_DIR=<scratch> python run.py experiment --densities 50 200 500 --runs 10 --no-report`,
and the same with `EXP_MALICIOUS_COOPERATION=0.9 --densities 200`. Seeds 0–9 per density. Every run reported model
status `ready` and `decisions_changed: false`.

| Setting (10 runs each) | CAMs scored | Flagged | Flag rate | Mean what-if trust drop (honest / misbehaving) | Would lose trusted status (honest / misbehaving) | CH changes | Committee changes | Quorum would fail |
|---|---|---|---|---|---|---|---|---|
| default, 50 vehicles | 36,753 | 5,807 | 15.8 % | 0.032 / 0.000 | 0 / 0 | 0 | 0 | 0 |
| default, 200 vehicles | 155,664 | 28,692 | 18.4 % | 0.035 / 0.001 | 1 / 0 | 0 | 0 | 0 |
| default, 500 vehicles | 363,183 | 96,549 | 26.6 % | 0.048 / 0.001 | 11 / 0 | 0 | 0 | 0 |
| on-off 0.9, 200 vehicles | 155,664 | 28,692 | 18.4 % | 0.035 / 0.029 | 2 / 13 | 6 | 1 | 0 |

**Every flag is a false positive.** No vehicle in this simulator falsifies CAM content, and the CAMs are built from true
SUMO states.

**Why so many?** A diagnostic of run d200_r00 (14,508 CAMs, 18.0 % flagged) found:
- **Stationary vehicles:** CAMs from vehicles at speed < 1 m/s, queued at signals, are 21.7 % of CAMs and **74 %** of them are flagged.
- **First CAMs:** a vehicle's first CAM is flagged 89 % of the time.
- **Not turns:** turning CAMs (heading change > 20° in 1 s) are flagged only 0.5 % of the time.
- **Flagged profile:** speed 0, residuals 0, nearest neighbour 6.4 m away.
- **Likely cause:** the model was trained on a low-density highway, where a vehicle reporting speed 0 looks like zeroSpeedReport or suddenStop. The noise-free SUMO positions (residuals exactly 0) are also outside the noisy VeReMi data. The rate grows with density because more vehicles queue.

**The on-off row is not detection.** The flag count is **identical** to the default row (28,692). Misbehaviour changes
only the watchdog draws, never CAM content, so the ML evidence carries no information about who misbehaves. On-off
attackers lose trusted status more often only because their trust (about 0.80) sits just above the 0.7 gate, so any
uniform penalty reaches them first. This must not be reported as ML detecting on-off attackers.

## 7. Tests (`validation/test_ml_trust.py`, 9 tests)

| Requirement | Test |
|---|---|
| Model loading; missing or tampered artifact; feature-list mismatch | `test_missing_or_tampered_artifacts…`, `test_the_exact_block_c_artifact_loads_read_only` |
| Feature ordering, width, type and missing values | `test_feature_width_type_and_missing_values_are_validated` |
| Inference success and failure (never malicious) | `test_inference_errors_are_reported…`, the artifact test |
| ML score into temporal trust; repeated suspicious observations; boundedness | `test_ml_flags_lower_the_what_if_trust_gradually_and_boundedly` |
| Duplicate receptions | `test_each_transmitted_cam_is_one_observation…` |
| Valid and invalid signatures | `test_signature_checks_never_consult_ml` |
| Genuine emergency alert not suppressed; shadow mode preserves every decision; off mode writes nothing new | `test_shadow_mode_changes_no_decision_and_off_mode_writes_nothing_new`: a full SUMO run, off vs shadow, comparing every scheme's metrics, the forgery test, the scenario, all protocol records, the route and the genuine alert's acceptance |
| Enforcement refused; unknown modes rejected; default is off | `test_enforcement_is_refused_and_unknown_modes_are_rejected` |
| Existing trust unchanged when disabled | The original 105 tests, including the record reproductions in `test_pipeline`, run in the default off mode and pass |

Commands:
- `python -m pytest validation -q`: 114 passed.
- `python -m pytest veremi -q`: 26 passed.

## 8. Limitations and unresolved integration points

1. **The simulator has no CAMs.** Shadow mode builds them from noise-free SUMO states, so there are no GNSS errors and no CAM attackers. The ML evidence can only measure false positives here.
2. **Domain gap:** 16–27 % false flags, against 1.6 % on VeReMi Test. The detector does not transfer from a low-density VeReMi highway to this urban, signalised grid. Fixing that would need training data from urban traffic (VeReMi urban subsets) and realistic sensor noise. Not done.
3. **Enforcement would be meaningful only with CAM-falsifying attackers in the simulator** and a recalibrated detector. Until then it is refused. Even with the bound, enforcement at 500 vehicles would have removed 11 honest vehicles from trusted roles in 10 runs.
4. **Approximations:**
   - History features use the sender's full CAM sequence, as if a receiver heard every CAM.
   - Receiver-relative features use the nearest neighbour as the single receiver.
   - Acceleration is the 1-second speed difference.
   - The receive delay is a constant.
5. **Not integrated:**
   - `trust_after_event` (post-event bookkeeping) ignores ML.
   - The SUMO-GUI demo and the web dashboard do not display the shadow log.
   - `run.py` has no dedicated flag; use `EXP_ML_TRUST_MODE=shadow`.
6. **Data scope:** VeReMi NextGen data is simulated, and the model was trained on one low-density highway scenario. Nothing here is real-world validation.
