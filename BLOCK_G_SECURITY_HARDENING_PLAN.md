# Block G: security hardening plan (read-only design audit)

**Date:** 2026-11-19. Branch `akhil`, uncommitted. This is a plan. No code was changed and nothing new was simulated.

**What the numbers below are:**
- Block F measurements: [BLOCK_F_ADVERSARIAL_REPORT.md](BLOCK_F_ADVERSARIAL_REPORT.md) and [results/adversarial/BLOCK_F_TABLES.md](results/adversarial/BLOCK_F_TABLES.md);
- analytic expectations, labelled as such.

**Nothing here claims an improvement.** Every proposed fix is a hypothesis with a pre-registered test in section 8.

## 1. Summary

| # | Block F weakness | Root cause | Proposed fix (smallest safe step) |
|---|---|---|---|
| W1 | Forged alerts are accepted when 3 reputable colluders sign. 1,200 of 3,060 at the default level against 47 of 3,060 with the opt-in committee check (sweeps B and C, gate 0.70). | `accept()` counts any reputable signer and never checks committee membership ([corroboration.py:109](corroboration.py#L109)). | Make committee membership part of the normal certificate check, behind a flag (`ENFORCE_COMMITTEE`, default off), at all five check sites. The committee is always derived by the receiver, never read from the certificate. |
| W2 | Vote withholding blocks genuine alerts: all 189 genuine failures in 6,120 runs had ≥ 3 attackers on the 5-seat committee. | Fixed quorum of 3 of 5. Silent members count as missing, with no timeout or fallback ([protocols.py:99-102](protocols.py#L99-L102)). | Evaluate larger majority committees (7 seats/quorum 4, 9 seats/quorum 5) together with W1's check. Both forging and blocking then need a local majority among more seats. This needs no new code: `COMMITTEE_SIZE` and `QUORUM` are already configuration values. |
| W3 | Attackers cooperating 90–95 % of the time pass the gate: 0–2.6 % detected at 0.70 (`BLOCK_F_TABLES.md`, Detection). | Cumulative Beta trust is a pass ratio. Expected attacker trust is 0.81–0.855 against 0.90 for honest vehicles, above any gate that spares honest vehicles. | (a) Do not raise the gate or weight failures more heavily: both only move the threshold (0.88 cost 34–38 % honest false alarms). (b) Add an opt-in burst detector on the watchdog sequence (`TRUST_BURST_K`, default off), calibrated with a false-alarm cap. It is expected to help only attackers with long "off" periods. |
| W4 | The calibration rule had no false-alarm limit, so it picked 0.88. | Rule design. | Every new calibration has a pre-registered honest false-alarm cap of ≤ 1 %. |
| W5 | Availability risks: no quorum fallback, committee shortfall, honest exclusion at high gates. | Single-shot corroboration; quorum fixed independently of how many reputable neighbours exist. | Measure committee fill and short-committee failures in every new sweep (W2). Do not add fallbacks that lower the quorum (section 4.1). |
| W6 | The committee check relies on positions and reputation that receivers rebuild themselves. | Simulation assumption: positions come from the recorded snapshot. | Document as a residual risk: a position-faking colluder could enter the rebuilt committee. Not addressed here; the ML detector stays shadow-only. |

## 2. Current implementation

| Mechanism | Where | What it does |
|---|---|---|
| Committee selection | [`corroboration.committee`](corroboration.py#L72) | The `COMMITTEE_SIZE` (5) nearest neighbours of the alert source that are within radio range (`adj`) and have trust ≥ `TRUST_CH_THRESHOLD` (0.70). The source's position is the claimed incident position. |
| Who votes | [`corroboration.plan`](corroboration.py#L79) | **Genuine:** honest committee members vote; attackers on the committee stay silent (withholding). **Forged:** the forger's nearest attacker neighbours (≤ `MAX_COLLUDERS`) vote, whether or not they are on the committee. |
| Vote collection and release | [protocols.py:93-113](protocols.py#L93-L113) | Committee members vote in rank order, one 0.5 ms slot each. The source releases on the `QUORUM`-th (3rd) distinct vote. **No timeout, no re-selection, no fallback:** if the quorum never arrives the alert is never sent (the simulation stops at 2 s, [channel.py:110](channel.py#L110)). |
| Certificate check | [`corroboration.accept`](corroboration.py#L97) | Source must be the first signer, the BLS aggregate must verify, signers must be distinct, and ≥ `QUORUM` endorsers must have trust ≥ 0.70. Block F added an optional `committee` argument (default `None`, unchanged behaviour). |
| Check sites | five calls | 1. source release, shared by every receiver and the RSU ([protocols.py:112](protocols.py#L112)); 2. CH-route local rounds ([protocols.py:207](protocols.py#L207)); 3. `cluster_votes` ([infrastructure.py:61](infrastructure.py#L61), no caller found); 4. `batch_authenticate` ([infrastructure.py:75](infrastructure.py#L75), called from [experiment.py:147-149](experiment.py#L147-L149)); 5. incident re-verification ([incident_response.py:96](incident_response.py#L96)). |
| Opt-in committee level | `COMMITTEE_CHECK=1` adds the `voting_reputation_committee` forgery level ([config.py:92](config.py#L92), [experiment.py:56](experiment.py#L56), [experiment.py:184](experiment.py#L184)) | Only the forgery test uses it; genuine dissemination never does. |
| Trust | [scenario.py:132-166](scenario.py#L132-L166), [`beta_trust`](clustering.py#L21) | Each second, a vehicle with a neighbour is observed relaying or not. An honest relay is missed with probability 0.10; an attacker fails unless it cooperates. Trust = (s+1)/(s+f+2) over every observation up to the incident (60–120 s), with no fading. One global value per vehicle. |
| On-off models | `MALICIOUS_COOPERATION` (per-second, independent); `ONOFF_PERIOD_S`/`ONOFF_DUTY` (phased, Block F, [scenario.py:142](scenario.py#L142)) | Attackers always drop the alert (unless `MALICIOUS_DROP_PROB` < 1) and always withhold genuine votes. |
| ML | `ML_TRUST_MODE = "off"` ([config.py:70](config.py#L70)) | Shadow-only by design; enforcement is refused. **Unchanged by this plan.** |

## 3. Root causes in numbers

**Withholding (W2).** Over all 6,120 Block F runs, the genuine alert failed **exactly** when ≥ 3 attackers sat on its committee: 189 failures, 0 exceptions. In general, with m seats and quorum q, the alert fails when attackers hold ≥ m − q + 1 seats. Committees were always full: 5 members in all 270 runs inspected at 100–300 vehicles, including at gate 0.88.

**Forgery (W1).** Accepted default-level forgeries had on average only 0.3–1.7 of their 3 reputable endorsers on the committee. The 51 forgeries the committee level still accepted all had 3 committee endorsers: 3–4 colluders held seats, mostly at 30 % attackers with cooperation 0.9.

**On-off (W3).** These are analytic expectations. Failure rate = (1 − duty) + duty × 0.10 for phased attackers, and 1 − 0.9 × cooperation for per-second attackers:

| Attacker | Expected failure share | Expected trust | Measured detection at 0.70 (Block F) |
|---|---|---|---|
| honest | 0.10 | ≈ 0.90 | (false alarm 0.0 %) |
| phased duty 0.5 | 0.55 | ≈ 0.45 | 100 % |
| phased duty 0.8 | 0.28 | ≈ 0.72 | 30.6–35.4 % (just above the gate) |
| per-second 0.9 / phased duty 0.9 | 0.19 | ≈ 0.81 | 0.3–2.6 % |
| phased duty 0.95 | 0.145 | ≈ 0.855 | 0.0–0.7 % (AUC 0.72–0.83) |

## 4. Design by area

### 4.1 Committee security and vote withholding (W2)

**Rejected options.** Each would let forged alerts in, or weaken the certificate:

| Option | Why rejected |
|---|---|
| Release after a timeout with fewer votes | Lowers the quorum for everyone. A forger with 2 colluding seats could then forge. |
| Adaptive escalation (if 5 seats fail, try 7, then 9) | Receivers cannot verify that a timeout happened, so a forger would claim whichever committee size has a colluder majority. Forgery success becomes the union over sizes, which is worse than any single size. |
| Excluding silent members and moving to the next-nearest | Receivers cannot verify silence. A forger would "exclude" honest members to bring colluders onto the committee. |
| Committee list carried in the certificate | A forger would list its colluders. The committee must be rebuilt by the receiver. |
| An "unconfirmed" alert class sent when no quorum forms | Keeps the information flowing, but forged alerts would flow the same way. Out of scope unless you accept that trade-off explicitly. |
| Lower quorum on a larger committee (e.g. 3 of 7) | Easier to reach for genuine alerts, but colluders also need only 3 of 7 seats. Included in the evaluation only as a contrast arm. |

**Proposed: a fixed, larger committee with a majority quorum, and committee membership enforced.**
- 7 seats with quorum 4, or 9 seats with quorum 5; the size is fixed in advance, never adaptive.
- **Why it is symmetric:**
  - forging needs colluders to hold a majority of the m seats nearest the claimed position;
  - blocking needs attackers to hold more than m − q seats.
- **Why it might help:** with attackers below 50 % and spread across the map, holding a majority of a larger local committee becomes less likely as m grows. This is a hypothesis, tested in experiment G2.
- **Costs to measure:**
  - more vote frames (`vote_tx`);
  - quorum delay grows by roughly 1–2 vote slots (0.5 ms each) plus processing;
  - committees may run short of m reputable neighbours at low density or high gate. There is no fallback, so a short committee cannot reach quorum q, and the genuine alert fails.
- **No new code:** `COMMITTEE_SIZE` and `QUORUM` are already configuration values used at every site ([corroboration.py:33](corroboration.py#L33), [protocols.py:31](protocols.py#L31), [infrastructure.py:15](infrastructure.py#L15)), and `EXP_` overrides take single values.
- **The forging adversary is kept at full strength:** `MAX_COLLUDERS` is set to m in these runs.

**Not proposed now:** multi-event trust feedback, where committee members who stay silent while the event is corroborated lose trust. It is the strongest long-term counter to withholding, but it needs several incidents per run, which is a bigger simulator change (section 10).

### 4.2 Forged-alert protection in the normal path (W1)

- **Why the opt-in level works.** It counts only endorsers among the committee that the receiver rebuilds for the claimed position. The forger's colluders are its nearest attacker neighbours, but the committee is its nearest reputable neighbours, which are mostly honest. So colluders rarely hold 3 seats: at most 1 in all 25 accepted on-off forgeries in d200 (Block F, phase 1 audit).
- **Proposed flag.** `ENFORCE_COMMITTEE` (default 0, so tracked results and default behaviour are unchanged). When 1, every check site passes the committee rebuilt by the receiver:
  1. source release ([protocols.py:111-113](protocols.py#L111-L113)): committee = `sec["committee"]` for every voting plan;
  2. CH-route local rounds ([protocols.py:207](protocols.py#L207)): committee = that head's round voters, i.e. the head plus its reputable cluster members. Without this the CH-route certificates would be rejected;
  3. `cluster_votes` ([infrastructure.py:61](infrastructure.py#L61)): committee = `members`, for consistency (no caller found);
  4. `batch_authenticate` ([infrastructure.py:75](infrastructure.py#L75)): each item carries its own committee (main committee or round voters), built in [experiment.py:147](experiment.py#L147);
  5. incident re-verification ([incident_response.py:96](incident_response.py#L96)): committee = the record's `committee`.
- **Security rule, enforced in tests.** The committee passed to `accept()` always comes from the simulator's rebuild (`corroboration.committee` for the claimed position), never from fields in the certificate.
- **Expected effect (to verify in G1):**
  - genuine outcomes stay identical, because 100 % of accepted genuine certificates passed the committee check in Block F;
  - default-level forgery acceptance falls to the Block F committee-level numbers;
  - per-run acceptance decisions are expected to match Block F's committee level. Delivery shares may differ slightly, because the levels use different channel random streams (`[seed, 100]` against `[seed, 103]`).
- **Decision for you.** Should enforcement also apply to the `voting_only` ablation? My recommendation is yes: membership is part of the voting rule, so the ablation would then isolate the reputation gate alone. It is your call.
- **Trade-off.** It assumes receivers can rebuild the committee (beacon positions and network-wide reputation); see W6. It does not stop 3 colluders who genuinely hold committee seats (26.7 % at 30 % attackers, cooperation 0.9, 200 vehicles).

### 4.3 On-off detection (W3)

- **Counts are the best possible statistic for per-second attackers.** With independent per-second behaviour, the pass and fail counts (s, f) are a sufficient statistic. No temporal reweighting (fading, windows, run lengths) can separate a per-second-0.9 attacker from honest vehicles better than counts, and fading only adds variance. With a fixed history length, detecting them better needs **more observations** (longer history) or **other evidence**, such as alert-dropping and withholding seen across several events.
- **Heavier failure weights and higher gates only move the threshold.** Trust (s+1)/(s+w·f+2) ranks vehicles almost exactly as the Beta mean does for the same counts, so it moves the operating point like the 0.88 gate did: in calibration, 94–99 % of attackers fell below 0.88, but so did 35–38 % of honest vehicles. Not proposed as a fix. It can be added as a contrast arm if you want it shown empirically.
- **Phased attackers do leave a temporal signature.** Their failures come in bursts of about L = (1 − duty) × period seconds of consecutive failed observations, while honest misses are scattered (p = 0.10):

| Duty \ period | 10 s | 30 s |
|---|---|---|
| 0.8 | L ≈ 2 | L ≈ 6 |
| 0.9 | L ≈ 1 | L ≈ 3 |
| 0.95 | L ≈ 0.5 | L ≈ 1.5 |

- **Proposed: an opt-in run-length detector.** It is the simplest temporal statistic, with one counter per vehicle and no random numbers. Setting `TRUST_BURST_K = k` (default 0 = off) flags a vehicle whose watchdog record contains k consecutive failed observations. A flagged vehicle's trust is capped at the uninformed prior, 0.5, so it is below every gate and excluded from cluster-head roles, committees and endorsement. The existing trust consumers stay unchanged.
- **Expected limits** (analytic; to be measured):
  - Honest vehicles produce k-runs at a rate of roughly N × 0.9 × 0.1^k over N ≈ 60–120 observations. A **≤ 1 % honest false-alarm cap** therefore probably needs k ≥ 4.
  - That would catch the long-off-period attacker (duty 0.8, period 30 s, L ≈ 6), sometimes duty 0.9 / period 30 s (when a miss extends the burst), and **not** duty 0.95 or any 10 s period.
  - Fully expected outcome: a modest, setting-specific gain. If calibration finds no k under the cap, the result is reported as negative and the detector stays off.
- **Not proposed:**
  - fading (exponential forgetting): it loses information against per-second attackers and only helps when behaviour changes over time;
  - ML enforcement: shadow-only stays.

### 4.4 Trust and alert availability (DoS register)

| Risk | Evidence | Mitigation in this plan |
|---|---|---|
| R1 vote withholding | 189/6,120 runs; up to 23 % of genuine alerts at 30 % attackers with cooperation 0.9 | W2 committee size (G2); multi-event feedback later |
| R2 committee shortfall (fewer than q reputable neighbours in range) | not observed at 100–300 vehicles (committees always full); possible at low density, with larger m, or at higher gates | report committee fill and short-committee failures; include 100 vehicles in every sweep |
| R3 honest exclusion by high gates | gate 0.88: 34–38 % honest below gate; CH-route RSU reception 77.8 → 55.6 % at 100 vehicles (n = 9, inconclusive) | keep gate 0.70; ≤ 1 % honest false-alarm cap for any new detector (W4) |
| R4 detector false alarms as a DoS lever | new with W3; honest vehicles flagged by unlucky misses | false-alarm cap; report flagged honest vehicles per run |
| R5 single-shot corroboration | no retry or second witness | not changed (section 4.1); documented |
| R6 committee rebuild relies on positions | position faking not modelled | documented residual risk; ML stays shadow-only |
| R7 forged-alert airtime | rejected alerts are not relayed; cost is the forger's frames plus colluder votes | none needed; transmissions reported |

## 5. Expected benefits and trade-offs (hypotheses to test)

| Change | Expected benefit | Possible cost |
|---|---|---|
| `ENFORCE_COMMITTEE=1` | Default-level forgery acceptance drops to the Block F committee-level numbers (for example 83.3 → 0 % at 10 % attackers, cooperation 0.9, 200 vehicles) | none expected for genuine alerts; relies on receivers rebuilding the committee (W6) |
| 7 seats/quorum 4, or 9 seats/quorum 5 | Fewer withholding failures and fewer committee-level forgeries at 20–30 % attackers | more vote frames, slightly longer quorum, possible shortfall at 100 vehicles |
| `TRUST_BURST_K` | Detects some phased attackers (long off periods) | honest false alarms (capped at ≤ 1 %); no gain against per-second attackers |

## 6. Minimal implementation sequence (after approval)

| Step | Change | Files | Default |
|---|---|---|---|
| G1 | `ENFORCE_COMMITTEE` flag; pass the receiver-rebuilt committee at all five check sites | `config.py`, `corroboration.py` (plan default), `protocols.py` (2 sites), `infrastructure.py` (2 sites), `experiment.py` (batch items), `incident_response.py` (1 site) | 0 = current behaviour |
| G2 | No code. Committee size and quorum through the existing `COMMITTEE_SIZE`/`QUORUM` overrides (`MAX_COLLUDERS` = m) | — | 5 / 3 |
| G3 | `TRUST_BURST_K` run-length detector in the watchdog loop; flagged trust capped at 0.5 | `config.py`, `scenario.py` | 0 = off; no random numbers drawn; trust identical |
| G4 | New sweeps `G1`–`G4` in `adversarial.py`, writing to `results/hardening/`; table script extended | `adversarial.py`, analysis script | — |
| G5 | Regression: default config reproduces every tracked `results/urban` CSV byte for byte (as in Block F); full test suites; portal bundle rebuilt | — | — |

Unchanged: certificate cryptography, the reputation gate, every Block F level, the ML shadow configuration and the tracked results.

## 7. Required tests

**Unit tests:**
1. `accept(..., committee=…)`:
   - outsider-signed certificate rejected and committee-signed accepted, with real BLS (exists for the opt-in path; repeated for the enforced path);
   - a committee list supplied inside a certificate is ignored.
2. `ENFORCE_COMMITTEE=1` on the hand-built network:
   - genuine alert accepted;
   - forged alert from 3 reputable non-members rejected;
   - CH-route local round with the head's reputable cluster voters accepted;
   - `batch_authenticate` accepts the same certificates as the protocol;
   - `incident_response.accepted_by` agrees.
3. Committee size and quorum overrides: `plan` returns m members, and the release needs q votes. **Withholding rule:** with m seats and quorum q, ≥ m − q + 1 silent attackers means no certificate; m − q silent attackers still give a certificate.
4. `TRUST_BURST_K`:
   - off: trust identical to the Block F stream, no random draw;
   - isolated misses are not flagged;
   - k consecutive failures are flagged and trust is capped at 0.5;
   - deterministic for the same seed;
   - honest trust unchanged when no burst occurs.

**Integration tests:**
5. Defaults reproduce the tracked `d200_r02` record fingerprint, and the existing 144 tests pass unchanged.
6. `ENFORCE_COMMITTEE=1` on `d200_r02`:
   - genuine records identical to the default run (all 13 schemes);
   - forgery decision equal to the Block F committee level.
7. Burst detector on `d50_r03`: deterministic, and only attackers with a k-run are flagged.
8. Sweep runner writes only to `results/hardening/`.

## 8. Reproducible evaluation plan

**Setup shared by every sweep:**
- Block F scenarios and seeds: densities 100, 200, 300;
- evaluation on runs 0–29; any calibration on held-out runs 30–59;
- seed = 10000 + 100·density + run;
- all 13 schemes plus the forgery levels; committee-level forgery test on (`COMMITTEE_CHECK=1`);
- tables use the Block F statistics: mean ± 95 % Student-t over runs, paired by seed against Block F.

| Sweep | Settings | Purpose | Approx. time |
|---|---|---|---|
| G1 enforce | Block F B (18) and C (16) settings with `ENFORCE_COMMITTEE=1` | **Must hold:** genuine rows identical to Block F; default-level forgery decisions equal to Block F committee-level decisions per run | ~35 min |
| G2 committee size | m/q ∈ {5/3, 7/4, 9/5} plus contrast 7/3 × attacker share {0.1, 0.2, 0.3} × attacker {per-second 0.9, phased 0.9/30 s}; `ENFORCE_COMMITTEE=1`, `MAX_COLLUDERS`=m | withholding failures, forgery acceptance, vote frames, quorum time, committee fill, short-committee failures | 24 settings, ~25 min |
| G3a burst calibration | k ∈ {3, 4, 5, 6} × attacker {per-second 0.9; phased 0.8/30 s, 0.9/30 s, 0.95/30 s, 0.9/10 s}, 10 % attackers, **held-out runs 30–59** | **Pre-registered rule:** smallest k with honest false alarm ≤ 1 % (mean per run) at every density. If none, report negative and stop G3. | 20 settings, ~20 min |
| G3b burst evaluation | chosen k on the Block F C grid (16) and per-second-0.9 B settings (3) | detection and false alarm against Block F; forgery and genuine effects | ~20 min |
| G4 combined | best m/q + `ENFORCE_COMMITTEE` + (k if G3 passed) on the Block F B and C grids | against Block F default (gate 0.70) and calibrated gate 0.88 | ~35 min |

Total about 2.3 h on 16 cores, about 2.5 GB under `results/hardening/`.

**Pre-registered adoption criteria** (decided before seeing results):
1. **No weakening:** for every setting and density, forgery acceptance at the default level is ≤ Block F's, and the BLS, reputation and source checks are unchanged.
2. **Genuine availability:** genuine acceptance and delivery are not lower than Block F's on any seed (paired), except failures fully explained by the measured withholding rule, which are reported.
3. **Fairness:** honest false alarm ≤ 1 % per run at every density for any new detector.
4. **Every outcome is reported**, including no gain or negative results, with confidence intervals and n.
5. **Default flip is a separate decision.** Changing any default (enforcement, committee size, detector) would change the tracked results and needs its own approval after the evidence.

## 9. Decisions for you

1. **Scope:** approve G1 (enforcement flag), G2 (committee-size evaluation, no code) and G3 (burst detector) as above, or a subset.
2. **`voting_only` ablation:** should enforcement apply to it? (Recommended: yes.)
3. **Optional contrast arm:** add a failure-weighted trust variant (W3), to show empirically that it only moves the operating point? It needs one more small opt-in setting.
4. **Output folder:** `results/hardening/`, or a subfolder of `results/adversarial/`.

## 10. Out of scope (not proposed in this block)

- **Multi-event simulation**, so that withholding and alert-dropping can lower trust in later events (the strongest expected counter to on-off attackers and withholding).
- **Second witnesses or multi-source corroboration.**
- **Position-plausibility checks for the rebuilt committee:** they would need the ML detector out of shadow mode, which is excluded.
- **Changes to cryptography, the reputation gate, or any Block F level, and model retraining.**
