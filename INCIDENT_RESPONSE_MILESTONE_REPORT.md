# Milestone: end-to-end incident response and rerouting (option a)

Date: 2026-11-18, updated for Block E (route-preserving detours, now the default). Branch `akhil`, on top of 107f1b4 plus the uncommitted Block D work. Nothing is committed.
SUMO 1.27.1, Python 3.11.4. **Simulation only.** The road network is the synthetic 5x5 urban grid, the demand is synthetic, and the incident is staged.

## 1. Result

One reproducible simulation now runs the whole chain on live SUMO traffic through TraCI:

**staged abrupt stop → detection from live telemetry → release of the verified alert → committee and BLS certificate (existing pipeline) → affected vehicles → TraCI rerouting → follow-up check**

At 200 vehicles over the 30 published seeds:

- Every acceptance criterion holds on all 30 seeds.
- On the 20 seeds where detection is physically possible, the stop was detected.
- Over those 20 seeds, 1070 vehicles were rerouted with a route-preserving detour, and none of them drove onto the incident edge during the 180 s follow-up window.
- Each detour keeps the vehicle's own route up to a split edge and from a rejoin edge right after the incident edge, and keeps the destination. The earlier shortest-path method is kept as `--method shortest`; the comparison is in [ROUTING_COMPARISON_REPORT.md](ROUTING_COMPARISON_REPORT.md).
- The rejected forged alert changed no route in 30/30 seeds.

The other 10 seeds are reported as **not detected**: the incident vehicle was stationary or slow when it stopped. In those seeds no alert is released and no vehicle is rerouted.

Every number below comes from `results/incident/summary_d200.csv` or the per-seed `results/incident/d200_rNN.json`. These are produced by:

```
python run.py incident -d 200 --runs 30      # 30 seeds in parallel, ~45 s on 16 cores (detour, the default)
python run.py incident -d 200 -r 2           # one seed (the showcase), ~13 s
python run.py incident -d 200 -r 2 --method shortest   # the earlier shortest-path method (baseline)
python run.py demo --reroute                 # the same chain at the end of the SUMO-GUI walkthrough
```

`python run.py demo` without `--reroute` makes exactly the same call as before. An existing test pins that call.

## 2. Implementation map

| Step | Where | What it does |
|---|---|---|
| Staged stop | `incident_response.crash` ([incident_response.py:40](incident_response.py#L40)) | TraCI turns off the vehicle's speed and lane-change checks and sets its speed to 0. These are the three calls the demo already made; the demo now calls this function ([demo.py:859](demo.py#L859)). |
| Detection | `StopDetector` ([incident_response.py:47](incident_response.py#L47)) | Runs every step on every vehicle's own TraCI speed. It flags a speed drop greater than the vehicle type's `emergencyDecel` + `CRASH_DECEL_MARGIN` (9.0 + 0.5 m/s²) within one 1 s step, ending at ≤ `CRASH_STOP_SPEED` (0.1 m/s). It reads neither the incident time nor the alert. |
| Release | `bind` ([incident_response.py:77](incident_response.py#L77)) | The recorded alert is released only for a detection of its own source vehicle within one step of the snapshot the dissemination was computed on. No detection means no alert. |
| Dissemination, committee, BLS | `experiment.run_one` (unchanged) | Its record for this seed, written to `results/incident/raw/`; never to `results/urban`. |
| Eligibility | `accepted_by` ([incident_response.py:89](incident_response.py#L89)) | Requires a recorded certificate with `accepted`, which must verify again with `corroboration.accept` (exact trust values from `scenario.build`). Only vehicles whose own check passed (`verified` and `rx_ms` set) are eligible. The alert source is excluded. No voting or a rejected certificate means nobody is eligible. |
| Affected vehicles | `crossing` ([incident_response.py:109](incident_response.py#L109)) | `upstream`: already on the incident edge behind the stop. `ahead`: the incident edge is still in the vehicle's remaining route (`getRoute()[getRouteIndex()+1:]`). |
| Rerouting (default) | `detour` ([incident_response.py:182](incident_response.py#L182)) | Keeps the remaining route up to a split edge before every future occurrence of the incident edge, bypasses it with SUMO's router and rejoins the original route right after it. Probes from the vehicle's own position use its own router and are undone (`_probe`, [incident_response.py:149](incident_response.py#L149)); nothing is installed unless `verify` and SUMO's own check pass. Details: [ROUTING_COMPARISON_REPORT.md](ROUTING_COMPARISON_REPORT.md), section 2. |
| Rerouting (baseline) | `reroute` ([incident_response.py:124](incident_response.py#L124)), `--method shortest` | Sets the vehicle's own travel time for the incident edge to `BLOCKED_EDGE_TT_S` (`setAdaptedTraveltime`) and calls `rerouteTraveltime(v, False)`: the whole remaining route becomes the travel-time shortest path to the same destination. |
| Follow-up | `Watch` ([incident_response.py:294](incident_response.py#L294)) | Each step it counts entries onto the incident edge per vehicle and checks that the stopped vehicle has not moved. At the end it checks destination and remaining route. |
| Shared chain | `Response` ([incident_response.py:341](incident_response.py#L341)) | The same after-stop chain is used by the headless `session` and by `demo.run(reroute=True)`. |
| Negative control | `session(..., forged=True)` ([incident_response.py:387](incident_response.py#L387)) | Same traffic, no stop. The forger's claim is evaluated with the `voting_reputation` record, and every route is compared before and after. The `voting_only` and `no_voting` outcomes are reported as counterfactuals and never applied. |
| Guard | `snapshot_drift` ([incident_response.py:378](incident_response.py#L378)) | Live SUMO must equal the recorded snapshot (same vehicles, < 0.05 m), else the run stops. |

Other changes:

- **`config.py`:** four constants under "incident response".
- **`run.py`:** a new `incident` subcommand and the `demo --reroute` flag.
- **`demo.py`:** a `reroute=False` argument. When it is on, rerouted vehicles turn green and the status line reports the outcome.
- **Portal bundle:** rebuilt with `python build_portal_assets.py`.
- **Tests:** `validation/test_incident_response.py` (10 tests).

## 3. Data flow (one seed)

1. `experiment.run_one(d, r)` runs into `results/incident/raw/`. It produces the scenario snapshot at the incident second t, every scheme's dissemination including the committee votes and the BLS certificate, and the forged-alert test. All of this is unchanged code.
2. `scenario.build(d, r)` provides the same routes and the exact trust values.
3. Headless SUMO runs with the SUMO-GUI demo's options (`--collision.action none --time-to-teleport -1`). The detector runs from the first step. At t, the drift check is applied.
4. The stop is staged at t. After one step (t + 1 s), the detector reports the vehicle, edge and lane position, and `bind` releases the recorded alert.
5. `accepted_by` determines eligibility. `crossing` classifies the affected vehicles, and `detour` (or `reroute` with `--method shortest`) handles each eligible `ahead` vehicle. Every attempt records the original and final route, its splices and any failure reason.
6. A 180 s follow-up window runs: entries onto the incident edge, destination, remaining route, and the stopped vehicle's speed, position and lane.
7. A second SUMO session on the same seed runs the forged-alert control.
8. `results/incident/<run_id>.json` is written. It holds the parameters, the command, the SUMO version, the record fingerprint, both sessions and the acceptance block.

## 4. Acceptance criteria (d200, seeds 0-29)

| Criterion (from the approval) | Result |
|---|---|
| 1. The stop is detected from live telemetry, not from the incident time or the alert | 20/30 detected. Each detection is a one-step drop equal to the vehicle's pre-stop speed (10.95-14.88 m/s) > 9.5 m/s². No other vehicle triggered the detector in any genuine or forged session: 0 false detections over 60 sessions. The 10 undetected seeds start the stop at 0.0 m/s (8 seeds), 1.21 m/s (r09) and 5.01 m/s (r28). |
| 2. Only vehicles that accepted the genuine alert through the certificate and committee check are rerouted | 30/30. In all 20 detected seeds the certificate re-verified. It was accepted by 199 of 199 other vehicles, the last reception at 50.4 ms (max over seeds). |
| 3. Destination preserved; rerouted vehicles avoid the incident edge throughout the window | 30/30. 1070 rerouted, 0 entries onto the incident edge. At the end of the window all 1070 were still driving (the detour keeps their trips) with the same destination and no incident edge ahead. Every final route was rebuilt from the recorded splices (`detours_rebuilt_from_record`), and every changed route belongs to a rerouted vehicle (`only_authorized_routes_changed`), 30/30. |
| 4. Vehicles without an alternative route are reported | 71 vehicles over 20 seeds (0-8 per seed), each listed with reason, road, lane position and speed (see 4.1). A further 15 were `unavoidable`: already on the incident edge behind the stop. |
| 5. A rejected forged alert causes zero reroutes | 30/30. 0 routes changed; the certificate was rejected in all 30 seeds. Counterfactuals, not applied: with the reputation gate removed (`voting_only`), the forged certificate would have been accepted in 26 seeds and would have rerouted 1207 vehicles in total. With no voting at all it would have rerouted 1357. |
| 6. ML off/shadow behaviour unchanged | Default `ML_TRUST_MODE = "off"`. With `EXP_ML_TRUST_MODE=shadow`, the d50_r03 incident record is byte-identical to the off record (same dissemination fingerprint; `decisions_changed: False`). |
| 7. Results directory and unrelated modules preserved | `git status results/urban` is clean. The tracked `d200_r02` record is only read (MD5 checked in the tests); its fingerprint equals the fresh one. No change to `corroboration.py`, `protocols.py`, `channel.py`, `clustering.py`, `rsu.py`, `infrastructure.py`, `ml_trust.py` or the existing tests. |
| Crashed vehicle stays stationary | 30/30: speed 0, displacement 0 m, same lane for the whole window. |

### 4.1 The 71 "no alternative" vehicles

The same 71 vehicles under both methods. The detour leaves their routes unchanged and reports each with its reason, road, lane position and speed:

| Group | Count | Explanation |
|---|---|---|
| Destination is the incident edge itself | 58 | No route can avoid it. |
| Already on the junction lane leading into the incident edge | 5 | Already committed to the incident edge (`committed: crossing the junction onto the incident edge`). |
| No split before and no rejoin after the incident edge works | 8 | 6 on the edge into a corner junction whose only exit is the incident edge (D4E4→E4E3 in r15, D0E0→E0E1 in r20; no U-turn there). 2 too close to the junction to turn elsewhere: r03 v177, 0.5 m before it; r10 v163, 11.6 m before it at 15.0 m/s (braking gap ≈ 25 m) in a lane that leads only toward the incident edge. SUMO's own router keeps their committed next edge, and the detour never forces a last-second turn. |

## 5. Showcase d200_r02 (seed 30002), headless and SUMO-GUI

- **Staged stop:** v164 at 11.53 m/s on lane D3E3_1, t = 114 s.
- **Detection:** at t = 115 s, a drop of 11.53 m/s in one step, on edge D3E3.
- **Alert:** EVT-30002-v164-1 is released. Its certificate re-verified ("BLS aggregate valid, 3 of 3 endorsers counted"), and 199 vehicles accepted it.
- **Affected vehicles:** 53 vehicles cross the incident edge:
  - 49 rerouted;
  - 3 without an alternative (v107, v195, v73, all with destination D3E3);
  - 1 unavoidable (v197, already upstream on D3E3).
- **Follow-up:** 0 entries onto D3E3 by rerouted vehicles in 180 s, and v164 did not move. All 49 detours keep the route up to the edge before D3E3; 8 vehicles cross D3E3 twice and are detoured around both crossings.
- **Forged control:** the forged alert EVT-30002-v34-1 was rejected ("only 0 reputable endorser(s), 3 needed") and changed 0 routes. Counterfactually, `voting_only` would have rerouted 48 vehicles.
- **SUMO-GUI** (`EXP_RESULTS_DIR=results/incident_routing/gui python run.py demo --reroute --no-wait`, detour default): it printed the same decision, "detected True; rerouted 49, no alternative ['v107', 'v195', 'v73']; entries onto the incident edge by rerouted vehicles in 19 s: 0". The GUI window simulates only 20 s after the response; the 180 s check is headless.

## 6. Tests

`validation/test_incident_response.py` has 10 tests and runs in about 27 s:

- detection from live telemetry and release on the showcase;
- the detector rejects 9 m/s² braking, a stop from 8.9 m/s, and an 11 m/s drop that does not end at standstill;
- eligibility only for vehicles that accepted the certificate, covering:
  - a rejected certificate;
  - no certificate;
  - a failed re-verification;
  - a vehicle whose own certificate check failed;
- `no_alternative` and `destination_changed` are reported;
- destination kept and edge avoided on the showcase;
- the stopped vehicle stays put;
- the forged alert changes no route;
- an undetected stop (d50_r04: abrupt stop from 8.88 m/s, below the trigger) releases nothing and reroutes nobody;
- the same seed gives the same incident record;
- a record that does not match live SUMO is refused.

Block E adds `validation/test_incident_routing.py` (11 tests; see [ROUTING_COMPARISON_REPORT.md](ROUTING_COMPARISON_REPORT.md), section 7). The 10 tests above are unchanged and now run with the detour default.

Full regression after the portal rebuild: `python -m pytest validation -q` gives 135 passed (114 original + 10 incident + 11 routing). `python -m pytest veremi -q` gives 26 passed.

## 7. Limitations (state these with any result)

1. **The incident is staged.** TraCI stops the vehicle; it is not a SUMO collision (option b was not built). Every other vehicle reacts only through car-following.
2. **The detector is a threshold rule on simulated kinematics, not a validated crash detector.** By construction it cannot see a stop that starts from ≤ 9.5 m/s. That covers 10 of the 30 d200 seeds, where the scenario picks a vehicle that is queued or slow at the incident second. Lowering the margin would not help much, because 8 of those 10 seeds start at 0.0 m/s. Ordinary braking stays well below the trigger in this simulator. In d200_r02, no vehicle other than the staged one lost more than 4.6 m/s in one step over 200 s, and across the 30 seeds the detector never fired on another vehicle. That is a property of SUMO's Krauss model (`decel` 4.5 m/s²), not evidence for real vehicles.
3. **The dissemination is computed on the snapshot at t; the stop is detected at t + 1 s.** The radio, committee and certificate are the experiment's record for that snapshot, so vehicle positions in the radio model are one step older than the detection. The receptions take ≤ 50.4 ms, so every eligible vehicle reroutes in the detection step.
4. **"Not informed" is 0 in every detected seed.** At 200 vehicles the proposed scheme delivers the verified alert to all 199 other vehicles. On genuine traffic the eligibility gate therefore excludes nobody. It is exercised by the forged control (30/30 excluded everybody) and by the unit tests, not by a genuine partial delivery.
5. **Resolved in Block E: rerouting no longer replaces the rest of the route.** The earlier method (`--method shortest`) replaces the remaining random-walk route with the shortest path to the destination, which cut trips short (922 of 1070 rerouted vehicles arrived within 180 s). The default detour keeps the trip, so its cost is measurable: +87 s [72, 102] and +606 m [538, 674] per affected vehicle against no incident (ROUTING_COMPARISON_REPORT.md).
6. **The knowledge is effectively per vehicle.** Only eligible vehicles get a new route (`setRoute`); there is no rerouting device and no later re-planning. The detour sets one global travel-time weight on the incident edge so that SUMO's `findRoute` can plan from an edge ahead of the vehicle; nothing else reads global weights in this project. The shortest-path baseline uses the vehicle's own adapted travel time only. Traffic-wide effects are measured in ROUTING_COMPARISON_REPORT.md.
7. **The security architecture is unchanged.** That includes the known gap in `corroboration.accept`, which counts any ≥ 3 reputable signers and does not check that they are the committee (CLAUDE.md).
8. **Coverage of seeds and densities.** The 30-seed evaluation is at 200 vehicles only. The tests also use d50 seeds 3 and 4.
9. **Two stale local records.** `results/urban/raw/d200_r08` and `d200_r12` are untracked local files from 3 Nov. They differ from a fresh run only in the `ch_route` record; the scenario, `proposed` and forgery parts used here are identical. All 30 seeds match on those parts (`saved_parts_used_identical` = 1 in the CSV).
10. **SUMO-GUI presentation order.** The radio replay is still shown with the clock paused before the stop is applied. The detection and rerouting happen when the clock resumes. The headless run is the order-faithful version.

## 8. Files

**New**

- `incident_response.py`
- `validation/test_incident_response.py`
- `INCIDENT_RESPONSE_MILESTONE_REPORT.md`
- Block E: `incident_routing.py`, `validation/test_incident_routing.py`, `ROUTING_COMPARISON_REPORT.md`, `results/incident_routing/`
- `results/incident/`: generated, untracked (regenerated in Block E with the detour default)
  - `summary_d200.csv`
  - `d200_r00.json` … `d200_r29.json`
  - `raw/`
  - `infrastructure/`
  - `logs/`

**Modified:** `config.py`, `run.py`, `demo.py`, and `portal/downloads/{source.zip, config.py, SNAPSHOT.txt}` (rebuilt).

**Unchanged:** the tracked `results/urban`, the security/trust/radio modules, the ML adapter and the Block C model, and the existing tests.
