# Project Memory & Pipeline — IoV Broadcast Storm Mitigation

**What this file is:** the single self-contained briefing for this project — for a panel member, a new
collaborator, or an AI assistant starting cold. It states what the system does, what is genuinely built
versus not, where every number and citation comes from, and the rules the project is developed under.

**Last verified:** 2026-09-05. Basis: `pytest -q` → **94 passed**; full 7-density evaluation sweep re-run
from source; canonical live SUMO demo re-run and its printed summary transcribed; every citation below
spot-checked against the actual PDF text this session. Re-verify against current code before asserting any
of this as still true in a much later session.

---

## 1. Summary

This project replaces naive flooding of VANET emergency alerts with a trust-aware, mobility-aware,
cryptographically batch-authenticated dissemination pipeline, implemented end-to-end on SUMO/TraCI. Vehicles
are continuously scored by a four-factor Bayesian trust model with persistent RSU feedback; grouped by a
velocity-weighted DBSCAN variant; each cluster elects a Cluster Head from TRUSTED vehicles (with a documented
bootstrap fallback); a Cluster Head must obtain majority-vote corroboration from its own cluster before
forwarding; alerts then travel Cluster-Head-only over GPSR geographic routing with a real 300 m wireless-range
cap, right-hand-rule perimeter void recovery and a four-tier fallback chain; and the receiving RSU verifies a
BLS12-381 chain-of-custody signature using three-tier trust-gated verification, with a real ECDSA (NIST P-256)
ablation arm for honest comparison. Every reported number is produced by executing the system — nothing is
analytically projected or hand-entered — and every algorithm is traced to a specific paper on disk or
explicitly labelled this project's own contribution.

---

## 2. The 9-stage pipeline

```
 ┌─────────────────────────────────────────────────────────────────────┐
 │  SUMO / TraCI — live vehicle mobility (urban 5×5 grid, 700×700 m)   │
 └────────────────────────────────┬────────────────────────────────────┘
                                  ▼
 ①  Vehicle Classification & Bayesian Trust Update            trust.py
        T(v) = 0.80·(0.30·Tf + 0.25·Tc + 0.20·Ts + 0.25·Th) + 0.20·R(v)
        TRUSTED ≥0.70  ·  UNKNOWN 0.30–0.70  ·  MALICIOUS <0.30
                                  │  (trust feeds ②③⑥⑦)
                                  ▼
 ②  Velocity-Weighted DBSCAN Clustering (VWCA)            clustering.py
        d(i,j) = 0.6‖pᵢ−pⱼ‖ + 0.4‖p′ᵢ−p′ⱼ‖ ,  ε = 80 m, MinPts = 2
        + directional gate: reject pairs with Δheading > 120°
                                  ▼
 ③  Cluster Head Election                                cluster_head.py
        Score(v) = 0.6·T(v) + 0.4·SpeedStability(v),  TRUSTED-only
        + documented bootstrap fallback to UNKNOWN (avoids deadlock)
                                  ▼
 ④  Accident Event → Emergency Message                      accident.py
        2-vehicle collision; congestion propagates by alert radius
                                  ▼
 ⑤  BLS Chain-of-Custody Signing                            bls_auth.py
        sender + active CHs co-sign, capped at MAX_CHAIN_SIGNERS = 14
                                  ▼
 ⑥  Majority-Vote Confirmation  ── withhold ──▶ [not forwarded]
        >50% of the CH's own cluster must corroborate      broadcast.py
                                  ▼
 ⑦  GPSR Geographic Routing                                  routing.py
        300 m range cap on every hop · perimeter mode on voids · TTL 5
        fallback: own CH ≤80 m → trusted CH ≤300 m → any RSU ≤300 m
                                     → Store-Carry-Forward (honest fail)
                                  ▼
 ⑧  RSU Ingress Pipeline                                          rsu.py
        UUID cross-event dedup → 3-tier verify (aggregate / individual /
        reject-unverified) → decision → persistent trust feedback → ACK
                                  ▼
 ⑨  Metrics · CSV export · IEEE 300 DPI graphs      metrics.py, graphs.py
```

---

## 3. Status — built vs. not built

| Component | Status | Note |
|---|---|---|
| 4-factor Bayesian trust + persistent RSU feedback | ✅ | Rule-based/analytic, **not** machine-learned |
| Velocity-weighted DBSCAN (VWCA) + ε-sensitivity ablation | ✅ | ε re-tuned to 80 m for this topology, measured |
| CH election, TRUSTED-only + bootstrap fallback | ✅ | Fallback is a real deadlock fix |
| Majority-vote CH confirmation | ✅ | Own contribution |
| GPSR: 300 m cap, perimeter mode, 4-tier fallback | ✅ | Range check previously absent entirely |
| Multi-RSU delivery check | ✅ | Added 2026-09-05 — see §5.5 and §7 |
| Tiered BLS12-381 batch authentication | ✅ | 3-tier trust-gated |
| Real ECDSA (P-256) ablation arm | ✅ | Standard sign/verify, not the full NIZK protocol |
| RSU persistent trust feedback + UUID dedup | ✅ | Dedup correct but rarely exercised |
| Evaluation harness: 7 densities × 5 seeds × 5 events | ✅ | Synthetic mobility (see §8) |
| Proof-of-work citation mapping | ✅ | 8 papers read in full |
| ML-assisted trust model | ❌ | Trust is analytic |
| Adaptive/probabilistic geographic rebroadcast | ❌ | Majority-vote covers only part of the intent |
| Multi-RSU *coordination*/handoff | ❌ | 5 RSUs deployed; they do not coordinate |
| Persistent cross-run blacklist | ❌ | |
| Production PKI / certificate authority | ❌ | In-memory key registries |
| FORGED_RECOMMENDATION detection | ❌ | No recommendation-exchange mechanism exists |
| Full Naskar et al. NIZK ECDSA\* protocol | ❌ | Deliberately scoped down |
| Live-TraCI multi-density sweep | ❌ | Sweep uses the synthetic harness; the demo is real TraCI |

---

## 4. Citation corpus

Literature lives in **two** folders under `base papers/` — the second is easy to miss.

**`base papers/base papers/` — primary foundation (4 papers)**

| Ref | Paper | Grounds |
|---|---|---|
| [1] | Chen, Q. & Wu, Q. (2024). *Dynamic Networking Method of Vehicles in VANET.* Computers, Materials & Continua 81(1). DOI 10.32604/cmc.2024.054799 | VWCA clustering |
| [2] | Kaur, R.; Doss, R.; Pan, L. (2024). *The route based emergency message dissemination scheme…* Telecommunication Systems 87, 1183–1199. DOI 10.1007/s11235-024-01223-5 | CH-controlled dissemination; density set |
| [3] | Naskar, S. et al. (2025). *Authentication Framework With Enhanced Privacy and Batch Verifiable Message Sharing in VANETs.* IEEE TVT 74(12), p. 18556 ff. DOI 10.1109/TVT.2025.3587756 | Batch-verification premise |
| [4] | Azizi, M. & Shokrollahi, S. (2024). *RTRV: An RSU-assisted trust-based routing protocol for VANETs.* Ad Hoc Networks 154, art. 103387. DOI 10.1016/j.adhoc.2023.103387 | Direct+indirect trust; RSU as active participant |

**`base papers/Research paper-set1/` — ~25 papers; 7 read, 4 used**

| Ref | Paper | Corroborates |
|---|---|---|
| [6] | Zhang, Z. & Ye, N. (2026). *VANET-GPSR+.* Sensors 26(8), art. 2525. DOI 10.3390/s26082525 | Third independent 300 m range; verifies the Karp & Kung citation via its own reference list |
| [7] | Darabkh, K.A. et al. (2025). *Leveraging fog computing and SDN…* J. Supercomputing 81, art. 426. DOI 10.1007/s11227-024-06883-3 | Weighted multi-factor CH scoring (Lifetime/Distance/Speed) |
| [8] | Khan, A.W. et al. (2026). *Multi-criteria based stable clustering technique for VANETs.* Scientific Reports 16, art. 17086. DOI 10.1038/s41598-026-47837-4 | Weighted multi-factor CH scoring (CLS/Degree/PCL) |
| [9] | Qi, J. et al. (2024). *A hybrid-trust-based emergency message dissemination model for VANETs.* J. Information Security and Applications 81, art. 103699. DOI 10.1016/j.jisa.2024.103699 | Multi-source event corroboration premise (different mechanism) |

[5] Karp, B. & Kung, H.T. (2000). *GPSR: Greedy Perimeter Stateless Routing for Wireless Networks.* Proc. 6th
ACM/IEEE MobiCom, Boston MA, 6–11 Aug 2000. No local copy; title/venue/date corroborated **indirectly** via
[6]'s reference list — secondary verification, stated as such.

Two subfolders there are named "(Future Work)" by whoever assembled the corpus — independent confirmation of
scoping decisions already made here. **~18 papers remain unread**: treat "own contribution" as "not found in
the 8 papers actually read," not as a claim about all VANET literature.

> **Unverifiable-source warning.** The trust weights (0.30/0.25/0.20/0.25), EMA pair (0.85/0.15), RSU blend
> (0.80/0.20), tier cutoffs (0.7/0.3) and `MAX_CHAIN_SIGNERS=14` come from a "Final Project Report (Group 83)"
> that **does not exist anywhere on disk**. They cannot be audited. Treat them as own-contribution values with
> a stated but uncheckable provenance — not as literature citations. The surrounding *structure* is separately
> and genuinely cited.

The authoritative row-by-row mapping (~20 components: grounding, verbatim quoted evidence, adaptation made)
is `docs/ALGORITHMS.md` → **Proof-of-Work Mapping**. This file summarises it.

---

## 5. Algorithm reference

### 5.1 Bayesian trust — `trust.py`
```
t_current = (0.30·Tf + 0.25·Tc + 0.20·Ts) / 0.75
Th_new    = 0.85·Th_old + 0.15·t_current
Trust(v)  = 0.30·Tf + 0.25·Tc + 0.20·Ts + 0.25·Th
Final(v)  = 0.80·Trust(v) + 0.20·R(v)
```
- **Tf** forwarding behaviour — `successful_forwards / forward_attempts`; neutral 0.5 with no evidence.
  Grounded in [4] §4.2 (direct trust from monitored packet forwarding).
- **Tc** message consistency — claimed-vs-actual sender location, tolerance 50 m. **Own contribution.**
- **Ts** speed plausibility — kinematic feasibility, |Δspeed| ≤ 4.5 m/s (matches the SUMO vType's own
  `decel`), speed ≤ 22 m/s. **Own contribution.**
- **R(v)** persistent RSU assessment, nudged ±0.05 per verification outcome, blended every call.
- **Never reads `is_malicious`.** That flag only decides what an attacker's *actions* are.
- Structural finding: with no real events trust asymptotes at **≈0.61**, below the 0.70 TRUSTED gate — a real
  bootstrap deadlock, resolved in §5.3.

### 5.2 VWCA clustering — `clustering.py`
`d(i,j) = 0.6‖pᵢ−pⱼ‖ + 0.4‖p′ᵢ−p′ⱼ‖`, `p′ = p + v·H`, `H = 2.0 s`; +10⁶ penalty if Δheading > 120°
(gate skipped below 1 m/s); DBSCAN `ε = 80 m`, `MinPts = 2`.
Verified in [1]'s own table: *"Transmission range 300 m"*, *"ε (20, 40) m"*, and *"a value of 20 is more
suitable for the application scenarios in this paper"* — a 3-lane 3000 m **highway**. Measured here
(`eps_sensitivity.py`): ε = 20/40 m give 70–100% noise on this urban grid, so **ε = 80 m is this project's own
re-tuned value**, disclosed, not [1]'s number transplanted.

### 5.3 CH election — `cluster_head.py`
`Score(v) = 0.6·T(v) + 0.4·max(0, 1 − speed/22.0)`, TRUSTED-only, **bootstrap fallback** to UNKNOWN when a
cluster has no TRUSTED candidate (logged `[BOOTSTRAP: no TRUSTED candidate available]`). Weighted
multi-factor CH scoring is confirmed as the field's standard pattern by [1], [4], [7], [8] — **none of which
use trust as a factor**, so the trust term is a security-motivated extension; the 0.6/0.4 split is own tuning.

### 5.4 Majority-vote confirmation — `broadcast.py`
```
confirms(u,m) = ‖p_u − p_claimed‖ ≤ radius(m)  OR  is_braking(u)  OR  is_accident(u)
forward(CH,m) = |{u ∈ cluster : confirms(u,m)}| / |cluster| > 0.5
```
**Own contribution.** [9] reaches the same defensive premise by a different mechanism (entropy-weighted
aggregation across multiple senders) — cited as related, not as source.

### 5.5 GPSR routing — `routing.py`
`GPSR_RANGE_M = 300`, `GPSR_OWN_CH_RANGE_M = 80`, `GPSR_TTL_HOPS = 5`.
Greedy next hop = nearest in-range, trust-gated candidate making progress; on a void, right-hand-rule
perimeter mode until progress resumes. Fallback: own CH ≤80 m → nearest trusted CH ≤300 m → **any RSU
≤300 m** → Store-Carry-Forward.
300 m matches three independent papers ([1], [2], [6]); [4] uses 350 m — disclosed, not reconciled.
**Multi-RSU delivery (added 2026-09-05):** the greedy/perimeter *geometry* stays anchored to one destination
(standard GPSR), but the *delivery test* now accepts any of the 5 RSUs within range. See §7.

### 5.6 Tiered authentication — `bls_auth.py`, `ecdsa_auth.py`
```
High   T ≥ 0.7     → aggregate-verify in one pairing check (BLS only)
Mid    0.3 ≤ T<0.7 → verify individually
Reject T < 0.3     → rejected with NO verification attempt (real compute saved)
```
BLS12-381 via `py_ecc` gives true aggregation: N signatures → one constant **96-byte** aggregate. ECDSA has
**no** native aggregation; its "batch" column is honestly-labelled sequential verification.

### 5.7 RSU pipeline — `rsu.py`
UUID cross-event dedup; persistent trust feedback (±0.05, blended 0.80/0.20) — fixing a real bug where the
nudge was overwritten on the next recomputation. 5 RSUs at the grid's cardinal midpoints + centre.

---

## 6. How to run

```bash
# Live GUI demo — the rehearsed panel configuration
python3 main.py --gui --density 250 --steps 200 --seed 4

# Same pipeline headless (also re-runs the full sweep afterwards)
python3 main.py --density 250 --steps 200 --seed 4

# Evaluation sweep only
python3 main.py --eval-only

# The exact sweep behind the numbers in §7
python3 -c "from comparison import ComparisonEngine; ComparisonEngine().run_all_comparisons(densities=[50,100,150,200,250,300,500], runs=5, steps=100)"

# DBSCAN ε-sensitivity ablation
python3 eps_sensitivity.py

# Test suite — expect 94 passed
python3 -m pytest -q
```
Dual-window demo (SUMO GUI beside a companion webpage): `docs/DEMO_GUIDE.md` §1b.
**Note:** `main.py` regenerates `network/routes*.xml` with fresh randomness; `git checkout -- network/` after
a run if you don't want that diff.

---

## 7. Results (real, from `outputs/logs/comparison_results.csv`, 2026-09-05)

7 densities × 5 seeds × 5 emergency events per run, mean ± 95% CI.

| Density | PDR flood → proposed | Total delay flood → proposed | Routing-only flood → proposed | Overhead reduction | Duplicate suppression |
|---|---|---|---|---|---|
| 50 | 100% → 96% | 10.30 → 363.74 ms | 10.30 → 2.80 ms | 94.25% | 100% (906 → 0) |
| 100 | 100% → 100% | 10.19 → 344.44 ms | 10.19 → 3.18 ms | 96.88% | 100% (3,588 → 0) |
| 150 | 100% → 84% | 9.02 → 340.87 ms | 9.02 → 2.67 ms | 98.36% | 100% (10,633 → 0) |
| 200 | 100% → 88% | 8.90 → 315.22 ms | 8.90 → 2.18 ms | 98.85% | 100% (19,703 → 0) |
| 250 | 100% → 88% | 9.02 → 313.04 ms | 9.02 → 2.01 ms | 99.15% | 100% (29,254 → 0) |
| 300 | 100% → 80% | 8.74 → 314.77 ms | 8.74 → 1.79 ms | 99.33% | 100% (45,199 → 0) |
| 500 | 100% → 88% | 8.06 → 301.24 ms | 8.06 → 1.79 ms | 99.59% | 100% (129,278 → 0) |

**Multi-RSU delivery fix, this revision.** Every non-delivery was instrumented and attributed to a cause.
Store-Carry-Forward dominated — and most of it was an artifact: the route pre-selected one target RSU from
the accident's position and never reconsidered, so a message that hopped into a *different* RSU's coverage
was still declared undelivered. At density 150, **5 of 5** SCF failures had another RSU within 300 m of the
dead route's end.

| Density | 50 | 100 | 150 | 200 | 250 | 300 | 500 | **mean** |
|---|---|---|---|---|---|---|---|---|
| PDR before | 96% | 100% | 64% | 68% | 76% | 76% | 72% | **78.9%** |
| PDR after | 96% | 100% | **84%** | **88%** | **88%** | **80%** | **88%** | **89.1%** |

Densities 50 and 100 are unchanged — they had no SCF failures. A useful negative control: the fix moved
exactly the metric it should and nothing else. **No safety check was relaxed**: majority-vote, the 300 m cap
and trust gating are enforced identically before and after.

**Residual non-delivery is all genuine** (instrumented): density 150 — 2 majority-vote withholds + 2 malicious
PACKET_DROP relays, zero SCF; density 300 — 1 withhold + 4 SCF, all four being real 300–400 m RSU coverage
gaps.

**BLS12-381 vs ECDSA** (`outputs/logs/*_benchmark.csv`, scenario-independent):

| N | BLS individual | BLS batch | speedup | ECDSA individual | ECDSA "batch" | bytes BLS/ECDSA |
|---|---|---|---|---|---|---|
| 1 | 299.6 ms | 299.9 ms | 1.00× | 0.077 ms | 0.068 ms | 96 / 71 |
| 2 | 650.8 ms | 442.5 ms | 1.47× | 0.137 ms | 0.129 ms | 96 / 140 |
| 5 | 1537.0 ms | 844.7 ms | 1.82× | 0.318 ms | 0.313 ms | 96 / 355 |
| 10 | 3040.5 ms | 1566.6 ms | **1.94×** | 1.057 ms | 0.670 ms | 96 / 710 |
| 20 | 6086.6 ms | 2972.4 ms | 2.05× | 1.292 ms | 1.238 ms | 96 / 1420 |

⚠ **Absolute milliseconds are wall-clock and swing ≈25% run-to-run on the same machine with no code change**
(individual N=10 measured at 2947.8 / 3677.5 / 3040.5 ms in three runs on one day). Quote the **speedup ratio**
(~1.9–2.4× at N≥10) and the **constant 96-byte aggregate** — never the raw ms — and never read the total-delay
column above as a between-revision result.

**Live demo run** (`--density 250 --steps 200 --seed 4`, verified 2026-09-05): 215 vehicles, 13 clusters /
13 CHs, 1 emergency message, **PDR 100%**, end-to-end delay 311.12 ms, 18 duplicates suppressed, auth success
100%, path `Accident Vehicle (v85) → CH (v74) → RSU (RSU_SOUTH)`, one `[Withheld]` majority-vote event, zero
packet drops.

---

## 8. Known limitations — honest, do not quietly "fix"

1. **PDR remains below flooding at 5 of 7 densities.** Real reliability-vs-efficiency trade-off: flooding's
   redundant paths survive a failed hop, a single efficient CH path does not.
2. **Real RSU coverage gap.** 5 RSUs on 700×700 m at a uniform 300 m range leaves corners 300–400 m from any
   RSU. Adding RSUs or widening range to [2]'s 1000 m would raise PDR — that would be tuning the topology
   until it flatters the scheme. The gap is reported instead.
3. **Synthetic-harness DBSCAN cluster collapse at density ≥200** — the sweep harness's open-plane drift
   mobility merges the fleet into one mega-cluster. **Not present in the live SUMO pipeline** (13–20
   well-distributed clusters at comparable density). Read density ≥200 overhead figures with this in mind.
4. **Tc and Ts are own constructions** — no formula for either exists in the 8 papers read.
5. **FORGED_RECOMMENDATION is undetectable** — no recommendation-exchange mechanism in a 4-factor model.
6. **Store-Carry-Forward is not a retry mechanic** — undelivered means undelivered for that trigger.
7. **ECDSA is standard sign/verify**, not [3]'s full NIZK protocol.
8. **RSU cross-event dedup is correct but rarely exercised** in a single-route-per-event pipeline.
9. **The sweep uses synthetic grid mobility**, not live TraCI; the demo uses real TraCI.
10. **No MAC-layer contention model** — if anything this *understates* flooding's real-world disadvantage.
11. **BLS absolute latency is a pure-Python artifact** (`blst`/`relic` verify in ~1–2 ms).
12. **Parameters from the "Group 83" report are unauditable** — see the warning in §4.

---

## 9. Standing rules

1. **Zero fabricated numbers.** Every metric, timing and citation detail comes from executing code or reading
   a real source. If it cannot be verified, disclose the gap — never guess plausibly.
2. **Citation integrity.** Trace every algorithm/parameter to a paper actually on disk, or label it own
   contribution. Never attribute a mechanism to a paper that does not specify it. Check **both** folders (§4).
3. **Real outputs only.** Never hand-edit a results CSV or graph.
4. **Diagnose before changing.** Instrument and attribute a problem to a cause before altering an algorithm;
   A/B measure the change; if there is no measured effect, **do not ship it** (see §7's rejected entry-hop
   change). Record null results rather than discarding them.
5. **Never silently improve a number by weakening a check.** If PDR rises, state precisely why and confirm no
   safety gate was relaxed.
6. **Prefer hardening existing modules** over new abstraction layers.
7. **No AI/Claude attribution in git metadata** — commits, PR descriptions, trailers.
8. **`docs/ALGORITHMS.md` owns citations; `outputs/RESULTS_SUMMARY.md` owns numbers.** This file summarises
   both; if they disagree, they win and this file gets corrected.
9. **When a result looks unflattering, investigate and disclose rather than patch it away** — several of this
   project's most credible findings came from exactly that.
10. **Re-rehearse the demo after any routing change.** The seed-4 narrative has already changed once (§7);
    stale presenter notes are worse than none.

---

## 10. Roadmap

1. Hybrid reliability scheme for the residual PDR gap (redundant forwarding at low density, or relaxing
   corroboration for downstream relay hops — note the latter was measured and would **not** help: all
   majority-vote failures occur at hop 1).
2. Live SUMO/TraCI-driven multi-density sweep, replacing the synthetic harness.
3. Redesign the harness mobility model to remove the cluster-collapse artifact (§8.3).
4. FORGED_RECOMMENDATION detection via a recommendation-exchange mechanism.
5. ML-assisted trust modelling.
6. Adaptive/geographic probabilistic rebroadcasting.
7. Production PKI/CA-backed key registration for both schemes.
8. Multi-RSU coordination, handoff and network-wide trust aggregation.
9. Malicious-ratio and highway-topology sweeps.
10. Read the ~18 uncatalogued papers in `Research paper-set1/` — may ground current own-contribution items.
