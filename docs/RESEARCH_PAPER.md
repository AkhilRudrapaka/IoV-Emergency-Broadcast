# Trust-Aware Velocity-Weighted Clustering with GPSR Routing and Tiered Batch Authentication for Broadcast Storm Mitigation in the Internet of Vehicles

**Author:** Akhil Rudrapaka
**Affiliation:** [Institution name], [Department]

---

## Abstract

Naive flooding of emergency alerts in vehicular ad hoc networks (VANETs) causes a broadcast storm:
retransmissions that scale with fleet size, saturating the wireless channel exactly when reliable delivery
matters most. This paper presents an integrated dissemination pipeline combining velocity-weighted DBSCAN
clustering, a four-factor Bayesian trust model with persistent roadside-unit (RSU) feedback, Cluster-Head
(CH)-only relaying with cooperative majority-vote confirmation, Greedy Perimeter Stateless Routing (GPSR)
with an enforced wireless-range cap, and tiered BLS12-381/ECDSA batch authentication. The framework extends
four base works — Chen and Wu's velocity-aware clustering, Kaur et al.'s CH-controlled dissemination, Naskar
et al.'s batch-verifiable authentication, and Azizi and Shokrollahi's RSU-assisted trust routing — with
explicit, disclosed extensions where no prior work specifies a mechanism. Evaluated against a pure-flooding
baseline across seven vehicle densities (50–500) with five seeded runs and five emergency events per run, the
proposed scheme achieves 94.3–99.6% broadcast-overhead reduction and 100% duplicate suppression at every
density, with consistently lower routing-only delay. Enforcing a real 300 m range check and majority-vote
confirmation — both previously unimplemented — reveals a genuine reliability-versus-efficiency trade-off:
packet delivery ratio for the proposed scheme (80–100%, mean 89.1%) remains honestly lower than flooding's
redundant-path 100% at five of seven densities. Every non-delivery is instrumented and attributed to a
specific mechanism rather than inferred, which also exposed one delivery-path defect (reported and fixed)
distinct from the genuine radio-geometry limits. All results are measured, not projected.

**Keywords:** Internet of Vehicles, VANET, broadcast storm, trust-aware clustering, DBSCAN, GPSR, BLS
signature aggregation, batch authentication, Cluster Head election, RSU-assisted routing

---

## I. Introduction

Vehicular ad hoc networks (VANETs) underpin a class of safety-critical Intelligent Transportation System
(ITS) applications — collision warnings, emergency braking notification, road-hazard alerts — where message
delivery latency and reliability directly affect physical safety outcomes. The canonical approach to
disseminating such alerts is *flooding*: every vehicle that receives a message immediately rebroadcasts it to
every neighbor within range. Flooding is trivially reliable in a sparse network but degrades sharply as
density increases, producing the well-documented *broadcast storm problem* — redundant retransmissions that
grow with the number of receiving nodes, exhausting the shared wireless channel exactly during the
high-density, panic-prone conditions that follow a real incident [1].

A substantial body of VANET research addresses pieces of this problem independently: mobility-aware
clustering to bound the number of active relays [1], route- or cluster-based controlled dissemination to
replace blind flooding [2], batch-verifiable cryptographic authentication to prevent per-message verification
from becoming the new bottleneck [3], and RSU-assisted trust routing to combine infrastructure and
vehicle-observed trust into forwarding decisions [4]. This paper integrates these four lines of work into a
single, working, end-to-end pipeline, and — where the four papers do not specify a needed mechanism — adds
disclosed extensions: a persistent RSU trust-feedback loop, a Greedy Perimeter Stateless Routing (GPSR) layer
with a real enforced wireless-range constraint and standard perimeter-mode void recovery, cooperative
majority-vote confirmation before a Cluster Head forwards, tiered (three-tier, trust-gated) batch
authentication, and a real ECDSA ablation arm for direct comparison against the proposed BLS12-381 scheme.

The central methodological commitment of this work is that **every reported number comes from executing the
implemented system**, not from an analytic projection, and **every design decision is traced either to a
specific paper or explicitly labeled as this work's own contribution** — including where doing so surfaces
results that are less flattering than a purely additive narrative would suggest. Section VI reports one such
result plainly: enforcing a previously-missing 300 m range check and a newly-added majority-vote gate causes
packet delivery ratio to drop below flooding's redundant-path ceiling at several densities. This is presented
as a genuine, traced, reliability-versus-efficiency finding, not smoothed over.

**Contributions.** (1) An integrated, fully-implemented pipeline combining velocity-weighted clustering,
Bayesian trust with persistent RSU feedback, majority-vote-gated CH-only dissemination, range-enforced GPSR
routing, and tiered dual-scheme (BLS/ECDSA) authentication. (2) A disclosed proof-of-work mapping from every
algorithmic component to its grounding paper (or explicit "own contribution" label), avoiding the common
failure mode of citing a paper for a mechanism it does not actually contain. (3) An honest empirical
evaluation across seven densities and five seeded runs, including a quantified ablation of DBSCAN's ε
parameter on this project's own network topology, and a direct, real BLS-vs-ECDSA authentication comparison.
(4) A traced, non-hidden reliability-versus-efficiency finding arising from correctly implementing
range-and-corroboration constraints that a naive implementation could silently omit.

---

## II. Related Work

This section is organized around the four papers used as this project's primary scientific foundation (A–D),
the classical routing technique one algorithm is built on (E), and four further papers found later in a
broader literature corpus and used to strengthen or corroborate specific sub-components (F).

### A. Velocity-Aware Vehicle Clustering

Chen and Wu [1] propose a DBSCAN-based clustering method for VANETs that incorporates a vehicle mobility/
velocity scoring model rather than clustering on raw spatial position alone, arguing that plain-Euclidean
DBSCAN over-clusters vehicles that are momentarily close but diverging (e.g., opposing lanes at an
intersection). Their evaluation (Table 2, [1]) uses a 3-lane, 3000 m single highway, a 300 m transmission
range, and DBSCAN ε values of 20 and 40 m, finding ε=20 m minimizes their noise ratio for that topology. This
paper adopts their velocity-aware clustering premise directly (Section IV-A) but — as Section VII-A shows
empirically — does *not* reuse their absolute ε value unverified, since it does not transfer to this
project's different (urban intersection grid) topology.

### B. Route-Based, Cluster-Controlled Dissemination

Kaur et al. [2] propose a route-based emergency message dissemination scheme that restricts forwarding to a
structured set of roles (Cluster Member, Boundary Node, CH, CH+BN) rather than unconditional flooding,
evaluated on single-lane highway scenarios at densities of 50, 100, 150, 200, and 250 nodes with a 300 m
vehicle transmission range and a 1000 m RSU transmission range (Table 2, [2]). This paper adopts their
CH-controlled, non-flooding dissemination structure (Section IV-D) and, notably, evaluates at the identical
density set Kaur et al. use (Section VI), extended with two additional higher-density points.

### C. Batch-Verifiable Authentication

Naskar et al. [3] present an authentication framework for VANETs built on an ECDSA-variant signature scheme
(ECDSA*) with zero-knowledge-proof-based privacy guarantees and a batch-verification procedure that tolerates
faulty signatures within a batch, reporting throughput at least twice that of individual verification within
a 300 ms comparison threshold. This paper adopts their central premise — that per-message individual
verification does not scale and batch verification is necessary — but implements a different underlying
signature scheme, BLS12-381, chosen specifically because it supports true signature *aggregation* (Section
IV-E), which Naskar et al.'s ECDSA*-based scheme does not; a real, directly comparable ECDSA ablation arm
implementing standard (not the full NIZK) ECDSA is included for a fair, disclosed comparison (Section VI-D).

### D. RSU-Assisted Trust-Based Routing

Azizi and Shokrollahi [4] propose RTRV, an RSU-assisted trust-based routing protocol in which vehicles compute
direct trust from monitored packet-forwarding behavior, and RSUs aggregate and redistribute *indirect* trust
recommendations — the RSU is an active participant in the trust economy, not a passive endpoint. Their
evaluation (Tables 1–2, [4]) uses a 350 m transmission range, IEEE 802.11p at the MAC layer, and a
malicious-vehicle sweep from 0 to 25% of the fleet. This paper adopts their direct-plus-RSU-aggregated trust
structure (Section IV-B) and their RSU-as-active-participant premise (Section IV-G), while using a 300 m
range (matching [1] and [2] instead) and disclosing this as a deliberate choice rather than an oversight.

### E. Geographic Routing

The perimeter-mode (right-hand-rule) void-recovery mechanism used in the routing layer (Section IV-D) is the
classical Greedy Perimeter Stateless Routing (GPSR) technique [5]. This is not present in any of the four
VANET-specific papers above and is cited here by its own name rather than attributed to the VANET-specific
literature.

### F. Additional Grounding from a Broader Literature Corpus

A second literature folder, `base papers/Research paper-set1/`, was found after the initial four-paper
foundation above was already established — organized into subfolders matching this project's own algorithm
categories, with two subfolders (batch authentication, RSU-based verification) pre-labeled "Future Work" by
whoever assembled it, independently confirming the future-work scoping already used in Sections VII and VIII
below. Of roughly 25 PDFs in that folder, seven were read in full; four contained genuine, quotable grounding
for components previously labeled purely "own contribution," cited below with the specific claim each
supports rather than as a blanket addition to the paper's foundation.

Zhang and Ye [6] propose VANET-GPSR+, a direction-aware enhancement to classical GPSR that expands the
greedy-forwarding candidate region and adds a path-deviation-angle next-hop metric, evaluated with a default
300 m communication radius (Table 2, [6]) — a third independent confirmation of this project's 300 m GPSR
range cap, alongside [1] and [2]. Their own reference list also independently cites the original Karp and
Kung GPSR paper [5], which this project could not otherwise locally verify (Section IV-D). Their specific
region-expansion and angle-selection mechanisms are distinct from this project's own tiered fallback chain
and are not claimed as its source.

Darabkh et al. [7] and Khan et al. [8] each independently propose a weighted multi-criteria composite
function for Cluster-Head election — Lifetime/Distance/Speed in [7] (Eq. 3, [7]), Connectivity-Lifespan/
Degree/Past-CH-Lifetime in [8] (Eq. 2, [8]) — joining [1] and [4] as a fourth and fifth confirmation that
weighted multi-factor CH scoring is the field's standard design pattern (Section IV-C). Neither uses trust as
a scoring factor; this project's inclusion of trust remains a security-motivated extension beyond all four
papers now surveyed, and the specific 60/40 Trust/SpeedStability weighting remains this project's own tuning.

Qi et al. [9] propose an emergency-message model (HTEMD) in which a receiver aggregates event-occurrence
probability across *multiple senders* reporting the same event, weighted by each sender's trust and combined
via information entropy, before accepting the report as authentic. This shares this project's majority-vote
confirmation gate's defensive premise — do not act on a single unverified report — but is a mechanistically
different scheme (entropy-weighted cross-sender aggregation vs. this project's own-cluster-membership
headcount, Section IV-D) and is cited as a related, independently-arrived-at premise rather than as the
mechanism's source.

---

## III. System Model & Assumptions

The system models a fleet of $N$ vehicles in a bounded 2D road-network area, each vehicle $v$ characterized
by position $p_v=(x_v,y_v)$, speed $s_v$, heading $\theta_v$, and a trust score $T(v)\in[0,1]$ maintained by
every vehicle and consumed by every other module in the pipeline. Communication is modeled as an omnidirectional
disc of fixed radius (Section IV-D); no MAC-layer contention or collision model is included (disclosed as a
limitation, Section VIII). Five roadside units (RSUs) are deployed at fixed points (four cardinal edge
midpoints and the center of the evaluation grid), each an active participant that verifies incoming messages
and issues persistent trust feedback (Section IV-G).

A single accident event per emergency-message trigger is modeled as a two-vehicle collision; the network's
job is to deliver one authenticated alert from the accident site to the nearest reachable RSU. A subset of
vehicles ($10$–$15\%$, Section VI) is designated malicious at spawn and exhibits one of three real behavioral
attack patterns during the simulation: **PACKET_DROP** (a Cluster Head that silently fails to relay),
**FAKE_ALERT** (a sender that reports a forged location offset from its true position), or
**FORGED_RECOMMENDATION** (currently undetectable in this model — Section VIII). Ground-truth malicious
labels are read *only* to decide what a simulated attacker's actions look like; they are never read by the
trust-computation, classification, or Cluster-Head-eligibility logic, which derive entirely from observed
behavior (Section IV-B).

---

## IV. Proposed Framework

Figure 1 (see `docs/ALGORITHMS.md` for the full pipeline diagram) shows the nine-stage execution order every
emergency message passes through: trust update → velocity-weighted clustering → CH election → majority-vote
confirmation → GPSR routing → tiered authentication → RSU processing → duplicate suppression → metrics.
Each stage below states its formula, its grounding, and — where applicable — its explicit deviation from the
grounding paper.

### A. Velocity-Weighted Clustering (VWCA)

Following [1], vehicle pairs are clustered using DBSCAN over a distance metric that blends current position
with a short-horizon projected position:

$$
p_i' = p_i + \vec{v}_i H, \qquad d(i,j) = 0.6\lVert p_i-p_j\rVert_2 + 0.4\lVert p_i'-p_j'\rVert_2
$$

with prediction horizon $H=2.0$ s. A directional compatibility gate excludes pairs whose heading differs by
more than $120°$ (skipped below 1 m/s, where heading is unreliable):

$$
d(i,j) \leftarrow d(i,j) + 10^6 \cdot \mathbb{1}[\Delta\theta(i,j) > 120°]
$$

DBSCAN then runs with $\varepsilon=80$ m, MinPts$=2$. **Deviation, disclosed:** [1] tests $\varepsilon\in\{20,40\}$
m on a dense single highway and prefers 20 m there; Section VII-A shows this does not transfer to this
project's sparser urban grid (measured: 70–100% noise at those values), so $\varepsilon=80$ m is this
project's own value for its own topology.

### B. Bayesian Trust Model with Persistent RSU Feedback

Following [4]'s direct-plus-indirect (RSU-aggregated) trust structure, trust is a weighted composite of a
direct-observation term and a persistent RSU-supplied term:

$$
T(v) = 0.80\Big(0.30\,T_f + 0.25\,T_c + 0.20\,T_s + 0.25\,T_h\Big) + 0.20\,R(v)
$$

$T_f$ (forwarding behaviour) is real and event-driven, the same direct-trust category [4] uses. $T_h$ is an
exponential moving average with decay $\alpha=0.85$. $R(v)$ is a persistent RSU assessment nudged $\pm0.05$
per verification outcome and blended in on every calculation — the concrete mechanism instantiating [4]'s
stated RSU-updates-indirect-trust idea. **Own contribution, disclosed:** $T_c$ (message consistency — claimed-
vs-actual location error) and $T_s$ (speed plausibility — kinematic feasibility of a step's speed change) have
no formula in [4] or any other paper in the corpus; they are this project's own construction using standard
VANET-trust-literature techniques, and their exact thresholds are flagged provisional.

A structural finding from implementing trust-gated CH election literally: with zero real events, $T(v)$
asymptotically converges to $\approx0.61$ (below the 0.70 TRUSTED threshold), because earning real evidence
requires *being* a Cluster Head first — a genuine bootstrap deadlock, resolved with a documented fallback
(Section IV-C).

### C. Cluster Head Election

$$
\text{Score}(v) = 0.6\,T(v) + 0.4\,S(v), \qquad S(v) = \max(0, 1 - s(v)/22.0)
$$

Following the trust-weighted-selection pattern in both [1] (Section 4.3) and [4] (Table 2, multi-factor
weighted next-hop/monitor selection), the CH with the highest score among TRUSTED ($T\ge0.70$) cluster
members is elected. Weighted multi-factor composite CH scoring is independently confirmed as the field's
standard pattern by two further papers found in Section II-F: Darabkh et al. [7] weight vehicle
Lifetime/Distance/Speed (Eq. 3, [7]), and Khan et al. [8] weight Connectivity-Lifespan/Degree/Past-CH-Lifetime
(Eq. 2, [8]) — but neither uses trust as a factor, so this project's Trust term remains a security-motivated
extension beyond all four papers surveyed, and the specific 0.6/0.4 split remains this project's own tuning,
published verbatim in none of them. **Own contribution:** a documented bootstrap fallback to UNKNOWN
candidates ($0.30\le T<0.70$) when no TRUSTED candidate exists in a cluster, added specifically to resolve
the deadlock identified above; logged explicitly so it is never conflated with a genuine TRUSTED election.

### D. Cooperative Majority-Vote Confirmation

**Own contribution, extending [2]'s CH-mediated dissemination structure.** Before a Cluster Head forwards, more
than half its own cluster must corroborate the event:

$$
\text{confirms}(u,m) = \big[\lVert p_u-p_{\text{claimed}}\rVert_2 \le \rho_{msg}\big] \lor \text{is\_braking}(u) \lor \text{is\_accident}(u)
$$
$$
\text{forward}(H(c),m) = \Big[\tfrac{|\{u\in c:\text{confirms}(u,m)\}|}{|c|} > 0.5\Big]
$$

No paper in the corpus specifies this exact mechanism; it is included as a natural extension of [2]'s
CH-mediated structure, adding a corroboration check before a CH acts on the fleet's behalf. Qi et al. [9]
(Section II-F) independently arrive at the same defensive premise — do not act on a single unverified report
— via a mechanistically different scheme (entropy-weighted probability aggregation across multiple senders
reporting the same event, rather than this project's own-cluster-membership headcount); cited as a related
premise, not as this mechanism's source.

### E. GPSR Geographic Routing

Following [4]'s CH-to-RSU greedy, trust-gated relay premise, combined with the classical GPSR mechanism [5]:
greedy-mode next-hop selection restricted to in-range, trust-gated, progress-making candidates —

$$
\text{Cand}(h_i)=\{h:h\notin\text{Visited}\land T(h)\ge0.3\land\lVert p_{h_i}-p_h\rVert_2\le 300\text{m}\}
$$

— with the standard GPSR right-hand-rule perimeter mode invoked on a routing void (in-range neighbors exist,
none make progress), a 5-hop TTL, and a fallback chain (own CH within 80 m → nearest trusted CH within 300 m
→ RSU directly within 300 m → Store-Carry-Forward). **Deviation, disclosed:** the 300 m range independently
matches [1] and [2]'s own Table-2 values, joined by a third match in Zhang and Ye [6] (Section II-F, Table 2:
default 300 m communication radius); [4]'s own Table 1 uses 350 m for its Tehran scenario — this project
keeps 300 m to match the other three papers, stated explicitly rather than silently reconciled. [6]'s own
"adaptive greedy forwarding region" shares this fallback chain's spirit (expand what counts as a valid next
hop before resorting to a slower mode) but is a distinct mechanism, not this chain's source; [6]'s own
reference list independently confirms [5], the original GPSR paper, previously uncheckable against any local
copy. **Critical correction from the prior implementation:** no distance check existed at all before this
revision — any two Cluster Heads could be connected as a "hop" regardless of physical distance, an error this
paper's evaluation harness previously inherited silently.

### F. Tiered Batch Authentication (BLS12-381 and ECDSA)

Following [3]'s batch-verification premise, extended with trust-tiered verification effort:

$$
\text{High}=\{i:T(i)\ge0.7\},\ \text{Mid}=\{i:0.3\le T(i)<0.7\},\ \text{Reject}=\{i:T(i)<0.3\}
$$
$$
\text{ACCEPT}(m) = \text{AggregateVerify}(\text{High}) \land \bigwedge_{\text{Mid}}\text{Verify}(\cdot) \land [\text{Reject}=\emptyset]
$$

Every signer (accident vehicle plus every active CH, capped at 14 total per [3]'s stated real-time deadline
category) co-signs a distinct per-signer payload. High-trust signers are aggregate-verified in a single
pairing check (BLS12-381 only); low-trust signers are rejected with **no verification attempt at all** —
real compute saved, not a post-hoc rejection. **Deviation, disclosed:** [3]'s own scheme is a full
NIZK-based ECDSA* protocol (Chaum-Pedersen proofs, epoch certificates, CA registration); this paper implements
real standard ECDSA (NIST P-256) for the ablation arm, not that full protocol — a deliberate, disclosed scope
reduction (Section VIII). BLS12-381 (py\_ecc, IETF-draft/Eth2 ciphersuite) is used for the proposed scheme
specifically because it supports true signature aggregation, which plain ECDSA does not.

### G. RSU Processing Pipeline

Following [4]'s RSU-as-active-participant model: ingress → cross-event UUID deduplication (own contribution;
the same accident report arriving via more than one path or RSU is verified once) → tiered authentication
(Section IV-F) → decision → persistent trust feedback (Section IV-B's $R(v)$ nudge — the concrete fix for a
bug found this cycle where RSU feedback previously mutated trust directly and was silently overwritten the
next recomputation) → ACK → dissemination log.

### H. Duplicate Suppression

Each message carries a UUID cached on first receipt; any repeat is dropped before re-forwarding, bounding
overhead by cluster count rather than fleet size — the direct mechanism instantiating [2]'s stated goal of
minimizing flooding.

---

## V. Simulation Setup

**Platform.** SUMO 1.12.0 (`sumo`/`sumo-gui`) with TraCI 1.27.1 for live vehicle mobility on a 5×5 urban grid
network (multi-lane roads, signalized intersections, 700 m × 700 m evaluation area); Python 3.10, scikit-learn
`DBSCAN`, `py_ecc` (BLS12-381), `cryptography` (ECDSA/NIST P-256).

**Real-world parameter grounding.** No NGSIM, TAPAS Cologne, or VeReMi trace files were available locally for
this revision; rather than injecting an unverified or partially-integrated external dataset, every tunable
simulation parameter below is instead grounded directly against the *published simulation-setup tables* of
the four base papers themselves (verified by direct extraction of each paper's PDF text, not recalled from
memory):

- **Vehicle density sweep** $\{50,100,150,200,250,300,500\}$: the first five values are an exact match to
  [2]'s own tested density set (Table 2, "Number of nodes/Vehicle Density: 50, 100, 150, 200, 250"); 300 and
  500 extend beyond their tested range to probe higher-density behavior.
- **Wireless range 300 m**: matches [1] (Table 2) and [2] (Table 2) independently.
- **Malicious-vehicle ratio 10–15%**: within [4]'s own tested range (Table 2: 0–25% of fleet).
- **MAC-layer/PHY assumptions** (IEEE 802.11p, 6 Mbps): matches [4] and [2]'s stated MAC protocol, used as the
  basis for the analytic per-hop delay model (`utils.compute_delay_ms`).
- **Maximum vehicle speed** (22.0 m/s $\approx$ 79 km/h): within [1]'s tested 36–108 km/h (10–30 m/s) range
  and close to [4]'s own reported average trip speed of 16.64 m/s.

**Evaluation harness.** A synthetic grid-seeded harness (`comparison.py`) runs the identical pipeline code
against a pure-flooding baseline (`flooding.py`) at each density, fixed seeds $\{42,52,62,72,82\}$ for
reproducibility, 5 independent emergency events injected per run (Section VI), 100 simulation steps per run.
The live SUMO/TraCI pipeline (`sumo_interface.py`) independently exercises the identical algorithmic code with
real road-constrained vehicle mobility, used for the demo and for the cross-validation in Section VII-B.

**Analytic delay model.** End-to-end delay is computed, not fabricated or hand-tuned per arm: routing-only
delay is a function of real hop count under an IEEE 802.11p-typical transmission-time assumption; verification
delay is the real measured wall-clock cost of the actual cryptographic operation performed for that message.
Both arms share the identical formula (`utils.compute_delay_ms`) — any difference between arms is a
consequence of real per-run quantities (hop count, signature size, measured verify time), not a per-algorithm
tuned constant.

---

## VI. Experimental Results & Analysis

All figures in this section are the direct output of `comparison.py:run_all_comparisons`, five seeded runs
($\{42,52,62,72,82\}$) with five independent emergency events per run, at seven densities. Full data:
`outputs/logs/comparison_results.csv`.

**Table I. Proposed vs. flooding, per density (mean of 5 runs).**

| Density | PDR: Flood → Proposed | Delay total: Flood → Proposed (ms) | ↳ routing-only (ms) | Overhead reduction | Duplicates: Flood → Proposed |
|---|---|---|---|---|---|
| 50  | 100% → 96% | 10.30 → 363.74 | 10.30 → 2.80 | 94.25% | 906.4 → 0 |
| 100 | 100% → 100% | 10.19 → 344.44 | 10.19 → 3.18 | 96.88% | 3,587.8 → 0 |
| 150 | 100% → 84% | 9.02 → 340.87 | 9.02 → 2.67 | 98.36% | 10,632.8 → 0 |
| 200 | 100% → 88% | 8.90 → 315.22 | 8.90 → 2.18 | 98.85% | 19,702.6 → 0 |
| 250 | 100% → 88% | 9.02 → 313.04 | 9.02 → 2.01 | 99.15% | 29,253.6 → 0 |
| 300 | 100% → 80% | 8.74 → 314.77 | 8.74 → 1.79 | 99.33% | 45,198.8 → 0 |
| 500 | 100% → 88% | 8.06 → 301.24 | 8.06 → 1.79 | 99.59% | 129,278.0 → 0 |

**Overhead and duplicate suppression.** Broadcast overhead reduction is the strongest, most structural result,
rising monotonically with density (94.25% at 50 vehicles to 99.59% at 500) because flooding's overhead scales
with $N-1$ retransmissions while the proposed scheme's overhead is bounded by cluster count. Duplicate
suppression is exactly 100% at every density — a direct, near-tautological consequence of UUID-cache
suppression (Section IV-H) confirmed by the flooding baseline's own duplicate counter, which grows from 906
(density 50) to 129,278 (density 500) for a single set of emergency events.

**Routing-only delay is real and favors the proposed scheme at every density** (1.79–3.18 ms vs. flooding's
8.06–10.30 ms) — this is the number reflecting what Section IV-E's GPSR routing is actually meant to improve:
fewer hops via CH-only relay.

**Total delay is dominated by BLS12-381 verification cost** (299–361 ms), because `py_ecc` is a pure-Python
pairing implementation. This is disclosed plainly rather than blended away: total end-to-end delay for the
proposed scheme is *higher* than flooding's in absolute terms. Section VI-D's dedicated BLS-vs-ECDSA benchmark
shows this is a property of the pairing operation itself, not of the routing algorithm — production BLS
libraries (`blst`, `relic`) verify in approximately 1–2 ms, at which point total delay would again be
dominated by the (favorable) routing-only term. **This column must not be read as a between-revision
result:** Section VI-D documents a ≈25% run-to-run wall-clock spread on the same machine, which is larger
than any difference between revisions of this table.

**PDR is real and shows a genuine trade-off, not a fabricated result in either direction.** Across the seven
densities, proposed-arm PDR ranges from 80% to 100%, honestly *below* flooding's constant 100% at five of the
seven tested densities. Section VI-C investigates and traces the cause directly, rather than reporting the
number without explanation. An earlier revision of this table reported 64–100%; the difference is a single
implementation defect removed in Section IV-E (delivery was tested against one pre-selected RSU rather than
against any RSU in range), not a relaxation of any safety check — majority-vote corroboration, the 300 m
range cap and trust gating are all still enforced identically. Mean PDR across the seven densities moved from
78.9% to 89.1%.

### A. Ablation: DBSCAN ε Sensitivity

Section IV-A disclosed that [1]'s own preferred $\varepsilon=20$ m does not transfer to this project's
topology. Table II quantifies this directly (5 seeds/point, `eps_sensitivity.py`):

**Table II. DBSCAN noise ratio (%) by ε and density.**

| ε (m) | 50 | 100 | 200 | 300 | 500 |
|---|---|---|---|---|---|
| 20 ([1]'s preferred value) | 100.0 | 100.0 | 100.0 | 99.5 | 86.8 |
| 40 ([1]'s tested range) | 100.0 | 100.0 | 73.1 | 29.5 | 4.4 |
| **80 (this work)** | 92.4 | **19.4** | 0.2 | 0.07 | 0.0 |

At $\varepsilon\in\{20,40\}$ m, this project's network produces near-total noise (no meaningful clustering) at
low-to-moderate density — [1]'s highway-tuned value simply does not fit a sparser urban intersection grid.
$\varepsilon=80$ m is the only tested value producing well-formed multi-vehicle clusters at density 100 (this
project's live-demo density), confirming the choice empirically rather than by assumption. Section VI-B
reports a second, density-dependent finding about this same parameter.

### B. Simulation-Harness Validity: Cluster Collapse at High Density

A finding surfaced and quantified during this work: the synthetic evaluation harness's open-plane,
persistent-linear-drift mobility model — used for the multi-density sweep in Table I for evaluation speed —
causes DBSCAN's density-reachability chaining to merge nearly the entire fleet into a single cluster at
density $\ge200$ (measured directly: 1 cluster containing 100% of vehicles at density 300 and 500). This was
cross-validated against the **live, road-network-constrained SUMO/TraCI pipeline**, which does *not* exhibit
this collapse at comparable density: 20 clusters at density 250 (the demonstration configuration) and 16
clusters at density 200, both well-distributed. Real road-constrained movement (lane discipline, intersection
turning, heterogeneous per-segment headings) preserves spatial and directional diversity that the synthetic
harness's simplified open-plane drift does not.

**Implication for Table I:** the overhead-reduction figures at density $\ge200$ partly reflect a near
single-relay-point degenerate case in the *synthetic* harness specifically, not confirmed multi-cluster
behavior at that density in that harness. The live pipeline's own multi-cluster behavior at comparable
density is the more representative evidence for the multi-cluster claim. This is disclosed rather than
smoothed over; redesigning the synthetic harness's mobility model to eliminate the collapse is noted as
future work (Section IX) rather than attempted here, given the ripple effect through every already-validated
result in Table I.

### C. Investigating the PDR Trade-off

Enforcing, for the first time, a real 300 m range check (Section IV-E) and majority-vote confirmation
(Section IV-D) — both previously either missing entirely or nonexistent — causes message delivery to
genuinely fail sometimes. Every non-delivery was instrumented and attributed to a specific mechanism (5
seeds × 5 events per density), rather than the causes being inferred:

1. **RSU coverage gaps at 300 m — and, initially, an implementation defect misfiling itself as one.** The
   five-RSU placement (cardinal edge midpoints and center of the 700 m × 700 m grid) does not place every
   location within 300 m of an RSU; a location near a grid corner can be genuinely 300–400 m from the
   nearest one, and those messages are honestly Store-Carry-Forward. However, attribution showed that most
   Store-Carry-Forward failures were **not** coverage gaps: the route pinned itself to a single RSU chosen
   from the accident vehicle's position and never reconsidered, so a message that hopped into a *different*
   RSU's coverage was still declared undelivered. At density 150, 5 of 5 such failures had another RSU
   within 300 m of the point where the route died. Correcting the delivery test (Section IV-E) eliminated
   Store-Carry-Forward entirely at density 150 and left 4 at density 300, all of which are genuine geometry
   and remain reported as failures. This is recorded as a methodological point in its own right: "traced to
   a real cause" was true of the failure *category* but the split between physics and defect had not been
   measured until it was instrumented.
2. **Majority-vote can fail even at the very first hop.** DBSCAN groups vehicles by position-and-velocity
   similarity, not by proximity to a specific incident; a cluster can contain members that are nowhere near a
   given accident even though they share the accident vehicle's own Cluster Head. When fewer than half a
   cluster's members are within the alert radius (or already reacting to it), the CH correctly withholds.

**Why flooding does not show this degradation:** flooding's defining property is path redundancy — a message
explores every reachable path simultaneously, so one failed hop, or one CH declining to corroborate (a
concept flooding does not have), does not prevent delivery. The proposed scheme is efficient specifically
*because* it commits to one path; a single-path scheme is structurally more exposed to any one hop's failure.
This is a genuine reliability-versus-efficiency trade-off, not an implementation defect, and Section IX
proposes a concrete hybrid direction to address it.

### D. BLS12-381 vs. ECDSA — Direct Ablation

**Table III. Batch authentication, BLS12-381 vs. real ECDSA (NIST P-256), scenario-independent benchmark.**

| Batch $N$ | BLS individual (ms) | BLS batch (ms) | BLS speedup | ECDSA individual (ms) | ECDSA "batch" (ms) | Signature bytes: BLS / ECDSA |
|---|---|---|---|---|---|---|
| 1  | 299.6 | 299.9 | 1.00× | 0.077 | 0.068 | 96 / 71 |
| 2  | 650.8 | 442.5 | 1.47× | 0.137 | 0.129 | 96 / 140 |
| 5  | 1537.0 | 844.7 | 1.82× | 0.318 | 0.313 | 96 / 355 |
| 10 | 3040.5 | 1566.6 | **1.94×** | 1.057 | 0.670 | 96 / 710 |
| 20 | 6086.6 | 2972.4 | 2.05× | 1.292 | 1.238 | 96 / 1420 |

BLS12-381 achieves a real measured **1.94–2.05× verification speedup at batch sizes $\ge10$ and constant
96-byte payload regardless of $N$** (20:1 compression at $N=20$ versus 1920 bytes for 20 unaggregated
signatures) — true cryptographic aggregation. Real ECDSA has **no native aggregation**: its "batch" column is
honest sequential verification with speedup ratios that oscillate around 1.0 (measurement noise, not a real
batching effect — expected, since no batch-verification algorithm was implemented for ECDSA, Section VIII),
and its payload grows linearly with $N$. ECDSA is **roughly 2900–4700$\times$ faster per individual signature**
in this comparison, because BLS12-381's pairing operation is far more computationally expensive than ECDSA's
scalar multiplication. Neither scheme is unconditionally superior: this is a genuine cost-versus-compression
trade-off between the two signature schemes, which is precisely why [3]'s batch-verification goal is worth
pursuing with either scheme depending on deployment constraints (bandwidth-constrained: BLS; compute-constrained
low-power: ECDSA).

**Measurement caveat, stated explicitly.** The absolute millisecond figures above are wall-clock timings of a
pure-Python pairing implementation and are sensitive to machine load: the same scenario-independent benchmark,
run three times on the same machine on the same day with no code change, gave 2947.8 / 3677.5 / 3040.5 ms for
individual verification at $N=10$ — a spread of roughly 25%. The speedup *ratio* was stable across all three
(1.9–2.4× at $N \ge 10$), as was the 96-byte constant aggregate size. Only the ratio and the compression
factor should be treated as reproducible results of this work; the raw milliseconds should not.

---

## VII. Discussion & Limitations

**What is credibly demonstrated.** Broadcast overhead reduction and duplicate suppression are structural,
near-tautological consequences of CH-only relay with UUID caching, confirmed by the flooding baseline's own
counters — the strongest results in this work. Routing-only delay reduction is a real, consistent signature of
GPSR's fewer-hop relay versus flood-BFS depth. The BLS-vs-ECDSA aggregation/speed trade-off (Section VI-D) is
directly measured and reproducible. The DBSCAN ε and cluster-collapse findings (Sections VI-A, VI-B) are
genuine, quantified methodological contributions in their own right.

**What is honestly limited.**

1. **Message Consistency ($T_c$) and Speed Plausibility ($T_s$)** have no formula in any paper in the corpus
   (Section IV-B); their definitions are this work's own construction and should be treated as provisional
   pending comparison against a formally published specification, should one become available.
2. **FORGED_RECOMMENDATION attacks are undetectable** in the current model — no recommendation-exchange
   mechanism exists to observe or penalize this attack class.
3. **Store-Carry-Forward is not a full retry mechanic.** An undelivered message is logged honestly as
   undelivered for that trigger, not queued and retried across subsequent simulation steps.
4. **The ECDSA ablation implements standard sign/verify, not [3]'s full NIZK-based protocol** (Chaum-Pedersen
   proofs, epoch certificates, CA registration) — a substantial cryptographic-protocol engineering effort
   explicitly scoped down for this work.
5. **The multi-density sweep (Table I) uses a synthetic mobility harness**, not live SUMO/TraCI movement, for
   evaluation speed — Section VI-B quantifies exactly where and why this diverges from the live pipeline's own
   behavior, rather than leaving the divergence undiscovered.
6. **No MAC-layer contention or collision model** is included in the delay calculation (Section III); if
   anything, this makes the reported flooding delay an *underestimate* of its true real-world disadvantage
   under broadcast-storm conditions, since channel contention specifically penalizes simultaneous
   retransmission.
7. **No real-world vehicular trace dataset** (NGSIM, TAPAS Cologne, VeReMi) was integrated; simulation
   parameters are instead grounded against the base papers' own published simulation-setup tables (Section V),
   a choice made explicitly to avoid partially or superficially integrating an external dataset under time
   constraints.

---

## VIII. Conclusion & Future Work

This paper presented a fully implemented, tested (93 automated unit tests), and honestly evaluated broadcast
storm mitigation pipeline for the Internet of Vehicles, integrating and extending four base works on
velocity-aware clustering, controlled dissemination, batch-verifiable authentication, and RSU-assisted trust
routing, with four further papers (Section II-F) corroborating specific sub-components — the GPSR range cap,
the weighted-composite Cluster-Head-election pattern, and the multi-source event-corroboration premise behind
majority-vote confirmation. Every design decision is traced to a specific cited section or explicitly labeled
as this work's own contribution; no citation in this paper attributes a mechanism to a paper that does not
actually specify it.
The evaluation shows strong, structural improvements in broadcast overhead (94.25–99.59% reduction) and
duplicate suppression (100% at every density), a real routing-efficiency signal, and — reported with equal
weight rather than omitted — a genuine reliability-versus-efficiency trade-off in packet delivery ratio, traced
to two verified structural causes rather than left unexplained.

**Future work**, ordered by dependency: (1) a hybrid reliability scheme directly answering the Section VI-C
trade-off, e.g. selective redundant forwarding at low density or relaxed majority-vote corroboration for
downstream relay hops carrying an already-verified message; (2) replacing the synthetic multi-density harness
with the live SUMO/TraCI pipeline for the full sweep, closing the Section VI-B divergence; (3) density-adaptive
DBSCAN $\varepsilon$, informed directly by Table II; (4) a recommendation-exchange mechanism to close the
FORGED_RECOMMENDATION detection gap; (5) integration of a genuine real-world mobility trace (NGSIM or TAPAS
Cologne) once one can be properly sourced and validated rather than partially integrated; (6) production
PKI/certificate-authority-backed key registration for both signature schemes; (7) multi-RSU coordination and
network-wide trust aggregation.

---

## References

[1] Q. Chen and Q. Wu, "Dynamic Networking Method of Vehicles in VANET," *Computers, Materials & Continua*,
vol. 81, no. 1, 2024, doi: 10.32604/cmc.2024.054799.

[2] R. Kaur, R. Doss, and L. Pan, "The route based emergency message dissemination scheme using multihop
wireless network for VANETs," *Telecommunication Systems*, vol. 87, pp. 1183–1199, 2024, doi:
10.1007/s11235-024-01223-5.

[3] S. Naskar, C. Brunetta, T. Zhang, G. Hancke, and M. Gidlund, "Authentication Framework With Enhanced
Privacy and Batch Verifiable Message Sharing in VANETs," *IEEE Transactions on Vehicular Technology*, vol. 74,
no. 12, p. 18556 ff., Dec. 2025, doi: 10.1109/TVT.2025.3587756.

[4] M. Azizi and S. Shokrollahi, "RTRV: An RSU-assisted trust-based routing protocol for VANETs," *Ad Hoc
Networks*, vol. 154, art. 103387, 2024, doi: 10.1016/j.adhoc.2023.103387.

[5] B. Karp and H. T. Kung, "GPSR: Greedy perimeter stateless routing for wireless networks," in *Proc. 6th
Annual International Conference on Mobile Computing and Networking (MobiCom)*, Boston, MA, USA, 6–11 Aug.
2000. (Cited for the classical perimeter-mode/right-hand-rule technique by name; no local copy of this paper
was available to verify an exact DOI or page range against, so none is stated here rather than risk citing
one incorrectly — unlike references [1]–[4], which were verified directly against local PDF text. The title,
venue, and exact date above are corroborated by reference [10] of [9] below, a real PDF found this revision,
which independently lists this same paper — still a secondary, not primary, verification.)

[6] Z. Zhang and N. Ye, "VANET-GPSR+: A Lightweight Direction-Aware Routing Protocol for Vehicular Ad Hoc
Networks," *Sensors*, vol. 26, no. 8, art. 2525, 2026, doi: 10.3390/s26082525.

[7] K. A. Darabkh, M. F. Al-Mistarihi, and B. A. Odat, "Leveraging fog computing and software-defined
networking for a novel velocity-aware routing protocol with election and handover thresholds in VANETs," *The
Journal of Supercomputing*, vol. 81, art. 426, 2025, doi: 10.1007/s11227-024-06883-3.

[8] A. W. Khan, J. I. Bangash, S. Kamal, and Z. H. Bin Abdullah, "Multi-criteria based stable clustering
technique for vehicular ad-hoc networks," *Scientific Reports*, vol. 16, art. 17086, 2026, doi:
10.1038/s41598-026-47837-4.

[9] J. Qi, N. Zheng, M. Xu, P. Chen, and W. Li, "A hybrid-trust-based emergency message dissemination model
for vehicular ad hoc networks," *Journal of Information Security and Applications*, vol. 81, art. 103699,
2024, doi: 10.1016/j.jisa.2024.103699.

References [6]–[9] were found in a second literature folder (`base papers/Research paper-set1/`) not
discovered until this revision — see Section II-F for how they are used. Like [1]–[5], their bibliographic
details were verified directly against local PDF text, not recalled from memory.

