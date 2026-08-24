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
  demonstrates *three* real mechanisms in one run: (1) the controlled fan-out broadcast correctly shows
  several distant Cluster Heads **withholding** the alert (`[Withheld] ... lacked majority corroboration`)
  because their own cluster members aren't near the accident — majority-vote confirmation working as
  designed, not a failure; (2) duplicate suppression still runs across the CHs that do corroborate;
  (3) on the GPSR route itself, the Cluster Head that ends up carrying the message turns out to be a real
  PACKET_DROP attacker, and it genuinely drops the packet instead of relaying. Say this part out loud
  before the terminal summary prints, don't let it be found first: **this specific run ends with
  PDR = 0% / 0 delivered messages**, because the dropped message genuinely never reaches the RSU. Frame it
  as "watch three real safety mechanisms fire, and watch the attacker still get through the last one" —
  then point to `outputs/RESULTS_SUMMARY.md` for the honest aggregate picture: with the 300m range check and
  majority-vote confirmation now both enforced for real, proposed-arm PDR is genuinely lower than flooding's
  at most densities (a real reliability-vs-efficiency trade-off, explained in full there) — this run is a
  representative example of *why*, not a cherry-picked outlier.
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

## 2. Headless evaluation sweep (Proposed vs. Flooding, all densities)

```bash
python3 main.py --eval-only
```
This regenerates `outputs/logs/comparison_results.csv` (5 runs/density, 5 emergency events per run) and
all IEEE graphs in `outputs/graphs/`. To run the full density set used for the current results (including
the required 150), or just the comparison engine directly (skipping the route-file regeneration step):
```bash
python3 -c "from comparison import ComparisonEngine; ComparisonEngine().run_all_comparisons(densities=[50,100,150,200,300,500], runs=5, steps=100)"
```

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
| 12 IEEE-style 300 DPI graphs | `outputs/graphs/*.png` |
| Honest results write-up (this re-run) | `outputs/RESULTS_SUMMARY.md` |
| Panel explanation script | `docs/PANEL_TALKING_POINTS.md` |
| Algorithm formulas & Report gap analysis | `docs/ALGORITHMS.md` |
