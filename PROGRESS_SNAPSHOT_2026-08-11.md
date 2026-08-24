# PROGRESS SNAPSHOT — 2026-08-11

**Project:** Mitigation of Broadcast Storm for Reliable Emergency Message Dissemination in IoV
**Branch:** `akhil` (clean, in sync with `origin/akhil`) · **HEAD:** `1614f1a` (2026-08-09)
**Reviewer context:** Guide Review 1 window Aug 10–14, 2026
**Verification basis:** full source read + `pytest` run (52 passed, 22.59s) + inspection of committed output artifacts

> ⚠️ **Scope caveat on this review.** The two spec documents named in the review request —
> `P3_ML_TRUST_MODEL_SPEC.md` and `PHASE2_EXECUTION_PLAN.md` — **do not exist** in the working tree,
> anywhere else on disk under `~`, or in any commit in git history (`git log --all --diff-filter=D`
> returns no deleted `.md` files). Section 4 (Deviations) is therefore assessed against the only
> written plan that exists in-repo: the six-priority roadmap in `docs/PROJECT_REPORT.md` §5.2–5.3.
> **If those specs exist outside this repo, Section 4 must be re-run against them.**

---

## 1. Implementation Status per Module

| Module | Status | Completion | Evidence |
|---|---|---|---|
| **P1 — Adaptive DBSCAN** | ✅ **DONE** | 100% | `clustering.py`, `cluster_stability.py`, `cluster_head.py` |
| **P2 — BLS Batch Auth** | ✅ **DONE** | 100% | `bls_auth.py`, real BLS12-381 via `py_ecc` |
| **P3 — ML Trust** | 🔴 **NOT STARTED** *(as ML)* | 0% ML / heuristic base exists | `trust.py` — fixed-weight + EMA, zero learned components |
| **P4 — Probabilistic Broadcast** | 🔴 **NOT STARTED** | 0% | `broadcast.py` is deterministic cache suppression only |
| **P5 — Evaluation Harness** | 🟡 **PARTIAL** | ~40% | `comparison.py`, `metrics.py`, `graphs.py` |
| **P6 — Multi-RSU / Blacklist / Feedback** | 🟡 **PARTIAL** | ~25% | `rsu.py` + blacklist flag scattered across modules |

### P1 — Adaptive DBSCAN · DONE
Fully implemented and the strongest module in the codebase.
- Velocity-aware precomputed distance matrix: `0.6·pos_dist + 0.4·predicted_dist` at a 2.0 s horizon ([clustering.py:85-115](clustering.py#L85-L115)).
- Directional compatibility gate (>120° heading difference ⇒ `+1e6` penalty), with a stationary-vehicle safeguard at `speed ≤ 1.0 m/s` so post-accident queues still cluster ([clustering.py:107-110](clustering.py#L107-L110)).
- Persistent cross-step cluster identity via Jaccard best-overlap matching — correctly solves the fact that DBSCAN integer labels are not stable across steps ([cluster_stability.py:67-99](cluster_stability.py#L67-L99)).
- `ReclusteringController` with 4 trigger conditions (membership churn, mobility variance, trust delta, stability score) + minimum-interval gate ([cluster_stability.py:190-238](cluster_stability.py#L190-L238)).
- `"baseline"` ablation flag retained and tested.

*Only gap:* the O(n²) Python double loop in `_compute_mobility_distance_matrix` will be a wall at density 500 (250k pair computations per reclustering pass, per step). Not blocking, but see Risk R6.

### P2 — BLS Batch Auth · DONE
- Genuine BLS12-381 `Sign` / `Verify` / `Aggregate` / `AggregateVerify` via `py_ecc.bls.G2ProofOfPossession` — not a mock.
- Chain-signature model: sender + every active CH co-signs a distinct payload embedding `signer_id|role`, which correctly satisfies the distinct-message precondition for basic aggregate BLS (rogue-key resistance) — this is genuinely well-reasoned and documented at [bls_auth.py:42-47](bls_auth.py#L42-L47).
- Trust-gated split: high-trust signers aggregate-verified in one pairing; low-trust individually verified or rejected per `BLS_REJECT_LOW_TRUST`.
- Correct failure handling: aggregate failure falls back to per-item verification to identify the culprit ([bls_auth.py:164-168](bls_auth.py#L164-L168)).
- 4 ablation modes (`bls_batch` / `bls_individual` / `baseline` / `none`), synthetic benchmark harness, CSV export.
- 15 dedicated unit tests, all passing.

### P3 — ML Trust · NOT STARTED
**There is no machine learning anywhere in this codebase.** The only `sklearn` import in the entire repo is `DBSCAN` in `clustering.py`. No classifier, no regressor, no online learner, no `fit`/`predict` on trust, no model persistence, no feature extraction pipeline, no training data.

What exists in [trust.py](trust.py) is a **5-term fixed-weight linear score with an EMA history term** — a hand-tuned heuristic:
```
T = 0.30·T_fwd + 0.25·T_auth + 0.20·T_pdr + 0.15·T_hist + 0.10·T_rec
T_hist = 0.7·T_hist_prev + 0.3·T_current
```
Weights are hardcoded constants in `config.py`, never learned. Against the P3 scope in `PROJECT_REPORT.md` §5.3, the following are **all absent**: multi-dimensional feature model, message-consistency scoring, speed-stability scoring, historical reporting accuracy, trust decay over time, indirect RSU-recommended trust, and the online ML trust predictor feeding CH election.

**🔴 Blocking defect for P3 — ground-truth oracle leak.** Trust and classification read the simulator's `is_malicious` ground-truth label directly, in three places:
- [trust.py:97](trust.py#L97) — `if final_trust < THRESHOLD or vehicle.is_malicious:` → forces `MALICIOUS` classification
- [trust.py:45-49](trust.py#L45-L49) — malicious vehicles have their behavior counters synthetically degraded before scoring
- [vehicle.py:110](vehicle.py#L110) — `if self.is_malicious or self.is_blacklisted or self.trust < 0.3:` → forces `MALICIOUS`

The consequence: **detection accuracy is unmeasurable and any figure derived from it would be circular** — the system classifies malicious nodes correctly because it is told which ones they are. `docs/ALGORITHMS.md` → *Honest Scope Notes* partially discloses this ("does not yet perform unsupervised anomaly detection"), which is to the project's credit, but the disclosure understates it: it is not merely that detection is absent, it is that the ground-truth label is a live input to the classification path. **This must be severed before any P3 ML work begins**, or the ML model will train and evaluate against a leaked label.

### P4 — Probabilistic Broadcast · NOT STARTED
`broadcast.py` (75 LOC) implements deterministic message-ID cache suppression plus CH fan-out. Grep for `probabilit|p_persist|rebroadcast|counter_based|distance_based` across the repo returns **one** hit — `random.random() < 0.15` in `sumo_interface.py:140`, which is unrelated (malicious-vehicle spawn assignment). None of the P4 scope exists: no p-persistence, no timer-based/slotted rebroadcast, no trust-and-distance-aware forwarding probability, no geographic/zone-aware dissemination, no adaptive TTL or hop limits.

Note the current `broadcast_route` docstring ([broadcast.py:50-63](broadcast.py#L50-L63)) documents a genuine, correct bug fix — per-hop cache re-checking used to mislabel every hop after the first as a "blocked duplicate." Good catch, worth keeping in the writeup.

### P5 — Evaluation Harness · PARTIAL (~40%)
**Built:** density sweep across 5 densities, PROPOSED-vs-FLOODING dual-arm execution, 39-column metrics CSV, IEEE-style markdown/CSV comparison table generation, 11 matplotlib graphs, seeded RNG for reproducibility.

**Missing against P5 scope:** statistical reporting (no std dev, no confidence intervals — `_average_metrics` computes a bare mean over `runs=2`), malicious-ratio sweep, highway-vs-urban scenario sweep, and the ablation matrix across completed enhancements. Critically, **`comparison.py` never instantiates `ClusterManager` or `AuthenticationManager` in any mode other than the config default** — so despite P1 and P2 both shipping working ablation switches, *the harness has never exercised them.* The ablation capability exists but is unused.

**🔴 See Section 5 for the fabricated-delay defect, which is the most serious problem in this module.**

### P6 — Multi-RSU / Blacklist / Feedback · PARTIAL (~25%)
| Sub-feature | Status |
|---|---|
| Multi-RSU deployment (5 RSUs) | ✅ Done — `RSUManager.deploy_default_network()` |
| Nearest-RSU selection | ✅ Done — `get_nearest_rsu()` (Euclidean) |
| Per-RSU analytics + ACK | ✅ Done |
| RSU→sender trust bump | 🟡 Rudimentary — flat `+0.05` on the sender ([rsu.py:175](rsu.py#L175)), not a real feedback protocol |
| **RSU coordination / handoff** | 🔴 Absent — grep for `handoff\|handover` returns zero hits |
| **RSU global trust aggregation** | 🔴 Absent — grep for `global_trust\|aggregate_trust` returns zero hits |
| **Persistent blacklist** | 🔴 Absent — see below |
| **RSU/TCC → vehicle feedback loop** | 🔴 Stub — `disseminate_to_tcc_and_network()` is log-only, mutates nothing ([rsu.py:211-218](rsu.py#L211-L218)) |

The blacklist is **not persistent**. `is_blacklisted` is a per-vehicle boolean that `TrustManager.calculate_trust` fully recomputes every step and *clears* the moment trust recovers above threshold ([trust.py:102](trust.py#L102), [trust.py:105](trust.py#L105)). There is no cross-step blacklist store, no repeat-offender tracking, no RSU-held list. P6's "persistent blacklist for repeatedly malicious vehicles" is unimplemented.

---

## 2. Test Status

**52 passed / 0 failed / 0 skipped — 22.59s.** Suite is green. Environment: Python 3.10.12, all 7 runtime deps + pytest import cleanly.

| Test file | Tests | Target |
|---|---|---|
| `tests/test_bls_auth.py` | 15 | P2 |
| `tests/test_clustering.py` | 12 | P1 (5 clustering + 5 reclustering + 2 stability) |
| `tests/test_rsu.py` | 6 | P6 |
| `tests/test_authentication.py` | 5 | P2 legacy |
| `tests/test_routing.py` | 4 | Routing + `broadcast.py` (indirect) |
| `tests/test_accident.py` | 3 | Accident |
| `tests/test_metrics.py` | 3 | P5 |
| `tests/test_neighbor_discovery.py` | 3 | Infra |
| `tests/test_graphs.py` | 1 | P5 |

### Coverage gaps — ranked by risk

| Module | LOC | Coverage | Risk |
|---|---|---|---|
| **`trust.py`** | 160 | **ZERO** — no test file, never imported by any test | 🔴 **Critical.** This is the P3 foundation and the module with the oracle leak. About to be rewritten with no regression net. |
| **`comparison.py`** | 294 | **ZERO** | 🔴 **Critical.** Produces every headline number in the report. Largest untested module. |
| **`flooding.py`** | 88 | **ZERO** | 🔴 High. It is the *baseline comparator* — every "% improvement" claim is measured against untested code. |
| `sumo_interface.py` | 312 | ZERO | 🟡 Medium (hard to test; needs TraCI) |
| `vehicle.py` | 171 | ZERO (indirect only) | 🟡 Medium |
| `graphs.py` | 193 | 1 smoke test | 🟡 Medium |
| `cluster_head.py` | 68 | ZERO (indirect only) | 🟢 Low |
| `broadcast.py` | 75 | Indirect via `test_routing.py` | 🟢 Low |
| `messaging.py`, `utils.py`, `logger.py`, `config.py`, `generate_routes.py`, `main.py` | 358 | ZERO | 🟢 Low |

**14 of 23 source modules have no dedicated test file.** No coverage tool is configured (`pytest-cov` is not in `requirements.txt`), so no line-coverage percentage is available — the table above is by-module presence/absence.

---

## 3. File Inventory

There is no prior review marker in the repo, so "since last review" is taken as **the last two commits** (`bac4555` + `1614f1a`, both 2026-08-09), which constitute the demo-readiness restructure.

### Files touched since last review
| File | Change |
|---|---|
| `README.md` | +238 (new), then +1/−1 |
| `docs/ALGORITHMS.md` | +336 (new) |
| `docs/PROJECT_REPORT.md` | +161 (new) |
| `LICENSE` | +21 (new) |
| `pytest.ini` | +6 (new) |
| `requirements.txt` | +5 |
| `broadcast.py` | +28/−… (the `broadcast_route` duplicate-accounting fix) |
| `vehicle.py` | +23 |
| `rsu.py` | +17 |
| `accident.py` | +11 |
| `bls_auth.py` | +9 |
| `sumo_interface.py` | +34 |
| `tests/*.py` × 9 | moved from root → `tests/` (0 content change) |

**Total: 21 files, +870 / −19.**

### LOC per module (source, excl. tests)
| Module group | Files | LOC |
|---|---|---|
| **P1 Adaptive DBSCAN** | `cluster_stability.py` 279, `clustering.py` 123, `cluster_head.py` 68, `utils.py` 25 | **495** |
| **P2 BLS Auth** | `bls_auth.py` 418, `authentication.py` 109 | **527** |
| **P3 Trust** | `trust.py` 160 | **160** |
| **P4 Broadcast** | `broadcast.py` 75, `routing.py` 162, `flooding.py` 88 *(baseline)* | **325** |
| **P5 Evaluation** | `metrics.py` 330, `comparison.py` 294, `graphs.py` 193 | **817** |
| **P6 RSU** | `rsu.py` 267 | **267** |
| **Infra / sim** | `sumo_interface.py` 312, `accident.py` 266, `vehicle.py` 171, `generate_routes.py` 116, `config.py` 86, `main.py` 53, `neighbor_discovery.py` 53, `logger.py` 40, `messaging.py` 38 | **1,135** |
| **Tests** | 9 files | **866** |
| **Docs** | `ALGORITHMS.md` 336, `README.md` 238, `PROJECT_REPORT.md` 161 | **735** |

**Source total ≈ 3,726 LOC · Tests 866 LOC · Test-to-source ratio ≈ 0.23**

The LOC distribution tells the story plainly: P5 (817) and P2 (527) are the heaviest, while P3 sits at 160 LOC of heuristic and P4 at 75 LOC of cache logic. The two unstarted priorities are exactly the two thinnest modules.

---

## 4. Deviations

Assessed against `docs/PROJECT_REPORT.md` §5.2–5.3 (see scope caveat at top — the two named spec files do not exist).

| # | Deviation | Severity | Assessment |
|---|---|---|---|
| **D1** | **End-to-end delay is fabricated, not measured.** `comparison.py` assigns delay from hardcoded formulas: PROPOSED `delay_ms = 12.4 + len(route)·1.5` ([comparison.py:159](comparison.py#L159)); FLOODING `delay_ms = 28.7 + hops·3.2` ([comparison.py:170](comparison.py#L170)). No queuing, transmission, propagation, or contention model exists anywhere in the codebase. | 🔴 **Critical** | The published "65–68% delay reduction" is an **arithmetic consequence of two chosen constants (12.4 vs 28.7)**, not an experimental result. It would reproduce identically if the algorithms were swapped. This is the single most serious integrity issue in the project. |
| **D2** | **P1/P2 ablation switches exist but are never exercised.** Both priorities ship working mode flags; `comparison.py` instantiates `ClusterManager()` and `AuthenticationManager()` with defaults only. | 🔴 High | The roadmap's ablation requirement is unmet despite the enabling work being done. Cheap to fix — the plumbing already exists. |
| **D3** | **`runs=2` with no dispersion reporting.** `_average_metrics` returns a bare mean; seeds 42 and 52 only. | 🔴 High | Two runs cannot support a mean ± std or CI. Falls short of P5 scope and of any IEEE reviewer's expectation. |
| **D4** | **Malicious ratio hardcoded, bypassing config.** `comparison.py:87` uses `v_idx % 7 == 0` (≈14.3%) instead of reading `config.MALICIOUS_RATIO` (0.15). | 🟡 Medium | Breaks the project's own config-driven design and silently blocks the malicious-ratio sweep P5 requires. |
| **D5** | **Comparison harness bypasses SUMO entirely.** Synthetic grid seeding + random drift ([comparison.py:68-105](comparison.py#L68-L105)), not TraCI mobility. | 🟡 Medium | **Already disclosed** in `README.md:220`. Honest, but means P1's velocity-aware clustering is evaluated on synthetic straight-line drift — the mobility realism its gate is designed for is absent from the very experiment meant to validate it. |
| **D6** | **`steps` inconsistency.** `run_density_simulation` defaults to `steps=100`; `run_all_comparisons` hardcodes `steps=50` at call sites ([comparison.py:203-204](comparison.py#L203-L204)). Accident fires at step 20. | 🟢 Low | Cosmetic, but the published results are 50-step runs while the signature implies 100. Worth aligning before anyone reads the code. |
| **D7** | **Ground-truth oracle in the trust path.** Detailed in §1/P3 above. | 🔴 **Critical** | Partially disclosed in `ALGORITHMS.md`; the disclosure understates the severity. |

**Why the deviations happened (inferred):** D1, D4, and D6 all sit in `comparison.py` — the single largest module with **zero test coverage**. It was written early to produce demo-ready tables and has not been revisited since P1/P2 landed. D2 follows from the same cause: the harness predates the ablation switches and was never updated to use them.

---

## 5. Unvalidated Claims

**No `[TO MEASURE]` tags are present in the repo.** Grep across all `.py` and `.md` for `[TO MEASURE]|TODO|FIXME|TBD|XXX` returns only three hits, all of which are the word "placeholder" describing the legacy SHA-256 scheme — not open measurement markers. **The absence of tags is itself the finding:** unvalidated numbers are currently published *without* any marker distinguishing them from measured ones.

### 🔴 U1 — Delay reduction (65–68%) is not an experimental result
Published in `README.md:206-210` and `docs/PROJECT_REPORT.md`. Traceable directly to the hardcoded constants in D1. **Must not be presented to the guide as a measured outcome.**

### 🔴 U2 — Three mutually inconsistent result sets are committed simultaneously
| Source | Date | Baseline delay | Delay reduction | Duplicates @500 |
|---|---|---|---|---|
| `outputs/logs/comparison_results.csv` | **2026-07-31** | 47.9–55.9 ms | 64.7–68.4% | 26,294 |
| `README.md:206-210` | 2026-08-09 | *(matches CSV)* | 64.7–68.4% | — |
| `outputs/simulation_demonstration_report.md` | 2026-08-09 | **38.30 ms** | **55.87%** | **110,614.5** |

The demonstration report disagrees with the comparison CSV on **every** metric — duplicates differ by 4.2× at density 500. Both are committed and both are presentable artifacts.

### 🔴 U3 — The comparison CSV predates the work it purports to evaluate
`comparison_results.csv` is dated **2026-07-31**. All P1 and P2 source files are dated **2026-08-09**. **The headline comparison table was generated 10 days before velocity-aware clustering and BLS batch authentication existed.** Every "Proposed Algorithm" number in the README's main results table describes a pre-P1, pre-P2 codebase.

### 🟡 U4 — README's BLS benchmark table does not match the committed CSV
| N | README | `bls_benchmark.csv` (2026-08-09) |
|---|---|---|
| 1 | 290.1 ms ind / 294.0 batch / 0.99× | 362.6 / 362.6 / 1.00× |
| 5 | 1477.9 / 878.7 / 1.68× | 1794.3 / 1076.2 / 1.667× |
| 20 | 5867.6 / 2851.0 / **2.06×** | 7869.0 / 3770.1 / **2.087×** |

Speedup ratios agree closely; **absolute timings differ by 25–35%.** The README table came from an earlier or different-machine run and was never refreshed. The headline "2.06×" should read **2.09×** per the committed data.

### 🟡 U5 — BLS speedup is real but needs a stated caveat
The 2.09× is genuinely measured and the CSV is current. But ~360 ms per individual verification reflects **`py_ecc`'s pure-Python pairing implementation** — production BLS libraries (`blst`, `relic`) verify in ~1–2 ms. The *ratio* is the defensible claim; the absolute milliseconds are not representative of deployable V2X latency and will draw fire if presented without that note.

### 🟡 U6 — Two headline metrics are degenerate, not favorable
PDR is **100.0% for both arms at every density** (improvement +0.00%) and throughput is **0.82 Kbps for both** (gain +0.00%). Throughput is computed as `delivered_messages × 4.096 / (steps × 0.1)` ([metrics.py:98-101](metrics.py#L98-L101)) — with exactly one emergency message per run, this is a constant by construction and cannot differentiate anything. `README.md:220` discloses this honestly.

### ✅ What IS credibly measured
- **Broadcast overhead reduction (97.96–99.80%)** — real counter arithmetic (flooding forwards N−1 times; CH broadcast forwards once). Structurally near-tautological, but not fabricated.
- **Duplicate suppression (99.32–99.99%)** — real, from the flooding BFS duplicate counter. The strongest genuine result in the project.
- **BLS speedup ratio (2.09× @ N=20) and 20:1 signature compression (1920 B → 96 B)** — real, current, reproducible.
- **All P1 cluster-stability metrics** (lifetime, CH-change rate, connectivity, stability score) — real, computed, exported to `simulation_metrics.csv`.

---

## 6. Next Direction

### Verdict: **Challenge the proposed sequence.** P3→P5(parallel)→P4→P6 is wrong on two counts.

**Problem 1 — P5 cannot run in parallel with P3; it is a hard prerequisite for it.** The harness currently fabricates delay (D1), has never exercised an ablation switch (D2), and reports no dispersion (D3). Building P3 against that harness means the ML trust model gets evaluated by an instrument that cannot measure it — and P3's value shows up precisely in detection quality and delay under attack, the two things the harness handles worst. Parallelizing here does not save time; it produces a P3 whose results have to be thrown away and re-run once P5 is fixed.

**Problem 2 — P3 cannot start at all until the oracle leak (D7) is severed.** Training or evaluating a trust predictor while `is_malicious` is a live input to the classification path yields a model that is either trivially perfect or meaningless. This is a prerequisite, not a P3 subtask.

### Recommended order

**P5a (harness integrity) → P3 → P5b (statistical sweep) → P4 → P6**

**Stage 0 — Pre-work, ~1 day. Do this before Guide Review if at all possible.**
1. Sever the oracle: remove `is_malicious` from [trust.py:97](trust.py#L97), [trust.py:45-49](trust.py#L45-L49), [vehicle.py:110](vehicle.py#L110). Let classification derive from observed counters only. Expect detection quality to drop sharply — **that is the correct and honest result**, and it establishes the real baseline P3 must beat.
2. Write `tests/test_trust.py` first. `trust.py` is about to be rewritten and currently has zero regression protection.

**Stage 1 — P5a, harness integrity, ~2–3 days.** Non-negotiable before any new priority.
1. Replace fabricated delay with a computed model (per-hop transmission + queuing + verification cost). Even a simple analytic model is defensible; a hardcoded constant is not.
2. Wire `CLUSTERING_MODE` and `AUTHENTICATION_MODE` through `run_density_simulation` as parameters → unlocks the ablation matrix using switches that already work.
3. `runs` 2 → ≥10; add std dev and 95% CI to `_average_metrics`.
4. Read `MALICIOUS_RATIO` from config (D4); align `steps` (D6).
5. Write `tests/test_comparison.py` and `tests/test_flooding.py`.
6. Regenerate **all** artifacts; delete the two stale/contradictory result sets (U2, U3).

**Stage 2 — P3 ML Trust, ~1 week.** Now measurable. Build features from observed behavior only, add trust decay and indirect RSU-recommended trust, then layer the online predictor. Keep the current heuristic as the ablation baseline — the project's established pattern, and it works well.

**Stage 3 — P5b, full statistical sweep.** Density × malicious-ratio × scenario × ablation matrix.

**Stage 4 — P4 Probabilistic Broadcast.** Correctly placed *after* P3: trust-and-distance-aware rebroadcast probability consumes P3's trust output as an input. Building P4 first would mean re-tuning it once P3 changes the trust distribution underneath it.

**Stage 5 — P6.** Correctly last; genuinely depends on P3 (global trust aggregation) and benefits from P4.

**Net change from the proposed sequence:** P5's integrity half moves *ahead* of P3 rather than parallel to it, and a Stage-0 unblock is inserted. P4→P6 ordering is confirmed as correct.

---

## 7. Risks — Guide Review 1 (Aug 10–14)

| ID | Risk | Sev | Mitigation |
|---|---|---|---|
| **R1** | **Fabricated delay metric is discoverable.** `comparison.py:159` and `:170` are two greppable lines. A guide who opens the evaluation harness — the natural thing to do when a 68% improvement is claimed — sees hardcoded constants. This escalates from "incomplete work" to a **research-integrity question**, which is far harder to recover from. | 🔴 **Critical** | **Get ahead of it.** Either fix before the review, or state it unprompted: "delay is currently modeled by an analytic placeholder, not measured; it is the top item in the P5 fix list." Self-disclosure converts a credibility failure into evidence of rigor. Do **not** let the guide find it first. |
| **R2** | **Three contradictory result sets in one repo** (U2), one of them predating the features it evaluates (U3). Any two documents opened side by side disagree. | 🔴 **Critical** | Regenerate everything from one run today. If time is short, **delete** `outputs/simulation_demonstration_report.md` and the stale `comparison_results.csv` rather than present contradictions. One honest dataset beats three inconsistent ones. |
| **R3** | **"2 of 6 priorities complete" reads as 33% at the midpoint.** `PROJECT_REPORT.md:115` states it plainly. | 🔴 High | Reframe on evidence, not count: P1 and P2 are the two hardest and most novel modules and both are *fully* done — real BLS12-381 pairing cryptography, not a mock. Lead with the 52-test suite, the ablation-switch discipline, and the documented *Honest Scope Notes*. Present the P5-first resequencing as a deliberate, reasoned correction — it demonstrates exactly the judgment a reviewer wants to see. |
| **R4** | **Oracle leak challenged in questioning.** "How does the system know a vehicle is malicious?" is a natural first question, and the honest answer is currently "it is told." | 🔴 High | Prepare the answer. `ALGORITHMS.md` already discloses it — cite that disclosure, own the full extent, and present severing it as Stage 0 of the P3 plan with the expected accuracy drop stated in advance. |
| **R5** | **`trust.py`, `comparison.py`, `flooding.py` have zero test coverage** — 542 LOC producing every headline number, untested, while the README displays a "52 tests passing" badge. | 🟡 Medium | If asked about coverage, answer by module rather than by count. Adding `test_trust.py` alone materially improves the story and is a few hours' work. |
| **R6** | O(n²) Python clustering loop; a live density-500 demo may hang or crash mid-review. | 🟡 Medium | **Do not live-demo at 500.** Demo at 100–250 (README already recommends 250) and show pre-generated artifacts for 500. Rehearse the exact demo command end to end. |
| **R7** | Absolute BLS timings (~360 ms) look unusable for real V2X if presented without the pure-Python caveat. | 🟡 Medium | State the `py_ecc` caveat proactively; claim the **ratio**, note that `blst` reaches ~1–2 ms in production. |
| **R8** | Referenced planning documents (`P3_ML_TRUST_MODEL_SPEC.md`, `PHASE2_EXECUTION_PLAN.md`) do not exist in the repo. If they were promised as deliverables, they are missing. | 🟡 Medium | Confirm whether these exist outside the repo. If they were committed to the guide, reconstruct at minimum the P3 spec — Section 6 Stage 2 above provides its skeleton. |

### Minimum viable action before the review
If only a few hours are available, do these three in order:
1. **Regenerate all output artifacts from a single run** and delete the contradictory ones (R2). Highest credibility-per-hour.
2. **Prepare the disclosure script for the delay metric** (R1) — a rehearsed two-sentence self-disclosure.
3. **Rehearse the density-250 demo end to end** (R6).

---

## Summary

Two of six priorities (P1, P2) are genuinely, verifiably complete and are strong work — the BLS module in particular reflects real cryptographic understanding, and the ablation-switch discipline across both is exactly right. The suite is green at 52/52. The project's *engineering* is in better shape than its module count suggests.

The exposure is not in the unbuilt priorities — it is in the **evaluation layer**. The harness that produces every headline number fabricates its delay metric, has never exercised the ablation switches the completed priorities provide, reports no statistical dispersion, and has published three mutually contradictory result sets, the primary one generated before the features it claims to evaluate existed. That layer is also the largest untested module in the codebase, which is very likely why it drifted.

The correct next move is to fix the instrument before building anything else to measure with it, and to sever the ground-truth oracle before P3 begins. That resequencing costs roughly three days and converts the entire results section from indefensible to publishable.
