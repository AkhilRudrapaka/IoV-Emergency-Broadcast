# Block G final report: security hardening of trust-aware emergency alerts

**Status:** complete (2026-11-21). Committed in `81d416e` and published on `origin/akhil`, except the per-run CSVs and
raw records.

**Scope:** simulation only. SUMO 1.27.1, Python 3.11.4, `network/urban.net.xml` (hand-built synthetic 5×5 grid with synthetic traffic demand; an OSM import was attempted but not completed, so no OSM data is used). No
result here is a real-world validation.

**Labels used throughout:**
- **[M]**: measured in this simulation;
- **[A]**: analytical expectation;
- **[D]**: design decision (approved).

**Evidence:** every number below traces to a CSV through the reports and analysis scripts listed in section 12.

## 1. Research objective and security problem

**Objective:** harden the emergency-alert certificate path against the gaps Block F measured, without weakening
genuine-alert availability or changing the cryptography, source authentication or the 0.70 reputation gate.

**Problems found in Block F** (`BLOCK_F_ADVERSARIAL_REPORT.md`):
- **W1: any reputable signers counted.** The certificate check accepted any ≥ 3 reputable signers and never checked
  that they were the committee of the claimed incident. **[M]**
  - On-off attackers (per-second cooperation 0.9) keep their Beta trust above the gate: only 1.7 % fall below 0.70
    (0.3 % for phased 0.9/30 s).
  - With reputable colluders, a forged alert was registered at the RSU in 25 of 30 runs of the tracked on-off set.
  - Across the Block F B and C grids, 1200 of 3060 runs accepted a default-level forgery, and 2748 at the voting-only
    level.
- **W2: vote withholding.** A genuine alert fails when at least m − q + 1 = 3 attackers sit on the 5-seat committee.
  This held in 189/6120 runs, with no exception. **[M]**
- **W3: on-off attackers rank low but stay above the gate.** AUC is 0.935 for per-second 0.9 attackers and 0.959 for
  phased 0.9/30 s, but almost none fall below 0.70. **[M]**

## 2. Final architecture and implemented changes

| Component | Implementation | Default |
|---|---|---|
| Committee membership enforcement (`ENFORCE_COMMITTEE`) | `corroboration.accept(..., committee=)` counts only endorsers in the committee that the **receiver rebuilds** (the 5 nearest reputable neighbours of the claimed position). Applied at all five check sites: source release and every receiver (`protocols.py:112`), CH-route local rounds (`protocols.py:209`), `infrastructure.cluster_votes`, `infrastructure.batch_authenticate`, `incident_response.accepted_by`. A committee listed in a certificate is never used. | **ON (1)**; `EXP_ENFORCE_COMMITTEE=0` reproduces Block F |
| Committee size / quorum | Unchanged 5 / 3 (G2 evaluated 7/4, 9/5 and the 7/3 contrast). | 5 / 3 |
| Burst detector (`TRUST_BURST_K`) | `scenario.build` counts consecutive failed watchdog observations per vehicle, with no random draw. A vehicle whose longest run ≥ k is flagged; `decision_trust` caps it at the prior 0.5 for every eligibility decision. The recorded Beta trust is never changed. | **OFF (0)**; k = 4 opt-in |
| CH-route quorum | Uses the global `QUORUM`; no separate local quorum. | — |
| ML (VeReMi) | Shadow only; never used for any decision. | `ML_TRUST_MODE="off"` |
| Evaluation code | `adversarial.py`: sweeps G1–G4, the corrected committee selection, the G3b gate-0.75 comparison arm, G4 de-duplication. Tests in `validation/test_hardening.py`. | — |

**Unchanged [D]:**
- BLS12-381 signing and verification;
- source authentication;
- the Beta trust formula;
- the 0.70 gate;
- the forgery adversary (`MAX_COLLUDERS` 5);
- no timeout, fallback or adaptive quorum.

## 3. G1: committee enforcement

**Setup:** the 34 Block F B and C settings, 3060 runs (`BLOCK_G_TABLES.md`, G1).

| Measure | Block F | G1 (enforced) |
|---|---|---|
| Genuine `runs.csv` | — | byte-identical in **34/34** settings **[M]** |
| Default-level forged alert accepted | 1200 / 3060 | **47 / 3060** **[M]** |
| Voting-only forged alert accepted | 2748 / 3060 | **126 / 3060** **[M]** |

- **Equivalence with the committee check:** the default-level decision under enforcement equals Block F's opt-in
  committee-level decision in **3060/3060** runs. **[M]**
- **New default on the tracked scenarios** (2026-11-21, `analysis/final_baseline_check_output.txt`):
  - genuine CSVs are byte-identical; **[M]**
  - voting-only forgeries registered at the RSU: 134/180 → **1/180** (default matrix); **[M]**
  - on-off 0.9 set, default level: 25/30 → **0/30**; **[M]**
  - the remaining voting-only case: that level ignores reputation, so its committee is simply the 5 nearest vehicles,
    and 3 colluders were among them. **[M]**

## 4. G2: committee size, and why 5/3 was retained

**Setup:** 24 settings, 540 runs per configuration (`results/hardening/G2_RESULTS_REPORT.md`).

| m/q | Genuine accepted | Forged accepted | CH-route local rounds succeeded | CH-route violations vs Block F (delivery / RSU relay) |
|---|---|---|---|---|
| 5/3 | 89.6 % | 6.1 % | 94.2 % | 0 / 0 |
| 7/4 | 93.1 % | 3.9 % | 81.7 % | 18 / 18 |
| 9/5 | 96.7 % | 1.9 % | 67.6 % | 37 / 34 |
| 7/3 (contrast) | 98.5 % | 16.9 % | 94.5 % | 0 / 0 |

- **Measured [M]:**
  - every genuine failure was explained by withholding;
  - committees were always full;
  - 9/5 costs +3.3 vote frames per alert and +1.0 ms quorum delay.
- **Selection [D]:**
  - the registered selection rule picks 9/5;
  - under the adoption criteria, which include the CH route (approved), only **5/3** qualifies
    (`G2_selection_corrected.json`);
  - 9/5 was not adopted, despite its lowest forgery rate.
- **Selection bug, fixed [M]:** the original selection ranked the 7/3 contrast as a candidate and could not select
  nothing. The historical `G2_selection.json` (7/3) is kept unchanged.

## 5. G3a: burst detector calibration

**Setup:** held-out runs 30–59, 10 % attackers, 5 attacker types, k ∈ {3, 4, 5, 6} (`G3A_CALIBRATION_REPORT.md`).

**The rule:** the smallest k whose *mean* honest false-alarm rate over runs is ≤ 1 % in every setting and density.

| k | Worst mean honest flagged | Runs > 1 % (of 450) | Maximum run |
|---|---|---|---|
| 3 | 6.80 % | 450 | 11.11 % |
| **4 (chosen)** | **0.72 %** | **146** | **4.44 %** |
| 5 | 0.15 % | 12 | 1.11 % |
| 6 | 0.02 % | 0 | 0.56 % |

- **The cap is a mean, not a per-run guarantee [D].** k = 4 passes only the mean cap. Under a strict "every run ≤ 1 %"
  reading, only k = 6 would pass.
- **Calibration population [M]:** the four phased settings share one honest observation stream, so the calibration has
  2 independent honest samples per density.

## 6. G3b: burst detector evaluation (k = 4)

**Setup:** 19 Block F settings, runs 0–29, paired with Block F (gate 0.70) and a count gate at 0.75
(`G3B_EVALUATION_REPORT.md`).

| Attacker (share) | Attackers ineligible: no detector → k = 4 → gate 0.75 | Forged accepted: no detector → k = 4 → gate 0.75 |
|---|---|---|
| **phased 0.9/30 s** (10 % ; 20 %) | 0.6 → **40.7** → 7.2 %; 0.5 → **40.2** → 7.2 % | 77.8 → **18.9** → 68.9 %; 95.6 → **24.4** → 80.0 % |
| **phased 0.8/30 s** (10 %) | 33.6 → **100** → 82.4 % | 30.0 → **0.0** → 2.2 % |
| per-second 0.9 (10 %) | 1.6 → 8.7 → **12.5** % | 73.3 → 64.4 → **48.9** % |
| phased 0.8/10 s (10 %) | 31.8 → 39.1 → **86.9** % | 28.9 → 21.1 → **1.1** % |
| phased 0.9/10 s, 0.95/10 s, 0.95/30 s | ≤ 0.6 → 1.5–4.7 → 0.8–6.3 % | small reductions in both arms |

- **Measured [M]:**
  - the detector helps only against phased attackers whose off-windows are about 3 s or longer at a 30 s period;
  - **it does not improve per-second attackers:** gate 0.75 detects more, excludes far fewer honest vehicles, and
    accepts fewer forgeries;
  - gate 0.75 is also better for every 10 s period;
  - genuine acceptance: 15 gains, 0 losses.
- **Analytical [A]:** a count gate is better for per-second attackers because, for independent per-second behaviour,
  the failure count is a sufficient statistic.

## 7. G4: combined confirmation (5/3 + enforcement + k = 4)

**Setup:** 25 settings, 2250 runs, paired with Block F and G1 (`results/hardening/G4_CONFIRMATION_REPORT.md`).

- **Settings:** the nine 3-colluder B settings fold into the 5-colluder ones under the pre-registered
  `MAX_COLLUDERS = max(setting, m)` rule. The prepared runner's duplicate listing was removed. The B settings with
  3 colluders are not re-evaluated in G4; G1 covers them.

| Measure | Block F | G1 (enforcement) | G4 (enforcement + k = 4) |
|---|---|---|---|
| Default-level forgeries (2250 runs) | 969 | **31** | **28** |
| Genuine accepted, paired vs Block F | — | +0 / −0 | **+15 / −0** (p = 6.1e-5) |
| CH-route relayed RSU reception vs Block F | — | identical | +16 / −2 (p = 0.0013) |
| Honest exclusion per run (mean per density) | ≈ 0 % | ≈ 0 % | 0.68–0.82 %; 36 % of runs > 1 %; max 3.75 % |
| Quorum delay | 12.06 ms | 12.06 ms | 12.06 ms |

- **Measured [M]:**
  - **no additive forgery gain:** the detector removes 3 of the 941 forgeries that enforcement plus detector remove;
    enforcement alone removes 938;
  - the detector's added value is genuine availability against phased attackers with long off-windows;
  - enforcement changes no genuine or eligibility outcome: G4 equals G3b in 1710/1710 shared runs.

## 8. Honest false-alarm and availability costs

| Cost | Value | Type |
|---|---|---|
| Enforcement: genuine alerts | none: byte-identical genuine results (G1, 34/34 settings; default matrix 180/180 runs) | [M] |
| k = 4: honest vehicles excluded | 0.68–0.83 % per run on average (G3b, G4); above 1 % in 36–37 % of runs; max 3.75 % (4.44 % in G3a); one G3b cell exactly at the 1.00 % mean | [M] |
| k = 4: honest cluster heads replaced | about 0.1–0.2 per run in every setting, including settings where the detector adds nothing | [M] |
| k = 4: genuine-alert loss | none observed (0 losses in 1710 G3b and 2250 G4 paired runs); limited power at 10–20 % attackers | [M] |
| Larger committees (7/4, 9/5) | CH-route delivery lost on 18–37 seeds; +1.6 / +3.3 vote frames; +0.5 / +1.0 ms | [M] |

## 9. CH-route findings and why no separate quorum

- **The constraint is cluster size, not m [M]** (`G4_PREPARATION_REPORT.md`, `analysis/g4_ch_route.py`). CH-route
  local rounds take voters from the head's own DBSCAN cluster: in radio range, reputable, at most m. At q = 5, 48 of
  the 56 failed rounds had a head with only 2–3 eligible cluster neighbours, and so a ceiling of 3–4 endorsements. At
  q = 3 every head could reach quorum except where attackers stayed silent.
- **The main certificate rule is unaffected by the local round [A, from code].**
  - Every vehicle and the RSU accept only on the main certificate (`protocols.on_alert`; `metrics.py:99` into
    `rsu.register`).
  - The local round only gates forwarding on the CH path. A separate local quorum would therefore not weaken the main
    certificate rule.
- **The forgery effect of a local quorum is unmeasured.** The forged-alert test never runs the CH route, and the model's
  honest local voters endorse unconditionally.
- **Not implemented [D]:** 5/3 was retained, so local q = 3 already holds and there is no conflict. The original
  CH-route results stay visible in every table.

## 10. Final recommended configuration

| Setting | Value | Basis |
|---|---|---|
| `ENFORCE_COMMITTEE` | **1 (default)** | G1: large forgery reduction, no genuine cost [M]; approved [D] |
| `COMMITTEE_SIZE` / `QUORUM` | **5 / 3** | G2 adoption criteria incl. CH route [M, D] |
| `TRUST_BURST_K` | **0 (default)**; 4 opt-in for phased attackers | G3a/G3b/G4 [M]; approved [D] |
| `TRUST_CH_THRESHOLD` | 0.70 (unchanged) | — |
| `COMMITTEE_CHECK` | 0 (Block F opt-in reporting level; redundant under enforcement) | — |
| CH-route quorum | global quorum | [D] |
| `ML_TRUST_MODE` | `"off"` (shadow only) | [D] |

**Baseline reproduction:** `EXP_ENFORCE_COMMITTEE=0 EXP_TRUST_BURST_K=0`. This was verified byte-identical against the
tracked `results/urban` default matrix and on-off set, twice (before and after G4). **[M]**

## 11. Limitations, assumptions, unresolved questions

**Model assumptions:**
- Synthetic demand.
- An abstract watchdog (miss probability 0.1, one observation per second).
- One global reputation per vehicle.
- Honest voters observe ground truth.
- One incident per run.
- Unit-disk radio.

**Committee rebuilding** assumes receivers share the beacon positions and reputation snapshot that the simulation
records.

**Adversary:**
- `MAX_COLLUDERS` 5, attackers placed uniformly at random, 10–30 %.
- Collusion beyond 5 is evaluated only for larger committees (G2).
- The forged-alert test does not exercise the CH route.

**Burst detector:**
- The calibration cap is a mean; there is no per-run false-alarm guarantee.
- The calibration population has 2 independent honest streams per density.
- Gate 0.75 combined with k = 4 was never run.

**Demonstration record:** the published `results/urban/raw/d200_r02.json.gz` predates enforcement. The live incident
chain reproduces its genuine dissemination exactly; only its forged-alert section differs (the voting-only forgery is
now rejected).

**Documentation:** the portal (`portal/app.js`) now states the Block G defaults (`results/hardening/final/PORTAL_CORRECTIONS.md`).
The downloadable `Project_Website_Documentation_Portal.docx` is still stale: it says "two independent scenarios per
density" and does not mention Block G. Its generator, `create_portal_document.py`, needs `python-docx`, which is not
installed, and the project rule forbids adding dependencies. It must be regenerated where `python-docx` is available.

**Unresolved:**
- multi-event trust feedback (silence on corroborated events), the strongest proposed counter to withholding;
- per-observer reputation;
- a CH-route forgery model with honest local voters who endorse only real events;
- a decoupled local quorum, if larger source committees are ever pursued;
- whether more watchdog evidence can detect per-second on-off attackers.

## 12. Reproducibility

**Seeds:** seed = 10000 + 100·density + run.
- Evaluation: runs 0–29.
- Calibration: held-out runs 30–59.
- Densities: 100/200/300 (Block F/G).
- Default matrix: 50–500 vehicles.

Each sweep folder's `summaries/experiment_config.json` records its overrides, versions, commit and network hash.

```
python run.py adversarial G1 | G2 | G3a | G3b | G3b_gate | G4     # results/hardening/<sweep>/ (finished settings are skipped)
python -X utf8 results/hardening/analysis/final_baseline_check.py results/hardening/final_checks/<new folder>
python -X utf8 results/hardening/analysis/{g2_paired,g3a_calibration,g3b_evaluation,g4_ch_route,g4_confirmation}.py
python -X utf8 results/hardening/analysis/blockg_tables.py         # results/hardening/BLOCK_G_TABLES.md
python -m pytest validation -q ; python -m pytest veremi -q
```

| Evidence | Path |
|---|---|
| Plan and pre-registered rules | `BLOCK_G_SECURITY_HARDENING_PLAN.md`, `results/hardening/PREREGISTERED_RULES.json` |
| G1–G4 runs | `results/hardening/{G1,G2,G3a,G3b,G3b_gate,G4}/`, `results/hardening/*_runs.csv`, `*_summary.csv` |
| Reports | `results/hardening/{G2_RESULTS_REPORT,G3A_CALIBRATION_REPORT,G3B_EVALUATION_REPORT,G4_PREPARATION_REPORT,G4_CONFIRMATION_REPORT}.md` |
| Selections | `results/hardening/G2_selection.json` (historical), `G2_selection_corrected.json`, `G3a_calibration_choice.json` |
| Tables | `results/hardening/BLOCK_G_TABLES.md` |
| Baseline / new-default checks | `results/hardening/final_checks/` (`baseline_off`, `onoff09_off`, `default_on`, `onoff09_on`, `post_g4/`, `cleanup/`, `incident_demo/`, `incident_demo_cleanup/`) |
| k = 0 reproduction | `results/hardening/G3b_k0_check/` |
| Final test, integrity, configuration, changed-files, portal-correction and git-diff records | `results/hardening/final/` |
