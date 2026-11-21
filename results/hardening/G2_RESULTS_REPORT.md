# G2 results: committee size and quorum (Block G)

Simulation only (SUMO 1.27.1, Python 3.11.4, `network/urban.net.xml`: real topology, synthetic demand). No default was
changed (`COMMITTEE_SIZE` 5, `QUORUM` 3, `ENFORCE_COMMITTEE` 0). Nothing is committed. Every number below is produced by
`results/hardening/analysis/g2_paired.py` (output saved in `analysis/g2_paired_output.txt`) or by
`analysis/blockg_tables.py` (per-cell tables in `BLOCK_G_TABLES.md`) from `results/hardening/G2_*_runs.csv` and the Block F
CSVs in `results/adversarial/`.

## 1. Outcome

- **Selection rule** (pre-registered `G2_admissible` + `G2_selection`), applied to the majority-quorum candidates the plan
  allows (5/3, 7/4, 9/5): **9/5**. It accepts the most genuine alerts and the fewest forgeries.
- **Adoption criteria** (plan section 8): **not met by 7/4 or 9/5.** Criterion 2 (genuine delivery not lower than Block F on
  any seed, except losses explained by withholding) fails on the CH route, the design's CH-to-CH path to the RSUs:
  relayed RSU reception is lost on 20 (7/4) and 34 (9/5) of 168 seeds paired with Block F, with 3 gains each. The
  withholding rule does not explain these losses.
- **No configuration is recommended for adoption.** 5/3 stays. 9/5 is better only on the source-committee path; see section 7.

## 2. What ran, and integrity

| Item | Value |
|---|---|
| Settings | 24 = {5/3, 7/4, 9/5, 7/3} × share {0.1, 0.2, 0.3} × attacker {per-second 0.9, phased 0.9/30 s} |
| Fixed | `ENFORCE_COMMITTEE=1`, `COMMITTEE_CHECK=1`, `MAX_COLLUDERS=m`, gate 0.70, VeReMi ML off |
| Seeds | runs 0–29, densities 100/200/300, seed = 10000 + 100·density + run |
| Completed | 24/24 settings; every setting has all 90 (density, run) pairs; 2160 raw records |
| Time | 06:48:32–07:12:31 UTC |

- **Block F unchanged:** newest file 05:17:23 UTC, before Block G started (06:14:32).
- **G1 unchanged:** newest file 06:48:32 UTC.
- **`results/urban` clean** (`git status`).
- **Implementation unchanged:** file hashes identical since the sweep chain started.
- **The 5/3 arm reproduces G1 byte-identically** in the 5 cells they share (3 per-second, 2 phased). So "vs 5/3" below is
  also "vs G1". The phased 30 % cell has no G1 or Block F counterpart; it is reported but used in no criterion.

## 3. Deviations (disclosed)

1. **7/3 was a selection candidate.** The coded `select_committee` included the 7/3 contrast arm among the candidates, so
   `G2_selection.json` records `"chosen": [7, 3]`. The plan (section 4.1) lists 7/3 as a contrast arm only, and safeguard 5
   forbids a weaker quorum.
   - The same rule was applied here to 5/3, 7/4 and 9/5.
   - `G2_selection.json` is kept unchanged as the record of the coded run.
   - **Consequence:** `adversarial._choices` would pass 7/3 to G4, so **G4 must not be run until `select_committee` is
     fixed**. That is a code change and needs approval.
2. **G3a was blocked.** The sweep chain would have started G3a automatically after G2. Only the loop shell was stopped,
   after G2 finished normally. Neither G3 nor G4 was started.
3. **Analysis scripts only, no simulator code:**
   - `blockg_tables.py` now lists only the sweeps that ran and prints this deviation note;
   - `g2_paired.py` is new.

## 4. Pooled results

540 runs per configuration (6 cells × 90). Clopper–Pearson 95 % intervals.

| m/q | Genuine accepted | Genuine failures with ≥ m−q+1 attackers on committee | Forged accepted, default level | Forged accepted, voting only | CH-route relayed RSU reception (n = 202) |
|---|---|---|---|---|---|
| 5/3 | 89.6 % [86.7, 92.1] | 56 of 56 | 6.1 % [4.2, 8.5] | 6.3 % [4.4, 8.7] | 66.3 % [59.4, 72.8] |
| 7/4 | 93.1 % [90.7, 95.1] | 37 of 37 | 3.9 % [2.4, 5.9] | 4.1 % [2.6, 6.1] | 56.9 % [49.8, 63.9] |
| 9/5 | 96.7 % [94.8, 98.0] | 18 of 18 | 1.9 % [0.9, 3.4] | 1.9 % [0.9, 3.4] | 48.0 % [41.0, 55.1] |
| 7/3 (contrast) | 98.5 % [97.1, 99.4] | 8 of 8 | 16.9 % [13.8, 20.3] | 17.4 % [14.3, 20.9] | 68.8 % [61.9, 75.1] |

- **Vote withholding explains every genuine failure.** Every genuine failure in every configuration had at least
  m − q + 1 attackers on the committee.
- **Committee fill never failed.** The committee was full in 100 % of runs and below quorum in 0 %, in all 72
  configuration × cell × density groups. Shortfall was not observed on this map at 100–300 vehicles; 50 vehicles was not
  tested.

## 5. Per density

6 cells, 180 runs per row. Mean ± 95 % Student-t half-width.

| m/q | Vehicles | Genuine accepted % | Forged accepted % (default) | Attackers on committee | CH relayed RSU % (n) | Vote frames per alert | Quorum delay ms |
|---|---|---|---|---|---|---|---|
| 5/3 | 100 | 89.4 ± 4.5 | 6.7 ± 3.7 | 1.11 ± 0.14 | 53.2 ± 12.8 (62) | 3.9 ± 0.1 | 12.06 |
| 5/3 | 200 | 90.0 ± 4.4 | 10.6 ± 4.5 | 1.16 ± 0.15 | 78.9 ± 9.4 (76) | 3.8 ± 0.2 | 12.06 |
| 5/3 | 300 | 89.4 ± 4.5 | 1.1 ± 1.5 | 1.04 ± 0.15 | 64.1 ± 12.1 (64) | 4.0 ± 0.2 | 12.06 |
| 7/4 | 100 | 94.4 ± 3.4 | 3.3 ± 2.6 | 1.47 ± 0.18 | 35.5 ± 12.2 (62) | 5.5 ± 0.2 | 12.58 |
| 7/4 | 200 | 93.3 ± 3.7 | 7.2 ± 3.8 | 1.59 ± 0.18 | 78.9 ± 9.4 (76) | 5.4 ± 0.2 | 12.56 |
| 7/4 | 300 | 91.7 ± 4.1 | 1.1 ± 1.5 | 1.45 ± 0.20 | 51.6 ± 12.6 (64) | 5.5 ± 0.2 | 12.57 |
| 9/5 | 100 | 97.8 ± 2.2 | 2.2 ± 2.2 | 1.74 ± 0.20 | 25.8 ± 11.2 (62) | 7.3 ± 0.2 | 13.06 |
| 9/5 | 200 | 97.8 ± 2.2 | 3.3 ± 2.6 | 1.96 ± 0.20 | 63.2 ± 11.1 (76) | 7.0 ± 0.2 | 13.06 |
| 9/5 | 300 | 94.4 ± 3.4 | 0.0 ± 0.0 | 1.77 ± 0.22 | 51.6 ± 12.6 (64) | 7.2 ± 0.2 | 13.07 |
| 7/3 | 100 | 98.9 ± 1.5 | 15.6 ± 5.3 | 1.47 ± 0.18 | 58.1 ± 12.6 (62) | 5.5 ± 0.2 | 12.06 |
| 7/3 | 200 | 97.8 ± 2.2 | 18.9 ± 5.8 | 1.59 ± 0.18 | 81.6 ± 8.9 (76) | 5.4 ± 0.2 | 12.06 |
| 7/3 | 300 | 98.9 ± 1.5 | 16.1 ± 5.4 | 1.45 ± 0.20 | 64.1 ± 12.1 (64) | 5.5 ± 0.2 | 12.06 |

- **Quorum delay** CIs are below 0.01 ms.
- **CH-route n** counts only runs where a CH route to an RSU existed.
- **Per-cell tables** (30 runs per cell, every metric) are in `BLOCK_G_TABLES.md`, section G2.
- **"0.0 ± 0.0" means no event was observed**, not zero uncertainty. The Clopper–Pearson upper bound is 2.0 % for 0/180
  and 11.6 % for 0/30.

## 6. Paired by seed

Each cell is gains / losses, then the exact sign test. A forgery "gain" means the configuration accepts a forgery that
the reference rejected (worse).

| Comparison | Genuine accepted | Forgery: newly accepted / newly rejected | CH relayed RSU reception |
|---|---|---|---|
| 7/4 vs 5/3 = G1 (540 pairs) | +22 / −3 (p = 1.6e-4) | 8 / 20 (p = 0.036) | +3 / −22 of 202 (p = 1.6e-4) |
| 9/5 vs 5/3 = G1 (540) | +41 / −3 (p = 1.6e-9) | 0 / 23 (p = 2.4e-7) | +3 / −40 of 202 (p = 3e-9) |
| 7/3 vs 5/3 = G1 (540) | +48 / −0 (p = 7.1e-15) | 58 / 0 (p = 6.9e-18) | +5 / −0 of 202 (p = 0.062) |
| 5/3 vs Block F default (450) | +0 / −0 | 0 / 368 | +0 / −0 of 168 |
| 7/4 vs Block F default (450) | +18 / −3 (p = 0.0015) | 0 / 374 | +3 / −20 of 168 (p = 4.9e-4) |
| 9/5 vs Block F default (450) | +30 / −2 (p = 2.5e-7) | 0 / 381 | +3 / −34 of 168 (p = 1.2e-7) |
| 7/3 vs Block F default (450) | +34 / −0 (p = 1.2e-10) | 0 / 329 | +4 / −0 of 168 (p = 0.12) |

- **Block F's default level** accepted 387 of the 450 forgeries.
- **Genuine losses vs Block F all match the withholding rule:**
  - 7/4: d300_r07 at 20 % (per-second and phased), d300_r13 at 30 % per-second; 4 attackers each;
  - 9/5: d300_r11 at 20 % phased, d100_r23 at 30 % per-second; 5 attackers each.
- **Proposed-scheme delivery** is identical to Block F on every seed where both accepted (n = 409–412 per
  configuration).
- **CH-route delivery** is lower than Block F on 18 seeds (7/4) and 37 seeds (9/5), and never higher.

## 7. Pre-registered criteria applied

**Selection rule (`PREREGISTERED_RULES.json`):**
- Criterion 1 (forgery ≤ Block F in every reference cell and density) holds for all four configurations.
- Criterion 2 as written there checks only the proposed scheme's delivery. All four pass it; the 3 (7/4) and 2 (9/5)
  regressions above are exempt under the withholding rule.
- Ranking by pooled genuine acceptance over the majority-quorum candidates gives 9/5 (96.7 %) > 7/4 (93.1 %) > 5/3 (89.6 %).

**Adoption criteria (plan section 8):**
1. *No weakening:* holds for 5/3, 7/4 and 9/5. The BLS, reputation and source checks are unchanged.
2. *Genuine acceptance and delivery not lower than Block F on any seed, except losses explained by withholding:*
   - holds for the proposed scheme;
   - **fails on the CH route for 7/4 and 9/5.**
   - **Why the CH route fails:**
     - The CH route's local rounds use the global `QUORUM` ([protocols.py:204](../../protocols.py#L204)). Each round
       has the head plus up to m reputable, adjacent cluster members.
     - In every seed where 9/5 lost a relay that 5/3 delivered, a route head collected 3 or 4 endorsements (20 seeds
       each): enough for q = 3, short of q = 5.
     - For 7/4: 20 of 22 lost relays had a head with exactly 3 endorsements. In the other 2, the genuine alert was not
       accepted at the source.
     - 7/3 (7 seats, q = 3) has no CH-route loss.
     - These losses are a quorum effect inside clusters, not the source-committee withholding rule.
3. *Fairness:* not applicable (no detector in G2).
4. *Everything reported:* this file, `BLOCK_G_TABLES.md`, `g2_paired_output.txt`.
5. *Defaults:* none changed.

The plan's criterion 2 says "genuine acceptance and delivery", without naming one scheme. It is applied as written here,
not narrowed to the proposed scheme after seeing the results. Whether the CH route counts is a decision for you. If you
rule that only the proposed scheme counts, the pre-registered pick is 9/5.

**Options (none taken):**
- (a) keep 5/3;
- (b) give the CH-route local rounds their own quorum, not lower than the current 3. This decouples them from the
  source committee. It is a design change: it needs approval and its own pre-registered evaluation.

## 8. Negative and neutral findings

- **CH-route regression:** largest at 100 vehicles, where relayed reception falls from 53.2 % (5/3) to 25.8 % (9/5).
- **7/4 accepts 8 forgeries that 5/3 rejected** while rejecting 20 it accepted:
  - 1 each at 20 % attackers (per-second and phased, at 100 and 300 vehicles);
  - 2 each at 30 % attackers, 200 vehicles;
  - its forger has 7 colluders against 5. It stays at or below Block F everywhere.
- **7/3 behaves as the plan predicted:** most genuine alerts (98.5 %), but 16.9 % forged acceptance against 6.1 % for
  5/3: 58 new forgeries and none removed. It is not a hardening.
- **More attackers sit on larger committees** (1.1 → 1.8 average at 9/5). The gain comes from the higher withholding
  threshold m − q + 1 (3 → 5), not from fewer attackers.
- **At 30 % attackers, 9/5 still loses 7–13 % of genuine alerts** to withholding (cells 86.7–93.3 %).
- **Costs:** +1.6 (7/4) and +3.3 (9/5) vote frames per alert; quorum delay +0.5 and +1.0 ms.
- **The two attacker models give almost the same numbers.** Phased 0.9/30 s and per-second 0.9 are nearly identical, as
  Block F found (0.3 % and 1.7 % of these attackers fall below gate 0.70).
- **Baseline schemes shift slightly.** Slotted 1-p and flooding are not in the criteria. Against Block F, slotted 1-p
  delivery changes on about 150 seeds per configuration in both directions; its mean is −0.5 to −0.6 pp at 7/4, 9/5 and
  7/3. Flooding's mean shift is within ±0.1 pp. 5/3 shows no change. The likely cause is the extra vote frames on the
  channel; this was not isolated.

## 9. Reproduce

```
python run.py adversarial G2                                   # the sweep (already complete; finished settings are skipped)
python -X utf8 results/hardening/analysis/g2_paired.py         # sections 4-7
python -X utf8 results/hardening/analysis/blockg_tables.py     # BLOCK_G_TABLES.md
```

Each setting's `summaries/experiment_config.json` records its overrides, SUMO version, Python version, commit and network
hash.
