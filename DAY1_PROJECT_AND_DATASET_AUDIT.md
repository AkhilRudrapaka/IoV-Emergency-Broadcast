# Day 1: Project and Dataset Audit

**Date:** 18 November 2026. **Repository:** branch `akhil` at `107f1b4` (baseline tag `v0.9-baseline` = `33304f6`, pushed).
**Scope:** This audit reuses the verified results of the 17 November code audit (four review dimensions, each finding
checked by an independent skeptic, plus two empirical analyses). It re-investigates only unresolved items and
dataset integration. No source code was changed.

**Evidence labels used below:**
- **Verified:** checked by running code or commands.
- **Code-read:** taken from reading the source; not executed.
- **Unverified:** a claim nobody has independently confirmed.

---

## 1. Existing project architecture

```
SUMO 1.27.1 (subprocess, 1-s FCD, seeded)          scenario.py:68 run_sumo, :75 read_fcd
  -> one scenario snapshot at the incident second   scenario.py:106 build (watchdog Beta trust, one incident)
  -> 13 forwarding schemes on the SAME snapshot      experiment.py:106 run_one (paired by construction)
       DBSCAN + trusted cluster heads                clustering.py:25 elect_roles
       committee vote + BLS12-381 certificate        corroboration.py:72-108 (py_ecc)
       802.11p channel model + forwarding rules      channel.py:110 simulate; protocols.py:166-303
       RSU validation, registration, SQLite outbox   rsu.py:43, :67; infrastructure.py:18, :84
  -> metrics, CSVs, figures, reports                 metrics.py:63; experiment.py:285; figures.py; report.py
```

The radio and the trust decisions are evaluated on one traffic snapshot at the incident second. Experiments have no live
TraCI loop: TraCI is used only by the SUMO-GUI replay (`demo.py`) and one test. Entry point: `python run.py <command>`
(`run.py:250`).

## 2. Existing working and missing modules

| Area | File(s) | What exists | Status | Reusable | Minimum change for the ML/dataset work |
|---|---|---|---|---|---|
| Entry point | `run.py:250` | Subcommands: experiment, single, explain, sensitivity, demo, pair, web, dashboard | **Working.** Verified: the on-off sweep reproduced bit-exactly, 25/30 | Yes | None |
| Environment | `requirements.txt`, `pytest.ini` | Python 3.11.4; SUMO/TraCI/sumolib 1.27.1; numpy 2.2.6; scipy 1.17.1; scikit-learn 1.7.2; matplotlib 3.10.9; py_ecc 8.0.0 | **Working.** Verified: `pip check` is clean | Yes | None; no new dependency needed |
| SUMO integration | `scenario.py:68-87` | Offline SUMO run with FCD output at 1 s | **Working** (Verified) | Yes | Would also be the CAM source if CAMs are generated (§7) |
| TraCI | `demo.py`, `validation/test_pipeline.py` | GUI replay of a recorded run | **Working, replay only** (test passes) | Not needed for ML | None |
| Vehicle / scenario data | `scenario.py:149-157` | Dict: ids, xy, speed, angle, lane, malicious, trust, alert, history | **Working**, but stores a snapshot only; history exists only for the demo (`history_s`) | Yes | Keep per-vehicle per-second watchdog outcomes and kinematics |
| Message data | `scenario.py:90-103` (alert), `experiment.py:182-242` (record) | DENM-like accident alert; per-run JSON record | **Working** | Yes | None. The project does not generate CAMs, which VeReMi is made of |
| Beta reputation | `clustering.py:21-22`, `scenario.py:121-143` | trust = (s+1)/(s+f+2) over per-second watchdog draws | **Working as designed.** One global value per vehicle, with no per-observer view. The "on-off" attacker is an i.i.d. per-second grey-hole, not a phased attacker (TS-1 substance confirmed by ML-1 and the methods review) | Yes, unchanged | Log `n_obs`, `n_fail` per vehicle |
| Malicious detection | Gate `trust >= 0.7` at `clustering.py:33`, `corroboration.py:75`, `:104`, `protocols.py:181`, `infrastructure.py:25`, `:58` | Threshold only; no ML | **Partial.** Stops persistent black holes (AUC 1.00) but not on-off attackers at 0.7: 25/30 forged events registered at 200 vehicles (Verified) | Yes | One integration point: the per-run trust/eligibility array built in `scenario.build` |
| DBSCAN + CH election | `clustering.py:25-55` | DBSCAN (eps 40 m, MinPts 3), greedy trusted set cover | **Working** (tests) | Yes | None |
| Committee + BLS | `corroboration.py:72-108` | 5 nearest reputable neighbours, quorum 3, BLS FastAggregateVerify | **Working for the rule as written.** Gaps: `accept()` does not check that signers are the committee; all 25 registered forgeries used non-committee endorsers (TS-4). Colluders are chosen without regard to trust (TS-2, confirmed) | Yes | A design decision, not ML work |
| Emergency broadcasting | `protocols.py:237` Flooding, `:250` Slotted1P, `:269` Proposed, `:166` CHRoute; `channel.py:50-132` | 5 broadcast schemes + CH-to-CH route, 802.11p unit-disk model | **Working** by tests and bit-exact reproduction. **Not re-audited:** this review dimension did not run (usage limit) | Yes | None |
| RSU / backhaul | `rsu.py`, `infrastructure.py` | Validation, registration, SQLite outbox, optional dispatch | **Working** (tests) | Yes | None |
| ML / data processing | none for ML; `metrics.py`, `experiment.py:263-316`, `figures.py`, `report.py` | scikit-learn is used only for DBSCAN. Aggregation, CIs and paired differences exist | **ML missing** | `metrics.summarize` can be reused for CIs | New files only: dataset loader, features, training/evaluation |
| Tests | `validation/` (105 tests) | Pipeline, protocols, corroboration, RSU, web | **105/105 pass in the author's tree** (Verified 17 Nov, 101 s). **3 fail in a fresh clone** (RC-2, confirmed) | Yes | Fix RC-2 before teammates clone |

Results-presentation defects (confirmed) to fix before paper tables:
- **MS-2:** Student-t CIs are applied to 0/1 outcomes, so 0/30 prints as "0.0 ± 0.0".
- **MS-3:** `t_last_ms` is 0 instead of NaN when the alert never leaves the source.

All quoted numbers recompute exactly from the CSVs (MS-5).

## 3. VeReMi NextGen dataset feasibility

**Sources checked on 18 November:**
- the website <https://veremi-dataset.github.io/veremi-nextgen>
- the Zenodo record API (DOI 10.5281/zenodo.19665762)
- the record's README
- the GitHub repository landing page
- one small sample, read with HTTP range requests: 8.1 MB of one 20.9 MB archive, plus the first 1.5 KB of two ground-truth files

Nothing else was downloaded.

**What it is: simulated data, not real-world recordings.** The website describes "simulated V2X message logs with
ground-truth labels":
- **Tools:** MOSAIC, SUMO and OMNeT++. The versions are inconsistent: the website says MOSAIC 25.0 and SUMO 1.22.0, the GitHub badges say MOSAIC 25.2 and SUMO 1.25.0.
- **Traffic:** the InTAS scenario of Ingolstadt. The road network is a real city's, but every vehicle and message is simulated.
- **Authors:** Hermann, Remmers, Eisermann, Erb and Kargl (Ulm University).
- **Licences:** dataset CC-BY 4.0; generator code Apache-2.0.
- **Publication:** on Zenodo on 2026-06-08. The website's citation names IEEE VNC 2026, but the page says both "accepted" and "submitted". Cite the Zenodo DOI and confirm the paper's status before citing the paper.

It is a public, versioned research benchmark of simulated data. It is not recorded vehicle trajectories, and the paper
must say exactly that.

**File structure (Verified):**
- 78 files, **36.19 GB** in total.
- 4 scenarios: `InTAS_urban_2` (2 AM, low density), `urban_7` (7 AM, high density), `highway_2`, `highway_7`.
- Each scenario has one baseline zip (no attack), 15 attack zips, and 3 ground-truth JSON files (Train, Validation, Test).
- Each attack zip contains `Train/`, `Validation/` and `Test/`, each holding an inner zip. The inner zip has one file per receiving vehicle (`veh_<n>.json`), and each file is an array of the CAMs that vehicle received.
- Archive size per attack: `highway_2` ≈ 20 MB; `urban_2` ≈ 158 MB; `highway_7` ≈ 0.9 GB; `urban_7` ≈ 1.0–2.0 GB.

**Message format (Verified on the sample):**
- **Top-level fields:** `rcvTime`, `sendTime` (integer nanoseconds), `sender_id`, `sender_alias` (pseudonym), `messageID`, `attacker` (0/1).
- **`receiver{...}`:** `pos`, `pos_noise`, `spd`, `spd_noise`, `acl`, `acl_noise`, `hed`, `hed_noise`, `driversProfile`.
- **`sender{...}`:** the same fields plus `distance_to_road_edge`.

Deviations from the README:
- `pos` and `pos_noise` are strings `"x,y,z"`, not arrays.
- Profile values are upper case (`NORMAL`, `CAUTIOUS`, `AGGRESSIVE`).
- Coordinates are projected metres (about 216 km, 452 km).

**Labels:**
- **Per message:** `attacker`. The website defines 1 as "a significant deviation in at least one attribute"; the threshold is not stated.
- **Per vehicle:** in the one-attack sample, labels never changed within a sender. *Corrected 18 Nov after the full
  download (`DATASET_ACQUISITION_REPORT.md`):* for 7 of 15 attacks some attacker senders carry both labels, because
  labels mark significant deviations rather than attacker identity. `any(attacker)` therefore finds only the attackers
  with at least one significant deviation.
- **Ground-truth files:** separate JSON files per scenario and split. They have no `attacker` field and store every value as a string. Their schema differs between splits (Validation nests `receiver`/`sender`; Test is flat) and so do their names (`_groundTruth` vs `_ground_truth`). They look like the unmodified message values keyed by `messageID`; the documentation does not say so. *Verified
  18 Nov:* each holds exactly one record per sent message and matches the baseline's distinct (`sender_id`,
  `messageID`) pairs 100 % in every split.

**Attack types (15):**
- **Position:** `constantPositionOffset`, `randomPositionOffset`, `positionMirroring`
- **Speed:** `constantSpeedOffset`, `randomSpeedOffset`, `zeroSpeedReport`, `suddenConstantSpeed`
- **Heading:** `reversedHeading`
- **Acceleration:** `feignedBraking`, `accelerationMultiplication`
- **Timing:** `timeDelayAttack`
- **Multi-parameter:** `dosAttack`, `trafficCongestionSybil`, `suddenStop`, `dataReplay`

The website gives the attacker density as 20 %; the sample has 19.9 % of senders as attackers.

**Splits:**
- Fixed Train, Validation and Test sets per attack.
- Train and Validation come from a different simulated area than Test, so the test set is spatially disjoint.
- The README gives the ratio as 50/10/40, with Train/Validation split by time.
- Durations: 9000/1800/7200 s for the `_2` scenarios and 375/75/300 s for the `_7` scenarios.

**Sample measurement** (highway_2, constantPositionOffset, Train split):
- 482 receiver files and 37,701 received CAMs; 20.8 % of messages labelled as attack.
- 96 of 482 senders are attackers.
- Senders transmit once per second (median gap 10⁹ ns).
- Parsing the whole split file by file took 1.3 s, with a peak of 3 MB of Python memory.

**How it fits this project (the key finding):**
- **Different attack layer.** VeReMi attacks falsify CAM *content*. This project's attackers misbehave in *relaying* (black/grey hole) and *forge a DENM alert* with colluding endorsements, and the project generates no CAMs at all. VeReMi therefore does not plug into the current pipeline unchanged.
- **Partial overlap:**
  - `suddenStop` and `feignedBraking` are fake hazards, close to a forged accident alert.
  - `trafficCongestionSybil` is phantom vehicles, close to colluding endorsers.
  - `dataReplay` matches the RSU's replay check.
  - `dosAttack` is message flooding.
- **Why ML belongs here and not on the simulator's own data.** The 17 November analysis (methods review passed) showed that ML gains nothing on the simulator's watchdog data. Kinematic features carry no signal there (AUC 0.49–0.50, label-independent by construction). Test-split results:

  | Attacker model | Beta trust | Likelihood ratio / LogReg | HistGradientBoosting | IsolationForest | Oracle HMM |
  |---|---|---|---|---|---|
  | i.i.d. on-off (repo) | 0.941 | 0.944 | 0.923 | 0.733 | — |
  | Bursty (two-state Markov) | 0.833 | 0.835 | 0.782 | 0.706 | 0.873 |

  VeReMi supplies what the simulator lacks: attacks whose signal lies in message content, which is where a learned detector has something to learn.

## 4. Recommended dataset subset

**Initial (Day 2):** `InTAS_highway_2` with 6 attacks:
- `constantPositionOffset`, `randomPositionOffset`, `suddenStop`, `feignedBraking`, `dataReplay`, `trafficCongestionSybil`
- plus `InTAS_highway_2.zip` (baseline) and its 3 ground-truth files

That is about **175 MB compressed**, and an estimated 0.6–0.8 GB as JSON if fully extracted. The estimate is extrapolated from the sample's 4.7× ratio; inner zips can also be read without extracting them.

**Why these:**
- They are the smallest files.
- They cover the classic position falsification.
- They include the fake hazards closest to a forged emergency alert.
- They include the replay and Sybil attacks closest to colluding endorsers.

**Second step (if time allows):** `InTAS_urban_2` for 2–3 of the same attacks, at about 158 MB each, to give urban results matching the project's urban setting.

**Out of scope for the sprint:** the `_7` scenarios, at 0.9–2 GB per attack. Keep all data in `data/veremi_nextgen/`, which must be gitignored, record the Zenodo checksums, and never commit raw data.

## 5. Recommended lightweight ML models

No model has been trained yet. Installed: scikit-learn 1.7.2. Not installed: xgboost.

| Model | Detection potential (tabular plausibility features) | Inference / memory | Complexity | Role |
|---|---|---|---|---|
| Decision Tree | Moderate; unstable | Microseconds per sample; KB | Lowest | Interpretable baseline; rules can be read off |
| **Random Forest** | High, robust, needs no feature scaling | Fast; grows with trees (cap at 100–200 trees and limit depth) | Low | **Primary model** |
| XGBoost | High | Fast | Needs a **new dependency** | Use scikit-learn's `HistGradientBoostingClassifier` instead: same family, native NaN handling, already installed. Add xgboost only if HGB measurably falls short |
| Small MLP | Possibly similar | Fast at inference; needs scaling | More tuning, less interpretable | **Not justified now.** `MLPClassifier` is available without a new dependency if the trees plateau |

**Mandatory non-ML baselines**, so the comparison is honest:
- On VeReMi: simple plausibility rules (speed and acceleration bounds, position jump vs speed·Δt, heading vs direction of travel, message rate).
- On the simulator: a Beta gate calibrated on held-out seeds (runs ≥ 30) and the likelihood ratio.

**Metrics:**
- per-attack precision, recall, F1, FPR and PR-AUC on the official Test split
- per-vehicle detection and time to detection
- inference time per message, measured on this laptop

## 6. Proposed feature list

**Group A: VeReMi content plausibility**, computed per (receiver, sender) message stream from fields a receiver actually has:
1. Position jump between consecutive CAMs of a sender vs reported speed × Δt.
2. Speed change / Δt vs reported acceleration.
3. Heading vs direction of displacement (angular difference).
4. Reported speed, acceleration and heading change rate (bounds).
5. Sender–receiver distance (range plausibility).
6. `rcvTime − sendTime` delay and inter-message interval (`timeDelayAttack`, `dosAttack`).
7. Message rate per sender per window (DoS); repeated content (`dataReplay`).
8. `distance_to_road_edge` (on-road plausibility).
9. Reported confidences: `pos_noise`, `spd_noise`, `hed_noise`.
10. Windowed versions over the last 5–10 CAMs of a sender: mean, max and std of 1–9, plus a count of rule violations.

**Excluded from Group A:**
- `sender_id`, `messageID` and absolute times. They are identities and timestamps that leak labels or do not generalise. Group by `sender_alias`, which is what a receiver sees; use `sender_id` only for labels.
- `driversProfile`, to avoid a possible shortcut. Whether it correlates with attacker assignment is **Unverified**.

**Group B: simulator watchdog**, pre-incident only:
- `n_obs`, `n_fail`, Beta trust, windowed failures, likelihood ratio.
- SUMO kinematics are kept only as a negative control (no signal by construction).
- Anything recorded at or after the incident leaks the label (TS-3).

**Group C: neighbour trust discrepancy.** Not available. The model keeps one global reputation and no per-observer observations, so there is nothing to compare. Adding it needs a per-observer watchdog model, which is not proposed for this sprint.

## 7. Proposed integration architecture

**Path to the pipeline.**
- **Offline:** a VeReMi-trained detector can be evaluated on VeReMi alone.
- **Inside the simulator:** this needs CAMs, generated every 1 s per vehicle from the SUMO FCD the code already reads. Position, speed and angle come directly from FCD, and acceleration from the change in speed. Attack injection applies to attacker vehicles (2–3 VeReMi attack types) and GNSS-like noise to everyone.

**Input:** Group A windowed features per sender at the incident second.

**Output:** a per-message probability, aggregated per vehicle over the last W messages. Proposed record entry, stored next to Beta trust:

```json
{"vehicle": "v123", "t_s": 114, "n_msgs": 10, "p_misbehaving": 0.87, "flag": true,
 "threshold": 0.62, "model": "rf-v1-<config-hash>"}
```

**Influence on trust, with the formula unchanged:** ML is a second gate on the same role decisions:
`eligible_v = (beta_v >= tau_beta) and not flag_v`.
- Implement it in one place, where `scenario.build` produces the trust array, so all six gate sites stay consistent.
- Feeding ML flags into Beta as extra negative observations would change the formula, so it is deferred.

**Protecting genuine emergency messages from false rejection:**
1. ML never drops a received alert. It only removes vehicles from cluster-head, committee and endorser eligibility.
2. The threshold is set on Validation data for a target honest-vehicle FPR (for example ≤ 2 %) and is never tuned on test seeds.
3. Every detector setting reports genuine-alert certification (x/30), reach and t90 per density, especially at 50 vehicles. In the 17 November exploratory sweep, a 0.88 Beta gate already lost 2/30 genuine alerts at 50 vehicles.
4. **Fail-safe (team decision):** if exclusions leave fewer than `QUORUM` eligible neighbours, fall back to the Beta-only gate for that alert and log it. This relates to the quorum-timeout fallback that `docs/SYSTEM_DESIGN.md` specifies but the code does not implement.
5. The incident source is not trust-gated (`accept()` never checks the source; TS-4). Keep that for availability, and state the forging risk.

## 8. Dependencies and environment issues

- **No new dependency needed:**
  - Standard library: `json`, `zipfile`, `urllib`.
  - Installed: numpy, scipy, scikit-learn 1.7.2.
  - Not installed and not required: xgboost, pandas.
- **Zenodo supports HTTP range requests** (Verified: HTTP 206). Single members of an archive can be read without downloading it whole.
- **Disk:** the initial subset is about 175 MB compressed; the full dataset is 36 GB, so never fetch it.
- **OSM map download is blocked from this machine.** All four Overpass downloads on 17 November timed out after 180 s each. Options:
  - a manual export from openstreetmap.org
  - the real OSM-derived Berlin network that ships offline with SUMO: `tools/game/DRT/osm.net.xml`, 5.4 MB, found by the portability review
- **Known OSM blockers in code:**
  - RSU junction IDs are hard-coded (OSM-1/RC-5, confirmed).
  - The road graph includes walkingarea/crossing edges, and random-walk routes stop at dead ends (OSM-2/OSM-3). Both claims are confirmed by reading `scenario.py:31-57`; their runtime effect is **Unverified**.
- **No LaTeX toolchain locally.** IEEEtran sources must be compiled elsewhere.

## 9. Exact Day 2 implementation tasks

All new code goes in new files. Existing source stays untouched until the team approves integration. Run the tests after each step.

1. **Fetch** (`veremi/fetch.py`): download the §4 subset into `data/veremi_nextgen/` (add it to `.gitignore`), verify the Zenodo checksums, and write a manifest (file, size, checksum, date). *Done when:* all checksums match.
2. **Load** (`veremi/load.py`): stream the inner zips; parse the `"x,y,z"` strings; handle both ground-truth schemas; produce per-message and per-vehicle labels. *Done when:* highway_2/constantPositionOffset/Train reproduces 37,701 CAMs, 20.8 % attack and 96 attackers.
3. **Features** (`veremi/features.py`): Group A per message and windowed, keyed by alias; no IDs or times as features. *Done when:* the Train/Validation/Test feature tables for the 6 attacks are saved as `.npz` with a feature list, and one synthetic-stream check passes.
4. **Rule baselines:** plausibility thresholds; per-attack P/R/F1 on Validation.
5. **Models**, if time allows: Decision Tree, Random Forest and HistGradientBoosting with fixed seeds. Select on Validation, test once, and log hyper-parameters and timings.
6. **Design note** (no code) for CAM generation in the simulator: FCD → CAM, attack injection, noise model. The team decides go/no-go.
7. **Fix-before-results items from the code audit**, each small:
   - RC-2: fresh-clone test failures
   - MS-2: exact binomial CIs for counts such as 25/30
   - MS-3: `t_last_ms` should be NaN when the alert never leaves the source
   - TS-2: add a trust-aware coalition forgery variant next to the current one

## 10. Risks and blockers

| Risk | Impact | Mitigation |
|---|---|---|
| VeReMi NextGen is simulated, not real-world data | An overclaim would be caught in review | Use the wording in §3 everywhere |
| Attack-layer mismatch (CAM content vs relaying and forged DENM) | VeReMi results do not by themselves fix the 25/30 | Report the VeReMi evaluation separately; integrate only through simulator CAM generation (§7) |
| Domain gap: MOSAIC/OMNeT++, GNSS noise, InTAS vs our noise-free SUMO FCD | A model trained on VeReMi may not transfer | Add a noise model; report in-domain and transfer results separately |
| Undocumented label threshold; schema and naming inconsistencies; tool-version discrepancy | Silent parsing or labelling errors | Loader checks against the sample numbers in §3; report per attack |
| Paper status ambiguous (VNC 2026 "accepted" vs "submitted") | Citation error | Cite the Zenodo DOI; verify before citing the paper |
| ML cannot beat Beta/likelihood ratio on watchdog data (Verified) | A claim that ML fixes on-off detection would be false | State it as a measured negative result |
| A calibrated gate (0.84–0.86) gives 0/30 forgeries only against the current weak coalition, and only in-sample | Overstated security result | Re-test on held-out seeds and against a trust-aware coalition (TS-2): 26/30 at 0.7, needs about 0.86 |
| Committee membership not checked at verification (TS-4) | A design gap no detector fixes | Team decision: add a committee-bound certificate check |
| Not reviewed: radio-forwarding dimension; skeptic checks of TS-1, OSM-2, OSM-3 and the OSM analysis (usage limit) | Unknown defects may remain | Review before final results |
| 3 of 105 tests fail in a fresh clone (RC-2) | Teammates cannot reproduce | Day 2 task 7 |
| OSM downloads time out | Map work blocked | Manual export, or the offline Berlin network |
| Full dataset is 36 GB | Disk and time | Stay on the §4 subset |
