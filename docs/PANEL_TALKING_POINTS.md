# Panel Talking Points

Explanation script for a mixed (technical + non-technical) panel, organized around what they'll actually
see live during the GUI demo (see `docs/DEMO_GUIDE.md` for the exact command and current rehearsed seed).
Each algorithm is explicitly tied to the base paper it's built from, per the project's four-paper foundation
(strengthened by four further corroborating papers found later — see `docs/ALGORITHMS.md`'s Proof-of-Work
Mapping and `docs/RESEARCH_PAPER.md` Section II-F for the GPSR-range, CH-election, and majority-vote details).

## Panel Review 1 narrative — what to lead with, what to keep brief

**Important distinction:** the code is 100% complete and every claim in `docs/RESEARCH_PAPER.md` is honest —
nothing below asks you to say anything untrue. This is about *time allocation and emphasis* in a live talk
with a limited slot, not about hiding working code. Stay consistent with the paper's own citations if asked
to go deeper on anything below.

**Lead with these — strongest, most stable, most directly evidenced:**
1. **Velocity-weighted clustering** (Chen & Wu, 2024) — the oldest, most-tested module, and the DBSCAN ε
   ablation (Table II, paper) is a genuine, quantified engagement with the cited paper's own findings — a
   strong "we didn't just copy the number" story if asked how closely you followed the paper.
2. **BLS12-381 batch authentication + the ECDSA ablation** (Naskar et al., 2025) — real cryptography, a real
   measured 1.97–2.04× speedup, and a direct side-by-side comparison against the paper's own specified
   scheme. This is the most "textbook-complete" piece: implemented, benchmarked, ablated, honestly caveated.
3. **Duplicate suppression / broadcast overhead reduction** (Kaur et al., 2024) — the cleanest, most
   structural numbers in the whole project (94–99.6% overhead reduction, 100% duplicate suppression at every
   density). Easy to explain to a non-technical panelist, hard to argue with.

**Mention, but don't dwell — present matter-of-factly, not defensively:**
4. **GPSR routing + majority-vote confirmation** — real, tested, and the source of this cycle's most
   interesting finding (the PDR trade-off). Frame the trade-off as a *finding*, stated once, clearly, then
   move on — don't let it become the whole conversation unless the panel steers there themselves.
5. **The Bayesian trust model's Tc/Ts factors** — say plainly that these two specific factors are this
   project's own construction (no source paper had a formula), same framing as the paper's own "Proposed
   Extensions." Don't over-explain; one sentence, then move to the parts that are more clearly grounded.

**Hold in reserve — only go here if directly asked:**
6. The synthetic-harness cluster-collapse finding (Section VI-B of the paper) — genuinely good, rigorous
   work, but dense and easy to over-explain into confusion for a mixed panel. Have the one-sentence version
   ready ("the fast evaluation harness we used for the density sweep has a known mobility-model limitation at
   high density, which we found, measured, and cross-checked against the real SUMO pipeline — full writeup in
   the paper") rather than leading with it.
7. The full Naskar et al. NIZK protocol vs. this project's simplified ECDSA — only if someone asks "why isn't
   ECDSA doing the full privacy-preserving protocol from the paper."

**If asked "is this finished?"** — yes: 93/93 tests passing, every CRITICAL/HIGH item from the project's own
Report implemented, all four base papers' core ideas integrated and traced. The "future work" list in the
paper's Section IX is exactly that — genuine next steps beyond a complete, working system, not unfinished
pieces of this one.

## 1. The problem: broadcast storm

When a vehicle sees an accident, the obvious thing to do is tell everyone nearby immediately. If every
vehicle that hears the alert re-broadcasts it to everyone *it* can hear, the same message gets
retransmitted thousands of times in a few seconds — a "broadcast storm" that saturates the wireless
channel right when it's needed most. Our flooding baseline demonstrates this directly: at density 500,
flooding generates over 20,000 duplicate transmissions for a single message; the proposed system generates
zero — not by luck, but by construction (§4).

## 2. Algorithm 2 — Velocity-Weighted Clustering (VWCA)

**Base paper: Chen & Wu 2024**, *Dynamic Networking Method of Vehicles in VANET* — DBSCAN-based vehicle
clustering with a velocity/mobility scoring model.

Vehicles are grouped using DBSCAN, but the distance metric isn't just "how close are these two vehicles
right now" — it's 60% current position + 40% where each vehicle is *predicted to be* 2 seconds from now,
based on its speed and heading. A directional gate (>120° heading difference ⇒ excluded from clustering
together) prevents oncoming traffic from being grouped with traffic it's about to pass. A stationary-vehicle
safeguard (below 1 m/s, heading is unreliable, so it's ignored) makes sure the post-accident traffic jam
still clusters correctly. This is what forms the colored cluster groups in the GUI, re-evaluated
dynamically based on membership churn (>20%), trust change (>0.15), mobility variance, or stability
dropping below 0.70 — not on a fixed timer.

## 3. Algorithm 1 — Bayesian Trust Model, and Cluster Head election

**Base paper: Azizi & Shokrollahi 2024 (RTRV)** — RSU-assisted, direct + indirect trust assessment as the
architectural pattern this model follows, specifically the idea of an RSU actively contributing to a
vehicle's trust rather than just consuming it.

Every vehicle gets a trust score from four weighted factors: **Forwarding Behaviour** (30%, real relay
success rate), **Message Consistency** (25%, does a reported alert's claimed location match where the
vehicle actually was), **Speed Plausibility** (20%, is the vehicle's motion kinematically realistic), and
**Historical Trust** (25%, an EMA of past scores with 0.85 decay). A persistent RSU assessment then blends
in at 80% vehicle / 20% RSU. **State this proactively:** trust is derived only from what a vehicle is
observed to do — the simulator's internal "this vehicle is secretly malicious" flag is never read by the
trust formula. It only decides what a simulated attacker's *actions* look like (a packet-drop attacker
really does fail to relay; a fake-alert attacker really does report a forged location) — never what the
trust system concludes. A vehicle with no observed history starts neutral (0.5), same as everyone else.
Cluster Heads are elected from **TRUSTED vehicles only** (T≥0.7) at 60% trust + 40% speed stability — with
a documented bootstrap fallback to UNKNOWN candidates (0.3≤T<0.7) when a cluster has no TRUSTED candidate
yet, since every vehicle starting neutral would otherwise deadlock the whole election process before any
real evidence exists (a real structural finding from implementing this literally, not a hypothetical).

**A scoped, disclosed limitation, worth stating before it's asked:** packet-dropping and location-forgery
are both now observable. A `FORGED_RECOMMENDATION` attack (a vehicle lying about a *third party's*
trustworthiness) is not — no recommendation-exchange mechanism exists in this 4-factor model. Closing that
gap is exactly what a future behavioral/ML trust layer would do.

## 4. Algorithm 3 — GPSR Geographic Forwarding + only Cluster Heads forward

**Base paper: Kaur et al. 2024** — the "only CHs forward" controlled-dissemination structure that fixes
the broadcast storm. **Base paper: Azizi & Shokrollahi 2024 (RTRV)** — trust-gated, RSU-aware geographic
routing. The forwarding mechanism itself is the classical GPSR algorithm (Karp & Kung).

Only the elected Cluster Head per cluster forwards, and every message carries a UUID cached on receipt —
any duplicate is silently dropped before re-forwarding. Routing enforces a real **300 m wireless range**
on every hop — a vehicle cannot relay to another vehicle it couldn't physically reach, fixed this session
(previously routes could span any distance). The fallback chain tries, in order: the vehicle's own Cluster
Head within 80 m; the nearest trusted CH within 300 m; the RSU directly within 300 m (so an isolated
vehicle with no CH nearby still has a path); or Store-Carry-Forward if nothing is in range — an honest
"not delivered this time," not a magic guaranteed connection. When greedy forwarding hits a routing void
(in-range neighbors exist, but none make progress toward the RSU), the standard GPSR right-hand rule
walks around the void until progress resumes, capped at 5 hops total.

**New this session — cooperative majority-vote confirmation:** before a Cluster Head forwards, more than
50% of its own cluster members must corroborate the event (within the alert's real radius, or already
reacting to it). This prevents a single confused or compromised report from propagating on one node's say-so.

## 5. Algorithm 4 — Tiered Batch Authentication: BLS12-381 (proposed) vs. ECDSA (ablation)

**Base paper: Naskar et al. 2025** — the architecture's specified scheme is ECDSA batch verification for
V2V messages; this project implements real BLS12-381 as an improvement, and keeps real ECDSA as the direct
ablation comparison.

Each Cluster Head along the route co-signs the alert with a real cryptographic signature — capped at 14
total signers per message (a ~100 ms verification deadline at ~7 ms/signature). At the RSU, signers are
tiered by trust: **T≥0.7 → aggregate-verified in one batch**, **0.3≤T<0.7 → verified individually**,
**T<0.3 → rejected immediately with no verify attempt at all** (real compute saved on already-blacklisted
signers, not just a post-hoc rejection).

**The honest BLS-vs-ECDSA contrast, state proactively:** BLS gives true cryptographic aggregation — N
signatures collapse into one 96-byte aggregate, checked with one pairing operation, measured at **2.04×
speedup and 20:1 payload compression** at batch size 20. Plain ECDSA has **no native aggregation** — its
"batch" mode here is real, honestly-labeled sequential verification of N signatures, with no compression
(N signatures in, N signatures worth of bytes out, always). ECDSA is dramatically *cheaper per signature*
in this comparison (~0.07 ms vs. BLS's ~300 ms, since BLS pairing operations are far more computationally
expensive than ECDSA scalar multiplication) — but it cannot compress or batch-verify the way BLS does. That
tradeoff is fundamental to the two signature schemes, not an artifact of implementation quality. Also state:
the absolute BLS millisecond figures reflect `py_ecc`'s pure-Python pairing implementation, not deployable
V2X latency — production libraries (`blst`, `relic`) verify in ~1-2 ms; the *ratio* is the defensible,
implementation-independent claim.

## 6. RSU pipeline: persistent trust feedback + cross-event dedup

**Base paper: Azizi & Shokrollahi 2024 (RTRV)** — RSU as an active, coordinating participant.

Every RSU verification outcome nudges a vehicle's RSU-trust assessment — and this session fixed a real bug
where that nudge was silently overwritten the very next time trust got recomputed, meaning the "RSU
feedback" had no lasting effect at all. It's now a genuine persistent input, blended into every trust
calculation (§3.1.4) going forward. RSUs also now deduplicate by accident UUID across multiple reports or
multiple RSUs — the same event is verified once, not re-verified every time it's independently reported.

## 7. The measured improvements vs. flooding — real numbers, including the uncomfortable one

From `outputs/RESULTS_SUMMARY.md` (5 runs/density, 5 emergency events per run, mean ± 95% CI — see that
file for the authoritative current numbers before quoting any figure here):

- **Broadcast overhead reduction** and **duplicate suppression** are the strongest, most structural
  results — bounded by cluster-head count instead of network size.
- **Routing-only delay is consistently lower for proposed** — fewer hops via CH-only GPSR routing, the
  thing Algorithm 3 is actually meant to improve.
- **Total end-to-end delay is currently higher for proposed** because BLS verification cost (§5's caveat)
  dominates the blended number. State this directly — it's a genuine tradeoff of real cryptographic
  authentication with a reference (non-production) crypto library, not a routing flaw.
- **PDR now varies meaningfully run to run**, with 5 independent emergency events per run instead of 1 —
  a malicious Cluster Head can genuinely drop a message, and a majority-vote check can genuinely withhold
  a forward, so PDR reflects real outcomes rather than a fabricated flat number either direction.

## What the rehearsed demo seed's own numbers will show — say this before anyone else notices

**Updated 2026-09-05 — the previous version of this section is obsolete.** Before the multi-RSU delivery fix
this seed ended at *PDR 0%* with a malicious Cluster Head dropping the packet, and this script told you to
pre-empt that. It no longer happens: the fix re-routes this seed and **zero** `[Dropped]` lines appear.
Do not narrate a packet drop on this seed.

What the rehearsed seed (density 250, steps 200, seed 4) actually prints, verified live: **Packet Delivery
Ratio 100.00%, Delivered Messages 1/1**, End-to-End Delay 311.12 ms, 13 clusters / 13 Cluster Heads, 18
duplicate messages suppressed, Auth Success Rate 100%. Narrate it in this order:

1. **A Cluster Head withholds the alert** — `[Withheld] Cluster 2 CH 'v2' lacked majority corroboration;
   not forwarded`. Its own cluster members aren't near the accident, so majority-vote confirmation correctly
   refuses to forward on their behalf. This is the security mechanism firing, not a failure.
2. **Duplicate suppression** blocks 18 redundant relays across the CHs that do corroborate.
3. **The GPSR path resolves and is logged in full** —
   `Accident Vehicle (v85) -> CH (v74) -> RSU (RSU_SOUTH)`. Worth one sentence: it delivers to RSU_SOUTH,
   which is *not* the RSU nearest the accident. That's the multi-RSU delivery fix visible on screen, and it
   is the single change that moved mean PDR from 78.9% to 89.1%.
4. **The RSU authenticates the BLS signature chain and ACKs** — `Authentication: PASS | Decision: ACCEPTED`.

Then give the honest aggregate immediately, before anyone asks: across the unbiased 5-seed, 5-event sweep in
`outputs/RESULTS_SUMMARY.md`, proposed-arm PDR (80–100%) is **still below** flooding's 100% at most
densities, because flooding's redundant paths survive a single failed hop and a single efficient CH path
does not. The residual failures are all real — malicious relays dropping packets, the corroboration gate
correctly withholding, and genuine 300–400 m RSU coverage gaps — none of them accounting artifacts. That
trade-off is a finding, not a defect.

## 8. SUMO GUI visual legend

| Color / ring | Meaning |
|---|---|
| White | Trusted vehicle |
| Yellow | Unknown / not yet classified |
| Black | Classified malicious (by observed behavior, not by a hidden flag — see §3) |
| Blue (+ blue ring) | Active Cluster Head |
| Orange ring | Actively forwarding CH, or braking/queued near the accident |
| Red (+ red ring) | Collided vehicle(s) |
| Green polygon/tower | Roadside RSU |
| RSU flashes cyan | ACK sent after successful verification |
