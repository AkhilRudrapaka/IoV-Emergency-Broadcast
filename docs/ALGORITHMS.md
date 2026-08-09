# Algorithms & Mathematical Model

**Project:** Mitigation of Broadcast Storm Problem for Reliable Emergency Message Dissemination in Internet of Vehicles using Trust-Aware Clustering and Batch Authentication

This document formalizes the six core algorithms implemented in the codebase and shows how they compose into a single emergency-dissemination pipeline. Every symbol, weight, and threshold below is taken directly from the implementation (`config.py`, `trust.py`, `clustering.py`, `cluster_head.py`, `routing.py`, `bls_auth.py`, `broadcast.py`) — this is a description of what runs, not an aspirational design.

---

## 1. Trust Evaluation Score

**Implementation:** `trust.py :: TrustManager.calculate_trust()`

For a vehicle $v$ with behavior counters accumulated over the simulation, trust is a weighted composite of five components.

### 1.1 Component scores

**Forwarding trust** (successful relays / attempted relays):

$$
T_{fwd}(v) = \begin{cases} \dfrac{\text{successful\_forwards}(v)}{\text{forward\_attempts}(v)} & \text{if forward\_attempts}(v) > 0 \\[6pt] 0.85 \;(\text{or } 0.15 \text{ if malicious w/ PACKET\_DROP}) & \text{otherwise} \end{cases}
$$

**Authentication trust** (successful auth / attempted auth):

$$
T_{auth}(v) = \begin{cases} \dfrac{\text{auth\_successes}(v)}{\text{auth\_attempts}(v)} & \text{if auth\_attempts}(v) > 0 \\[6pt] 0.95 \;(\text{or } 0.10 \text{ if malicious w/ FAKE\_ALERT}) & \text{otherwise} \end{cases}
$$

**Packet delivery ratio trust:**

$$
T_{pdr}(v) = \begin{cases} \dfrac{\text{successful\_forwards}(v)}{\text{total\_received}(v)} & \text{if total\_received}(v) > 0 \\[6pt] 0.90 \;(\text{or } 0.25 \text{ if malicious}) & \text{otherwise} \end{cases}
$$

**Neighbor recommendation trust** — average trust reported by non-blacklisted, non-malicious neighbors $N(v)$ (falls back to a neighbor's own trust score if it has not filed an explicit recommendation for $v$):

$$
T_{rec}(v) = \frac{1}{|N'(v)|}\sum_{u \,\in\, N'(v)} \text{rec}_u(v), \qquad N'(v) = \{u \in N(v) : \neg\text{blacklisted}(u) \wedge \neg\text{malicious}(u)\}
$$

All three counter-based ratios are clipped to $[0,1]$. Malicious vehicles have their own behavior counters synthetically degraded before scoring (`PACKET_DROP` reduces `successful_forwards`, `FAKE_ALERT` reduces `auth_successes`), so the trust drop is a consequence of simulated bad behavior, not a hard-coded label.

### 1.2 Historical trust (EMA)

An intermediate, non-historical composite is computed first:

$$
T_{current}(v) = \frac{w_{fwd} T_{fwd} + w_{auth} T_{auth} + w_{pdr} T_{pdr} + w_{rec} T_{rec}}{w_{fwd} + w_{auth} + w_{pdr} + w_{rec}}
$$

then folded into an exponential moving average of historical trust with smoothing factor $\alpha$:

$$
T_{hist}^{(t)}(v) = \alpha \, T_{hist}^{(t-1)}(v) + (1-\alpha)\, T_{current}^{(t)}(v), \qquad \alpha = \texttt{TRUST\_EMA\_ALPHA} = 0.7
$$

### 1.3 Composite trust (the "full 5-term formula")

$$
\boxed{T(v) = w_{fwd}T_{fwd}(v) + w_{auth}T_{auth}(v) + w_{pdr}T_{pdr}(v) + w_{hist}T_{hist}(v) + w_{rec}T_{rec}(v)}
$$

$$
w_{fwd}=0.30,\quad w_{auth}=0.25,\quad w_{pdr}=0.20,\quad w_{hist}=0.15,\quad w_{rec}=0.10 \qquad \left(\textstyle\sum w_i = 1.00\right)
$$

$$
T(v) \leftarrow \text{clip}\big(\text{round}(T(v), 2),\; T_{min}=0,\; T_{max}=1\big)
$$

### 1.4 Blacklisting / classification condition

$$
\text{class}(v) = \begin{cases}
\textsf{MALICIOUS} & \text{if } T(v) < 0.3 \;\lor\; \text{is\_malicious}(v) \\
\textsf{TRUSTED} & \text{if } T(v) \ge 0.7 \\
\textsf{UNKNOWN} & \text{otherwise}
\end{cases}
$$

A vehicle entering the `MALICIOUS` branch is blacklisted (`is_blacklisted = True`) and immediately loses Cluster Head eligibility.

---

## 2. Velocity-Aware Clustering (DBSCAN variant)

**Implementation:** `clustering.py :: ClusterManager`

Two ablation modes share the same DBSCAN core but differ in the distance function fed to it.

### 2.1 Mobility-aware distance function

For vehicles $i, j$ with position $p = (x,y)$, speed $s$, heading $\theta$ (radians), a short-horizon projected position is computed using the velocity vector $\vec{v} = (s\cos\theta,\, s\sin\theta)$:

$$
p_i' = p_i + \vec{v}_i \cdot H, \qquad H = \texttt{VELOCITY\_PREDICTION\_HORIZON} = 2.0\ \text{s}
$$

The pairwise distance blends current and projected separation:

$$
d(i,j) = w_{pos}\,\lVert p_i - p_j \rVert_2 \;+\; w_{mob}\,\lVert p_i' - p_j' \rVert_2
$$

$$
w_{pos} = \texttt{VELOCITY\_WEIGHT\_POSITION} = 0.6, \qquad w_{mob} = \texttt{VELOCITY\_WEIGHT\_MOBILITY} = 0.4
$$

### 2.2 Directional compatibility gate

Applied only when both vehicles are moving fast enough for heading to be meaningful ($s_i, s_j > \texttt{MIN\_SPEED\_FOR\_HEADING\_GATE} = 1.0$ m/s):

$$
\Delta\theta(i,j) = \min\big(|\theta_i - \theta_j| \bmod 360^\circ,\; 360^\circ - (|\theta_i-\theta_j| \bmod 360^\circ)\big) \in [0^\circ, 180^\circ]
$$

$$
d(i,j) \leftarrow d(i,j) + P \cdot \mathbb{1}\big[\Delta\theta(i,j) > \texttt{MAX\_HEADING\_DIFF\_DEG} = 120^\circ\big], \qquad P = 10^6
$$

The penalty $P$ pushes directionally incompatible pairs (e.g. opposing lanes) far beyond $\varepsilon$, effectively excluding them as DBSCAN neighbors — without this gate, two vehicles that are momentarily close but diverging would be wrongly clustered. Stationary vehicles ($s \le 1.0$ m/s, e.g. queued behind an accident) skip the gate entirely, since a stale heading from before they stopped is not a reliable directional signal.

### 2.3 DBSCAN clustering

$$
C = \text{DBSCAN}(D,\; \varepsilon,\; \text{MinPts}), \qquad \varepsilon = \texttt{DBSCAN\_EPS} = 80.0\text{ m}, \quad \text{MinPts} = \texttt{DBSCAN\_MIN\_SAMPLES} = 2
$$

where $D = [d(i,j)]$ is the precomputed distance matrix from §2.1–2.2 (`metric="precomputed"`) in velocity-aware mode, or plain Euclidean $\lVert p_i-p_j\rVert_2$ in baseline mode. Standard DBSCAN semantics apply: a point is a *core point* if $\ge$ MinPts points (incl. itself) lie within $\varepsilon$; clusters are formed by density-reachability from core points; points reachable from no core point are labeled **noise** ($C(v) = -1$).

---

## 3. Cluster Head Election

**Implementation:** `cluster_head.py :: ClusterHeadManager.select_cluster_heads()`

For every non-noise cluster $c$, the eligible member set excludes blacklisted, malicious, or very-low-trust vehicles:

$$
E(c) = \{ v \in c : \neg\text{blacklisted}(v) \wedge \neg\text{malicious}(v) \wedge T(v) \ge 0.3 \}
$$

Speed stability rewards vehicles moving close to a steady, low speed relative to the network's configured maximum speed $s_{max}=22.0$ m/s:

$$
S(v) = \max\Big(0,\; 1 - \frac{s(v)}{22.0}\Big)
$$

Election score and winner:

$$
\text{Score}(v) = 0.6\,T(v) + 0.4\,S(v), \qquad \boxed{H(c) = \operatorname*{argmax}_{v \in E(c)}\; \text{Score}(v)}
$$

If $E(c) = \emptyset$ the cluster elects no head that step (all candidates blacklisted/malicious/too-low-trust).

---

## 4. Emergency Message Routing

**Implementation:** `routing.py :: RoutingEngine.find_route()`

Greedy, loop-free, trust-gated multi-hop forwarding from the accident vehicle $v_{acc}$ to the geographically nearest RSU.

**Initial hop.** The accident vehicle's own Cluster Head is used if eligible; otherwise the geographically nearest non-blacklisted CH is chosen:

$$
h_0 = \begin{cases} H(C(v_{acc})) & \text{if defined and } \neg\text{blacklisted} \\ \displaystyle\operatorname*{argmin}_{h \,\in\, \{H(c)\}} \lVert p_{v_{acc}} - p_h \rVert_2 & \text{otherwise} \end{cases}
$$

**Greedy hop selection.** From current hop $h_i$, restrict candidates to CHs not yet visited and passing the trust gate, then require strict progress toward the RSU, breaking ties by nearest physical hop:

$$
\text{Cand}(h_i) = \{ h \in \{H(c)\} \setminus \text{Visited} \;:\; T(h) \ge 0.3 \;\wedge\; \lVert p_h - p_{RSU}\rVert_2 < \lVert p_{h_i} - p_{RSU}\rVert_2 \}
$$

$$
h_{i+1} = \begin{cases} \displaystyle\operatorname*{argmin}_{h \,\in\, \text{Cand}(h_i)} \lVert p_{h_i} - p_h \rVert_2 & \text{if } \text{Cand}(h_i) \ne \emptyset \\ \text{RSU (terminate)} & \text{otherwise} \end{cases}
$$

**Loop prevention.** $\text{Visited} \leftarrow \text{Visited} \cup \{h_i\}$ after every hop, and $\text{Cand}(h_i)$ explicitly excludes $\text{Visited}$ — a CH can appear in the path at most once, guaranteeing termination in at most $|\{H(c)\}|$ hops.

**Nearest RSU:**

$$
\text{RSU}^* = \operatorname*{argmin}_{r \,\in\, \text{RSUs}} \lVert p_{v_{acc}} - p_r \rVert_2
$$

---

## 5. Batch Authentication (BLS)

**Implementation:** `bls_auth.py`, using `py_ecc.bls.G2ProofOfPossession` (BLS12-381, IETF-draft / Eth2 ciphersuite)

### 5.1 Key generation

$$
sk_v = \text{KeyGen}(\text{seed}_v), \qquad pk_v = sk_v \cdot G_1 \quad \text{(SkToPk)}
$$

### 5.2 Per-signer payload

Every signer (the sending vehicle, and every currently active Cluster Head) signs a *distinct* payload — required for the aggregate scheme's security precondition, and what defeats classic rogue-key attacks against BLS aggregation:

$$
m_{v,\rho} = \texttt{message\_id} \,\|\, \texttt{sender} \,\|\, \texttt{location} \,\|\, \texttt{severity} \,\|\, v \,\|\, \rho, \qquad \rho \in \{\textsf{SENDER}, \textsf{FORWARDING\_CH}\}
$$

### 5.3 Individual sign / verify

$$
\sigma_v = \text{Sign}(sk_v,\, m_{v,\rho}) \in \mathbb{G}_2 \qquad(96\text{ bytes})
$$

$$
\text{Verify}(pk_v, m_{v,\rho}, \sigma_v) = \mathbb{1}\Big[\, e(\sigma_v,\, G_2) = e\big(H(m_{v,\rho}),\, pk_v\big) \,\Big]
$$

where $e(\cdot,\cdot)$ is the BLS12-381 bilinear pairing and $H(\cdot)$ hashes to the curve.

### 5.4 Aggregate / AggregateVerify

For a signer set $\{1, \dots, n\}$ (sender + active CHs) with distinct payloads $m_1,\dots,m_n$:

$$
\sigma_{agg} = \sigma_1 \oplus \sigma_2 \oplus \dots \oplus \sigma_n \quad \text{(elliptic-curve point addition in } \mathbb{G}_2\text{)}
$$

$$
\text{AggregateVerify} = \mathbb{1}\left[\, e(\sigma_{agg}, G_2) = \prod_{i=1}^{n} e\big(H(m_i),\, pk_i\big) \,\right]
$$

This collapses $n$ pairing checks into effectively one aggregate check — a 96-byte signature regardless of $n$, versus $96n$ bytes for $n$ independent signatures.

### 5.5 Trust-gated verification (the "proposed" scheme)

Signers are partitioned by trust threshold $\theta = \texttt{BLS\_TRUST\_THRESHOLD} = 0.7$:

$$
\text{High} = \{ i : T(i) \ge \theta \}, \qquad \text{Low} = \{ i : T(i) < \theta \}
$$

$$
\text{valid(High)} = \text{AggregateVerify}(\{m_i, \sigma_i, pk_i\}_{i \in \text{High}})
$$

$$
\text{valid(Low)} = \begin{cases} \text{false (rejected outright)} & \text{if } \texttt{BLS\_REJECT\_LOW\_TRUST} = \text{True} \\ \bigwedge_{i \in \text{Low}} \text{Verify}(pk_i, m_i, \sigma_i) & \text{otherwise (individually verified)} \end{cases}
$$

$$
\boxed{\text{ACCEPT}_{BLS}(m) = \text{valid(High)} \,\wedge\, \text{valid(Low)}}
$$

High-trust signers (the common case) are cheaply batch-verified in one pairing check; low-trust signers get full individual scrutiny (or are refused outright) — trust directly gates where cryptographic verification effort is spent.

---

## 6. Duplicate Suppression

**Implementation:** `broadcast.py :: BroadcastManager`, `messaging.py :: EmergencyMessage`

Each emergency message carries a unique identifier:

$$
\texttt{message\_id} = \texttt{"MSG\_"} \,\|\, \texttt{sender} \,\|\, \texttt{"\_"} \,\|\, \texttt{uuid4()[:8]}
$$

A single mutable cache $\mathcal{C}$ (a hash set) tracks every `message_id` already relayed:

$$
\Phi(\texttt{id}, \mathcal{C}) = \begin{cases} \textsf{NEW}, \; \mathcal{C} \leftarrow \mathcal{C} \cup \{\texttt{id}\} & \text{if } \texttt{id} \notin \mathcal{C} \\ \textsf{DUPLICATE} & \text{if } \texttt{id} \in \mathcal{C} \end{cases}
$$

Membership test and insertion are both $O(1)$ average case (Python `set`). Two distinct suppression contexts use $\Phi$ against the same cache:

- **Controlled fan-out** (`broadcast()`): every currently active Cluster Head is a candidate relay for the same alert; the first one processed gets $\textsf{NEW}$ and forwards, every other CH gets $\textsf{DUPLICATE}$ and is suppressed — this is what bounds broadcast overhead to $O(|\text{clusters}|)$ instead of $O(|V|)$ under naive flooding.
- **Route relay** (`broadcast_route()`): each hop of the loop-free path from §4 is logged as it forwards; since the path is loop-free by construction, no node repeats within a single route.

---

## 7. Combined System-Level Formulation

The full emergency-dissemination pipeline is the composition of the six operators above, evaluated once per simulation step over the active vehicle set $V$, and triggered end-to-end on an accident event at vehicle $v_{acc}$:

$$
\boxed{
\text{Dissemination}(v_{acc}) \;=\; \text{ACCEPT}_{BLS}\Big(\; \mathcal{R}\big(v_{acc},\; \mathcal{H}(\mathcal{C}_{D}(V,\tau)),\; \text{RSU}^*\big),\; \Phi \;\Big) \;\wedge\; \text{verify\_sender}(v_{acc})
}
$$

read left to right, this is exactly the run-time call chain in `sumo_interface.py`:

$$
\underbrace{\tau : V \to [0,1]}_{\text{§1 Trust}} \;\longrightarrow\;
\underbrace{\mathcal{C}_D(V,\tau) = \text{DBSCAN}(D(V),\varepsilon,\text{MinPts})}_{\text{§2 Clustering}} \;\longrightarrow\;
\underbrace{\mathcal{H}(c) = \operatorname*{argmax}_{v \in E(c)} 0.6\,\tau(v) + 0.4\,S(v)}_{\text{§3 CH Election}}
$$

$$
\longrightarrow\;
\underbrace{\mathcal{R}(v_{acc}, \{\mathcal{H}(c)\}, \text{RSU}^*) \text{ gated at every hop by } \Phi}_{\text{§4 Routing} \,+\, \text{§6 Duplicate Suppression}}
\;\longrightarrow\;
\underbrace{\text{ACCEPT}_{BLS}(m) = \text{valid(High)} \wedge \text{valid(Low)}}_{\text{§5 BLS Batch Authentication}}
$$

with a feedback edge back into §1: a successful RSU verification increases the sender's `auth_successes` and directly boosts $\tau(v_{acc})$ by $+0.05$ (clipped to 1.0), which can in turn change its classification, its Cluster-Head eligibility, and — if the trust delta exceeds $\texttt{RECLUSTER\_TRUST\_DELTA\_THRESHOLD}=0.2$ — trigger re-clustering on the next step. Trust is therefore not a static input to the pipeline but a state variable that the pipeline's own output (successful authenticated delivery) feeds back into.

---

## Parameter Reference

All values as configured in `config.py` at the time of writing:

| Symbol | Name | Value |
|---|---|---|
| $w_{fwd}, w_{auth}, w_{pdr}, w_{hist}, w_{rec}$ | Trust weights | $0.30, 0.25, 0.20, 0.15, 0.10$ |
| $\alpha$ | Trust EMA smoothing | $0.7$ |
| Blacklist / Trusted thresholds | | $0.3 \,/\, 0.7$ |
| $\varepsilon$, MinPts | DBSCAN | $80.0\text{ m}, 2$ |
| $H$ | Velocity prediction horizon | $2.0\text{ s}$ |
| $w_{pos}, w_{mob}$ | Clustering distance weights | $0.6, 0.4$ |
| Max heading gate | Directional compatibility | $120^\circ$ (above $1.0$ m/s) |
| CH score weights | Trust / Speed-stability | $0.6, 0.4$ |
| $s_{max}$ | Speed-stability normalizer | $22.0$ m/s |
| Comm. range | Neighbor discovery | $150.0$ m |
| $\theta$ | BLS trust threshold | $0.7$ |
| Signature size | BLS12-381 G2 | $96$ bytes (constant, any batch size) |

---

## Honest Scope Notes

- **Malicious-vehicle labeling** is ground truth at spawn time (`is_malicious`), used to synthetically degrade behavior counters that then drive $T(v)$ down through the real formula above. The system does not yet perform unsupervised anomaly *detection* from behavior alone — trust-based *response* to bad behavior is what's implemented and demonstrated.
- **BLS key issuance** (`BLSKeyRegistry`) is an in-memory, self-issued registry, not a production PKI/certificate authority — this models the standard "trusted registration" assumption used in VANET security literature (e.g. IEEE 1609.2), with CA modeling explicitly out of scope for this simulation.
- **Routing (§4)** is a custom greedy nearest-progress heuristic, not a named standard VANET routing protocol (e.g. AODV, GPSR).
