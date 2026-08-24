# Algorithms & Mathematical Model

**Project:** Mitigation of Broadcast Storm Problem for Reliable Emergency Message Dissemination in Internet of Vehicles using Trust-Aware Clustering and Batch Authentication

This document formalizes the algorithms implemented in the codebase and shows how they compose into a single emergency-dissemination pipeline. Every symbol, weight, and threshold below is taken directly from the implementation (`config.py`, `trust.py`, `clustering.py`, `cluster_head.py`, `routing.py`, `bls_auth.py`, `ecdsa_auth.py`, `broadcast.py`, `rsu.py`) — this is a description of what runs, not an aspirational design.

**Provenance note (read before quoting formulas as report-verbatim):** this revision aligns the four algorithms below to weights and definitions supplied directly in chat by the project author, described as coming from a "Final Project Report (Group 83)." That document itself was not available on disk when this revision was made (checked project root, `base papers/`, and the whole home directory) — two factors, **Message Consistency (Tc)** and **Speed Plausibility (Ts)** in §1, were given as names and weights only, with no formula. Their definitions below are this session's own construction from standard VANET-trust-literature techniques (kinematic plausibility, claimed-location consistency), clearly marked where they appear. Everything else (weights, thresholds, the GPSR fallback chain and range values, the tiered-authentication cutoffs) was given explicitly and is implemented as specified.

---

## 1. Bayesian Trust Model

**Implementation:** `trust.py :: TrustManager.calculate_trust()`
**Base paper lineage:** Azizi & Shokrollahi 2024 (RTRV) — direct+indirect, RSU-aggregated trust assessment as the architectural pattern this section's RSU boost follows.

For a vehicle $v$, trust is a weighted composite of four factors, all derived from real observed behavior — **never** from the simulator's ground-truth `is_malicious` label.

### 1.1 Component scores

**Forwarding Behaviour ($T_f$)** — real, event-driven, populated by `update_behavior_event()` calls from `broadcast.py` on every actual relay attempt:

$$
T_f(v) = \begin{cases} \dfrac{\text{successful\_forwards}(v)}{\text{forward\_attempts}(v)} & \text{if forward\_attempts}(v) > 0 \\[6pt] 0.5\ (\text{neutral}) & \text{otherwise} \end{cases}
$$

**Message Consistency ($T_c$, this session's construction — see provenance note)** — claimed-vs-actual sender location at the moment $v$ last reported an emergency message (`accident.py`). An honest sender's claimed location is always its true position (error $=0$); a simulated `FAKE_ALERT` attacker's claimed location is deliberately offset by a real, disclosed forgery vector (200–500 m, `FAKE_ALERT_LOCATION_OFFSET_RANGE_M`) — a real attacker-behavior simulation, not a fabricated detection result:

$$
T_c(v) = \begin{cases} 1.0 & \text{if } \neg\text{has\_reported\_message}(v)\ (\text{neutral, no evidence yet}) \\ 0.5 & \text{if has\_reported\_message}(v) \wedge \text{err}(v) = 0 \\[3pt] 1.0 & \text{if has\_reported\_message}(v) \wedge \text{err}(v) \le \tau_{loc} \\[3pt] \max\!\big(0,\; 1 - \tfrac{\text{err}(v) - \tau_{loc}}{\tau_{loc}}\big) & \text{if has\_reported\_message}(v) \wedge \text{err}(v) > \tau_{loc} \end{cases}
$$

*(reads as: no message reported yet → neutral 0.5; reported and within the GPS-class tolerance $\tau_{loc} = \texttt{MESSAGE\_LOCATION\_TOLERANCE\_M} = 50\text{ m}$ → full credit 1.0; beyond it → linear penalty)*

**Speed Plausibility ($T_s$, this session's construction — see provenance note)** — kinematic feasibility: is this step's speed change within a physically realistic bound? The bound matches the SUMO vehicle type's own `decel="4.5"` (already used in `network/routes*.xml`, not an invented constant):

$$
T_s(v) = \begin{cases} \max\!\big(0,\; 1 - \tfrac{s(v) - s_{max}}{s_{max}}\big) & \text{if } s(v) > s_{max} = 22.0\text{ m/s} \\[3pt] 1.0 & \text{if } |s(v) - s_{prev}(v)| \le \delta_{max} = 4.5\text{ m/s} \\[3pt] \max\!\big(0,\; 1 - \tfrac{|s(v)-s_{prev}(v)| - \delta_{max}}{\delta_{max}}\big) & \text{otherwise} \end{cases}
$$

### 1.2 Historical trust (EMA)

$$
T_{current}(v) = \frac{w_f T_f + w_c T_c + w_s T_s}{w_f + w_c + w_s}
$$

$$
T_h^{(t)}(v) = \alpha\, T_h^{(t-1)}(v) + (1-\alpha)\, T_{current}^{(t)}(v), \qquad \alpha = \texttt{TRUST\_EMA\_ALPHA} = 0.85
$$

### 1.3 Composite trust

$$
\boxed{T_{composite}(v) = w_f T_f(v) + w_c T_c(v) + w_s T_s(v) + w_h T_h(v)}
$$

$$
w_f = 0.30,\quad w_c = 0.25,\quad w_s = 0.20,\quad w_h = 0.25 \qquad \left(\textstyle\sum w_i = 1.00\right)
$$

### 1.4 RSU boost (persistent)

Every RSU verification outcome for a vehicle nudges a **persistent** per-vehicle assessment $R(v)$ (`vehicle.rsu_trust_assessment`, initialized neutral at 0.5) by `RSU_TRUST_NUDGE = 0.05` toward 1 (success) or 0 (failure), clamped to $[0,1]$. Unlike the pre-revision design — which mutated `vehicle.trust` directly and had that mutation **silently overwritten** the next time `calculate_trust()` ran — $R(v)$ is a genuine, persistent *input* to the formula:

$$
\boxed{T(v) = w_{veh}\, T_{composite}(v) + w_{rsu}\, R(v)}, \qquad w_{veh} = 0.80,\ w_{rsu} = 0.20
$$

$$
T(v) \leftarrow \text{clip}(\text{round}(T(v), 2),\ 0,\ 1)
$$

### 1.5 Classification

$$
\text{class}(v) = \begin{cases}
\textsf{MALICIOUS} & \text{if } T(v) < 0.3 \\
\textsf{TRUSTED} & \text{if } T(v) \ge 0.7 \\
\textsf{UNKNOWN} & \text{otherwise}
\end{cases}
$$

A `MALICIOUS` vehicle is blacklisted and immediately loses Cluster-Head eligibility. **`is_malicious`/`attack_type` never appear on the right-hand side of any equation in this section** — they only decide what a simulated attacker's real actions look like elsewhere in the pipeline (§6, §7).

### 1.6 Bootstrap consequence (found and resolved this session)

Every vehicle starts at $T=0.5$, and $T_f/T_c/T_s$ all start neutral too — so with **zero** real events, $T(v)$ asymptotically converges to $\approx 0.61$, strictly below the $0.7$ TRUSTED threshold, and never crosses it without real forwarding/RSU evidence. Since forwarding evidence requires *being* a Cluster Head to generate in the first place, taking "CH election only among TRUSTED vehicles" (§3) completely literally creates a permanent deadlock: no vehicle would ever become CH-eligible, and the pipeline would silently elect zero Cluster Heads forever. §3 documents the bootstrap-fallback resolution.

---

## 2. Velocity-Weighted Clustering Algorithm (VWCA)

**Implementation:** `clustering.py :: ClusterManager`
**Base paper lineage:** Chen & Wu 2024 — DBSCAN-based vehicle clustering with a mobility/velocity scoring model.

Unchanged from the prior revision — confirmed to already match the supplied specification exactly.

### 2.1 Mobility-aware distance function

$$
p_i' = p_i + \vec{v}_i \cdot H, \qquad H = \texttt{VELOCITY\_PREDICTION\_HORIZON} = 2.0\text{ s}
$$

$$
d(i,j) = w_{pos}\lVert p_i - p_j\rVert_2 + w_{mob}\lVert p_i' - p_j'\rVert_2, \qquad w_{pos}=0.6,\ w_{mob}=0.4
$$

### 2.2 Directional compatibility gate

Applied only when both vehicles exceed $1.0$ m/s (`MIN_SPEED_FOR_HEADING_GATE`):

$$
d(i,j) \leftarrow d(i,j) + 10^6 \cdot \mathbb{1}[\Delta\theta(i,j) > 120^\circ]
$$

Stationary vehicles ($s \le 1.0$ m/s — e.g. queued behind an accident) skip the gate entirely.

### 2.3 DBSCAN

$$
C = \text{DBSCAN}(D,\ \varepsilon=80.0\text{ m},\ \text{MinPts}=2)
$$

### 2.4 Smart re-clustering (skip conditions)

A full re-clustering pass is skipped unless **any** of:

$$
\text{churn} > 0.20 \quad\lor\quad \max_v |\Delta T(v)| > 0.15 \quad\lor\quad \sigma_{speed} > 3.0\text{ m/s} \quad\lor\quad \text{stability} < 0.70
$$

(`RECLUSTER_MEMBERSHIP_CHANGE_THRESHOLD`, `RECLUSTER_TRUST_DELTA_THRESHOLD`, `RECLUSTER_MOBILITY_STD_THRESHOLD`, `RECLUSTER_STABILITY_SCORE_THRESHOLD` respectively.) Cluster identity persists across steps via Jaccard best-overlap matching (`cluster_stability.py`).

---

## 3. Cluster Head Election

**Implementation:** `cluster_head.py :: ClusterHeadManager.select_cluster_heads()`

Per the supplied specification, election is restricted to **TRUSTED** vehicles ($T \ge 0.7$) — with the bootstrap fallback from §1.6, since taking this literally with no fallback deadlocks the pipeline:

$$
E_1(c) = \{v \in c : \neg\text{blacklisted}(v) \wedge T(v) \ge 0.7\}
$$

$$
E_2(c) = \{v \in c : \neg\text{blacklisted}(v) \wedge T(v) \ge 0.3\} \qquad \text{(bootstrap fallback, used only if } E_1(c)=\emptyset\text{)}
$$

$$
S(v) = \max\!\big(0,\ 1 - \tfrac{s(v)}{22.0}\big), \qquad \text{Score}(v) = 0.6\,T(v) + 0.4\,S(v)
$$

$$
\boxed{H(c) = \operatorname*{argmax}_{v \in E_1(c)} \text{Score}(v), \quad \text{falling back to } \operatorname*{argmax}_{v \in E_2(c)} \text{Score}(v) \text{ if } E_1(c) = \emptyset}
$$

A bootstrap election is logged explicitly (`[BOOTSTRAP: no TRUSTED candidate available]`) so it's never silently indistinguishable from a genuine TRUSTED election.

---

## 4. GPSR Geographic Forwarding

**Implementation:** `routing.py :: RoutingEngine.find_route()`
**Base paper lineage:** Kaur et al. 2024 (CH-controlled dissemination) for the "only CHs forward" structure; Azizi & Shokrollahi 2024 (RTRV) for trust-gated, RSU-aware geographic routing; classical GPSR (Karp & Kung, 2000) for the greedy/perimeter mechanism itself.

The prior revision's routing had **no distance cap on any hop** — routes could span physically impossible distances regardless of a vehicle's actual wireless range. This section replaces that with a real 300 m range enforcement, a fallback chain, and standard GPSR perimeter-mode recovery.

### 4.1 Fallback chain

1. **Own Cluster Head within 80 m** ($r_{own} = \texttt{GPSR\_OWN\_CH\_RANGE\_M}$).
2. **Nearest trusted CH within 300 m** ($T \ge 0.3$, $r = \texttt{GPSR\_RANGE\_M}$).
3. **RSU directly within 300 m** (RSU-as-CH fallback for isolated/noise vehicles).
4. **Store-Carry-Forward** — no relay available; the message is honestly undelivered this trigger. (This pass does not implement multi-step message queuing/retry — a materially larger scope, disclosed as a simplification.)

### 4.2 Greedy mode

From hop $h_i$, restricted to unvisited, trust-gated, **in-range** candidates:

$$
\text{Cand}(h_i) = \{h : h \notin \text{Visited} \wedge T(h) \ge 0.3 \wedge \lVert p_{h_i}-p_h\rVert_2 \le 300\text{ m}\}
$$

$$
\text{Progress}(h_i) = \{h \in \text{Cand}(h_i) : \lVert p_h - p_{RSU}\rVert_2 < \lVert p_{h_i} - p_{RSU}\rVert_2\}
$$

$$
h_{i+1} = \operatorname*{argmin}_{h \in \text{Progress}(h_i)} \lVert p_{h_i} - p_h\rVert_2 \qquad \text{if } \text{Progress}(h_i) \ne \emptyset
$$

### 4.3 Perimeter mode (routing voids)

If $\text{Progress}(h_i) = \emptyset$ but $\text{Cand}(h_i) \ne \emptyset$ (a *void*: in-range neighbors exist, none make progress), switch to the standard right-hand rule: from the bearing $\beta_{in}$ the path arrived on, pick the neighbor reached by the smallest **clockwise** turn —

$$
h_{i+1} = \operatorname*{argmin}_{h \in \text{Cand}(h_i)} \big[(\beta_{in} - \beta(h_i, h)) \bmod 2\pi\big]
$$

— and continue walking the perimeter until a hop closer to the RSU than the void-entry distance is found (resume greedy mode) or the path dead-ends.

### 4.4 Termination

$$
\text{TTL} = 5 \text{ hops}\ (\texttt{GPSR\_TTL\_HOPS}); \qquad \text{success if } \lVert p_{h_i} - p_{RSU}\rVert_2 \le 300\text{ m} \text{ for some } i \le \text{TTL}
$$

Otherwise: Store-Carry-Forward. Loop prevention is enforced throughout ($h_i \notin \text{Visited}$ for all $i$), guaranteeing termination.

---

## 5. Cooperative Majority-Vote Confirmation

**Implementation:** `broadcast.py :: BroadcastManager._has_majority_confirmation()`

Before a Cluster Head forwards (in both the fan-out and route-relay paths), more than 50% of its own cluster members must corroborate the event. A member $u$ *confirms* if it is within the message's real alert radius $\rho_{msg}$ (set per severity in `accident.py`, e.g. 400 m for HIGH) of the claimed location, or is itself already reacting to the accident (`is_braking`/`is_accident` — real, already-tracked congestion state):

$$
\text{confirms}(u, m) = \big[\lVert p_u - p_{claimed}\rVert_2 \le \rho_{msg}\big] \;\lor\; \text{is\_braking}(u) \;\lor\; \text{is\_accident}(u)
$$

$$
\boxed{\text{forward}(H(c), m) = \Big[\tfrac{|\{u \in c : \text{confirms}(u,m)\}|}{|c|} > 0.5\Big]}
$$

If the check fails, the CH withholds — logged explicitly, no trust penalty (withholding for lack of corroboration is not misbehavior).

---

## 6. Tiered Batch Authentication: BLS12-381 (proposed) and ECDSA (ablation)

**Implementation:** `bls_auth.py`, `ecdsa_auth.py`
**Base paper lineage:** Naskar et al. 2025 — the architecture's specified scheme is ECDSA batch verification; this project implements real BLS12-381 as an improvement, with real ECDSA kept as the ablation baseline for a direct comparison.

### 6.1 Chain-of-custody signing (both schemes)

The accident vehicle and every active Cluster Head co-sign a distinct per-signer payload, capped at `MAX_CHAIN_SIGNERS = 14` total signers (Report S6: ~100 ms deadline / ~7 ms per signature) — when more CHs are active than the cap allows, only the highest-trust ones co-sign:

$$
m_{v,\rho} = \texttt{message\_id} \,\|\, \texttt{sender} \,\|\, \texttt{location} \,\|\, \texttt{severity} \,\|\, v \,\|\, \rho
$$

### 6.2 BLS12-381 (`bls_auth.py`, via `py_ecc.bls.G2ProofOfPossession`)

$$
\sigma_v = \text{Sign}(sk_v, m_{v,\rho}) \in \mathbb{G}_2\ (96\text{ bytes, constant regardless of batch size})
$$

$$
\sigma_{agg} = \sigma_1 \oplus \cdots \oplus \sigma_n, \qquad \text{AggregateVerify} = \mathbb{1}\Big[e(\sigma_{agg}, G_2) = \textstyle\prod_i e(H(m_i), pk_i)\Big]
$$

True cryptographic aggregation: $n$ signatures collapse into one 96-byte aggregate, verified with one pairing check — real measured **2.11× speedup and 20:1 payload compression** at batch size 20 (`outputs/RESULTS_SUMMARY.md`).

### 6.3 ECDSA (`ecdsa_auth.py`, NIST P-256, via the `cryptography` library)

$$
\sigma_v = \text{Sign}_{ECDSA}(sk_v, m_{v,\rho}), \qquad \text{Verify}_{ECDSA}(pk_v, m_{v,\rho}, \sigma_v) \in \{0,1\}
$$

**No native aggregation exists for plain ECDSA.** "Batch" here means real, honestly-labeled sequential verification of $n$ signatures — genuine per-signer cost, no pairing-based speedup, no payload compression ($n$ DER-encoded signatures in, $n$ bytes out, always). This is the central, real, reportable contrast with BLS: ECDSA is dramatically cheaper *per signature* in this pure-Python comparison (~0.07 ms vs. BLS's ~300 ms, since BLS pairing is far more computationally expensive than ECDSA scalar multiplication) but cannot compress or batch-verify the way BLS does — the tradeoff is fundamental to the two signature schemes, not an implementation artifact.

### 6.4 Tiered verification (both schemes, `bls_auth.py`'s `bls_batch` mode)

Signers are partitioned by trust into three tiers — the middle and reject tiers are new this revision (previously a 2-way high/low split gated by a global on/off flag):

$$
\text{High} = \{i : T(i) \ge 0.7\}, \quad \text{Mid} = \{i : 0.3 \le T(i) < 0.7\}, \quad \text{Reject} = \{i : T(i) < 0.3\}
$$

$$
\text{valid(High)} = \text{AggregateVerify}(\text{High}), \qquad \text{valid(Mid)} = \bigwedge_{i \in \text{Mid}} \text{Verify}(pk_i, m_i, \sigma_i)
$$

$$
\text{valid(Reject)} = \big[\text{Reject} = \emptyset\big] \qquad \text{(no verify attempt at all -- real compute saved, unconditional)}
$$

$$
\boxed{\text{ACCEPT}(m) = \text{valid(High)} \wedge \text{valid(Mid)} \wedge \text{valid(Reject)}}
$$

---

## 7. RSU Processing Pipeline

**Implementation:** `rsu.py :: RSU.receive_and_process_message()`, `RSUManager`
**Base paper lineage:** Azizi & Shokrollahi 2024 (RTRV) — RSU as an active, coordinating trust/routing participant, not a passive endpoint.

1. **Ingress** — message received from the routed path.
2. **Cross-event dedup** — the same accident UUID (`message.message_id`), whether reported via multiple Cluster Heads or delivered to more than one RSU, is verified **only once**; a duplicate returns the cached ACK without re-verifying (`RSUManager.processed_message_ids`).
3. **Tiered batch authentication** — §6.4.
4. **Decision** (accept/reject) + analytics log entry.
5. **Persistent trust feedback** — §1.4's $R(v)$ nudge, survives across steps (the CRITICAL fix — the prior design's `vehicle.trust += 0.05` was silently overwritten the next `calculate_trust()` call).
6. **ACK** + TCC dissemination log.

---

## 8. Duplicate Suppression

**Implementation:** `broadcast.py :: BroadcastManager`, `messaging.py :: EmergencyMessage`

Unchanged from the prior revision. Each message carries a UUID; a mutable cache tracks every `message_id` already relayed, giving $O(1)$ average-case duplicate detection. Two contexts share the same cache: controlled fan-out across active CHs (first relay accepted, rest suppressed — bounds overhead to $O(|\text{clusters}|)$ instead of $O(|V|)$ under naive flooding) and route relay (loop-free by construction via §4's `Visited` set).

---

## Parameter Reference

| Symbol | Name | Value |
|---|---|---|
| $w_f, w_c, w_s, w_h$ | Bayesian trust weights (Tf/Tc/Ts/Th) | $0.30, 0.25, 0.20, 0.25$ |
| $\alpha$ | Trust EMA smoothing | $0.85$ |
| $w_{veh}, w_{rsu}$ | RSU trust boost blend | $0.80, 0.20$ |
| Blacklist / Trusted thresholds | | $0.3 \,/\, 0.7$ |
| $\delta_{max}$ | Max plausible per-step speed change | $4.5$ m/s |
| $\tau_{loc}$ | Message location consistency tolerance | $50$ m |
| $\varepsilon$, MinPts | DBSCAN | $80.0$ m, $2$ |
| $H$ | Velocity prediction horizon | $2.0$ s |
| $w_{pos}, w_{mob}$ | Clustering distance weights | $0.6, 0.4$ |
| Max heading gate | Directional compatibility | $120^\circ$ (above 1.0 m/s) |
| Reclustering skip thresholds | churn / trust-Δ / stability | $0.20 / 0.15 / 0.70$ |
| CH score weights | Trust / Speed-stability | $0.6, 0.4$ |
| GPSR range | Wireless hop limit | $300$ m |
| GPSR own-CH range | Fallback tier 1 | $80$ m |
| GPSR TTL | Max hops | $5$ |
| BLS/ECDSA trust tiers | High / Mid / Reject | $\ge 0.7$ / $0.3$–$0.7$ / $<0.3$ |
| Signature size (BLS) | G2, constant | $96$ bytes |
| Signature size (ECDSA) | DER-encoded P-256, ~constant | ~$71$–$72$ bytes |
| Max chain signers | CH pre-screening cap | $14$ |
| Majority-vote threshold | Cluster corroboration | $>50\%$ |

---

## Honest Scope Notes

- **Tc and Ts have no verified external formula** — see the provenance note at the top of this document. Compare against the source report's exact §3 once available.
- **`is_malicious`/`attack_type` never appear in §1's classification formula.** They decide only what a simulated attacker's real actions look like (§6's FAKE_ALERT location forgery, `broadcast.py`'s PACKET_DROP relay failure) — never what the trust system concludes. Only `PACKET_DROP` (via real forwarding failure) and, this revision, `FAKE_ALERT` (via §1's $T_c$ location-consistency check) produce observable behavioral signals. `FORGED_RECOMMENDATION` still produces none — no recommendation-exchange mechanism exists in the current 4-factor model (the prior 5-factor model had a neighbor-recommendation term; the supplied 4-factor spec does not).
- **Store-Carry-Forward (§4.1 tier 4) is not a full multi-step retry mechanic** — a message that can't find any in-range relay is honestly logged as undelivered for that trigger, not queued and retried on a later step. Building real message-lifetime persistence across steps is materially larger scope.
- **BLS key issuance** and **ECDSA key issuance** are both in-memory, self-issued registries, not a production PKI/certificate authority — the standard "trusted registration" assumption in VANET security literature (e.g. IEEE 1609.2), CA modeling out of scope.
- **ECDSA implements standard sign/verify, not the full Naskar et al. 2025 NIZK-based ECDSA\* protocol** (Chaum-Pedersen proofs, epoch certificates, CA registration) — a cryptographic-protocol engineering effort well beyond this pass's scope, and explicitly scoped down with the project author's approval.
- **RSU cross-event dedup (§7.2) is implemented and correct, but the current single-route-per-event pipeline doesn't yet generate many redundant-delivery scenarios for it to fire on every run** — it's exercised whenever one does occur (e.g. the same accident reported via more than one path).
