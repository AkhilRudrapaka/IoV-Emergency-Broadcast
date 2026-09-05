# Pre-Viva Verification Report

**Date:** 2026-09-05 · **Basis:** `pytest -q` → 94 passed; full 7-density sweep re-run from source; canonical
live SUMO demo re-run; every citation below opened and checked against actual PDF text this session.

**Purpose:** let a panel member audit, in five minutes, (a) that every implemented mechanism is either traced
to a real paper or honestly labelled own contribution, and (b) exactly what was changed this pass and why.

---

## A. Component-by-component verification

### 1. Bayesian Trust Model — `trust.py`
**Grounding:** [4] Azizi & Shokrollahi (RTRV) §4, verified verbatim in the PDF this session:
*"the indirect trust of the next-hop and provide recommendations to vehicles within their transmission
range."* Tf (forwarding behaviour) matches their direct-trust category. Malicious ratio 15% verified inside
their tested range — Table 2 reads *"0, 33, 66, 99, 132, 165"*, text confirms *"(0%–25%)"*.
**Own contribution (already labelled):** Tc (message consistency) and Ts (speed plausibility) — no formula for
either exists in any of the 8 papers read.
**Weak spot found:** the weights themselves (0.30/0.25/0.20/0.25), the EMA pair (0.85/0.15) and the RSU blend
(0.80/0.20) are attributed to a "Final Project Report (Group 83)" that **does not exist on disk** and cannot
be audited by a reviewer.
**Change made:** added an explicit *Unverifiable-source note* to `docs/ALGORITHMS.md` directing reviewers to
treat all such values as own-contribution-with-uncheckable-provenance rather than as literature citations.
No code change.

### 2. VWCA Clustering — `clustering.py`
**Grounding:** [1] Chen & Wu, verified verbatim from the PDF: parameter table reads *"Transmission range
300 m"*, *"ε (20, 40) m"*, 3 lanes, 3000 m; and the text states *"a value of 20 is more suitable for the
application scenarios in this paper."* This confirms both the 300 m match and that ε=20 m is their
highway-tuned preference.
**Own contribution (labelled):** ε = 80 m for this urban grid, justified by measurement (`eps_sensitivity.py`:
ε = 20/40 m give 70–100% noise here); the 0.6/0.4 blend, 2.0 s horizon and 120° gate are own tuning.
**Weak spots:** none. **Change made:** none needed.

### 3. Cluster Head Election — `cluster_head.py`
**Grounding:** weighted multi-factor CH scoring confirmed as the field's standard pattern by **four**
independent papers — [1] §4.3, [4] Table 2, plus [7] Darabkh Eq. 3 (Lifetime/Distance/Speed) and [8] Khan
Eq. 2 (`CCF = α·avgCLS + β·Deg + γ·avgPCL`), both read in full this session.
**Own contribution (labelled):** **none of the four use trust as a factor** — the trust term is a
security-motivated extension; the 0.6/0.4 split is own tuning; the bootstrap fallback is an own fix for a
deadlock proven analytically (trust asymptotes ≈0.61 < 0.70).
**Weak spots:** none. **Change made:** none needed.

### 4. Majority-Vote Confirmation — `broadcast.py`
**Grounding:** own contribution, extending [2]'s CH-mediated structure. [9] Qi et al. reaches the same
defensive premise via a different mechanism (entropy-weighted aggregation across multiple senders vs. this
project's own-cluster headcount) — cited as related, explicitly *not* as source.
**Weak spots:** none — correctly labelled.
**Change made:** none. **Note:** the roadmap previously proposed relaxing corroboration for downstream relay
hops to lift PDR. Instrumentation showed **every** majority-vote failure occurs at hop 1 (the origin CH), so
that change would have had zero effect. It was not made, and the roadmap entry is now annotated with this.

### 5. GPSR Routing — `routing.py`
**Grounding:** 300 m range now matches **three** independent papers — [1] and [2] (both verified from PDF
text this session) plus [6] Zhang & Ye Table 2 (*"Communication radius (variable): default 300 m"*). [4]'s
350 m divergence is disclosed. Perimeter mode = classical GPSR [5]; no local copy exists, but [6]'s own
reference list independently lists the same paper — secondary verification, stated as such.
**Weak spot found (quote fidelity):** `docs/ALGORITHMS.md` quoted [2] as *"300 m omnidirectional"*. The
published table literally reads **"300 ms omnidirectional"** (its next row reads *"1000 ms"* for the RSU) —
an obvious typo for metres in the source, but our doc had silently corrected a quotation.
**Change made:** the quote is now verbatim with the discrepancy noted inline. No code change for this.
**Weak spot found (defect):** see §B.1 — a real delivery-path defect, fixed.

### 6. Tiered BLS Authentication — `bls_auth.py`
**Grounding:** [3] Naskar et al.'s batch-verification premise, quoted in the module docstring
(*"…2-times more V2V messages [batch-verified]… within a time threshold of 300 ms"*).
**Own contribution (labelled):** the 3-tier trust-gated split; BLS12-381 itself (their scheme is NIZK-based
ECDSA*, disclosed as a deliberate divergence).
**Weak spot:** `MAX_CHAIN_SIGNERS = 14` derives from the missing Group 83 report — flagged in the
Unverifiable-source note (§A.1). **Change made:** documentation only.

### 7. ECDSA Ablation — `ecdsa_auth.py`
**Grounding:** [3] for the *scheme choice* only; implemented as standard NIST P-256 sign/verify, with the
scope reduction from the full NIZK protocol disclosed in the module docstring and in the paper.
**Weak spots:** none. **Change made:** none needed.

### 8. RSU Feedback Pipeline — `rsu.py`
**Grounding:** [4] §4 (RSU as active trust participant) — quote verified in PDF. The 120-RSU / 10500×10500 m
scale difference versus this project's 5-RSU / 700×700 m grid is disclosed rather than implied as a match
(verified: *"120 RSUs were arranged in the simulation environment"*).
**Own contribution (labelled):** the ±0.05 nudge, the 0.80/0.20 blend, and UUID cross-event dedup.
**Weak spots:** none. **Change made:** none needed.

---

## B. Changes made this pass

### B.1 Multi-RSU delivery check (the only functional code change)
- **What.** `routing.py` gains `_reachable_rsu()`. At each hop — and at the direct-RSU fallback tier — the
  route now delivers to the **nearest RSU actually within `GPSR_RANGE_M`**, instead of only the single RSU
  pre-selected from the accident vehicle's position. The greedy/perimeter **geometry is unchanged** and stays
  anchored to that fixed destination, preserving standard GPSR semantics. With no `rsu_manager` supplied
  (e.g. unit tests passing an explicit position) behaviour degrades exactly to the previous single-target path.
- **Why.** Not assumed — measured. Every non-delivery in the proposed arm was instrumented and attributed.
  Store-Carry-Forward dominated, and most of it was an accounting artifact rather than radio physics: at
  density 150, **5 of 5** SCF failures had another RSU within 300 m of the point where the route died; at
  density 300, 1 of 5. The network deploys five equally valid RSU sinks ([2] Table 2 likewise deploys
  multiple RSUs with their own range); nothing in any cited paper requires delivery to one pre-chosen tower.
- **Expected effect.** Removes artifact non-deliveries; leaves genuine coverage gaps failing.
- **Verified.** Sweep re-run from source. Mean PDR **78.9% → 89.1%**. SCF at density 150: **5 → 0**; at
  density 300: 5 → 4, the remaining four being real 300–400 m coverage gaps that still correctly fail.
  Densities 50 and 100 unchanged — they had no SCF failures, a clean negative control. **No safety check was
  relaxed**: majority-vote, the 300 m cap and trust gating are enforced identically before and after.

### B.2 Test suite: one fixture corrected, one regression test added
- `tests/test_rsu.py::test_routing_engine_integration` passed `rsu_pos=(150,150)` labelled "RSU_NORTH" while
  its own manager placed RSU_NORTH at (200,400) — 433.8 m away and out of range. The fixture contradicted
  itself. It now asserts the physically correct outcome (RSU_SOUTH, the only RSU genuinely within range at
  190.3 m).
- Added `test_delivers_to_reachable_rsu_not_preselected_one`, with geometry verified numerically before the
  assertions were written: the sender is out of range of **every** RSU (nearest, RSU_CENTER, at 335.0 m, so
  that becomes the pre-selected target); the CH hop is 346.5 m from RSU_CENTER (out of range) but 287.3 m
  from RSU_WEST. The old code returned Store-Carry-Forward here; the fix delivers to RSU_WEST.
- **Result: 94 passed** (all 93 originals + 1 new). No test was weakened to accommodate the change.

### B.3 Measured and **rejected** — recorded rather than discarded
Changing the tier-2 entry hop from "nearest CH to the source" to GPSR's textbook "in-range CH closest to the
destination" is arguably more faithful to [5]/[6]. A/B tested over the same 5 seeds: **identical PDR at both
density 150 and 300**. A change with no measured benefit is not worth the regression risk, so it was **not**
adopted. The null result is documented in `docs/ALGORITHMS.md` §4.4.

### B.4 Citation-integrity corrections (documentation only)
- [2]'s transmission-range quote made verbatim (*"300 ms"*) with the source typo noted, instead of silently
  corrected to *"300 m"*.
- Added the **Unverifiable-source note** covering every parameter traceable only to the missing Group 83
  report.
- Added a Proof-of-Work Mapping row for the new multi-RSU delivery mechanism, per the project's own rule that
  every mechanism must appear there.

### B.5 Demo narrative corrected — **action required before presenting**
The routing fix changed what the rehearsed seed does. Previously `--density 250 --steps 200 --seed 4` ended
at **PDR 0%** with a malicious CH dropping the packet, and both `docs/DEMO_GUIDE.md` and
`docs/PANEL_TALKING_POINTS.md` instructed the presenter to announce that. Re-run and transcribed live, the
seed now delivers: **PDR 100%**, 1/1 delivered, 311.12 ms, 13 clusters / 13 CHs, 18 duplicates suppressed,
path `Accident Vehicle (v85) → CH (v74) → RSU (RSU_SOUTH)`, one `[Withheld]` majority-vote event, and **zero**
packet drops. Both documents have been rewritten to match, with an explicit warning not to narrate a drop
that will no longer appear.

### B.6 Result propagation
`outputs/RESULTS_SUMMARY.md`, `README.md`, `docs/RESEARCH_PAPER.md` (Abstract, Table I, §VI-A/C/D,
Conclusion) and `PROJECT_MEMORY.md` updated from the regenerated CSVs. A measurement caveat was added
everywhere the total-delay column appears — see §C.

---

## C. A measurement caveat found while verifying

Total end-to-end delay fell from ~466–529 ms to ~301–364 ms between revisions. **This is not an algorithmic
result and is not claimed as one.** The column is dominated by pure-Python BLS pairing wall-clock. Running the
scenario-independent benchmark three times on this machine on one day, with no code change, gave individual
N=10 timings of **2947.8 / 3677.5 / 3040.5 ms** — a ≈25% spread, larger than any between-revision difference.
The **speedup ratio** (stable at ~1.9–2.4× for N≥10) and the constant **96-byte** aggregate are the
reproducible claims; the routing-only column is the algorithmically meaningful latency figure.

---

## D. Constraint compliance

| Constraint | Status |
|---|---|
| Test suite not broken | ✅ 94 passed (93 original + 1 new) |
| No breaking CLI / `main.py` changes | ✅ untouched |
| No new dependencies | ✅ none added |
| No AI attribution in git | ✅ no commits made; nothing added to git metadata |
| Existing modules edited, no new abstraction layers | ✅ one method added to `RoutingEngine` |
| Live SUMO/TraCI path working | ✅ re-run end-to-end, summary transcribed in §B.5 |
| Synthetic comparison harness working | ✅ full 7-density sweep re-run; results in `comparison_results.csv` |
| Honest findings not silently fixed | ✅ PDR trade-off, cluster collapse, Tc/Ts, coverage gaps all retained and re-stated |
| Zero fabricated numbers or citations | ✅ every number from an executed run; every quote from opened PDF text |

---

## E. Open items

1. ~18 papers in `base papers/Research paper-set1/` remain unread — may ground currently
   own-contribution items (notably Tc/Ts).
2. The Group 83 report remains missing; if it surfaces, the parameters in §A.1 can be upgraded from
   unauditable to cited.
3. The synthetic-harness cluster collapse at density ≥200 is unaddressed by design (§8.3 of
   `PROJECT_MEMORY.md`) — fixing it would invalidate every already-collected sweep result and needs its own
   pass.
