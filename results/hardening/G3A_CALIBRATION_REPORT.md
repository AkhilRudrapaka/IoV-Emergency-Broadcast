# G3a: burst detector calibration (Block G)

Simulation only (SUMO 1.27.1, Python 3.11.4, `network/urban.net.xml`: real topology, synthetic demand).

**Run conditions:**
- Held-out runs 30–59; densities 100/200/300.
- 10 % attackers; gate 0.70.
- `COMMITTEE_CHECK=1`, committee 5/3, `ENFORCE_COMMITTEE=0`.
- VeReMi ML off.

**No default changed:** `TRUST_BURST_K=0`. Nothing is committed. G3b and G4 were not run.

**Sources:** every number is from `analysis/g3a_calibration.py` (output: `analysis/g3a_calibration_output.txt`) or the G3a
section of `BLOCK_G_TABLES.md`. These are built from `results/hardening/G3a_*_runs.csv`, the raw records in
`results/hardening/G3a/`, and the Block F calibration runs in `results/adversarial/C_calibration/`.

## 1. Decision

- **G3a passes under the pre-registered rule, with k = 4.**
  - The rule: the smallest k for which, in every G3a setting and at every density, the mean over runs of the honest
    share flagged is ≤ 1 % (`PREREGISTERED_RULES.json`; plan section 8, "mean per run").
  - At k = 4 the worst mean is 0.72 %, and every upper 95 % CI is below 1 % (largest 0.95 %).
  - k = 3 fails (worst mean 6.80 %).
- **Under a stricter reading, the answer changes.** If "≤ 1 % per run" means *every individual run*, k = 4 fails: 146 of
  450 runs exceed 1 %, maximum 4.44 %. k = 5 also fails (12 runs, maximum 1.11 %). k = 6 would pass (maximum 0.56 %).
  - I applied the rule as written and did not pick another k. **Please confirm the reading before G3b.**
- **Detection at k = 4 is strong only for long off-windows:**
  - phased 0.8/30 s: 100 %;
  - phased 0.9/30 s: 41 %;
  - per-second 0.9: 8 %;
  - phased 0.95/30 s: 5 %;
  - phased 0.9/10 s: 3 %.
- **For per-second attackers, a plain count gate does better** (section 5).

## 2. Completeness and integrity

- **20/20 settings:** k ∈ {3, 4, 5, 6} × 5 attacker types.
  - Every setting has all 90 (density, run) pairs, 1170 `runs.csv` rows, and no missing, extra or duplicate run.
  - 1800 raw records in total.
  - Ran 08:42:53–09:03:10 UTC (`sweep_log.txt`); no failures.
- **Earlier results are unchanged.** A sha256 manifest of all 12,271 Block F, G1 and G2 files, taken before the sweep,
  matches afterwards, with no files added or removed. `results/urban` is clean (`git status`).
- **Code was unchanged during the sweep:** scenario, experiment, adversarial, corroboration, protocols, infrastructure,
  config and clustering, all hashed.
- **Beta trust is preserved in the sweep itself:**
  - for all 450 (attacker type, run) groups, per-vehicle Beta trust and the longest failure run are identical across
    k = 3–6;
  - in all 450, the flag equals (longest run ≥ k), and flags are nested in k;
  - for per-second 0.9 and phased 0.9/30 s, per-vehicle Beta trust equals the no-detector run on the same seed
    (Block F C_calibration, gate 0.70) in 90/90 runs each.

## 3. Implementation and tests

- **The detector existed already** (Block G implementation):
  - `scenario.build` counts consecutive failed watchdog observations per vehicle, with no random draws, and only when
    `TRUST_BURST_K > 0`;
  - `decision_trust` feeds every eligibility decision;
  - the recorded Beta trust is never changed.
- **Spec alignment (one line, [scenario.py](../../scenario.py)):** a flagged vehicle's decision trust is now
  `min(Beta, 0.5)`, the plan's "capped at the uninformed prior". It was 0.
  - Every consumer compares trust with the gate (0.70), so the behaviour is identical.
  - Every flagged vehicle in G3a had Beta ≥ 0.56, so its decision trust was exactly 0.500.
  - The existing test assertion was updated to match.
- **New tests** in `validation/test_hardening.py`. Both run with watchdog misses off and phased duty 0.9, so failure runs
  are exact:
  - `test_isolated_failures_never_form_a_burst`: 1 s off-windows give a longest run of exactly 1 and no flag at k = 2;
  - `test_exactly_k_consecutive_failures_raise_the_flag`: 3 s off-windows give runs of exactly 3; flagged at k = 3,
    never at k = 4.
- **Existing tests also cover:**
  - determinism (same seed, same runs);
  - Beta trust identical with the detector on;
  - flagged vehicles never being CH or on a committee.
- **k = 0 reproduction:** the k = 0 code path is unchanged, and the suite's comparisons against the tracked
  `results/urban` CSVs pass.
- **Portal bundle:** `python build_portal_assets.py` refreshed `portal/downloads/source.zip`, as
  `test_portal_downloads` requires after any source change.
- **Results:**
  - `python -m pytest validation -q`: **158 passed** (159.7 s);
  - `python -m pytest veremi -q`: **26 passed**.

## 4. Honest false alarm (calibration rule)

Share of honest vehicles flagged per run. Each cell: mean ± 95 % CI (n = 30) / maximum run / runs above 1 %.

- **Only two independent samples per density.** The four phased settings share identical honest observation sequences:
  phase comes from its own stream, and no cooperation draw is made. So their honest numbers are identical, and only
  "per-second" and "phased" are independent.

| k | Honest stream | 100 vehicles | 200 vehicles | 300 vehicles |
|---|---|---|---|---|
| 3 | per-second | 5.67 ± 0.73 / 10.00 / 30 | 6.80 ± 0.75 / 11.11 / 30 | 6.31 ± 0.84 / 10.74 / 30 |
| 3 | phased (×4) | 5.70 ± 0.93 / 11.11 / 30 | 6.44 ± 0.73 / 10.56 / 30 | 6.21 ± 0.88 / 9.26 / 30 |
| **4** | per-second | **0.63 ± 0.32** / 3.33 / 13 | **0.67 ± 0.25** / 2.22 / 9 | **0.58 ± 0.16** / 1.11 / 8 |
| **4** | phased (×4) | **0.56 ± 0.34** / 4.44 / 12 | **0.72 ± 0.22** / 1.67 / 12 | **0.62 ± 0.16** / 1.85 / 5 |
| 5 | per-second | 0.15 ± 0.14 / 1.11 / 4 | 0.02 ± 0.04 / 0.56 / 0 | 0.06 ± 0.05 / 0.37 / 0 |
| 5 | phased (×4) | 0.07 ± 0.11 / 1.11 / 2 | 0.11 ± 0.08 / 0.56 / 0 | 0.05 ± 0.05 / 0.37 / 0 |
| 6 | per-second | 0.00 / 0.00 / 0 | 0.02 ± 0.04 / 0.56 / 0 | 0.00 / 0.00 / 0 |
| 6 | phased (×4) | 0.00 / 0.00 / 0 | 0.00 / 0.00 / 0 | 0.02 ± 0.04 / 0.37 / 0 |

- **Worst mean by k:** 6.80 % (k = 3), 0.72 % (k = 4), 0.15 % (k = 5), 0.02 % (k = 6).
- **Chosen: k = 4** (`G3a_calibration_choice.json`).
- **Honest flagged vehicles at k = 4:** 100 (per-second) and 104 (phased) in 90 runs. All had Beta ≥ gate, so all lost
  eligibility: 0.63 ± 0.14 % of honest vehicles per run.

## 5. Attacker detection by type

Share of attackers flagged per run, pooled over densities (n = 90).
- *Newly ineligible:* flagged with Beta ≥ gate.
- *Beta below gate:* without the detector.

| Attacker | Off-window | Beta below gate | k = 3 flagged / newly inelig. | **k = 4** flagged / newly inelig. | k = 5 | k = 6 |
|---|---|---|---|---|---|---|
| per-second 0.9 | — | 2.2 ± 0.9 | 34.0 ± 2.7 / 32.0 | **8.2 ± 1.6 / 7.5** | 1.4 ± 0.6 / 1.2 | 0.4 ± 0.3 / 0.2 |
| phased 0.8/30 s | 6 s | 32.9 ± 2.4 | 100.0 / 67.1 | **100.0 / 67.1** | 100.0 / 67.1 | 99.9 / 67.1 |
| phased 0.9/30 s | 3 s | 0.5 ± 0.4 | 100.0 / 99.5 | **40.7 ± 3.0 / 40.3** | 7.6 ± 1.7 / 7.5 | 1.0 ± 0.6 / 0.9 |
| phased 0.95/30 s | 1.5 s | 0.2 ± 0.2 | 27.2 ± 2.5 / 27.0 | **4.6 ± 1.0 / 4.5** | 0.5 ± 0.4 / 0.5 | 0.0 / 0.0 |
| phased 0.9/10 s | 1 s | 0.5 ± 0.3 | 20.2 ± 2.4 / 19.9 | **2.9 ± 1.2 / 2.7** | 0.3 ± 0.3 / 0.2 | 0.1 ± 0.1 / 0.1 |

**Per density at k = 4** (100 / 200 / 300 vehicles, n = 30 each):

| Attacker | 100 | 200 | 300 |
|---|---|---|---|
| per-second 0.9 | 8.0 ± 4.0 | 8.2 ± 2.3 | 8.3 ± 2.4 |
| phased 0.8/30 s | 100.0 | 100.0 | 99.9 ± 0.2 |
| phased 0.9/30 s | 41.0 ± 6.4 | 39.8 ± 5.2 | 41.3 ± 4.2 |
| phased 0.95/30 s | 5.0 ± 1.9 | 4.3 ± 2.1 | 4.3 ± 1.3 |
| phased 0.9/10 s | 4.0 ± 3.2 | 2.5 ± 1.3 | 2.2 ± 0.9 |

**Comparison with a count-based gate on the same held-out seeds** (C_calibration, no detector). This uses existing data
only; the gate is not changed.

| Attacker | Gate 0.75: honest / attackers below | Gate 0.80: honest / attackers below | k = 4 detector at gate 0.70: honest / attackers ineligible |
|---|---|---|---|
| per-second 0.9 | 0.04 % / 12.3 % | 1.00 % / 44.5 % | 0.63 % / 9.7 % |
| phased 0.9/30 s | 0.05 % / 7.3 % | 1.06 % / 45.1 % | 0.64 % / 40.8 % |

- **Per-second attackers:** the k = 4 detector is **dominated** by gate 0.75, which flags fewer honest vehicles and
  catches more attackers. This matches the plan's argument that counts are sufficient for independent per-second
  behaviour. The detector's 8 % catch here only reflects that attackers fail more often (0.19 against 0.10).
- **Phased 0.9/30 s:** the detector point (0.64 %, 40.8 %) lies between the two gate points. It catches more attackers
  for a given honest rate than the line joining them.
- **Phased 0.8/30 s:** 100 % detection. There is no gate reference on held-out seeds for this attacker.

## 6. Impact at the chosen k = 4

**Beta trust:**
- The recorded Beta trust is unchanged (section 2).
- Decision trust of flagged vehicles is min(Beta, 0.5) = 0.500 for all of them.

| Attacker | Flagged attackers (90 runs): Beta mean [range] | Of these with Beta ≥ gate | Flagged honest: Beta mean [range] |
|---|---|---|---|
| per-second 0.9 | 148: 0.760 [0.57, 0.86] | 136 | 100: 0.842 [0.76, 0.91] |
| phased 0.8/30 s | 1799 of 1800: 0.715 [0.56, 0.85] | 1207 | 104: 0.847 [0.75, 0.92] |
| phased 0.9/30 s | 734: 0.789 [0.65, 0.89] | 727 | 104 |
| phased 0.95/30 s | 80: 0.808 [0.69, 0.87] | 79 | 104 |
| phased 0.9/10 s | 47: 0.762 [0.65, 0.83] | 43 | 104 |

**Cluster-head eligibility:**
- **Method:** the election was recomputed from the raw records (positions, speed, trust) with `clustering.elect_roles`.
  The recomputation reproduces the recorded roles in 180/180 no-detector runs and in 90/90 runs of every G3a setting.
- **Table:** per run, mean ± CI, n = 90.

| Attacker | Attacker CHs: no detector → k = 4 | Honest CHs removed (flagged) | Honest CHs added (replacements) | CHs total (both) |
|---|---|---|---|---|
| per-second 0.9 | 2.07 ± 0.34 → 1.89 ± 0.31 | 0.11 ± 0.07 | 0.29 ± 0.12 | 19.32 ± 1.21 |
| phased 0.8/30 s | 1.44 ± 0.26 → 0.00 | 0.11 ± 0.07 | 1.56 ± 0.26 | 19.32 ± 1.21 |
| phased 0.9/30 s | 2.09 ± 0.33 → 1.24 ± 0.25 | 0.10 ± 0.06 | 0.94 ± 0.21 | 19.32 ± 1.21 |
| phased 0.95/30 s | 2.10 ± 0.34 → 2.08 ± 0.33 | 0.10 ± 0.06 | 0.12 ± 0.07 | 19.32 ± 1.21 |
| phased 0.9/10 s | 2.09 ± 0.33 → 2.04 ± 0.33 | 0.10 ± 0.06 | 0.14 ± 0.07 | 19.32 ± 1.21 |

**Committee eligibility:**
- The committee was full in 1800/1800 G3a runs, never below quorum; 2.99–3.00 genuine votes counted.
- Attackers on the genuine committee, at k = 0 → k = 4:
  - per-second: 0.46 ± 0.13 → 0.44 ± 0.13;
  - phased 0.9/30 s: 0.48 ± 0.13 → 0.31 ± 0.12;
  - phased 0.8/30 s: 0.00 at every k;
  - phased 0.95/30 s and 0.9/10 s: 0.48 ± 0.13 (no k = 0 reference on these seeds).

**Genuine-alert availability:**
- Paired against k = 0 on the same seeds (per-second 0.9 and phased 0.9/30 s):
  - genuine accepted: +0 / −0 of 90 for both;
  - proposed delivery: never lower (0 of 89 both-accepted seeds);
  - CH relayed RSU reception: +1 / −0 of 30 for both.
- **Pooled acceptance:** 98.9 ± 2.2 % (100 / 100 / 96.7 % by density) for all types except 0.8/30 s, which is 100 %.
- **Caveat:** genuine failures are rare at 10 % attackers, so this sample has little power to detect a small
  availability loss.

**Forged alerts (observed during calibration; G3b is the evaluation):**
- Default level, paired against k = 0:
  - per-second: 73.3 % → 56.7 % (−15 / +0 of 90, p = 6.1e-5);
  - phased 0.9/30 s: 76.7 % → 16.7 % (−54 / +0, p = 1.1e-16).
- Without a k = 0 reference on these seeds: 0.8/30 s 0.0 %; 0.95/30 s 72.2 %; 0.9/10 s 74.4 %.
- Committee level: 1 forgery in 90 at k = 0 and at k = 4 (per-second); 0 for 0.9/30 s at k = 4.

## 7. Negative and neutral findings

- **k = 3 is unusable:** 5.7–6.8 % of honest vehicles are flagged.
- **k = 4 passes only on the mean.** Some individual runs flag up to 4.44 % of honest vehicles, and 32 % of runs
  exceed 1 %.
- **Per-second 0.9:** the detector is worse than a slightly higher count gate (section 5). It is not a fix for this
  attacker.
- **Phased 0.95/30 s and 0.9/10 s** (off-windows of 1.5 s and 1 s) are essentially undetected at k = 4 (5 % and 3 %).
  Their forged acceptance stays at 72–74 %.
- **About 0.1 honest CH per run is replaced** at k = 4. The CH count is unchanged.
- **No k = 0 reference on held-out seeds** for 0.8/30 s, 0.95/30 s and 0.9/10 s. Their genuine and forgery effects are
  unpaired here.
- **The calibration population** is effectively two honest samples per density, not five (section 4).

## 8. Reproduce

```
python run.py adversarial G3a                                      # 20 settings, runs 30-59 (finished ones are skipped)
python -X utf8 results/hardening/analysis/g3a_calibration.py       # sections 2 and 4-6
python -X utf8 results/hardening/analysis/blockg_tables.py         # BLOCK_G_TABLES.md, G3a section
python -m pytest validation -q ; python -m pytest veremi -q
```

Each setting's `summaries/experiment_config.json` records:
- its overrides (`EXP_TRUST_BURST_K`, `EXP_ONOFF_*` / `EXP_MALICIOUS_COOPERATION`, `EXP_MALICIOUS_RATIO=0.1`,
  `EXP_COMMITTEE_CHECK=1`);
- the SUMO and Python versions;
- the commit;
- the network hash.
