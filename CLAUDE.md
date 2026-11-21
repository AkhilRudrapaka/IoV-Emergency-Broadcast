# CLAUDE.md: IoV trust-aware emergency alerts (G083)

SUMO 1.27.1 + Python 3.11 simulator: Beta-reputation watchdog trust, DBSCAN + trusted cluster heads, 5-member
committee with BLS12-381 aggregate certificate, slotted/coverage broadcast suppression, CH-to-CH route to 2 RSUs.
Design: `docs/SYSTEM_DESIGN.md`; past audit and decisions: `docs/AUDIT.md`; current report: `final_panel_review/`.

## Sprint goal (2026-11-17, 5-7 days): see `docs/sprint/`
1. Realistic map: OSM extract -> netconvert, synthetic demand. Say "real topology, synthetic demand", never more.
2. Lightweight ML detector for on-off/intermittent attackers (scikit-learn only).
3. Re-evaluation with the original baselines plus calibrated and ML variants, with CIs.
4. IEEE two-column draft (IEEEtran .tex). There is no LaTeX toolchain here; compile elsewhere.

## Verified facts (2026-11-17, at tag `v0.9-baseline` = 33304f6, pushed)
- 105/105 tests pass (`python -m pytest validation -q`, ~100 s).
- `EXP_MALICIOUS_COOPERATION=0.9 ... experiment --densities 200` reproduces the tracked on-off CSVs bit-exactly:
  forged event registered in 25/30 runs. Runtime: 30 runs at 200 vehicles ~35 s; 4 densities x 30 runs ~75 s (16 cores).
  Since Block G this needs `EXP_ENFORCE_COMMITTEE=0 EXP_TRUST_BURST_K=0` (see below); with the new defaults: 0/30.
- The "on-off" attacker is i.i.d. per-second cooperation (p = 0.9), not a phased on-off attacker. Its only observable
  signature is the watchdog failure rate (~0.19 vs 0.10 honest). SUMO mobility ignores the malicious label, so kinematic
  features carry no signal by construction. Reputation is one global value per vehicle (no per-observer view).
- Beta trust already separates attackers (AUC 0.935). Exploratory sweep on the same 30 seeds: gate 0.84-0.86 gives
  0/30 forged registrations at 50/100/200/500 vehicles, genuine alerts 30/30, frames and t90 unchanged; 0.88 starts
  losing genuine alerts at 50 vehicles. Any ML result must be compared with a gate calibrated on held-out seeds, never
  only with 0.7.
- At this tag the certificate check (`corroboration.accept`) counted any >= 3 reputable signers, without checking that
  they are the committee. Fixed in Block G: see the next section.

## Block G final configuration (verified 2026-11-21; report: `BLOCK_G_FINAL_REPORT.md`)
- Committee membership enforcement is ON by default (`ENFORCE_COMMITTEE=1`). Every certificate check counts only
  endorsers in the committee the receiver rebuilds itself (the 5 nearest reputable neighbours of the claimed position):
  source release and every receiver (`protocols.py:112`), CH-route local rounds, `infrastructure.cluster_votes` and
  `batch_authenticate`, and the incident re-verification (`incident_response.accepted_by`). A committee listed in a
  certificate is never used. Crypto, source authentication and the 0.70 gate are unchanged.
- Committee size/quorum stay 5/3. No separate CH-route quorum (CH-route local rounds use the global quorum).
- Burst detector OFF by default (`TRUST_BURST_K=0`). k = 4 is an opt-in experimental setting. Measured benefit only
  against phased attackers with long off-windows (phased 0.9/30 s, 0.8/30 s); not better than a count gate for
  per-second attackers; cost about 0.7-0.8 % honest exclusion per run on average, above 1 % in about a third of runs
  (max 3.75 %). On top of enforcement it removed 3 of 941 forgeries (G4): no additive forgery gain.
- Historical baselines (tracked `results/urban`, Block F, the published 180 runs) are reproduced byte for byte with
  `EXP_ENFORCE_COMMITTEE=0 EXP_TRUST_BURST_K=0` (`results/hardening/analysis/final_baseline_check.py`). With the new
  defaults genuine-alert CSVs are identical and only forgery CSVs change (voting-only registered 134/180 -> 1/180), so
  a default run must never be written into `results/urban`.
- ML (VeReMi) stays shadow-only (`ML_TRUST_MODE="off"`).
- 166/166 validation tests (~175 s) and 26/26 VeReMi tests pass with these defaults.

## How to run safely
- Entry point `python run.py {experiment,single,explain,sensitivity,demo,pair,web,dashboard}`; every parameter is in
  `config.py`. `EXP_<NAME>=value` overrides config, but scalars only: the cast breaks lists and tuples.
- New experiments ALWAYS go to their own folder: `EXP_RESULTS_DIR=results/<name> python run.py experiment ...`.
  Tests compare against the tracked `results/urban`. `run.py demo`, `single`, and `experiment` without
  `EXP_RESULTS_DIR` rewrite tracked files. Restore with `git restore` if that happens by accident.
- Seed rule `10000 + 100*density + run`. Runs >= 30 are fresh seeds (held-out data for tuning/training).
- Keep default RNG streams identical: draw new randomness only when a new feature is enabled (pattern in
  `scenario.build`), so the published 180 runs stay reproducible.
- `run_experiment.sh` / `run_demo.sh` are stale (they reference `network/road.net.xml`, which nothing else uses).

## Rules
- Never fabricate results or citations. Only cite references verified against a publisher/DOI page
  (`final_panel_review/references.bib` + `research_paper_reference_check.md`). Simulation only: never claim
  real-world validation.
- No new dependencies: scikit-learn 1.7.2 has HistGradientBoosting (XGBoost equivalent), RandomForest and IsolationForest.
- Extend, don't rewrite. Smallest diff, then run the tests. Ask before destructive git operations or pushes.
- Log seeds, SUMO version, hyper-parameters and exact commands for every result (`summaries/experiment_config.json` does
  this per experiment folder).
- Writing: plain, specific, IEEE style; every number traceable to a CSV; report negative/neutral ML results.
