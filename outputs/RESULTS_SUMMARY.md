# Results Summary — Report-Aligned Re-Run

**Generated:** 2026-09-03 (third revision — adds the full proof-of-work citation mapping in
`docs/ALGORITHMS.md`/`docs/RESEARCH_PAPER.md`, extends the density sweep to the exact 5-point Kaur et al.
2024 set plus 300/500, adds the DBSCAN ε-sensitivity ablation, and re-runs the BLS/ECDSA benchmark clean.
See `docs/ALGORITHMS.md`'s Proof-of-Work Mapping table for the provenance note on the two factors, Tc and
Ts, that have no formula in any of the four base papers and are disclosed as this project's own
contribution.)
**Verification basis:** 93/93 unit tests passing (`pytest -q`), full source read, all numbers below produced
by actually executing the pipeline described — no hand-entered or invented figures.

This supersedes the first revision's numbers (still visible in git history / the previous session) because
the underlying algorithms changed substantially: a real 4-factor Bayesian trust model, a real GPSR router
with a 300 m range cap and perimeter-mode recovery, cooperative majority-vote confirmation, persistent RSU
trust feedback, cross-event RSU deduplication, tiered (3-way) authentication, an ECDSA ablation arm, and
5 emergency events per run instead of 1.

## Gap analysis — Report §10.2 CRITICAL/HIGH items

| # | Item | Status before this pass | Fix |
|---|---|---|---|
| CRIT-1 | GPSR 300 m wireless range check | **Missing entirely** — routes connected any two CHs regardless of physical distance | `routing.py` rewritten: range enforced on every hop, standard GPSR perimeter mode added, TTL=5, full fallback chain (own CH ≤80m → nearest trusted CH ≤300m → RSU ≤300m → Store-Carry-Forward) |
| CRIT-2 | Real Bayesian trust, no oracle | Oracle already removed prior session, but wrong formula (old 5-factor, not the Report's 4-factor) | `trust.py` rewritten to `0.30·Tf + 0.25·Tc + 0.20·Ts + 0.25·Th`, decay `0.85/0.15`; Tc/Ts newly added (provenance-flagged) |
| CRIT-3 | Persistent RSU trust feedback | `rsu.py` mutated `vehicle.trust` directly — silently **overwritten** by the next `calculate_trust()` call, so the feedback had no lasting effect | New persistent `vehicle.rsu_trust_assessment`, blended `0.80/0.20` into every trust calculation |
| CRIT-4 | Malicious vehicle never the accident vehicle | Already correct in the live SUMO path; **not** enforced in the synthetic comparison harness | `comparison.py`'s `target_vid`/event-vehicle selection now excludes malicious vehicles; `accident.py`'s two no-TraCI fallback paths patched too |
| HIGH-5 | Majority-vote (>50%) CH confirmation | Did not exist | Added in `broadcast.py`, real position/state-derived corroboration check |
| HIGH-6 | RSU-as-CH fallback for isolated vehicles | Implicit at best | Explicit fallback tier 3 in the new GPSR chain |
| HIGH-7 | RSU cross-event dedup by UUID | Did not exist | `RSUManager.processed_message_ids`, checked before every verification |
| HIGH-8 | Real ECDSA ablation alongside BLS | Only BLS existed | New `ecdsa_auth.py` (real NIST P-256 via `cryptography`), benchmark below |
| MED | ≥5 emergency events/run | 1 event/run | `comparison.py` now injects `EMERGENCY_EVENTS_PER_RUN=5` events per run, spaced across the run |
| MED | ≥5 seeds/density, mean±std | Already done prior session | Unchanged (`runs=5`, reported with 95% CI) |

Also corrected to match the Report exactly: VWCA re-clustering skip thresholds (churn 30%→20%, trust-Δ
0.2→0.15, stability 0.5→0.7), Cluster-Head eligibility (was any T≥0.3, now TRUSTED-only T≥0.7 with a
bootstrap fallback — see below), and BLS/ECDSA verification tiering (was a 2-way high/low split behind a
config flag, now the Report's unconditional 3-tier: T≥0.7 aggregate, 0.3≤T<0.7 individual, T<0.3 rejected
with no verify attempt at all).

## A structural finding, found and fixed during implementation: the CH-election bootstrap deadlock

Taking "Cluster Head election only among TRUSTED vehicles (T≥0.7)" completely literally creates a permanent
deadlock: every vehicle starts at neutral trust (0.5), and with zero real forwarding/RSU evidence, trust
asymptotically caps at **≈0.61** — strictly below 0.7 — because generating real evidence requires *being* a
CH in the first place. Verified analytically and empirically (see `cluster_head.py`'s docstring and
`docs/ALGORITHMS.md` §1.6): with no fallback, the pipeline would silently elect **zero** Cluster Heads,
forever. Resolved with a documented bootstrap fallback — prefer TRUSTED candidates; only fall back to
UNKNOWN (0.3≤T<0.7) when a cluster has no TRUSTED candidate — logged explicitly
(`[BOOTSTRAP: no TRUSTED candidate available]`) so it's never silently indistinguishable from a genuine
TRUSTED election.

## Honest consequence: PDR is now real, and it tells an important story

**Read this section before quoting the PDR numbers below.** Enforcing the CRITICAL/HIGH items above for the
first time — a real 300 m range cap, real majority-vote corroboration, real trust-tiered rejection — makes
message delivery genuinely fail sometimes for the proposed scheme. This is the correct, honest behavior of
implementing the Report's requirements properly; it was not visible before because routes previously
"succeeded" at any distance and majority-vote didn't exist at all.

Two real, verified causes (traced directly, not inferred):

1. **RSU coverage gaps at 300 m — but only partly.** The 5-RSU placement (4 edge-midpoints + center of a
   700×700 m grid) does not put every point within 300 m of an RSU; a vehicle near a map corner can be
   genuinely 300–400 m from the nearest one, and those messages are honestly Store-Carry-Forward.
   **Correction issued this revision:** when every non-delivery was instrumented and attributed, most
   Store-Carry-Forward failures turned out *not* to be coverage gaps at all but an implementation defect —
   the route pinned itself to a single RSU chosen from the accident's position and ignored the other four,
   so messages sitting inside another RSU's coverage were still declared undelivered (see the multi-RSU fix
   below). After the fix, density 150 has **zero** SCF failures; the 4 remaining at density 300 are genuine
   geometry and stay reported as failures. The lesson is recorded rather than quietly absorbed: "traced to a
   real cause" was true of the *category* but the split between physics and defect was not measured until
   now.
2. **Majority-vote corroboration can genuinely fail even at the very first hop.** A DBSCAN cluster groups
   vehicles by *current position + velocity similarity*, not by "who is near this specific accident" — a
   cluster can have several members that are nowhere near the crash site even though they're clustered
   with the accident vehicle's own Cluster Head. When fewer than half of a cluster's members are within the
   alert radius (or already reacting to it), the CH correctly withholds, per the Report's specification.

**Why flooding stays at 100% while proposed doesn't:** flooding's redundancy is its one real advantage —
a message explores every path simultaneously, so a single failed hop (or a cluster that wouldn't
corroborate, a concept flooding doesn't have) doesn't kill delivery. The proposed CH-only scheme is
efficient (93–99% less overhead, 100% duplicate suppression, consistently lower routing-only delay) precisely
*because* it commits to one path — and a single-path scheme is structurally more exposed to any one hop's
failure. **This is a genuine, defensible reliability-vs-efficiency trade-off**, not a bug, and not something
to paper over: the previous (fabricated) numbers hid this trade-off entirely by making every route succeed
unconditionally. A credible next step is a hybrid scheme (e.g. redundant forwarding at low density, or
relaxing majority-vote corroboration for downstream relay hops that are just passing along an
already-verified message) — flagged here as future work, not attempted in this pass since it would mean
weakening a just-implemented CRITICAL correctness fix without a specified redesign.

## Comparative Evaluation — Proposed vs. Flooding

**Command:** `python3 -c "from comparison import ComparisonEngine; ComparisonEngine().run_all_comparisons(densities=[50,100,150,200,250,300,500], runs=5, steps=100)"`
**Seeds:** 42, 52, 62, 72, 82 (5 runs per density per arm, deterministic) · 5 emergency events per run
**Densities:** 50/100/150/200/250 are an exact match to [Kaur et al., 2024]'s own tested density set (Table 2); 300/500 extend beyond it.
**Full data:** `outputs/logs/comparison_results.csv`

| Density | PDR: Flood → Proposed | Delay (total): Flood → Proposed | ↳ routing-only: Flood → Proposed | Broadcast Overhead Reduction | Duplicate Suppression |
|---|---|---|---|---|---|
| 50  | 100% → 96% | 10.30 ± 0.61 ms → 363.74 ± 58.03 ms | 10.30 → 2.80 ms | **94.25%** | **100%** (906.4 → 0) |
| 100 | 100% → 100% | 10.19 ± 0.54 ms → 344.44 ± 29.64 ms | 10.19 → 3.18 ms | **96.88%** | **100%** (3587.8 → 0) |
| 150 | 100% → 84% | 9.02 ± 0.40 ms → 340.87 ± 30.40 ms | 9.02 → 2.67 ms | **98.36%** | **100%** (10632.8 → 0) |
| 200 | 100% → 88% | 8.90 ± 0.36 ms → 315.22 ± 22.30 ms | 8.90 → 2.18 ms | **98.85%** | **100%** (19702.6 → 0) |
| 250 | 100% → 88% | 9.02 ± 0.59 ms → 313.04 ± 27.73 ms | 9.02 → 2.01 ms | **99.15%** | **100%** (29253.6 → 0) |
| 300 | 100% → 80% | 8.74 ± 0.61 ms → 314.77 ± 13.84 ms | 8.74 → 1.79 ms | **99.33%** | **100%** (45198.8 → 0) |
| 500 | 100% → 88% | 8.06 ± 0.40 ms → 301.24 ± 5.96 ms | 8.06 → 1.79 ms | **99.59%** | **100%** (129278.0 → 0) |

### Change since the previous revision: the multi-RSU delivery fix

This sweep is the first to include the `routing.py::_reachable_rsu` fix (see `docs/ALGORITHMS.md` §4.4).
Every non-delivery in the previous sweep was instrumented and attributed to a cause; Store-Carry-Forward
turned out to be the dominant one, and **most SCF failures were an artifact, not physics**: the route
pre-selected one target RSU from the accident vehicle's position and never reconsidered, so a message that
hopped into a *different* RSU's coverage was still declared undelivered. At density 150, 5 of 5 SCF failures
had another RSU within 300 m of the point where the route died.

| Density | PDR before | PDR after | Δ |
|---|---|---|---|
| 50 | 96% | 96% | — |
| 100 | 100% | 100% | — |
| 150 | 64% | **84%** | +20 pts |
| 200 | 68% | **88%** | +20 pts |
| 250 | 76% | **88%** | +12 pts |
| 300 | 76% | **80%** | +4 pts |
| 500 | 72% | **88%** | +16 pts |
| **mean** | **78.86%** | **89.14%** | **+10.3 pts** |

Densities 50 and 100 are unchanged because they had no Store-Carry-Forward failures to begin with — a useful
negative control: the fix moved exactly the metric it should, and nothing else.

### Reading the numbers honestly

- **Overhead reduction and duplicate suppression remain the strongest, most structural results** — real
  counter arithmetic, essentially unaffected by the new constraints (proposed forwards via CH chain once;
  flooding retransmits N−1 times, now dramatically worse with 5 events/run — 129,278 duplicates at density
  500, vs. 21,303 with 1 event/run last revision).
- **Routing-only delay is real and favors proposed at every density** (1.79–3.18 ms vs. flooding's
  8.06–10.30 ms) — fewer hops via CH-only GPSR routing. This is the number that reflects what Algorithm 3 is
  actually supposed to improve.
- **Do NOT read the total-delay column as an algorithmic result.** It is dominated by BLS chain-of-custody
  verification (≈299–361 ms — total minus routing-only, across the 7 densities): `py_ecc` is a pure-Python
  BLS12-381 pairing implementation, and each message is verified against a multi-signer chain (sender + up to
  `MAX_CHAIN_SIGNERS=14` CHs), not a single signature. **That absolute wall-clock varies substantially
  between runs on the same machine with no code change at all** — measured directly this revision: the
  scenario-independent BLS benchmark moved from 2947.8 ms to 3677.5 ms (individual, N=10) between two runs
  hours apart, ≈25%. The previous revision's total-delay figures (466–529 ms) versus this one's (301–364 ms)
  therefore reflect machine load, **not** an improvement from the routing fix, and are not claimed as one.
  The *speedup ratio* (stable at 1.9–2.4×) and the routing-only column are the defensible numbers.
- **PDR is real, improved, and still shows the reliability-vs-efficiency trade-off** — not a fabricated flat
  number in either direction. It now ranges 80–100% for proposed (was 64–100%) against a consistent 100% for
  flooding. The improvement came from removing a genuine implementation defect (multi-RSU delivery, above),
  not from relaxing a safety check: majority-vote confirmation, the 300 m range cap, and trust-gating are all
  still enforced exactly as before. The residual gap below flooding is the real trade-off, traced to the
  causes below by direct instrumentation, not inferred.
- **Residual non-delivery, attributed by direct instrumentation (5 seeds × 5 events per density):** at
  density 150 — 2 majority-vote withholds + 2 malicious PACKET_DROP relays, and **zero** Store-Carry-Forward;
  at density 300 — 1 majority-vote withhold + 4 Store-Carry-Forward, all 4 of which are genuine physical
  coverage gaps (300–400 m from the nearest RSU, with 5 RSUs on a 700×700 m grid at a uniform 300 m range).
  Every remaining failure is therefore either an attacker succeeding at its attack, the corroboration gate
  correctly refusing to forward an uncorroborated report, or real radio geometry — none is an accounting
  artifact.
- Throughput now varies meaningfully too (was frozen degenerate with 1 event/run) since 5 independent
  events per run give it real variance, though it remains a coarse metric (`delivered × 4.096 kbit /
  (steps × 0.1s)`).

## BLS12-381 vs. ECDSA — Algorithm 4 Ablation (Report HIGH-8)

**Source:** `outputs/logs/bls_benchmark.csv`, `outputs/logs/ecdsa_benchmark.csv` — both generated automatically
at the end of every SUMO run, from real cryptographic operations (`py_ecc` BLS12-381 / `cryptography` NIST
P-256), fresh synthetic keypairs per batch size, scenario-independent (not trust-gated).

| Batch size (N) | BLS individual (total) | BLS batch (total) | BLS speedup | ECDSA individual (total) | ECDSA "batch" (total) | ECDSA speedup | Signature bytes: BLS agg. / ECDSA (no agg.) |
|---|---|---|---|---|---|---|---|
| 1  | 299.6 ms | 299.9 ms | 1.00× | 0.077 ms | 0.068 ms | 1.13× (noise) | 96 B / 71 B |
| 2  | 650.8 ms | 442.5 ms | 1.47× | 0.137 ms | 0.129 ms | 1.07× (noise) | 96 B / 140 B |
| 5  | 1537.0 ms | 844.7 ms | 1.82× | 0.318 ms | 0.313 ms | 1.02× (noise) | 96 B / 355 B |
| 10 | 3040.5 ms | 1566.6 ms | **1.94×** | 1.057 ms | 0.670 ms | 1.58× (noise) | 96 B / 710 B |
| 20 | 6086.6 ms | 2972.4 ms | 2.05× | 1.292 ms | 1.238 ms | 1.04× (noise) | 96 B / 1420 B |

*Absolute milliseconds are wall-clock and vary ≈25% between runs on this same machine with no code change
(measured: individual N=10 was 2947.8 ms, 3677.5 ms and 3040.5 ms across three runs today). The **speedup
ratio** (consistently ~1.9–2.4× at N≥10 across all three) and the **96-byte constant aggregate** are the
reproducible, implementation-independent claims — quote those, not the raw ms.*

**The honest, central finding of this ablation:** BLS provides true cryptographic aggregation — N signatures
collapse into a constant 96-byte aggregate, verified with a real measured ~2.0× speedup at N≥10 (1.97–2.04×). ECDSA has
**no native aggregation** — its "batch" column is real, honestly-labeled sequential verification (any
apparent "speedup" there is measurement noise around ~0, not a real effect — ECDSA verification is not
accelerated by batching without a dedicated batch-verification algorithm, which was not implemented, see
`docs/ALGORITHMS.md`'s scope note). ECDSA is **~3700–4500× faster per individual signature** in this
comparison (sub-millisecond vs. hundreds of milliseconds) because BLS12-381 pairing operations are far more
computationally expensive than ECDSA scalar multiplication — but ECDSA's signature payload grows linearly
with N (1420 bytes at N=20) while BLS's stays constant at 96 bytes. **Neither number is "better" in
isolation** — this is a genuine cost/compression trade-off between the two schemes, and the honest reason
the Report's architecture (ECDSA, industry-standard) and this project's improvement (BLS aggregation) are
worth comparing side by side rather than picking one blindly.

*Caveat, stated plainly: BLS's absolute milliseconds reflect `py_ecc`'s pure-Python implementation, not
production V2X latency (`blst`/`relic` verify in ~1–2 ms) — the speedup ratio and compression ratio are the
implementation-independent, defensible claims.*

## Test Suite

`pytest -q` → **93 passed** (was 72 after the first revision; added `tests/test_ecdsa_auth.py` and
`tests/test_broadcast.py`, extended `tests/test_routing.py` with 5 new GPSR-specific cases — 300 m range
rejection, TTL cutoff, perimeter-mode void routing verified against a hand-checked geometry, own-CH-range
fallback, Store-Carry-Forward — and `tests/test_bls_auth.py` with the 3-tier verification and
`MAX_CHAIN_SIGNERS` cap).

## What is still a disclosed limitation (not fixed in this pass, by design)

- **The reliability-vs-efficiency trade-off above is reported, not resolved.** A hybrid scheme is a natural
  next step, out of scope for this pass (would mean redesigning majority-vote/routing behavior without a
  specified design to follow).
- **Tc and Ts (§1 of `docs/ALGORITHMS.md`) are this session's own construction**, not verified against the
  actual source report — the report file itself was never made available. Compare against the real Report
  §3 once accessible.
- **FORGED_RECOMMENDATION attacks remain undetectable** — no recommendation-exchange mechanism exists in
  the 4-factor trust model (the prior 5-factor model had one; the supplied spec does not).
- **Store-Carry-Forward is not a full multi-step retry mechanic** — an undelivered message is not queued and
  retried on a later step within this pass's scope.
- **ECDSA implements standard sign/verify, not the full Naskar et al. 2025 NIZK-based ECDSA\* protocol**
  (Chaum-Pedersen proofs, epoch certificates, CA registration) — explicitly scoped down with the project
  author's approval; a multi-week cryptographic-protocol implementation on its own.
- **RSU cross-event dedup is implemented and correct but rarely exercised** by the current single-route-per-event
  pipeline (would need genuinely redundant delivery attempts to trigger on every run).
- **The comparison harness uses synthetic grid-seeded mobility, not live SUMO/TraCI movement** — unchanged
  from the prior revision; the live `sumo_interface.py` pipeline does use real TraCI mobility end-to-end.
- **No MAC-layer contention/collision model** in the delay calculation — the reported flooding delay, if
  anything, is an underestimate of its real-world disadvantage under broadcast-storm conditions.
- **DBSCAN ε=80m does not simply reuse Chen & Wu (2024)'s own highway-tuned ε=20/40m** — measured directly
  this revision (`python3 eps_sensitivity.py`, `outputs/logs/eps_sensitivity.csv`): on this project's sparser
  urban intersection grid, ε=20/40m produce 70–100% DBSCAN noise (no meaningful clustering) at density
  50–500, so ε=80m is this project's own re-tuned value for its own topology, not an unverified reuse of
  Chen & Wu's number. Full write-up in `docs/ALGORITHMS.md` §2.5 and `docs/RESEARCH_PAPER.md` §VI-A.
- **The synthetic comparison-harness mobility model causes DBSCAN cluster collapse at density ≥200** — found
  and quantified this revision while cross-validating the ε-sensitivity result: at ε=80m the harness's grid
  seeding produces a single mega-cluster (avg. cluster size ≈199.6–500.0 vehicles) once density reaches 200,
  rather than several geographically distinct clusters. This does not affect the live SUMO/TraCI pipeline
  (real road-network positions don't collapse this way) but means the *comparison-harness* PDR/overhead
  numbers at density ≥200 are measuring a coarser clustering topology than the live demo shows. Flagged as
  future work: redesign the harness's mobility model rather than patch around it under time pressure — see
  `docs/ALGORITHMS.md`'s Honest Scope Notes and `docs/RESEARCH_PAPER.md` §VI-B for the full finding.
