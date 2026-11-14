# Trust-Aware Cluster-Based Broadcast Suppression for Vehicular Emergency Alerts

Presentation notes for faculty: how the project works, what the SUMO demo shows, and what problems it solves.
Covers the original committed code only. Numbers marked "demo run" come from `python run.py demo` (200 vehicles, run `d200_r02`, one accident).

## 1. Problem

When a vehicle crashes, nearby vehicles must be warned within milliseconds.

| Problem | Why it matters |
|---|---|
| Broadcast storm | If every vehicle rebroadcasts (blind flooding), the channel fills with redundant frames and collisions destroy the alerts |
| Selfish or malicious relays | Some vehicles receive but never forward |
| Forged alerts | An attacker can announce an accident that never happened |
| Signature cost | Verifying many signatures delays the alert |
| Infrastructure | The alert must also reach road-side units (RSUs) |

## 2. Our solution in one paragraph

Before an alert spreads, a committee of trusted neighbours vouches for it, and their signatures are aggregated into one certificate. Then only the vehicles that are needed rebroadcast: trusted cluster heads and bridges go first, farther vehicles go before nearer ones, and a vehicle stays silent if its neighbours are already covered.

## 3. Input and pipeline (per run)

**Inputs:** vehicle density (50–500), a seed, the road network `network/urban.net.xml`, and parameters in `config.py` (300 m radio range, 10% malicious vehicles, trust threshold 0.7).

| Step | What happens | Code |
|---|---|---|
| 1. Mobility | SUMO moves the vehicles; positions are recorded every second | `scenario.py` |
| 2. Incident | A random time (60–120 s) and a random vehicle are chosen; a snapshot of all positions is taken | `scenario.py` |
| 3. Trust | Neighbours watch who relays. Beta score (s+1)/(s+f+2) per vehicle. Malicious vehicles always fail; honest ones are missed 10% of the time | `scenario.py`, `clustering.py` |
| 4. Clustering | DBSCAN (eps 40 m, MinPts 3) groups vehicles. Trusted cluster heads are chosen by greedy set cover. Roles: CH, BRIDGE, MEMBER | `clustering.py` |
| 5. Corroboration | The source sends a signed proposal. The 5 nearest reputable neighbours vote with BLS signatures. With 3 of 5, the source builds one 96-byte aggregate certificate | `corroboration.py` |
| 6. Forwarding | Each vehicle decides once, on its first accepted copy (rules below) | `protocols.py` |
| 7. Radio | IEEE 802.11p CSMA/CA, slot by slot, with collisions, hidden terminals and half-duplex | `channel.py` |
| 8. Metrics | Frames, collisions, reach, time to 90% coverage, RSU delay | `metrics.py` |

## 4. Forwarding rules compared

| Scheme | Rule |
|---|---|
| Blind flooding | Rebroadcast immediately |
| Slotted 1-persistence | Wait by distance (farthest first); stay silent if a duplicate is heard |
| **Proposed** | Wait (tier × 5 + distance slot) × 5 ms plus a random delay. Rebroadcast only if some neighbour is still uncovered by the senders heard so far |
| CH route | Forward only along a selected cluster-head path to the RSU |

A receiver verifies the certificate before accepting or relaying. A forged alert gets no honest votes, so it is rejected.

## 5. How SUMO runs

1. `write_routes` creates N vehicles with random departures in the first 30 s and ~30-edge random-walk routes.
2. SUMO runs headless through `subprocess` with a 1 s step and FCD output (x, y, speed, angle per vehicle per second).
3. At the incident second, positions are frozen. The radio simulation runs on that snapshot.
4. TraCI is used only by the SUMO-GUI demo, to draw the replay.

## 6. What the demo shows (`python run.py demo`)

| Stage | What you see |
|---|---|
| Normal traffic | Each colour is one DBSCAN cluster; white cars are isolated; a black ring marks the cluster representative; blue circles are the RSUs, "listening" |
| Accident | The crashed car turns red with a red circle; traffic freezes while milliseconds of radio activity are replayed in slow motion |
| Voting | The committee turns violet and sends votes; the source releases the certificate |
| Spreading | Blue: accepted. Orange with a large ring (its 300 m range): rebroadcasting. Grey: suppressed. Purple: misbehaving, never relays. Thin lines show who forwarded to whom |
| Each scheme | Flooding first (the storm), then the others on the same accident |
| RSU | The label turns green: "ALERT RECEIVED, validated" |
| Forged alert | Receivers turn white ("rejected"); the RSU label turns red |
| Resume | Traffic moves again around the crashed car |

## 7. Results from the demo run

| Scheme | Reached | Frames sent | Collision losses | Time to RSU |
|---|---|---|---|---|
| Blind flooding | 189 / 200 (94.5%) | 176 | 9,509 (90.6% of receptions) | 19.3 ms |
| **Proposed** | **200 / 200 (100%)** | **28** | **138 (8.7%)** | 22.5 ms |
| CH shortest-path | 89 / 200 (44.5%) | 14 | 0 | 40.6 ms |
| Forged alert, full protection | 0 of 180 honest vehicles accepted it (73 received and rejected it) | 7 | 0 | none |

Frame counts include 1 proposal and 5 votes in every row. Flooding sent 170 alert frames, of which 143 reached nobody new.

## 8. Main points to highlight

| Problem | What we did | Evidence |
|---|---|---|
| Broadcast storm | Distance slots, random delay and a coverage test | 28 frames against 176 for flooding, with full reach |
| Selfish or malicious relays | Beta-reputation trust; trusted vehicles get priority | Misbehaving vehicles never relay, yet reach is 100% |
| Forged alerts | Quorum of 3 of 5 reputable witnesses plus BLS aggregate signature | Forged alert accepted by 0 honest vehicles |
| Signature cost | One aggregate certificate, one verification per receiver | 96 bytes however many endorsers |
| Reaching infrastructure | RSUs at intersections; an uncovered RSU triggers a relay | RSU registered the event after 22.5 ms |
| Credible results | Paired scenarios, 30 seeds per density, 95% confidence intervals, 7 ablations | Each mechanism removed in turn shows its effect |

## 9. Limitations to state upfront

- Unit-disk radio (300 m), no fading.
- Radio runs on a frozen snapshot, not live co-simulation.
- Trust values are synthetic and known network-wide.
- Keys are derived from the vehicle ID, not issued by a real PKI.
- Verification time is a fixed 4.3 ms per check.
- Proposed was slightly slower to the RSU than flooding in the demo run (22.5 vs 19.3 ms), because it waits to avoid redundant sends.
- Some older saved results do not reproduce with the current code; re-run before quoting them.
- The demo shows one accident. Averages over 30 seeds per density are in `results/urban/processed/summary.csv`.

## 10. Ideas for novelty scenarios (not yet implemented)

1. Higher malicious ratio (10%, 20%, 30%).
2. A colluding committee trying to certify a fake alert.
3. An incident far from every RSU, forcing multi-hop delivery.
4. Sparse and very dense traffic (50 vs 500 vehicles).
5. A shorter radio range (150 m), giving a partitioned network.
6. Verification delay and processing queues.

## 11. Commands

```
python run.py demo           # SUMO-GUI replay (keep the window open until it finishes)
python run.py explain        # same story in the terminal, no GUI
python run.py experiment     # full experiment (long)
```
