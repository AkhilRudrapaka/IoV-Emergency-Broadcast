# G4: combined confirmation (5/3 + committee enforcement + burst detector k = 4)

**Conditions:**
- Simulation only (SUMO 1.27.1, Python 3.11.4, `network/urban.net.xml`: hand-built synthetic 5×5 grid with synthetic traffic demand).
- Runs 0–29, densities 100/200/300, seed = 10000 + 100·density + run; gate 0.70.
- `COMMITTEE_CHECK=1`, VeReMi ML off (shadow only).

**Sources:** every number comes from `analysis/g4_confirmation.py`, whose output is
`analysis/g4_confirmation_output.txt`.

## What ran

- **G4 configuration:** `COMMITTEE_SIZE=5`, `QUORUM=3`, `ENFORCE_COMMITTEE=1`, `TRUST_BURST_K=4`, `MAX_COLLUDERS=5`.
- **How it was run:** `python run.py adversarial G4`. The configuration comes from `G2_selection_corrected.json` (5/3)
  and `G3a_calibration_choice.json` (k = 4).
- **Scope: 25 unique settings.**
  - The pre-registered rule (`MAX_COLLUDERS = max(setting, committee size)`) maps the nine 3-colluder Block F B
    settings onto the 5-colluder ones.
  - The prepared runner listed those duplicates (34 entries) and would have collected them twice. It now keeps each
    setting once.
  - The 25 settings are 9 B settings (per-second cooperation 0, 0.5 and 0.9 at 10/20/30 % attackers) and 16 C settings
    (phased duty 0.5/0.8/0.9/0.95 × period 10/30 s at 10/20 %).
  - The B settings with 3 colluders are not separately re-evaluated here; G1 covers them.
- **Completeness:** 25/25 settings, 2250 runs (90 per setting), all raw records present; ran 04:47:03–05:12:38 UTC.
- **Comparisons on the same seeds:**
  - **F:** Block F (no enforcement, no detector);
  - **E:** G1 (enforcement only);
  - **D:** G3b (detector only), covering 19 of the 25 cells;
  - **C:** G4 (both).

## Results

**Forged-alert acceptance, default level:**

| Arm | Accepted / runs (25 cells) | On the 19 cells with all four arms |
|---|---|---|
| F: Block F | 969 / 2250 | 969 / 1710 |
| E: enforcement only (G1) | **31** / 2250 | 31 / 1710 |
| D: detector only (G3b) | — | 697 / 1710 |
| C: enforcement + detector (G4) | **28** / 2250 | 28 / 1710 |

- **Paired vs F,** C removes forgeries in every cell where F accepted any, and adds none:
  - per-second 0.9: −66, −81, −70;
  - phased 0.8/30 s: −27, −28;
  - phased 0.9/30 s: −70, −83;
  - all p ≤ 1e-7.
- **The detector on top of enforcement (C vs E) removes 3 forgeries in 2250 runs** (per-second 0.9 at 30 %: −2;
  phased 0.8/30 s at 20 %: −1), and adds none. This is not significant.
- **Enforcement on top of the detector (C vs D) removes 669 forgeries** on the 19 cells.
- **The effects are not additive.** Enforcement alone removes 938 of Block F's 969 forgeries (96.8 %); both together
  remove 941 (97.1 %).
- **Voting-only level:**
  - Block F accepted 78.9–97.8 % of forgeries per cell; G4 accepts 0.0–15.6 %.
  - The highest remaining cells are at 30 % attackers (15.6 %): the voting-only committee ignores reputation, so
    colluders can be among the 5 nearest vehicles.

**Genuine alert, delivery and cost** (all 25 cells, paired vs F):

| Measure | E (enforcement only) | C (enforcement + k = 4) |
|---|---|---|
| Genuine alert accepted | identical to F (+0 / −0) | **+15 / −0** (p = 6.1e-5) |
| Proposed delivery (both accepted) | identical | never lower |
| CH-route relayed RSU reception | identical | +16 / −2 (p = 0.0013) |
| Vote frames per alert | = F | equal or higher (e.g. phased 0.8/30 s: 4.57 → 5.00) |
| Quorum delay | 12.06 ms | 12.06 ms (unchanged) |

- **Enforcement does not change any genuine-alert or eligibility outcome:** G4 equals G3b on every one of 1710 shared
  runs (genuine acceptance, honest exclusion, attackers on the committee).
- **The genuine gains come from the detector,** through fewer attackers withholding votes. The largest is phased
  0.9/30 s at 20 %: 91.1 → 96.7 %.
- **Vote frames rise** because removed attackers are replaced by honest committee members, who do vote.

**Detection, honest exclusion, committee and cluster-head eligibility** (G4 = G3b where both exist):

| Attacker | Attackers ineligible F → C | Attacker CHs per run F → C | Attackers on committee F → C |
|---|---|---|---|
| per-second 0.9 (10 / 20 / 30 %) | 1.6–2.0 → 8.1–8.9 % | 1.89 → 1.80; 3.63 → 3.46; 5.73 → 5.44 | 0.56 → 0.52; 1.12 → 1.09; 1.62 → 1.56 |
| phased 0.8/30 s (10 / 20 %) | 33.6–34.1 → **100 %** | 1.30 → **0**; 2.59 → **0** | 0.43 → 0; 0.73 → 0 |
| phased 0.9/30 s (10 / 20 %) | 0.5–0.6 → **40.2–40.7 %** | 1.91 → 1.16; 3.67 → 2.37 | 0.56 → 0.37; 1.14 → 0.76 |
| phased 0.8/10 s | 31–32 → 39–40 % | small change | small change |
| phased 0.9/10 s, 0.95/10 s, 0.95/30 s | ≤ 0.6 → 1.5–4.7 % | ≈ unchanged | ≈ unchanged |
| per-second 0 and 0.5; phased 0.5 | 100 % (Beta already) | 0 | 0 |

**Honest exclusion under G4,** per run, pooled over the 25 cells (n = 750 per density):

| Vehicles | Mean ± 95 % CI | Maximum run | Runs > 1 % | Runs > 2 % |
|---|---|---|---|---|
| 100 | 0.74 ± 0.07 % | 3.75 % | 346 | 105 |
| 200 | 0.82 ± 0.05 % | 3.12 % | 278 | 43 |
| 300 | 0.68 ± 0.04 % | 2.38 % | 188 | 13 |

- **36 % of G4 runs exclude more than 1 % of honest vehicles,** against about 0 % under Block F.
- **About 0.1–0.2 honest cluster heads are replaced per run in every cell**, including the cells where the detector
  adds nothing (per-second 0 and 0.5, phased 0.5).

## Interpretation

| Type | Statement |
|---|---|
| Measured | Committee enforcement provides essentially all of the forged-alert reduction. The detector adds 3 of 941 removed forgeries. |
| Measured | The detector's added value under enforcement is genuine availability for phased attackers with long off-windows: 15 genuine gains, CH relay +16 / −2. Its cost is about 0.7–0.8 % honest exclusion on average, more than 1 % in 36 % of runs. |
| Measured | No improvement against per-second 0.9 attackers beyond what G3b showed (gate 0.75 did better there). |
| Not claimed | Additive gains from combining the two defences. There is no forgery additivity, and the genuine gains belong to the detector alone. |
| Decision (approved) | Enforcement on by default; detector off by default, k = 4 opt-in. |
