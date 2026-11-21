# G3b: burst detector evaluation (k = 4)

Simulation only (SUMO 1.27.1, Python 3.11.4, `network/urban.net.xml`: hand-built synthetic 5×5 grid with synthetic traffic demand). No default was
changed (`TRUST_BURST_K=0`, gate 0.70, committee 5/3, `ENFORCE_COMMITTEE=0`). Committed in `81d416e` (published on `origin/akhil`), except the per-run CSVs and raw records. G4 was not run.

**Why k = 4:** the G3a pre-registered rule caps the *mean* share of honest vehicles flagged per run at ≤ 1 % at every
density, and k = 4 passes it. On the calibration seeds, **146 of 450 individual runs exceeded 1 %, with a maximum of
4.44 %**. There is **no per-run false-alarm guarantee**, and none is claimed here.

**Sources:** every number comes from `analysis/g3b_evaluation.py`, whose output is
`analysis/g3b_evaluation_output.txt`.

## Arms

All three arms use the same 19 settings and seeds: runs 0–29, seed = 10000 + 100·density + run, densities
100/200/300, `COMMITTEE_CHECK=1`, VeReMi ML off.

| Arm | Gate | Detector | Source |
|---|---|---|---|
| **F**: Block F baseline (no detector) | 0.70 | off | `results/adversarial/{B,C}` |
| **D**: burst detector | 0.70 | k = 4 | `results/hardening/G3b` |
| **G**: count-gate comparison | 0.75 | off | `results/hardening/G3b_gate` |

- **Settings:** the 16 Block F C settings (phased duty 0.5/0.8/0.9/0.95 × period 10/30 s × 10/20 % attackers) and the 3
  per-second-0.9 B settings (10/20/30 %, 5 colluders).
- **"Ineligible":** Beta trust below the gate, or, in arm D only, burst-flagged. Only ineligible vehicles are excluded
  from cluster-head roles, committees and endorsement.

## 1. Outcome

- **The detector measurably helps against phased 0.9/30 s** (3 s off-windows), and the count gate does not:
  - attackers made ineligible: 0.5–0.6 % → **40 %**; gate 0.75 reaches only 7.2 %;
  - forged-alert acceptance at 10 %: 77.8 % → **18.9 %** (gate 0.75: 68.9 %);
  - at 20 %: 95.6 % → **24.4 %** (gate 0.75: 80.0 %);
  - paired vs Block F: 53 and 64 forgeries removed, none added. D vs G: 47 and 54 fewer, p ≈ 1e-12.
- **It also helps against phased 0.8/30 s** (6 s off-windows):
  - every attacker is made ineligible; forged acceptance falls from 30 % to 0 %;
  - gate 0.75 reaches 2.2 %; the difference between the two is not significant (2 seeds, p = 0.5).
- **Phased 0.95/30 s gains are small:** 4–5 % ineligible against about 1 % for the gate; forged acceptance falls from
  79 to 71 % (10 %) and from 98 to 84 % (20 %).
- **No improvement against per-second 0.9.** Gate 0.75 detects more attackers (12.2–12.8 % against 8.1–8.9 %),
  excludes about seven to eighteen times fewer honest vehicles, and accepts fewer forgeries.
- **Also worse than gate 0.75 for every 10 s period:** 0.8/10 s (39 % against 87 % detected), 0.9/10 s and 0.95/10 s.
- **Cost:** about 0.6–0.9 % of honest vehicles excluded per run, against about 0.1 % for gate 0.75.
  - 37 % of runs exceed 1 %, with a maximum of 3.75 %.
  - One cell reaches exactly 1.00 % mean (per-second 10 %, 200 vehicles; CI upper bound 1.29 %).
  - About 0.1–0.2 honest cluster heads are replaced per run.
- **No genuine-alert availability loss was observed:**
  - 0 losses in 1710 paired runs (15 gains);
  - proposed delivery never lower;
  - CH-route RSU reception: 1 loss, 15 gains.

## 2. Completeness, integrity, tests

- **Completeness:**
  - G3b 19/19 and G3b_gate 19/19 settings; each setting 90/90 (density, run) pairs.
  - 1710 trust rows per arm, with keys identical to Block F's.
  - Times: G3b 10:30:56–10:49:51 UTC, G3b_gate 10:49:51–11:08:47 UTC (`sweep_log.txt`).
- **k = 0 reproduces the baseline exactly.** Two Block F settings were re-run with an explicit `TRUST_BURST_K=0`
  (phased 0.9/30 s at 10 %, and per-second 0.9 at 10 % with 5 colluders). Their `runs.csv` and `forgery_runs.csv` are
  byte-identical to Block F (`results/hardening/G3b_k0_check/`).
- **Beta trust is unchanged:** per-vehicle Beta trust is identical in F, D and G on the same seed in **1710 of 1710**
  runs.
- **Earlier results are unchanged:**
  - a sha256 manifest of all 14,226 Block F, G1, G2 and G3a files, taken before the chain, matches afterwards;
  - the only exception is `sweep_log.txt`, which was appended to (the old file is an exact prefix);
  - new files are only `G3b*` outputs and the analysis script;
  - `results/urban` is clean (`git status`).
- **Code added for the comparison arm** (no default changed):
  - `adversarial.G3B_COMPARISON_GATE = 0.75`;
  - a `G3b_gate` sweep (the G3b settings with gate 0.75 and no detector);
  - its choice in `run.py adversarial`;
  - the G3b guard extended to it.
- **Tests:** see section 8.

## 3. Detection, honest exclusion and forgery, by attacker type

Columns:
- *Attackers ineligible* and *honest ineligible*: % per run, pooled n = 90 (30 per density).
- *Forged accepted*: default level, % of runs.
- *D vs G*: forgeries accepted by D and not by G / by G and not by D, with an exact sign test.

| Attacker (share) | Attackers ineligible F / D / G | Honest ineligible F / D / G | Forged accepted F / D / G | D vs G |
|---|---|---|---|---|
| per-second 0.9 (10 %) | 1.6 / 8.7 / **12.5** | 0.03 / 0.85 / 0.12 | 73.3 / 64.4 / **48.9** | +19 / −5 (p = 0.0066) |
| per-second 0.9 (20 %) | 1.7 / 8.1 / **12.2** | 0.00 / 0.73 / 0.08 | 93.3 / 72.2 / 66.7 | +18 / −13 (p = 0.47) |
| per-second 0.9 (30 %) | 2.0 / 8.9 / **12.8** | 0.00 / 0.54 / 0.03 | 90.0 / 74.4 / 64.4 | +19 / −10 (p = 0.14) |
| phased 0.5/10 s and 0.5/30 s (10, 20 %) | 100 / 100 / 100 | ≈0 / 0.81, 0.72 / 0.07, 0.05 | 0 / 0 / 0 | — |
| phased 0.8/10 s (10 %) | 31.8 / 39.1 / **86.9** | 0.01 / 0.81 / 0.07 | 28.9 / 21.1 / **1.1** | +18 / −0 (p = 7.6e-6) |
| phased 0.8/10 s (20 %) | 31.2 / 39.5 / **86.8** | 0.00 / 0.72 / 0.05 | 28.9 / 18.9 / **0.0** | +17 / −0 (p = 1.5e-5) |
| phased 0.8/30 s (10 %) | 33.6 / **100** / 82.4 | 0.01 / 0.81 / 0.07 | 30.0 / **0.0** / 2.2 | +0 / −2 (p = 0.5) |
| phased 0.8/30 s (20 %) | 34.1 / **100** / 80.7 | 0.00 / 0.72 / 0.05 | 31.1 / **0.0** / 2.2 | +0 / −2 (p = 0.5) |
| phased 0.9/10 s (10 %) | 0.6 / 3.7 / **5.7** | 0.01 / 0.81 / 0.07 | 77.8 / 68.9 / 65.6 | +8 / −5 (p = 0.58) |
| phased 0.9/10 s (20 %) | 0.4 / 2.6 / **6.3** | 0.00 / 0.72 / 0.05 | 97.8 / 90.0 / **78.9** | +13 / −3 (p = 0.021) |
| **phased 0.9/30 s (10 %)** | 0.6 / **40.7** / 7.2 | 0.01 / 0.81 / 0.07 | 77.8 / **18.9** / 68.9 | +2 / −47 (p = 4.4e-12) |
| **phased 0.9/30 s (20 %)** | 0.5 / **40.2** / 7.2 | 0.00 / 0.72 / 0.05 | 95.6 / **24.4** / 80.0 | +4 / −54 (p = 3.2e-12) |
| phased 0.95/10 s (10 %) | 0.4 / 1.9 / **3.0** | 0.01 / 0.81 / 0.07 | 77.8 / 74.4 / 72.2 | +4 / −2 (p = 0.69) |
| phased 0.95/10 s (20 %) | 0.2 / 1.5 / **3.2** | 0.00 / 0.72 / 0.05 | 97.8 / 91.1 / 88.9 | +6 / −4 (p = 0.75) |
| phased 0.95/30 s (10 %) | 0.1 / **4.7** / 1.2 | 0.01 / 0.81 / 0.07 | 78.9 / 71.1 / 77.8 | +1 / −7 (p = 0.07) |
| phased 0.95/30 s (20 %) | 0.0 / **4.1** / 0.8 | 0.00 / 0.72 / 0.05 | 97.8 / **84.4** / 93.3 | +2 / −10 (p = 0.039) |

- **Per-density detection** values are in output section C. They are stable across densities; for phased 0.9/30 s, D
  makes 38–44 % of attackers ineligible at every density.
- **Forgeries removed vs Block F, paired (D):**
  - per-second: −8, −19, −14;
  - phased 0.8/10 s: −7, −9;
  - phased 0.8/30 s: −27, −28;
  - phased 0.9/10 s: −8, −7;
  - phased 0.9/30 s: −53, −64;
  - phased 0.95/10 s: −3 (n.s.), −6;
  - phased 0.95/30 s: −7, −12;
  - **no new forgery in any cell.**
- **Committee-level forgery** (`COMMITTEE_CHECK` variant) is unchanged by D except at per-second 30 % (14.4 → 12.2 %).

## 4. Honest exclusion per run and per density

The 8 phased types share one honest observation stream per attacker share (as in G3a). So there are five distinct
honest populations: per-second at 10/20/30 % and phased at 10/20 %.

**Pooled over all 19 settings** (n = 570 runs per density). Each cell: mean ± CI / maximum run / runs > 1 % / runs > 2 %.

| Arm | 100 vehicles | 200 vehicles | 300 vehicles |
|---|---|---|---|
| F (0.70) | 0.00 ± 0.00 / 1.11 / 1 / 0 | 0.00 ± 0.00 / 0.56 / 0 / 0 | 0.01 ± 0.01 / 0.37 / 0 / 0 |
| D (k = 4) | 0.75 ± 0.07 / 3.75 / **270** / 83 | 0.83 ± 0.06 / 3.12 / **217** / 31 | 0.69 ± 0.04 / 2.38 / **148** / 10 |
| G (0.75) | 0.06 ± 0.03 / 2.22 / 20 / 9 | 0.03 ± 0.01 / 1.25 / 2 / 0 | 0.10 ± 0.02 / 1.49 / 1 / 0 |

**Distribution per honest population** (n = 30 runs per row). Run counts in buckets 0 / (0, 1] / (1, 2] / (2, 3] /
> 3 %, then mean ± CI and maximum.

| Population | Vehicles | D (k = 4) | G (gate 0.75) |
|---|---|---|---|
| per-second 10 % | 100 | 14 / 0 / 10 / 5 / 1; 0.85 ± 0.36, max 3.33 | 29 / 0 / 0 / 1 / 0; 0.07 ± 0.15, max 2.22 |
| per-second 10 % | 200 | 4 / 12 / 9 / 5 / 0; **1.00 ± 0.29**, max 2.78 | 24 / 5 / 1 / 0 / 0; 0.13 ± 0.10, max 1.11 |
| per-second 10 % | 300 | 8 / 11 / 10 / 1 / 0; 0.69 ± 0.23, max 2.22 | 23 / 6 / 1 / 0 / 0; 0.15 ± 0.12, max 1.49 |
| per-second 20 % | 100 | 17 / 0 / 9 / 2 / 2; 0.79 ± 0.42, max 3.75 | 28 / 0 / 2 / 0 / 0; 0.08 ± 0.12, max 1.25 |
| per-second 20 % | 200 | 6 / 13 / 11 / 0 / 0; 0.77 ± 0.20, max 1.88 | 28 / 1 / 1 / 0 / 0; 0.06 ± 0.09, max 1.25 |
| per-second 20 % | 300 | 4 / 22 / 4 / 0 / 0; 0.63 ± 0.15, max 1.67 | 25 / 5 / 0 / 0 / 0; 0.10 ± 0.09, max 0.83 |
| per-second 30 % | 100 | 21 / 0 / 8 / 1 / 0; 0.48 ± 0.29, max 2.86 | 29 / 0 / 1 / 0 / 0; 0.05 ± 0.10, max 1.43 |
| per-second 30 % | 200 | 12 / 10 / 6 / 2 / 0; 0.67 ± 0.25, max 2.14 | 29 / 1 / 0 / 0 / 0; 0.02 ± 0.05, max 0.71 |
| per-second 30 % | 300 | 15 / 10 / 4 / 1 / 0; 0.49 ± 0.24, max 2.38 | 28 / 2 / 0 / 0 / 0; 0.03 ± 0.05, max 0.48 |
| phased 10 % | 100 | 13 / 0 / 11 / 5 / 1; 0.89 ± 0.35, max 3.33 | 29 / 0 / 0 / 1 / 0; 0.07 ± 0.15, max 2.22 |
| phased 10 % | 200 | 7 / 10 / 12 / 1 / 0; 0.81 ± 0.25, max 2.78 | 29 / 1 / 0 / 0 / 0; 0.02 ± 0.04, max 0.56 |
| phased 10 % | 300 | 2 / 19 / 9 / 0 / 0; 0.73 ± 0.17, max 1.85 | 22 / 8 / 0 / 0 / 0; 0.11 ± 0.07, max 0.74 |
| phased 20 % | 100 | 18 / 0 / 9 / 3 / 0; 0.63 ± 0.32, max 2.50 | 29 / 0 / 1 / 0 / 0; 0.04 ± 0.09, max 1.25 |
| phased 20 % | 200 | 8 / 12 / 8 / 1 / 1; 0.85 ± 0.30, max 3.12 | 29 / 1 / 0 / 0 / 0; 0.02 ± 0.04, max 0.62 |
| phased 20 % | 300 | 8 / 15 / 6 / 1 / 0; 0.68 ± 0.21, max 2.08 | 26 / 4 / 0 / 0 / 0; 0.08 ± 0.09, max 0.83 |

- **Mean versus cap:** on the evaluation seeds every D population stays at or below 1 % mean. Per-second 10 % at 200
  vehicles sits exactly at 1.00 % (honest flagged alone: 0.98 %). The calibrated k therefore has no margin on these seeds.
- **Why (0, 1] is empty at 100 vehicles:** one flagged honest vehicle is already more than 1 % of the 90 honest
  vehicles.

## 5. Genuine alerts

| Measure | D vs F (paired) | G vs F (paired) |
|---|---|---|
| Genuine alert accepted | 15 gains, **0 losses** of 1710 | 19 gains, 0 losses of 1710 |
| Proposed delivery (both accepted) | never lower | never lower |
| CH-route relayed RSU reception | 15 gains, **1 loss** (per-second 20 %) | 11 gains, 0 losses |

- **Genuine acceptance (D)** ranges over 81.1–100 % by cell, never below F in any cell.
- **Gains come from fewer attackers on the committee.** The largest is phased 0.9/30 s at 20 %: 91.1 → 96.7 %
  (+5 / −0, p = 0.062).

## 6. Committee and cluster-head eligibility

Per run, pooled n = 90.
- **F → D → G** columns give the attackers on the genuine committee and the attackers holding a CH role, without the
  detector, with it, and with gate 0.75.
- **Honest CHs removed** are CH in F, not CH in D (or G).
- **CH roles** are taken from the recorded runs (same seed, same positions).

| Attacker (share) | Attackers on committee F → D → G | Attacker CHs F → D → G | Honest CHs removed D / G | Honest CHs added D / G |
|---|---|---|---|---|
| per-second 0.9 (10 %) | 0.56 → 0.52 → 0.49 | 1.89 → 1.80 → 1.69 | 0.16 / 0.01 | 0.24 / 0.21 |
| per-second 0.9 (20 %) | 1.12 → 1.09 → 1.04 | 3.63 → 3.46 → 3.24 | 0.14 / 0.01 | 0.32 / 0.40 |
| per-second 0.9 (30 %) | 1.62 → 1.56 → 1.49 | 5.73 → 5.44 → 5.32 | 0.10 / 0.00 | 0.39 / 0.41 |
| phased 0.5/x (10 %, 20 %) | 0 → 0 → 0 | 0 → 0 → 0 | 0.18–0.21 / ≤ 0.01 | 0.18–0.20 / ≤ 0.01 |
| phased 0.8/10 s (10 %) | 0.42 → 0.39 → 0.08 | 1.34 → 1.23 → 0.32 | 0.13 / 0.01 | 0.24 / 1.03 |
| phased 0.8/10 s (20 %) | 0.83 → 0.71 → 0.13 | 2.77 → 2.52 → 0.62 | 0.21 / 0.00 | 0.46 / 2.13 |
| phased 0.8/30 s (10 %) | 0.43 → **0.00** → 0.13 | 1.30 → **0.00** → 0.41 | 0.14 / 0.01 | 1.44 / 0.90 |
| phased 0.8/30 s (20 %) | 0.73 → **0.00** → 0.22 | 2.59 → **0.00** → 0.88 | 0.21 / 0.00 | 2.78 / 1.71 |
| phased 0.9/10 s (10 %) | 0.56 → 0.54 → 0.54 | 1.91 → 1.87 → 1.81 | 0.13 / 0.01 | 0.18 / 0.11 |
| phased 0.9/10 s (20 %) | 1.14 → 1.12 → 1.07 | 3.67 → 3.66 → 3.47 | 0.20 / 0.00 | 0.21 / 0.20 |
| phased 0.9/30 s (10 %) | 0.56 → **0.37** → 0.54 | 1.91 → **1.16** → 1.80 | 0.13 / 0.01 | 0.89 / 0.12 |
| phased 0.9/30 s (20 %) | 1.14 → **0.76** → 1.09 | 3.67 → **2.37** → 3.46 | 0.20 / 0.00 | 1.50 / 0.21 |
| phased 0.95/10 s (10 %) | 0.56 → 0.56 → 0.56 | 1.91 → 1.90 → 1.88 | 0.13 / 0.01 | 0.14 / 0.04 |
| phased 0.95/10 s (20 %) | 1.14 → 1.12 → 1.11 | 3.67 → 3.68 → 3.54 | 0.20 / 0.00 | 0.19 / 0.12 |
| phased 0.95/30 s (10 %) | 0.56 → 0.53 → 0.56 | 1.91 → 1.83 → 1.91 | 0.13 / 0.01 | 0.21 / 0.01 |
| phased 0.95/30 s (20 %) | 1.14 → 1.11 → 1.13 | 3.68 → 3.63 → 3.66 | 0.20 / 0.00 | 0.24 / 0.02 |

The cost of D is visible even where it gains nothing. With phased 0.5 attackers, which Beta already excludes, D still
removes about 0.2 honest cluster heads per run.

## 7. Negative and neutral findings

- **Per-second 0.9: no improvement over a count gate.** Gate 0.75 beats k = 4 on detection, honest exclusion and forgery
  in all three shares. The plan predicted this: counts are a sufficient statistic for independent per-second behaviour.
- **Periods of 10 s:** the detector is worse than gate 0.75 for duty 0.8, 0.9 and 0.95.
- **The honest-exclusion cost** is about 10 times gate 0.75's. 37 % of D runs exceed 1 % (maximum 3.75 %), and one cell
  sits exactly at the 1 % mean cap.
- **About 0.1–0.2 honest cluster heads are replaced per run** under D, in every setting.
- **No configuration with both** gate 0.75 and k = 4 was run, so this report claims nothing about combining them.
- **The forged-alert test does not exercise the CH route** (it runs the proposed broadcast and its ablations), so no
  CH-route forgery effect is measured.

## 8. Tests and reproduction

- **Results:**
  - `python -m pytest validation -q`: **158 passed**, after `python build_portal_assets.py` refreshed the portal source
    bundle (the first run flagged only the stale bundle);
  - `python -m pytest veremi -q`: **26 passed**.
- **Reproduce:**

```
python run.py adversarial G3b          # k from G3a_calibration_choice.json (4); 19 settings, runs 0-29
python run.py adversarial G3b_gate     # the same settings at gate 0.75, no detector
python -X utf8 results/hardening/analysis/g3b_evaluation.py
```
