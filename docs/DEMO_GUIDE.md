# Demo Readiness Guide

Exact commands for the three things a panel review needs: a live visual demo, a headless evaluation
sweep, and proof the test suite is green. All commands assume the repo root as the working directory
and the `requirements.txt` environment active (`numpy`, `pandas`, `matplotlib`, `scikit-learn`, `py_ecc`,
`traci`, `sumolib`, `pytest`; SUMO/`sumo-gui` on `PATH`, `SUMO_HOME` set).

## 1. Live GUI demo

```bash
python3 main.py --gui --density 250 --steps 200 --seed 4
```

- `--seed 4` is **rehearsed, not cherry-picked for favorable metrics** — it's a fixed seed that reliably
  demonstrates the pipeline end-to-end. **Verified live on 2026-09-05** (density 250, steps 200, seed 4),
  the run prints:

  | Printed line | Value |
  |---|---|
  | Vehicle Count | 215 |
  | Cluster Count / Cluster Head Count | 13 / 13 |
  | Emergency Messages / Delivered | 1 / 1 |
  | Packet Delivery Ratio | **100.00%** |
  | End-to-End Delay | 311.12 ms |
  | Duplicate Messages (suppressed) | 18 |
  | Auth Success Rate | 100.00% |

  What to point at, in order: (1) the controlled fan-out shows a distant Cluster Head **withholding** the
  alert (`[Withheld] Cluster 2 CH 'v2' lacked majority corroboration; not forwarded`) because its own
  cluster members aren't near the accident — majority-vote confirmation working as designed, not a failure;
  (2) duplicate suppression runs across the CHs that do corroborate (18 duplicates blocked);
  (3) the GPSR route resolves and is logged in full —
  `Discovered Path: Accident Vehicle (v85) -> CH (v74) -> RSU (RSU_SOUTH)` — note it delivers to
  **RSU_SOUTH**, which is *not* the RSU nearest the accident; that is the multi-RSU delivery fix
  (`docs/ALGORITHMS.md` §4.4) visible on screen; (4) the RSU authenticates the BLS chain and ACKs
  (`Authentication: PASS | Decision: ACCEPTED`).

  > **Changed 2026-09-05 — re-rehearse before presenting.** Earlier revisions of this guide said this seed
  > ends at *PDR = 0%* with the carrying Cluster Head being a PACKET_DROP attacker. That was true before the
  > multi-RSU delivery fix, which re-routes this seed via v74 to RSU_SOUTH and no longer traverses the
  > malicious CH. **This seed no longer demonstrates a packet drop** (zero `[Dropped]` lines in the live
  > run). Do not narrate a drop that will not appear. If you want an attacker-succeeds moment in the talk,
  > use the aggregate instrumentation instead (`outputs/RESULTS_SUMMARY.md`: at density 150, 2 of 25 events
  > fail to malicious PACKET_DROP relays) rather than promising it live on this seed.

  Then point to `outputs/RESULTS_SUMMARY.md` for the honest aggregate picture: with the 300 m range check and
  majority-vote confirmation both enforced for real, proposed-arm PDR (80–100%) is still below flooding's
  100% at most densities — a real reliability-vs-efficiency trade-off, explained in full there.
- Accident triggers automatically at **step 50** (2-vehicle collision, both vehicles halt and turn red).
- Runtime: ~60-90s for the full 200-step run at density 250. **Do not live-demo at density 500** — the
  O(n²) DBSCAN distance-matrix cost makes it noticeably slower; density 100-250 is the sweet spot for a
  live audience.
- If `sumo-gui` doesn't have a display available (headless server), drop `--gui` to run the identical
  pipeline headless and show the terminal log + regenerated graphs instead.

Rehearsal / verification without the GUI (identical pipeline, just no SUMO window):
```bash
python3 main.py --density 250 --steps 200 --seed 4
```

## 1b. Dual-window demo (SUMO GUI + companion webpage, side by side)

For the strongest live demonstration, run the SUMO GUI on one side of the screen and the companion webpage
on the other, so the panel can watch the visual behavior and read the paper-cited explanation of it at the
same time.

1. **Left/main window — live SUMO GUI:**
   ```bash
   python3 main.py --gui --density 100 --steps 200 --seed 4
   ```
   (density 100 keeps the GUI responsive and legible for a live audience; density 250 also works but is
   busier on screen — pick 100 if screen real estate or projector resolution is limited.)
2. **Right/secondary window — companion webpage:** open the published companion page (colour legend, live
   run status, and a 7-step event sequence with the source paper of each visible behavior) in a browser
   window placed beside the SUMO GUI.
3. Narrate the two together using the speaking script below (§6 of this guide / `docs/PANEL_TALKING_POINTS.md`)
   — as each numbered event happens in SUMO, point to the matching card on the webpage.

## 2. Headless evaluation sweep (Proposed vs. Flooding, all densities)

```bash
python3 main.py --eval-only
```
This regenerates `outputs/logs/comparison_results.csv` (5 runs/density, 5 emergency events per run) and
all IEEE graphs in `outputs/graphs/`. To run the exact density set used for the current results (an exact
match to Kaur et al. 2024's own tested set of 50/100/150/200/250, extended with 300/500), or just the
comparison engine directly (skipping the route-file regeneration step):
```bash
python3 -c "from comparison import ComparisonEngine; ComparisonEngine().run_all_comparisons(densities=[50,100,150,200,250,300,500], runs=5, steps=100)"
```

### DBSCAN ε sensitivity ablation (real-world-parameter grounding check)

```bash
python3 eps_sensitivity.py
```
Re-runs the noise-ratio measurement Chen & Wu (2024) use, on this project's own network, across
ε ∈ {20, 40, 80} m and densities 50–500 — quantifies why this project's ε=80m does not simply reuse Chen &
Wu's own highway-tuned ε=20m. Saves `outputs/logs/eps_sensitivity.csv`; full write-up in
`docs/ALGORITHMS.md` §2.5 and `docs/RESEARCH_PAPER.md` §VI-A.

### Showing ablation switches ("Proposed vs Flooding", "BLS batch vs SHA-256")

```bash
python3 -c "
from comparison import ComparisonEngine
ce = ComparisonEngine()
for mode in ('bls_batch', 'bls_individual', 'baseline', 'none'):
    r = ce.run_density_simulation(100, algorithm='PROPOSED', steps=100, seed=42, authentication_mode=mode)
    print(mode, '-> auth_success_rate:', r['auth_success_rate'], 'verification_delay_ms:', r['verification_delay_ms'])
"
```
Swap `authentication_mode` for `clustering_mode` (`"baseline"` vs `"velocity_aware"`) to show the Priority 1
ablation instead.

## 3. Test suite

```bash
python3 -m pytest -q
```
Expect **93 passed** (0 failed, 0 skipped), ~25-35s.

## 4. Where the outputs land

| Artifact | Path |
|---|---|
| Per-step simulation telemetry (39 columns) | `outputs/logs/simulation_metrics.csv` |
| Density comparison table (Proposed vs Flooding, mean±std±CI) | `outputs/logs/comparison_results.csv` |
| BLS individual-vs-batch benchmark | `outputs/logs/bls_benchmark.csv` |
| ECDSA benchmark (Algorithm 4 ablation) | `outputs/logs/ecdsa_benchmark.csv` |
| Terminal run log | `outputs/logs/simulation_run.log` |
| 9 IEEE-style 300 DPI graphs | `outputs/graphs/*.png` |
| Honest results write-up (this re-run) | `outputs/RESULTS_SUMMARY.md` |
| Panel explanation script | `docs/PANEL_TALKING_POINTS.md` |
| Algorithm formulas & full proof-of-work mapping | `docs/ALGORITHMS.md` |
| DBSCAN ε sensitivity ablation | `outputs/logs/eps_sensitivity.csv` |
| Full IEEE-style research paper | `docs/RESEARCH_PAPER.md` |
