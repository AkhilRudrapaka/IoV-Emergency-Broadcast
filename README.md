# IoV Broadcast Storm Mitigation

**Mitigation of the Broadcast Storm Problem for Reliable Emergency Message Dissemination in the Internet of Vehicles using Trust-Aware Clustering and Batch Authentication**

A SUMO/TraCI-driven simulation platform that replaces naive emergency-alert flooding with trust-aware clustering, controlled Cluster-Head broadcasting, and real BLS12-381 batch authentication — built as an IEEE-style research prototype, not a toy demo.

[![Tests](https://img.shields.io/badge/tests-93%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.10-blue)]()
[![SUMO](https://img.shields.io/badge/SUMO-1.12.0-orange)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Problem Statement

In an Internet of Vehicles (IoV) network, a vehicle that detects a hazard (a collision, a stalled vehicle) must alert nearby traffic and infrastructure quickly and reliably. The naive way to guarantee reach is **flooding**: every vehicle that receives the alert immediately rebroadcasts it to every neighbor. Flooding is simple, and it is also the textbook cause of the **broadcast storm problem**:

- **Redundant transmissions** grow with vehicle density — the same message gets retransmitted by every receiving node.
- **Channel contention and collisions** spike exactly when reliable delivery matters most (dense, panic-prone post-accident traffic).
- **No defense against misbehaving nodes** — nothing stops a vehicle from injecting false alerts, silently dropping packets it should forward, or forging trust recommendations about its neighbors.
- **Mobility-blind clustering** (plain spatial DBSCAN) groups vehicles that happen to be close together even if they're moving in opposite directions on opposing lanes — producing clusters and Cluster Heads that dissolve almost immediately.
- **Signature verification doesn't scale** — checking one signature per message, per Cluster Head, per vehicle becomes a bottleneck exactly as network density (and therefore the number of relays) grows.

## Proposed Solution

Instead of flooding, this project disseminates emergency alerts through a **trust-aware, mobility-aware, cryptographically batch-authenticated pipeline**:

1. Vehicles are continuously classified (Trusted / Unknown / Malicious) from a real 4-factor Bayesian trust score, not static labels.
2. Vehicles are grouped by a **velocity-aware DBSCAN variant** that blends current position with a short-horizon predicted position and a directional compatibility gate — so vehicles converging from opposite lanes aren't wrongly clustered.
3. Each cluster elects a **Cluster Head** by a composite trust + speed-stability score, restricted to TRUSTED vehicles (with a documented bootstrap fallback).
4. Before forwarding, a Cluster Head requires **cooperative majority-vote confirmation** (>50% of its own cluster corroborating the event).
5. On an accident, only Cluster Heads relay the alert — via **GPSR geographic routing** with a real 300 m wireless-range cap, standard perimeter-mode void recovery, and a 4-tier fallback chain — with UUID-based duplicate suppression blocking every redundant relay.
6. The RSU authenticates the alert using **real BLS12-381 signatures** (with a real ECDSA ablation arm): the sender and every active Cluster Head co-sign a distinct attestation, and the RSU applies **3-tier trust-gated verification** — aggregate-batch for high trust, individual for mid trust, immediate rejection (no verify attempt) for low trust — with cross-event deduplication and persistent RSU trust feedback.

The full mathematical formulation of every stage is in **[`docs/ALGORITHMS.md`](docs/ALGORITHMS.md)**.

## Key Features

- Realistic 5×5 urban SUMO road network — multi-lane roads, intersections, traffic lights, 50–500+ vehicle densities
- Live TraCI-driven vehicle classification, trust scoring, and Cluster-Head election every simulation step
- Velocity-aware adaptive DBSCAN clustering with a dynamic re-clustering controller (skips redundant re-clustering when nothing material has changed)
- Realistic two-vehicle collision model with radius-based congestion propagation (braking, queueing, lane changes)
- UUID-based duplicate suppression and controlled Cluster-Head-only broadcasting
- Real BLS12-381 batch authentication (`py_ecc`) with 3-tier trust-gated verification (aggregate / individual / immediate-reject), and a measured **~2× verification speedup** at batch size ≥10
- Real ECDSA (NIST P-256, `cryptography`) ablation arm — a direct, honest comparison of BLS's aggregation against the Report's specified industry-standard scheme
- GPSR geographic routing with a real 300 m wireless-range cap, standard right-hand-rule perimeter-mode void recovery, a 4-tier fallback chain, and a 5-hop TTL
- Cooperative majority-vote confirmation (>50% of a Cluster Head's own cluster) before forwarding
- Full RSU ingress → cross-event dedup → tiered authentication → decision → analytics → persistent trust-feedback → dissemination pipeline, multi-RSU deployment
- Config-driven ablation switches (clustering mode, dynamic re-clustering, authentication mode) for controlled comparison studies
- 9 automated, 300 DPI, IEEE-style evaluation graphs and a flooding-baseline comparison harness
- 93 automated unit tests covering every core module

## System Architecture

```
SUMO / TraCI (live vehicle mobility)
        │
        ▼
Vehicle Classification & Trust Evaluation  ──────────────┐
        │                                                 │ (trust feeds
        ▼                                                 │  clustering,
Velocity-Aware DBSCAN Clustering                          │  CH election,
        │                                                 │  and BLS
        ▼                                                 │  verification)
Cluster Head Election (0.6·Trust + 0.4·SpeedStability)     │
        │                                                 │
        ▼                                                 │
Accident Event → Emergency Message → BLS Chain Signing     │
        │                                                 │
        ▼                                                 │
Controlled Broadcast (duplicate suppression) → Multi-Hop    │
Routing (loop-free, trust-gated) → Nearest RSU              │
        │                                                 │
        ▼                                                 │
RSU: Authenticate (BLS batch/individual) → Decision →       │
Trust Update ─────────────────────────────────────────────┘
        │
        ▼
Metrics, CSV Export, IEEE Graphs
```

## Mathematical Models

Full derivations, exact weights, and thresholds (matching the shipped code, not an idealized version of it) are in **[`docs/ALGORITHMS.md`](docs/ALGORITHMS.md)**. The headline formulas:

**Bayesian trust score** (4-factor weighted composite with EMA historical trust + persistent RSU boost):

$$T(v) = 0.80\big(0.30\,T_f + 0.25\,T_c + 0.20\,T_s + 0.25\,T_h\big) + 0.20\,R(v)$$

where $T_f$ = forwarding behaviour, $T_c$ = message consistency, $T_s$ = speed plausibility, $T_h$ = EMA historical trust (decay 0.85), $R(v)$ = persistent RSU trust assessment.

**Cluster Head election** (TRUSTED-only, T≥0.7, with a documented bootstrap fallback):

$$\text{Score}(v) = 0.6\,T(v) + 0.4\,S(v), \qquad H(c) = \operatorname*{argmax}_{v \in E_1(c)} \text{Score}(v)$$

**Velocity-aware clustering distance** (blends current + short-horizon projected position, gated by heading):

$$d(i,j) = 0.6\,\lVert p_i - p_j \rVert_2 + 0.4\,\lVert p_i' - p_j' \rVert_2, \qquad p' = p + \vec{v}\cdot H$$

**GPSR routing** (300 m range cap on every hop, perimeter-mode void recovery, 5-hop TTL):

$$h_{i+1} = \operatorname*{argmin}_{h \,\in\, \text{Progress}(h_i)} \lVert p_{h_i} - p_h \rVert_2, \qquad \text{Progress}(h_i) \subseteq \{h : \lVert p_{h_i}-p_h\rVert_2 \le 300\text{m}\}$$

**Tiered batch authentication** (BLS12-381, with a real ECDSA ablation arm):

$$\text{ACCEPT}(m) = \text{AggregateVerify}(\text{High}, T{\ge}0.7) \;\wedge\; \bigwedge_{\text{Mid}, 0.3\le T<0.7} \text{Verify}(\cdot) \;\wedge\; \big[\text{Reject}_{T<0.3} = \emptyset\big]$$

See `docs/ALGORITHMS.md` for every formula's full derivation, the GPSR fallback chain and perimeter-mode
mechanics, the majority-vote confirmation gate, and the combined system-level pipeline expression.

## Tech Stack

| Layer | Technology |
|---|---|
| Traffic simulation | SUMO 1.12.0 (`sumo`, `sumo-gui`) |
| Simulation control | TraCI / `traci`, `sumolib` (Python 3.10) |
| Clustering | scikit-learn `DBSCAN` (Euclidean + custom precomputed mobility-aware metric) |
| Numerical computing | NumPy, Pandas |
| Cryptography | `py_ecc` — BLS12-381 (`G2ProofOfPossession`, IETF-draft / Eth2 ciphersuite) |
| Visualization | Matplotlib (300 DPI IEEE-style figures) |
| Testing | pytest |

## Project Structure

```
IOV-Broadcast-problem/
├── main.py                    # Unified entry point (route gen + live run + eval + graphs)
├── config.py                  # Central configuration — every tunable parameter
├── vehicle.py                 # Vehicle state, classification, GUI color mapping
├── trust.py                   # Trust evaluation engine (§1 of ALGORITHMS.md)
├── clustering.py               # Velocity-aware DBSCAN clustering (§2)
├── cluster_stability.py         # Cluster persistence tracking + dynamic re-clustering
├── cluster_head.py               # Cluster Head election (§3)
├── neighbor_discovery.py          # Range-based neighbor table
├── accident.py                     # Two-vehicle collision + congestion simulation
├── messaging.py                     # EmergencyMessage data model
├── broadcast.py                      # Controlled broadcast + duplicate suppression (§6)
├── routing.py                         # GPSR geographic routing, 300m range + perimeter mode (§4)
├── rsu.py                              # RSU ingress/dedup/auth/decision/dissemination pipeline (§7)
├── authentication.py                    # Legacy SHA-256 baseline authentication
├── bls_auth.py                           # Real BLS12-381 tiered batch authentication (§6)
├── ecdsa_auth.py                          # Real ECDSA (P-256) ablation arm (§6)
├── flooding.py                            # Baseline flooding engine (for comparison)
├── comparison.py                           # Proposed vs. flooding evaluation harness
├── metrics.py                               # Telemetry collection / CSV export
├── graphs.py                                 # IEEE-style 300 DPI graph generation
├── generate_routes.py                         # SUMO route-file generation
├── logger.py                                   # Structured console/file logging
├── utils.py                                     # Geometry / angle helper functions
├── network/                                      # SUMO road network, routes, sumocfg
├── docs/
│   ├── ALGORITHMS.md                              # Full mathematical model (this is the one to read)
│   └── PROJECT_REPORT.md                           # Detailed implementation status report
├── outputs/
│   ├── graphs/                                      # Generated 300 DPI evaluation plots
│   └── logs/                                         # Metrics / comparison / BLS benchmark CSVs
├── tests/                                             # 93 unit tests (pytest)
├── requirements.txt
├── pytest.ini
└── README.md
```

> **Note on structure:** core modules are kept at the repository root rather than under `src/`. Every module currently imports its dependencies as flat, top-level names (`from vehicle import Vehicle`, etc.); moving 20+ interdependent, already-tested modules into a package would mean rewriting every cross-import for a purely cosmetic gain, with real risk to a pipeline that's currently fully working. `tests/` and `docs/` were introduced because they carry no such risk — tests import via `pytest.ini`'s `pythonpath = .`, which was verified against the full suite before and after the move.

## How to Install & Run

### Prerequisites

- Ubuntu 20.04+ (or similar Linux), Python 3.10+
- [SUMO](https://sumo.dlr.de/docs/Downloads.php) 1.12.0+ with `sumo` / `sumo-gui` on your `PATH`, and `SUMO_HOME` set

### Setup

```bash
git clone https://github.com/AkhilRudrapaka/IOV-Broadcast-problem.git
cd IOV-Broadcast-problem
pip install -r requirements.txt
```

### Run the live GUI demonstration

```bash
python3 main.py --gui --density 100
```

This generates the required SUMO route files, launches `sumo-gui`, and runs the full 15-phase pipeline live: vehicle classification → clustering → trust evaluation → Cluster Head election → a scripted two-vehicle accident at step 50 → BLS chain signing → controlled broadcast → multi-hop routing → RSU authentication and ACK → metrics/graph export.

### Other entry points

```bash
python3 main.py --eval-only                 # Run only the flooding-vs-proposed comparison + graphs
python3 -m pytest -q                         # Run the full 93-test suite
python3 sumo_interface.py                    # Run the live pipeline headlessly (SUMO_GUI=1 env var for GUI)
```

## Demonstration Highlights

What a reviewer watching `python3 main.py --gui --density 100` will see, in order:

1. **SUMO-GUI starts** with a realistic multi-lane urban grid, traffic lights, and live vehicle movement.
2. **Vehicle coloring updates every step** via real TraCI calls: white = trusted, yellow = unknown, black = malicious, blue = Cluster Head, orange = active forwarder / braking due to accident, red = accident vehicle.
3. **Clusters form and are logged** every re-clustering step (`[Clustering] Step N: Clusters Formed = ... | Sizes = {...} | Noise Vehicles = ...`).
4. **Trust scores update continuously**, with explicit before/after snapshots around the accident and after RSU verification.
5. **Cluster Heads are elected** with a logged score breakdown (`Score: 0.94 (Trust: 0.90, SpeedStab: 1.00)`).
6. **A two-vehicle collision triggers at step 50** — both vehicles halt and turn red with highlight rings; nearby traffic brakes, queues, and turns orange.
7. **BLS chain signatures are generated** (sender + every active Cluster Head), logged with signature count and real signing time.
8. **Controlled broadcast demonstrates duplicate suppression**: every active Cluster Head "hears" the alert, each checks majority-vote corroboration from its own cluster before forwarding (logged `[Withheld]` if it can't corroborate), and any already-cached message is logged as a blocked duplicate.
9. **The message routes hop-by-hop to the nearest RSU via GPSR**, with the full path logged — including a real 300m range check on every hop, and an honest `STORE_CARRY_FORWARD` if nothing is in range.
10. **The RSU deduplicates by accident UUID, authenticates (tiered BLS), accepts, and ACKs** the message (`Authentication: PASS -> Decision: ACCEPTED -> ACK Sent`), flashing cyan in the GUI, and persistently nudges the sender's RSU trust assessment.
11. **Metrics and 9 IEEE-style graphs are generated automatically** at the end of the run.

## Experimental Metrics

From `outputs/RESULTS_SUMMARY.md` (regenerated 2026-08-24, second revision aligning Algorithms 1–4 to the
project's Final Report specification; full methodology, gap analysis, and honest limitations there — read it
before quoting these numbers), comparing the proposed algorithm against a pure-flooding baseline across six
vehicle densities (synthetic grid harness, 5 seeded runs × 5 emergency events each, mean ± 95% CI):

| Density | PDR: Flood → Proposed | Delay (total): Flood → Proposed | ↳ routing-only: Flood → Proposed | Overhead Reduction | Duplicate Suppression |
|---|---|---|---|---|---|
| 50  | 100% → 96% | 10.30 ± 0.61 ms → 433.38 ± 36.02 ms | 10.30 → 2.87 ms | 94.16% | 100% |
| 100 | 100% → 100% | 10.19 ± 0.54 ms → 354.99 ± 26.13 ms | 10.19 → 3.18 ms | 96.88% | 100% |
| 150 | 100% → 64% | 9.02 ± 0.40 ms → 379.86 ± 47.90 ms | 9.02 → 2.70 ms | 98.42% | 100% |
| 200 | 100% → 68% | 8.90 ± 0.36 ms → 339.69 ± 42.92 ms | 8.90 → 1.86 ms | 98.95% | 100% |
| 300 | 100% → 76% | 8.74 ± 0.61 ms → 340.81 ± 44.65 ms | 8.74 → 1.73 ms | 99.34% | 100% |
| 500 | 100% → 72% | 8.06 ± 0.40 ms → 385.72 ± 48.93 ms | 8.06 → 1.53 ms | 99.62% | 100% |

**Read PDR and delay carefully — both tell an important, real story, not a flattering one.** Total delay is
*worse* for proposed because it's dominated by real BLS12-381 verification cost (`py_ecc`, a pure-Python
pairing implementation) — the **routing-only component** (what GPSR is actually meant to improve) is
consistently *lower* for proposed at every density. **PDR is now consistently lower for proposed too** —
this is the honest consequence of finally enforcing a real 300 m wireless range and real majority-vote
corroboration (both previously missing/nonexistent): flooding's path redundancy makes it resilient to any
single hop failing; the proposed scheme commits to one efficient path, which is structurally more exposed to
one hop failing. This is a genuine reliability-vs-efficiency trade-off, traced to two verified causes (RSU
coverage gaps at 300 m; DBSCAN clusters not all being geographically near a given accident) — see
`outputs/RESULTS_SUMMARY.md` for the full analysis and why it isn't something to hide or work around.

BLS12-381 vs. ECDSA authentication (`outputs/logs/bls_benchmark.csv`, `outputs/logs/ecdsa_benchmark.csv`, both real, scenario-independent benchmarks — Algorithm 4 ablation):

| Batch size | BLS individual | BLS batch | BLS speedup | ECDSA individual | ECDSA "batch" | Signature bytes: BLS / ECDSA |
|---|---|---|---|---|---|---|
| 1  | 361.8 ms | 374.6 ms | 0.97× | 0.086 ms | 0.075 ms | 96 B / 71 B |
| 10 | 3460.8 ms | 1544.9 ms | **2.24×** | 1.068 ms | 0.640 ms | 96 B / 710 B |
| 20 | 7546.7 ms | 3686.5 ms | 2.05× | 1.385 ms | 1.578 ms | 96 B / 1420 B |

**The honest ablation finding:** BLS aggregates — N signatures compress to a constant 96 bytes with a real
~2× verify speedup. ECDSA has no native aggregation — its "batch" column is real sequential verification with
no speedup or compression (payload grows linearly with N). ECDSA is ~1000–5000× faster *per signature* in
this pure-Python comparison, since BLS pairing is far more expensive than ECDSA scalar multiplication — a
genuine cost/compression trade-off between the two schemes, not one being objectively "better."

**Honest caveats** (full list in `outputs/RESULTS_SUMMARY.md` and `docs/ALGORITHMS.md` → *Honest Scope Notes*):
the comparison harness uses synthetic grid-seeded mobility rather than live SUMO/TraCI movement (the live
`sumo_interface.py` pipeline does use real TraCI mobility end-to-end — only the multi-density sweep uses the
faster synthetic harness). Absolute BLS milliseconds reflect a pure-Python reference implementation, not
production V2X latency — the speedup ratio is the defensible claim. Two trust factors (Message Consistency,
Speed Plausibility) are this project's own construction pending the source report — see `docs/ALGORITHMS.md`.

## Current Status & Roadmap

**Working today** (all verified against a live run, not just described): SUMO simulation, vehicle
classification, Bayesian trust evaluation derived only from observed behavior (no ground-truth shortcut —
see `outputs/RESULTS_SUMMARY.md`), velocity-aware clustering, TRUSTED-only Cluster Head election with a
documented bootstrap fallback, two-vehicle accident simulation, cooperative majority-vote confirmation,
duplicate suppression, GPSR routing with a real 300m range cap and perimeter-mode recovery, multi-hop
routing with real packet-drop consequences, RSU authentication (legacy SHA-256, real BLS12-381 tiered
batch, and a real ECDSA ablation), RSU cross-event dedup, persistent RSU trust feedback, metrics/graph
generation, flooding baseline comparison, multi-run statistical evaluation with 95% CI. 93/93 tests passing.

**Planned next** (see `docs/PROJECT_REPORT.md` for the full dependency-ordered roadmap):

1. A hybrid reliability scheme addressing the PDR trade-off documented in `outputs/RESULTS_SUMMARY.md` (the
   proposed scheme's efficiency now comes with a real single-path reliability cost under strict 300m-range
   and majority-vote enforcement, vs. flooding's redundant-path resilience)
2. Real SUMO/TraCI-driven multi-density comparison (replacing the synthetic mobility harness)
3. Detection of *content-forgery* attacks (FORGED_RECOMMENDATION remains undetectable — no
   recommendation-exchange mechanism exists in the current 4-factor trust model; FAKE_ALERT location-forgery
   is now detected via Message Consistency)
4. ML-assisted trust modeling
5. Adaptive/geographic probabilistic broadcasting
6. Production PKI/certificate-authority-backed key registration (both BLS and ECDSA)
7. Multi-RSU coordination and network-wide trust aggregation

## License

Released under the [MIT License](LICENSE).
