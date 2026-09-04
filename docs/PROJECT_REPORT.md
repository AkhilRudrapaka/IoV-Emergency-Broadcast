# Mitigation of the Broadcast Storm Problem for Reliable Emergency Message Dissemination in the Internet of Vehicles using Trust-Aware Clustering and Batch Authentication

**Report Type:** Project Status & Technical Report
**Date:** August 5, 2026
**Domain:** Internet of Vehicles (IoV) / Vehicular Ad-hoc Networks (VANET), Intelligent Transportation Systems

---

## 1. Executive Summary

This project delivers a complete, end-to-end simulation and mitigation framework for one of the most persistent reliability problems in vehicular networking: the **broadcast storm problem** during emergency message dissemination. Built on a SUMO/TraCI urban traffic simulation environment, the system models a realistic Internet of Vehicles (IoV) network in which vehicles must reliably and securely relay time-critical emergency alerts (e.g., collision notifications) to Roadside Units (RSUs) and a Traffic Control Center, without collapsing the wireless channel under redundant retransmissions.

The core contribution of the project is a **trust-aware, mobility-aware clustering architecture combined with cryptographic batch authentication**. Vehicles are dynamically organized into spatial clusters using a velocity- and heading-aware variant of DBSCAN, Cluster Heads (CHs) are elected based on a composite trust and mobility-stability score, and emergency messages are disseminated through controlled, duplicate-suppressed, multi-hop forwarding rather than naive flooding. Authentication of these messages is handled through a full implementation of the Boneh–Lynn–Shacham (BLS) signature scheme, enabling a Roadside Unit to cryptographically verify signatures from many Cluster Heads simultaneously in a single batched operation rather than one at a time.

The project's ultimate goal is twofold: (1) to produce a functioning, reproducible simulation platform that demonstrably reduces broadcast overhead, latency, and authentication cost relative to a flooding baseline, and (2) to raise the technical depth and novelty of the work to a level suitable for a strong IEEE conference paper or a Scopus-indexed journal submission. Two of six planned research-grade enhancements — velocity-aware adaptive clustering and full BLS batch authentication — are complete, tested, and verified end-to-end, with the remaining enhancements (advanced ML-assisted trust, improved probabilistic broadcasting, a rigorous statistical evaluation framework, and system-level RSU improvements) scoped and scheduled.

---

## 2. Existing Problem (The Problem Statement)

### 2.1 Current Situation

In an Internet of Vehicles network, a vehicle that detects a hazardous event (e.g., a collision) must broadcast an emergency alert so that nearby vehicles can react and so that infrastructure (RSUs, Traffic Control Centers) can log and respond to the incident. The simplest way to guarantee this alert reaches the widest possible audience is **flooding**: every vehicle that receives the message immediately rebroadcasts it to all of its neighbors. While flooding is simple to implement, it does not scale, and it is well documented in VANET literature as producing a **broadcast storm** — an uncontrolled cascade of redundant retransmissions that congests the wireless channel precisely when reliable delivery matters most (i.e., during accidents and dense, panic-prone traffic conditions).

### 2.2 Specific Pain Points and Inefficiencies

- **Redundant transmissions:** In flooding-based dissemination, the same message is retransmitted by every receiving node, causing transmission volume to grow rapidly with vehicle density. At densities of several hundred vehicles, this results in severe channel contention.
- **Increased collision rate and channel congestion:** Redundant broadcasts compete for the same limited wireless spectrum, increasing packet collisions and effectively reducing the probability that the *original, time-critical* message is received promptly by the vehicles and infrastructure that need it.
- **No mechanism to filter misbehaving or malicious nodes:** Without a trust or reputation layer, a network has no defense against vehicles that generate **false emergency alerts**, silently **drop packets** they are supposed to forward, or submit **forged trust recommendations** about their neighbors — all of which degrade network reliability or actively mislead other drivers and infrastructure.
- **Mobility-blind clustering:** Where clustering is used to organize vehicles and reduce redundant forwarding, naive spatial clustering (e.g., plain DBSCAN on vehicle coordinates) ignores vehicle speed and heading. Two vehicles that happen to be physically close but are moving in opposite directions (e.g., on opposing lanes) are treated identically to two vehicles traveling together — leading to clusters and elected Cluster Heads that dissolve almost immediately, causing frequent re-elections, broken forwarding paths, and dropped or delayed emergency messages.
- **Authentication does not scale with network density:** Conventional single-message signature verification (e.g., a simple hash or single-signature scheme) requires the receiving RSU to perform one full cryptographic check per incoming message. As the number of Cluster Heads and vehicles reporting or relaying an alert grows, verification cost grows linearly and can itself become a bottleneck — an authentication mechanism that cannot batch multiple signatures into a single check does not scale to realistic, high-density VANET deployments.
- **Absence of rigorous, statistically defensible benchmarking:** Without a structured evaluation framework spanning multiple vehicle densities, multiple malicious-vehicle ratios, and repeated independent runs with confidence intervals, it is difficult to make credible, reviewable claims about system performance, robustness, or security — a requirement for any publishable research contribution.

### 2.3 Impact of Leaving the Problem Unsolved

If unaddressed, these deficiencies compound into a system that is simultaneously **unreliable** (time-critical safety alerts are delayed or lost during the exact congestion events they are meant to report), **insecure** (susceptible to false-alarm injection, message forgery, and unchecked misbehavior), and **unscalable** (both the network channel and the authentication layer degrade as vehicle density increases — precisely the regime in which emergency dissemination matters most). For a safety-critical application such as collision notification, these are not incremental inefficiencies; they directly undermine the core value proposition of a connected-vehicle emergency system.

---

## 3. Proposed Solution

### 3.1 Conceptual Overview

The proposed system replaces naive flooding with a **trust-aware, mobility-aware, cryptographically batch-authenticated dissemination pipeline**. Vehicles are continuously classified and clustered; each cluster elects a Cluster Head based on trust and mobility stability; emergency messages are broadcast in a controlled, duplicate-suppressed manner through Cluster Heads and relayed via multi-hop routing to the nearest Roadside Unit; and the RSU authenticates incoming messages using real BLS cryptographic signatures, batch-verifying multiple signers in a single operation whenever trust conditions allow.

### 3.2 Key Features and Modules

| Module / Capability | Function | Problem(s) Addressed |
|---|---|---|
| **SUMO Urban Network & Vehicle Generation** | Realistic 5×5 urban road network supporting 50–500+ simulated vehicles | Provides a realistic, scalable testbed |
| **Vehicle Verification & Classification** | Continuously classifies every vehicle as Trusted / Unknown / Malicious | Establishes the foundation for trust-based filtering |
| **Velocity-Aware & Adaptive DBSCAN Clustering** | Clusters vehicles using a mobility-aware distance metric that blends current position with a short-horizon predicted position (from speed and heading), with a directional compatibility gate; re-clustering is triggered dynamically only when mobility, trust, or cluster stability actually change materially | Solves mobility-blind clustering; reduces unnecessary Cluster Head churn and unstable forwarding paths |
| **Trust Evaluation & Cluster Head Election** | Composite trust score (forwarding behavior, authentication success, packet delivery ratio, historical trust via exponential moving average, neighbor recommendations) drives both vehicle classification and CH election (trust + speed-stability) | Filters out unreliable/malicious candidates from taking on relay responsibility |
| **Accident Simulation & Emergency Message Generation** | Realistic two-vehicle collision model with congestion propagation and severity-scaled emergency messaging | Produces a realistic trigger event for the dissemination pipeline |
| **Duplicate Message Filtering** | UUID-based message cache suppresses re-processing of already-seen alerts | Directly eliminates the core cause of broadcast storms |
| **Controlled, Cluster-Head-Based Broadcasting & Multi-Hop Routing** | Only Cluster Heads forward messages, along a loop-free, greedy multi-hop path toward the nearest RSU | Replaces flooding with a bounded, predictable dissemination cost |
| **Full BLS Batch Authentication** | Real BLS12-381 signatures: the sending vehicle and every currently active Cluster Head co-sign a distinct attestation of the alert; the RSU aggregates and verifies high-trust signers in a single batched pairing check, while individually verifying (or rejecting) low-trust signers | Solves the authentication-scalability problem while directly using trust scores to allocate verification effort |
| **RSU Ingress & Decision Pipeline** | Authentication → decision engine → analytics → trust feedback → dissemination to the Traffic Control Center | Closes the loop between authentication outcome and network-wide trust state |
| **Metrics, Analytics & Automated Reporting** | Full CSV telemetry export and automatic generation of publication-quality (300 DPI) graphs | Enables quantitative, reviewable evaluation |
| **Flooding Baseline Engine** | A pure-flooding dissemination engine retained for direct, controlled comparison | Provides the comparative evidence that the proposed approach outperforms the naive baseline |

### 3.3 Unique Value Proposition

- **Config-driven ablation on every major feature.** Velocity-aware clustering, dynamic re-clustering, and each authentication mode (full BLS batch, BLS individual, legacy baseline, or no authentication) can be toggled independently through configuration flags — without touching code — enabling the kind of controlled ablation studies that reviewers expect from a credible research contribution.
- **Trust is not cosmetic — it directly gates cryptographic cost.** Rather than treating authentication as a uniform, all-or-nothing cost, the system preferentially batch-verifies signatures from high-trust Cluster Heads while individually scrutinizing (or outright rejecting) low-trust signers, tying the security layer directly to the trust layer.
- **Mobility is a first-class signal in clustering, not an afterthought.** The clustering distance metric explicitly incorporates predicted short-horizon vehicle motion and a directional compatibility gate, while still correctly handling stationary/queued traffic (e.g., vehicles halted at an accident site) — a case that a naive implementation would otherwise mishandle.
- **Reproducible and rigorously tested.** Every enhancement ships with fixed-seed reproducibility, extensive logging, and an automated regression test suite (93 tests passing at the current stage) that verifies both the new behavior and the continued correctness of all previously completed work.

---

## 4. System Architecture & Technology Stack

### 4.1 Simulation Environment

- **SUMO (Simulation of Urban MObility)** — microscopic traffic simulator providing the road network, vehicle mobility, and collision dynamics.
- **TraCI (Traffic Control Interface)** — real-time, bidirectional Python control of the running SUMO simulation (vehicle state, GUI visualization, dynamic control).

### 4.2 Core Technology Stack

| Layer | Technology |
|---|---|
| Language / Runtime | Python 3.10 |
| Clustering | scikit-learn `DBSCAN` (both plain-Euclidean baseline and a custom precomputed mobility-aware distance metric) |
| Numerical / Statistical Computation | NumPy |
| Data Analytics & Metrics | Pandas |
| Visualization / Reporting | Matplotlib (automated 300 DPI, IEEE-style figure generation) |
| Cryptography | `py_ecc` — pure-Python BLS12-381 pairing-based signature library (IETF-draft / Eth2-compliant `G2ProofOfPossession` ciphersuite), used for real sign / verify / aggregate batch-verify operations |
| Legacy / Baseline Authentication | SHA-256–based placeholder signature scheme, retained for ablation comparison |

### 4.3 Software Architecture

The codebase (~4,500+ lines across 32 Python modules) follows a modular design in which each research capability is isolated into its own file with a clear, documented interface:

- **Simulation orchestration:** `sumo_interface.py` (live TraCI-driven run), `comparison.py` (synthetic multi-density benchmarking harness), `main.py` (unified entry point)
- **Clustering:** `clustering.py`, `cluster_stability.py`
- **Trust & identity:** `trust.py`, `vehicle.py`
- **Cluster Head management:** `cluster_head.py`
- **Emergency events & messaging:** `accident.py`, `messaging.py`
- **Dissemination:** `broadcast.py`, `routing.py`, `flooding.py` (baseline), `neighbor_discovery.py`
- **Authentication:** `bls_auth.py` (BLS), `authentication.py` (legacy baseline)
- **Infrastructure:** `rsu.py`
- **Evaluation & reporting:** `metrics.py`, `graphs.py`
- **Configuration & utilities:** `config.py`, `utils.py`, `logger.py`, `generate_routes.py`

Every major algorithmic behavior — clustering mode, dynamic re-clustering, and authentication mode — is controlled centrally through `config.py`, and an automated test suite (one dedicated test module per core component) guards against regressions as new capabilities are added.

### 4.4 Execution Model

The system can be executed headlessly (`sumo`) for batch experimentation or with a full graphical interface (`sumo-gui`) for live visual demonstration, with standardized RGBA color coding for vehicle trust classification, Cluster Head status, active forwarding, and accident state. A single command-line entry point generates the required traffic route files across all target densities, runs the live simulation, executes the full comparative benchmark suite against the flooding baseline, and produces all metrics CSVs and graphs automatically.

---

## 5. Implementation Status

**Current Phase:** Active Development — Core Prototype Complete; Research Enhancement Roadmap In Progress (2 of 6 planned priorities complete and verified)

The project began from a fully functional baseline prototype (SUMO network, classification, clustering, trust, Cluster Head election, accident simulation, duplicate filtering, controlled broadcasting, multi-hop routing, baseline authentication, and full analytics/reporting). A six-priority enhancement roadmap was then defined to raise the system's novelty and technical depth to publication strength. Status against that roadmap is summarized below.

### 5.1 Completed — Foundational Prototype

- SUMO urban road network and multi-density vehicle generation (50 to 500+ vehicles)
- Vehicle verification and classification (Trusted / Unknown / Malicious)
- Baseline behavioral trust evaluation engine
- Cluster Head selection (composite trust + speed-stability scoring)
- Realistic two-vehicle collision simulation with traffic congestion propagation
- UUID-based duplicate emergency-message filtering
- Controlled, Cluster-Head-based broadcasting
- Multi-hop, loop-free greedy routing to the nearest Roadside Unit
- Baseline (SHA-256) authentication framework
- Full RSU ingress, decision, and dissemination pipeline
- Metrics collection, CSV export, and automated IEEE-style graph generation (9 graph types)
- Flooding baseline engine for comparative evaluation

### 5.2 Completed — Research Enhancement Roadmap

- ✅ **Priority 1 — Velocity-Aware & Adaptive DBSCAN Clustering.** Implemented a mobility-aware clustering distance metric (predictive-position projection plus a directional compatibility gate, with a stationary-vehicle safeguard for post-accident queues), persistent cross-step cluster-identity tracking, and a dynamic re-clustering controller that triggers full re-clustering only on significant mobility change, trust change, fleet-membership churn, or falling cluster stability — reducing unnecessary computation while improving Cluster Head stability. The original plain-DBSCAN approach is retained as a one-flag ablation baseline. Verified with 12 dedicated unit tests and a full live SUMO run (density 250, 200 steps), producing new cluster-lifetime, Cluster-Head-churn-rate, connectivity, and stability metrics in the exported CSV.
- ✅ **Priority 2 — Full BLS Batch Authentication.** Implemented real BLS12-381 signing, individual verification, and true aggregate batch verification. Every emergency alert is now co-signed by the originating vehicle and every currently active Cluster Head (capped at 14 total signers); the RSU applies 3-tier trust-gated verification — aggregate-verifies high-trust (T≥0.7) signers in a single pairing operation, individually verifies mid-trust (0.3≤T<0.7) signers, and rejects low-trust (T<0.3) signers immediately with no verify attempt. A dedicated performance benchmark demonstrated up to **~2× verification speedup** and a **20:1 reduction in signature payload size** (1,920 bytes → 96 bytes) at batch sizes ≥10; a real ECDSA (NIST P-256) ablation arm provides an honest side-by-side comparison against the Report's specified industry-standard scheme (see `docs/ALGORITHMS.md` §6). Four authentication modes (full batch, individual BLS, legacy baseline, none) are available as ablation switches. Verified with dedicated unit tests (`tests/test_bls_auth.py`, `tests/test_ecdsa_auth.py`) and a full live SUMO run with no regressions to Priority 1 or the foundational prototype.
- ✅ **Priority 3 — Multi-Factor Bayesian Trust Model (partial).** Trust is now a real 4-factor Bayesian
  composite — `Trust(v) = 0.30·Tf + 0.25·Tc + 0.20·Ts + 0.25·Th`, with an exponential-decay historical term
  (`Th_new = 0.85·Th_old + 0.15·t_current`) and a persistent RSU-feedback blend
  (`Final = 0.80·Trust(v) + 0.20·rsu_assessment`, nudged by real verification outcomes and carried across
  steps instead of being overwritten). Forwarding behavior (Tf), message-location consistency (Tc), and
  kinematic speed plausibility (Ts) are all derived from observed per-step simulation state, with no
  ground-truth (`is_malicious`) leak into the score. See `docs/ALGORITHMS.md` §1 and its Proof-of-Work
  Mapping table for the exact grounding and the explicit disclosure that Tc/Ts's specific formulas are this
  project's own construction. **Not yet done:** an online machine-learning trust predictor — the model
  remains fully rule-based/analytic, not learned.
- ✅ **Priority 4 — Improved Broadcasting (partial).** Cluster-Head-only forwarding now runs over real GPSR
  geographic routing (300 m wireless-range cap on every hop, standard right-hand-rule perimeter-mode void
  recovery, 5-hop TTL, a 4-tier fallback chain ending in a disclosed Store-Carry-Forward), gated by
  cooperative majority-vote confirmation (>50% of a Cluster Head's own cluster must corroborate before
  forwarding) and UUID-based cross-event RSU deduplication. **Not yet done:** trust-and-distance-aware
  probabilistic/timer-based rebroadcast and zone-aware dissemination — forwarding is still single-path
  CH-chain-only, which is the direct, disclosed cause of the PDR reliability-vs-efficiency trade-off in
  `outputs/RESULTS_SUMMARY.md`.
- ✅ **Priority 5 — Rigorous Evaluation Framework (substantially complete).** The comparison harness now
  sweeps 7 vehicle densities (50/100/150/200/250/300/500 — the first five an exact match to
  [Kaur et al., 2024]'s own tested set), 5 seeded runs per density with mean ± 95% CI, and 5 emergency
  events per run. Ablation switches exist and are exercised for clustering (baseline DBSCAN vs.
  velocity-aware), authentication (BLS batch / BLS individual / legacy baseline / none, plus a real ECDSA
  NIST P-256 arm), and DBSCAN ε sensitivity (`eps_sensitivity.py`, `docs/ALGORITHMS.md` §2.5). **Not yet
  done:** multiple malicious-vehicle ratios and a highway (non-urban-grid) scenario are not swept — only the
  default 15% ratio and the current urban grid are evaluated.
- 🔲 **Priority 6 — RSU & System-Level Improvements (partial).** Persistent RSU trust feedback (a real
  feedback loop from RSU verification outcomes back into each vehicle's trust score, carried across steps)
  is now implemented — see Priority 3 above. **Not yet done:** multi-RSU coordination/handoff and a
  persistent cross-run blacklist for repeatedly malicious vehicles remain unimplemented.
- **Combined verification status:** 93 of 93 automated tests passing across the full codebase at the
  current stage.

---

## 6. Future Scope & Conclusion

### 6.1 Future Enhancements

- **Machine-learning-driven trust prediction** (Priority 3), moving from the current rule-based/analytic 4-factor trust score to a model trained on observed vehicle behavior, improving resilience to more sophisticated adversarial strategies.
- **A hybrid, redundancy-aware forwarding scheme** (Priority 4), addressing the PDR reliability-vs-efficiency trade-off now visible in `outputs/RESULTS_SUMMARY.md` — the single-path CH-chain-only forwarding that makes the proposed scheme efficient is also what makes it structurally more exposed to any one hop failing than flooding's redundant paths.
- **Malicious-ratio and highway-scenario sweeps** (Priority 5), extending the now-substantially-complete 7-density/5-seed evaluation framework to also vary the malicious-vehicle ratio and test a non-urban-grid topology.
- **Multi-RSU coordination and a persistent cross-run blacklist** (Priority 6), extending the now-implemented single-RSU persistent trust feedback loop into a coordinated multi-RSU infrastructure layer.
- **Longer-term scalability and deployment directions:** extension to highway (in addition to urban grid) scenarios; integration with a production-grade PKI/certificate authority for BLS key registration in place of the current simulation-internal key registry; evaluation of optimized/compiled pairing-cryptography libraries to reduce BLS latency for larger-scale runs; and alignment with real-world V2X/C-V2X messaging standards for eventual hardware-in-the-loop testing.

### 6.2 Conclusion

The project has progressed from a functional baseline prototype to a system with two fully implemented, tested, and independently verifiable research-grade enhancements — velocity-aware adaptive clustering and full BLS batch authentication — each of which directly and measurably addresses a specific, well-documented weakness of naive broadcast-storm mitigation approaches in the IoV literature. The remaining roadmap (advanced ML-assisted trust, adaptive broadcasting, a rigorous statistical evaluation framework, and system-level RSU coordination) is clearly scoped and sequenced. Combined with the project's emphasis on reproducibility, extensive automated testing, and configuration-driven ablation, the system is on a well-defined and substantially de-risked path toward a technically credible, publishable contribution to reliable and secure emergency message dissemination in the Internet of Vehicles.
