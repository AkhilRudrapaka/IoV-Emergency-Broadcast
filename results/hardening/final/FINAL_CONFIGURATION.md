# Final security configuration (Block G, 2026-11-21)

Values as loaded from `config.py`, with no `EXP_` override.

| Setting | Value | Meaning |
|---|---|---|
| `ENFORCE_COMMITTEE` | **1** (was 0) | Every certificate check counts only endorsers in the committee the receiver rebuilds (the 5 nearest reputable neighbours of the claimed position). Applied at the source release and every receiver, CH-route local rounds, `infrastructure.cluster_votes` and `batch_authenticate`, and `incident_response.accepted_by`. A certificate-supplied committee is never used. |
| `COMMITTEE_SIZE` / `QUORUM` | **5 / 3** (unchanged) | CH-route local rounds use the same global quorum; there is no separate local quorum. |
| `TRUST_BURST_K` | **0** (unchanged) | Burst detector off. Opt-in experimental setting: `EXP_TRUST_BURST_K=4`. |
| `TRUST_CH_THRESHOLD` | 0.70 (unchanged) | Reputation gate. |
| `COMMITTEE_CHECK` | 0 (unchanged) | Block F reporting level; under enforcement the default level already applies it. |
| `MAX_COLLUDERS` | 5 (unchanged) | Forged-alert adversary. |
| `ML_TRUST_MODE` | `"off"` (unchanged) | VeReMi ML is shadow-only; it never enters a decision. |
| Cryptography, source authentication | unchanged | BLS12-381 (py_ecc); source signature verified before any vote. |

**Opt-in experimental configuration** (G3b/G4): `EXP_TRUST_BURST_K=4`.
- Measured benefit is limited to phased attackers with long off-windows.
- Cost: about 0.7–0.8 % of honest vehicles excluded per run on average; above 1 % in about a third of runs
  (maximum 3.75 %).

**Historical baseline reproduction:** `EXP_ENFORCE_COMMITTEE=0 EXP_TRUST_BURST_K=0`.
- Verified byte-identical against `results/urban/processed` (180 runs) and `results/urban/sensitivity/onoff_0.9`
  (30 runs).
- Verified twice: before G4 (`final_checks/baseline_off`, `onoff09_off`) and after G4 (`final_checks/post_g4/`).

**Effect of the new default** on the tracked scenarios (genuine CSVs byte-identical):

| Forged alert registered at the RSU | Tracked (enforcement off) | New default |
|---|---|---|
| Default matrix, voting-only level | 134 / 180 | 1 / 180 |
| Default matrix, full level | 0 / 180 | 0 / 180 |
| On-off 0.9 set, full level | 25 / 30 | 0 / 30 |
| On-off 0.9 set, voting-only level | 26 / 30 | 0 / 30 |
