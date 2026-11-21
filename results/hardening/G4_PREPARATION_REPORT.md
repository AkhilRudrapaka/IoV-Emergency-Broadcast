# G4 preparation: committee selection fix, CH-route quorum, proposed configuration

**Scope:** preparation only. No G4 simulation was run and no default changed. This report and the changes it describes are committed in
`81d416e` (published on `origin/akhil`).

**Evidence used:**
- G1 (`BLOCK_G_TABLES.md`);
- G2 (`G2_RESULTS_REPORT.md`);
- G3a (`G3A_CALIBRATION_REPORT.md`);
- G3b (`G3B_EVALUATION_REPORT.md`);
- the analyses `analysis/g4_ch_route.py` and `analysis/g4_ch_route_output.txt`.

Simulation only.

## 1. Summary

| Item | Result |
|---|---|
| G4.1: selection fix | `select_committee` now considers only 5/3, 7/4 and 9/5; 7/3 is a contrast. The registered rule picks **9/5**. **5/3** is the only candidate that also meets the adoption criteria on the CH route, so `chosen` = **5/3** (`G2_selection_corrected.json`). The historical `G2_selection.json` (7/3) is unchanged. |
| G4.2: CH route | Route heads gather only 3–4 endorsements because their local round is limited by their *cluster*, not by m. 48 of the 56 failed 9/5 rounds had a head with only 2–3 eligible cluster neighbours. A separate local quorum would not weaken the main certificate rule, which every receiver and the RSU check. Its forgery effect is **unmeasured**. Recommendation: keep the global quorum at 5/3. Evaluate a separate local quorum only if a larger source committee is pursued. |
| G4.3: configuration | Best-supported: **5/3 with `ENFORCE_COMMITTEE=1`** (G1). **k = 4** adds a real but narrow benefit (phased attackers with 3–6 s off-windows), and most of its forgery gain overlaps with enforcement. Defaults stay 5/3, enforcement off, detector off. |

## 2. G4.1: committee selection defect and fix

**The defect** (in `adversarial.select_committee`, used for G2):
1. **It ranked every G2 configuration.** The loop ran over `COMMITTEES`, which includes the 7/3 contrast arm, and the
   admissible set was ranked without a candidate filter. 7/3 has the highest pooled genuine acceptance (98.5 %), so it
   was "chosen". The plan (section 4.1) lists 7/3 as a contrast only, and safeguard 5 forbids a weaker quorum.
2. **It could not select nothing.** `max()` over an empty admissible set would raise, so "no configuration qualifies"
   was not expressible.

**The fix** (`adversarial.py`):
- **`COMMITTEE_CANDIDATES = [(5, 3), (7, 4), (9, 5)]`:**
  - only these can be selected;
  - 7/3 is still evaluated and reported, with `"candidate": false`.
- **The registered rule is kept exactly** (`PREREGISTERED["G2_admissible"]` and `["G2_selection"]`, unchanged). Its
  result is recorded as `selection_rule_choice`.
- **`chosen` also requires `ADOPTION_RULE`.** This is plan section 8 criterion 2 (genuine acceptance and delivery not
  lower than Block F on any seed) applied to both genuine paths of the proposed design:
  - the proposed broadcast (the registered criterion 2);
  - the CH route: honest delivery and relayed RSU reception, strict, on seeds where both arms accepted the genuine
    alert.
- **Disclosure:** the CH-route scope of criterion 2 was stated in `G2_RESULTS_REPORT.md` section 7 after the G2 results
  were seen. The plan's text names no scheme, and this applies it as written rather than narrowing it.
- **`chosen` is `None`** when no candidate qualifies. G4 then reports "not run".
- **Output file:** `G2_selection_corrected.json`. The historical `G2_selection.json` is never written again; its sha256
  is unchanged.
- **G4's input:** `adversarial._choices` (which G4 reads) now uses the corrected file and returns (k = 4, 5/3).

**Result on the existing G2 runs** (no simulation re-run):

| m/q | Candidate | Admissible (registered) | Withholding-explained regressions | CH-route violations (delivery / relay) | Adoptable | Pooled genuine | Pooled forgery |
|---|---|---|---|---|---|---|---|
| 5/3 | yes | yes | 0 | 0 / 0 | **yes** | 89.63 % | 6.11 % |
| 7/4 | yes | yes | 3 | 18 / 18 | no | 93.15 % | 3.89 % |
| 9/5 | yes | yes | 2 | 37 / 34 | no | 96.67 % | 1.85 % |
| 7/3 | **no** (contrast) | yes | 0 | 0 / 0 | no | 98.52 % | 16.85 % |

- **Registered rule:** 9/5.
- **Chosen** (meets the adoption criteria): **5/3**.
- **9/5 is not the winner** despite the lowest forgery acceptance: it loses CH-route delivery on 37 seeds and RSU
  reception on 34.

**New tests** (`validation/test_hardening.py`):
- `test_the_seven_three_contrast_can_never_be_selected`: 7/3 is admissible and would win the ranking; it is still
  never selected.
- `test_the_registered_rule_ranks_admissible_candidates_by_genuine_acceptance`: the rule is applied as registered
  (highest pooled genuine acceptance, then fewest forgeries, then smallest committee).
- `test_ch_route_losses_block_adoption_but_not_the_registered_rule`: a candidate that wins the registered rule but
  loses CH-route RSU reception is reported as `selection_rule_choice` and not chosen.
- `test_no_committee_is_selected_when_no_candidate_qualifies`: chosen is `None`, `_choices` returns no committee, and
  `main("G4")` returns "not run".
- The existing selection test now also checks that `G2_selection.json` is never written and that 7/3 is not a
  candidate.

## 3. G4.2: CH-route quorum

### 3.1 How the CH route verifies

- **Main certificate first** (`protocols.Protocol.on_alert`, [protocols.py:119-145](../../protocols.py#L119-L145)):
  - every receiver, route heads included, checks the source certificate (QUORUM of the COMMITTEE_SIZE-seat committee,
    committee-checked when enforced);
  - a failed certificate means reject, with no further processing;
  - only an accepted alert reaches `first_copy`.
- **The RSU checks the main certificate too:** it registers an event only if that certificate passes
  (`metrics.run_metrics` passes `proto.cert_ok` to `rsu.register`, [metrics.py:99](../../metrics.py#L99)).
- **Local round at each route head** (`CHRoute.first_copy` / `on_receive`, [protocols.py:177-214](../../protocols.py#L177-L214)):
  - the head runs a local round before forwarding;
  - voters are other vehicles in **its DBSCAN cluster** that are in its radio range, reputable (trust ≥ gate), and not
    the source; at most `COMMITTEE_SIZE` of them;
  - attackers stay silent; the head's own proposal counts as one endorsement;
  - the head forwards once `len(received) >= QUORUM` and the local certificate passes `corroboration.accept`;
  - the forwarded frame carries the *main* certificate; the local one is never sent on.
- **So the local round is an extra forwarding gate on the CH path.** It is not part of the certificate any receiver
  checks.

### 3.2 Why route heads gather only 3–4 endorsements under 9/5

The analysis rebuilds every local round in the G2 raw records exactly as `first_copy` does (`analysis/g4_ch_route.py`).

| m/q | Local rounds | Succeeded | Failed: cluster too small (< q−1 eligible members) | Failed: silent attackers (≥ q−1 eligible, < q−1 honest) | Failed: radio |
|---|---|---|---|---|---|
| 5/3 | 172 | 162 (94.2 %) | 0 | 10 | 0 |
| 7/3 | 181 | 171 (94.5 %) | 0 | 10 | 0 |
| 7/4 | 175 | 143 (81.7 %) | 20 | 12 | 0 |
| 9/5 | 173 | 117 (67.6 %) | **48** | 8 | 0 |

**Eligible cluster neighbours per head**, capped at m: 2 for 20 heads, 3 for 28, 4 for 6, and 5 or more for the rest
(9/5).

**Why this happens:**
- **The cluster sets the ceiling, not m.** DBSCAN uses eps 40 m and min_pts 3, and the members must also be in the
  head's radio range and reputable.
- **Small clusters cap the endorsements:** a head with 2 eligible members can collect at most 1 + 2 = 3 endorsements;
  with 3 members, at most 4.
- **Raising m adds no members to a small cluster, while raising q raises the bar.** At q = 5 those 48 heads (28 %) can
  never succeed. At q = 3 every head had at least 2 eligible members, and the only failures were silent attackers.
- **This matches the G2 observation:** in the seeds where 9/5 lost a relay that 5/3 delivered, the short head had
  exactly 3 or 4 endorsements.

### 3.3 A separate local quorum: implications

Assessed, not implemented. The global `QUORUM` is unchanged.

- **Main certificate rule:**
  - it is **not weakened** by a separate local quorum `q_local`;
  - every vehicle and the RSU accept only on the main certificate (section 3.1);
  - `q_local` only decides whether a route head forwards an alert that already passed it.
- **Genuine delivery:**
  - `q_local = 3` would remove the cluster-size failures;
  - the closest measured analogue is 7/3 (q = 3 in every local round), with 94.5 % of local rounds succeeding and
    68.8 % CH-relay reception, against 67.6 % and 48.0 % for 9/5;
  - this is a prediction for "9/5 main, 3 local"; it has not been measured.
- **Forgery on the CH path:**
  - **unmeasured**: the forged-alert test runs only the proposed broadcast and its ablations, never the CH route;
  - in the CH-route model, honest local voters endorse unconditionally, so the model cannot show whether local rounds
    stop a forged alert whose main certificate passed;
  - in a real deployment, honest members would endorse only what they observe;
  - a lower `q_local` would let colluders who hold a local majority push such an alert further along the CH path;
  - this matters only for forgeries that already beat the main certificate (G2, 9/5: 1.9 % of runs; G1, 5/3:
    47/3060 = 1.5 %).
- **Rejected variants:**
  - a local quorum that adapts to cluster size (for example, a majority of whoever is eligible) lets small or captured
    clusters forward on fewer endorsements;
  - it has the same problem as the adaptive escalation rejected in plan section 4.1.

**Recommendation:**
- **Keep the CH route on the global quorum.** At the chosen 5/3 the local quorum is 3, and there is no conflict.
- **Evaluate a separately defined, fixed local quorum only if a larger source committee is pursued.** That would mean:
  - an opt-in `CH_ROUTE_QUORUM`, defaulting to `QUORUM`, so nothing changes by default;
  - a pre-registered "9/5 main, 3 local" arm;
  - a new CH-route forgery test in which honest local voters endorse only genuine alerts.
- **The original CH-route results stay in every table** (`G2_RESULTS_REPORT.md`, `BLOCK_G_TABLES.md`). The CH route is
  not excluded from any evaluation.

## 4. G4.3: proposed combined configuration

**Evidence:**

| Component | Evidence | Benefit | Cost |
|---|---|---|---|
| `ENFORCE_COMMITTEE=1`, 5/3 (G1) | 34 Block F settings, 3060 runs | Default-level forgeries **1200 → 47** of 3060; voting-only 2748 → 126 | None measured: genuine `runs.csv` byte-identical in 34/34 settings (genuine accepted 2958 = 2958) |
| Larger committee 7/4, 9/5 (G2) | 24 settings | Fewer withholding failures and forgeries on the source path | Fails the adoption criteria: CH-route delivery and RSU reception lost on 18–37 seeds; more vote frames and +0.5 to +1.0 ms quorum delay |
| `TRUST_BURST_K=4` (G3b) | 19 settings, paired with gate 0.70 and gate 0.75 | Phased 0.9/30 s: forged acceptance 77.8 → 18.9 % and 95.6 → 24.4 %; phased 0.8/30 s: 30 → 0 % | About 0.7–0.8 % honest exclusion (37 % of runs above 1 %, maximum 3.75 %); no gain for per-second or 10 s-period attackers (gate 0.75 is better there) |

**Combining enforcement with burst detection:**
- **Most of the detector's forgery gain overlaps with enforcement.**
  - In the 19 G3b settings, k = 4 cut default-level forgeries from 969 to 697 (of 1710).
  - At the committee level, which is what enforcement gives (G1 matched in 3060/3060 runs), the cut is only
    **31 → 28**.
  - Expected forgery gain of k = 4 on top of 5/3 with enforcement: about 3 forgeries per 1710 runs.
- **What it would still add:**
  - fewer attackers on committees and in CH roles for phased attackers with long off-windows (for example, attacker
    CHs 3.67 → 2.37 per run at phased 0.9/30 s, 20 %);
  - small genuine-acceptance gains from less withholding (up to +5 of 90 seeds).
- **What it would still cost:** the same 0.7–0.8 % honest exclusion, and about 0.1–0.2 honest cluster heads replaced
  per run, in every setting.
- **What G4 would therefore show** (5/3 + enforcement + k = 4, the pre-registered G4 with the corrected selection):
  - forgery about equal to G1's;
  - genuine acceptance and CH roles about G3b's;
  - G4 would be mainly confirmatory; it covers all 34 B and C settings, about 35 min.

**Proposed G4 configuration:**
- **5/3 with `ENFORCE_COMMITTEE=1`**, optionally with `TRUST_BURST_K=4`.
- Without the detector, G4 equals G1 and is not run again (pre-registered rule).
- **Defaults stay 5/3, enforcement off, detector off.** A default change needs its own approval (plan section 8,
  criterion 5).
- **The best-supported default candidate is enforcement.** Its forgery reduction is large and its measured genuine
  cost is zero. Flipping it would change the tracked forgery results.

## 5. Decisions that need your approval

1. **CH-route scope of the adoption criteria.** Should criterion 2 include the CH route, as applied here (→ 5/3)? Or
   should it cover only the proposed scheme, as the registered G2 criterion 2 text says (→ 9/5)?
2. **G4 configuration.** Run 5/3 + enforcement + k = 4 as a confirmatory measurement, or skip G4 (G1 already covers
   5/3 + enforcement)?
3. **Burst detector.** Keep it as an optional, opt-in component for phased attackers, given the 0.7–0.8 % honest
   exclusion and the weaker per-second result?
4. **Separate CH-route quorum.** Pursue it (opt-in `CH_ROUTE_QUORUM`, a pre-registered "9/5 main, 3 local" arm and a
   CH-route forgery test), or close the larger-committee question at 5/3?
5. **Default flip** of `ENFORCE_COMMITTEE` to 1. This is a separate decision, and it changes the tracked forgery results.

## 6. Integrity and tests

- **Code changes in this stage:** see section 2 (`adversarial.py`: candidates, adoption rule, corrected output file,
  `_choices`) and the new tests. `blockg_tables.py` now shows the corrected selection next to the historical one.
- **Tests after the final code change:**
  - `python -m pytest validation -q`: **162 passed** (158 + 4 new selection tests), after `python build_portal_assets.py`
    refreshed the portal source bundle;
  - `python -m pytest veremi -q`: **26 passed**.
- **Earlier results:** a sha256 manifest of all 14,226 earlier result files (Block F, G1, G2, G3a) matches, except:
  - `BLOCK_G_TABLES.md`, the regenerated derived tables;
  - `analysis/blockg_tables.py`, the table script;
  - `sweep_log.txt`, appended to.
- **G3b run folders:** no file was modified after its sweep finished.
- **`results/urban` is clean.**
- **Code:** since before G3a, only `adversarial.py` changed (the G3b_gate comparison arm and this selection fix).
  `config.py`, `scenario.py`, `experiment.py`, `corroboration.py`, `protocols.py`, `infrastructure.py` and
  `clustering.py` are hash-identical.
- **Defaults:** `TRUST_BURST_K=0`, `ENFORCE_COMMITTEE=0`, `COMMITTEE_SIZE=5`, `QUORUM=3`, gate 0.70.
