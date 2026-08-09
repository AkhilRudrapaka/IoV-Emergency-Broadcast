# IoV Broadcast Storm Mitigation

**Trust-Aware Clustering and BLS Batch Authentication for Reliable Emergency Message Dissemination in the Internet of Vehicles**

A SUMO/TraCI-driven simulation platform that replaces naive emergency-alert flooding with trust-aware clustering, controlled Cluster-Head broadcasting, and real BLS12-381 batch authentication — built as an IEEE-style research prototype, not a toy demo.

[![Tests](https://img.shields.io/badge/tests-52%20passing-brightgreen)]()
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

1. Vehicles are continuously classified (Trusted / Unknown / Malicious) from real behavioral counters, not static labels.
2. Vehicles are grouped by a **velocity-aware DBSCAN variant** that blends current position with a short-horizon predicted position and a directional compatibility gate — so vehicles converging from opposite lanes aren't wrongly clustered.
3. Each cluster elects a **Cluster Head** by a composite trust + speed-stability score.
4. On an accident, only Cluster Heads relay the alert — via **greedy, loop-free, trust-gated multi-hop routing** toward the nearest RSU — with UUID-based duplicate suppression blocking every redundant relay.
5. The RSU authenticates the alert using **real BLS12-381 signatures**: the sender and every active Cluster Head co-sign a distinct attestation, and the RSU verifies high-trust signers in a single aggregate pairing check while individually scrutinizing (or rejecting) low-trust signers.

The full mathematical formulation of every stage is in **[`docs/ALGORITHMS.md`](docs/ALGORITHMS.md)**.

## Key Features

- Realistic 5×5 urban SUMO road network — multi-lane roads, intersections, traffic lights, 50–500+ vehicle densities
- Live TraCI-driven vehicle classification, trust scoring, and Cluster-Head election every simulation step
- Velocity-aware adaptive DBSCAN clustering with a dynamic re-clustering controller (skips redundant re-clustering when nothing material has changed)
- Realistic two-vehicle collision model with radius-based congestion propagation (braking, queueing, lane changes)
- UUID-based duplicate suppression and controlled Cluster-Head-only broadcasting
- Real BLS12-381 batch authentication (`py_ecc`) with a trust-gated aggregate/individual verification split, and a measured **2.06× verification speedup** at batch size 20
- Full RSU ingress → authentication → decision → analytics → trust-feedback → dissemination pipeline, multi-RSU deployment
- Config-driven ablation switches (clustering mode, dynamic re-clustering, authentication mode) for controlled comparison studies
- 9 automated, 300 DPI, IEEE-style evaluation graphs and a flooding-baseline comparison harness
- 52 automated unit tests covering every core module

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

**Trust score** (5-term weighted composite with EMA historical trust):

$$T(v) = 0.30\,T_{fwd} + 0.25\,T_{auth} + 0.20\,T_{pdr} + 0.15\,T_{hist} + 0.10\,T_{rec}$$

**Cluster Head election:**

$$\text{Score}(v) = 0.6\,T(v) + 0.4\,S(v), \qquad H(c) = \operatorname*{argmax}_{v \in E(c)} \text{Score}(v)$$

**Velocity-aware clustering distance** (blends current + short-horizon projected position, gated by heading):

$$d(i,j) = 0.6\,\lVert p_i - p_j \rVert_2 + 0.4\,\lVert p_i' - p_j' \rVert_2, \qquad p' = p + \vec{v}\cdot H$$

**BLS trust-gated batch authentication:**

$$\text{ACCEPT}_{BLS}(m) = \text{AggregateVerify}(\text{High-trust signers}) \;\wedge\; \bigwedge_{\text{Low-trust}} \text{Verify}(\cdot)$$

See §7 of `docs/ALGORITHMS.md` for the single combined system-level expression tying trust, clustering, CH election, routing, and BLS authentication into one pipeline.

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
├── routing.py                         # Greedy multi-hop trust-gated routing (§4)
├── rsu.py                              # RSU ingress/auth/decision/dissemination pipeline
├── authentication.py                    # Legacy SHA-256 baseline authentication
├── bls_auth.py                           # Real BLS12-381 batch authentication (§5)
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
├── tests/                                             # 52 unit tests (pytest)
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
python3 -m pytest -q                         # Run the full 52-test suite
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
8. **Controlled broadcast demonstrates duplicate suppression**: every active Cluster Head "hears" the alert, exactly one forwards, the rest are logged as blocked duplicates.
9. **The message routes hop-by-hop to the nearest RSU**, with the full path logged.
10. **The RSU authenticates, accepts, and ACKs** the message (`Authentication: PASS -> Decision: ACCEPTED -> ACK Sent`), flashing cyan in the GUI, and boosts the sender's trust.
11. **Metrics and 9 IEEE-style graphs are generated automatically** at the end of the run.

## Experimental Metrics

From the checked-in evaluation artifacts (`outputs/logs/`), comparing the proposed algorithm against a pure-flooding baseline across five vehicle densities (synthetic multi-density harness, 2 seeded runs each — see `comparison.py`):

| Density | Delay Reduction | Broadcast Overhead Reduction | Duplicate Reduction |
|---|---|---|---|
| 50 | 68.4% | 97.96% | 99.32% |
| 100 | 65.7% | 98.99% | 99.44% |
| 200 | 65.9% | 99.50% | 99.95% |
| 300 | 65.9% | 99.67% | 99.98% |
| 500 | 64.7% | 99.80% | 99.99% |

BLS batch authentication performance (`outputs/logs/bls_benchmark.csv`, real BLS12-381 operations):

| Batch size | Individual verify | Batch verify | Speedup | Signature payload |
|---|---|---|---|---|
| 1 | 290.1 ms | 294.0 ms | 0.99× | 96 B → 96 B |
| 5 | 1477.9 ms | 878.7 ms | 1.68× | 480 B → 96 B |
| 20 | 5867.6 ms | 2851.0 ms | **2.06×** | 1920 B → **96 B** (20:1) |

**Honest caveats** (see `docs/ALGORITHMS.md` → *Honest Scope Notes* for the full list): Packet Delivery Ratio and Throughput do not differentiate between the two algorithms in the current comparison harness (both saturate near their ceiling in this small-scale, low-loss synthetic scenario) — the meaningful, credible gains today are in delay, overhead, and duplicate suppression. The comparison harness also uses synthetic grid-seeded mobility rather than live SUMO/TraCI movement; see the roadmap below.

## Current Status & Roadmap

**Working today** (all verified against a live run, not just described): SUMO simulation, vehicle classification, trust evaluation, velocity-aware clustering, Cluster Head election, two-vehicle accident simulation, duplicate suppression, controlled broadcast, multi-hop routing, RSU authentication (both legacy SHA-256 and real BLS12-381 batch), metrics/graph generation, flooding baseline comparison. 52/52 tests passing.

**Planned next** (see `docs/PROJECT_REPORT.md` for the full dependency-ordered roadmap):

1. Real SUMO/TraCI-driven multi-density comparison (replacing the synthetic mobility harness)
2. Independent malicious-vehicle *detection* from behavior alone (currently ground-truth labeled, used to validate the trust *response* mechanism)
3. Multi-run statistical evaluation with confidence intervals across densities and malicious ratios
4. ML-assisted trust modeling
5. Adaptive/geographic probabilistic broadcasting
6. Production PKI/certificate-authority-backed BLS key registration
7. Multi-RSU coordination and network-wide trust aggregation

## License

Released under the [MIT License](LICENSE).
