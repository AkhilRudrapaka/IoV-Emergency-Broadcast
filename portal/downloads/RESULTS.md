# Results: Trust-Aware Cluster-Based Broadcast Suppression for Real-Time Vehicular Emergency Alerts

Generated 2026-10-07 by `python run.py experiment` from `results/processed/`. Values: mean ± 95 % CI over 2 independent scenarios per density, one alert each. Nothing in this file is typed by hand.

"Frames on air" counts everything transmitted for one alert: the proposal, the votes and every certified alert. All schemes in the headline comparison use the same corroboration (voting + BLS); only the forwarding rule differs.

## Headline comparison

| Vehicles | Scheme | Frames on air | Certified alerts | Redundant alerts | Receptions lost | Reachability (%) | 90 % reached (ms) | Last reached (ms) | CBR 100 ms (%) | Suppression (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| 50 | Blind flooding | 49.5 ± 19.1 | 43.5 ± 19.1 | 32.0 ± 25.4 | 534 ± 451 | 96.0 ± 50.8 | 22.1 ± 27.3 | 23.6 ± 9.3 | 5.0 ± 8.1 | 0.0 ± 0.0 |
| 50 | Slotted 1-persistence | 13.0 ± 50.8 | 7.0 ± 50.8 | 5.0 ± 50.8 | 56 ± 712 | 45.0 ± 88.9 | nan ± nan | 24.7 ± 31.8 | 1.7 ± 6.5 | 72.4 ± 201.5 |
| 50 | Proposed (full) | 17.0 ± 25.4 | 11.0 ± 25.4 | 2.0 ± 0.0 | 5 ± 64 | 100.0 ± 0.0 | 49.0 ± 129.7 | 56.2 ± 138.6 | 3.1 ± 3.5 | 77.3 ± 57.8 |
| 100 | Blind flooding | 95.5 ± 6.4 | 89.5 ± 6.4 | 72.5 ± 6.4 | 2525 ± 1004 | 99.0 ± 12.7 | 23.2 ± 4.7 | 25.4 ± 4.2 | 7.0 ± 4.8 | 0.0 ± 0.0 |
| 100 | Slotted 1-persistence | 17.5 ± 82.6 | 11.5 ± 82.6 | 4.0 ± 25.4 | 102 ± 273 | 71.5 ± 362.1 | 39.4 ± 0.0 | 34.0 ± 141.6 | 2.4 ± 12.9 | 85.2 ± 54.5 |
| 100 | Proposed (full) | 26.5 ± 6.4 | 20.5 ± 6.4 | 6.5 ± 31.8 | 127 ± 305 | 100.0 ± 0.0 | 38.5 ± 60.1 | 45.6 ± 50.8 | 4.5 ± 1.2 | 78.1 ± 7.1 |
| 200 | Blind flooding | 181.0 ± 50.8 | 175.0 ± 50.8 | 152.0 ± 88.9 | 9542 ± 1417 | 97.0 ± 31.8 | 26.1 ± 22.7 | 27.9 ± 9.2 | 8.8 ± 2.9 | 0.0 ± 0.0 |
| 200 | Slotted 1-persistence | 41.5 ± 108.0 | 35.5 ± 108.0 | 22.0 ± 88.9 | 1084 ± 3818 | 100.0 ± 0.0 | 32.9 ± 54.7 | 36.1 ± 22.7 | 4.5 ± 10.3 | 80.7 ± 60.3 |
| 200 | Proposed (full) | 24.5 ± 44.5 | 18.5 ± 44.5 | 6.5 ± 6.4 | 102 ± 375 | 100.0 ± 0.0 | 32.4 ± 10.1 | 35.2 ± 4.5 | 3.9 ± 7.1 | 90.2 ± 24.8 |
| 250 | Blind flooding | 230.5 ± 6.4 | 224.5 ± 6.4 | 199.0 ± 25.4 | 15271 ± 15654 | 100.0 ± 0.0 | 25.4 ± 13.7 | 30.4 ± 4.5 | 10.6 ± 4.6 | 0.2 ± 2.8 |
| 250 | Slotted 1-persistence | 66.0 ± 559.1 | 60.0 ± 559.1 | 46.0 ± 457.4 | 3972 ± 43404 | 79.2 ± 198.2 | 30.0 ± 0.0 | 28.2 ± 59.5 | 5.8 ± 43.4 | 70.6 ± 244.3 |
| 250 | Proposed (full) | 29.5 ± 69.9 | 23.5 ± 69.9 | 9.0 ± 38.1 | 224 ± 1391 | 100.0 ± 0.0 | 32.9 ± 26.7 | 39.5 ± 80.9 | 4.8 ± 8.8 | 90.0 ± 31.2 |

## Ablations: the full method with one component removed

| Vehicles | Scheme | Frames on air | Certified alerts | Redundant alerts | Receptions lost | Reachability (%) | 90 % reached (ms) | Last reached (ms) | CBR 100 ms (%) | Suppression (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| 50 | Proposed (full) | 17.0 ± 25.4 | 11.0 ± 25.4 | 2.0 ± 0.0 | 5 ± 64 | 100.0 ± 0.0 | 49.0 ± 129.7 | 56.2 ± 138.6 | 3.1 ± 3.5 | 77.3 ± 57.8 |
| 50 | without random delay | 21.0 ± 63.5 | 15.0 ± 63.5 | 7.0 ± 50.8 | 83 ± 953 | 99.0 ± 12.7 | 45.1 ± 164.4 | 57.7 ± 260.0 | 3.4 ± 4.9 | 67.7 ± 150.8 |
| 50 | without distance slots | 20.5 ± 19.1 | 14.5 ± 19.1 | 3.5 ± 6.4 | 10 ± 127 | 100.0 ± 0.0 | 38.4 ± 77.1 | 45.2 ± 58.6 | 3.8 ± 1.3 | 69.3 ± 43.3 |
| 50 | without coverage test | 51.0 ± 0.0 | 45.0 ± 0.0 | 35.5 ± 6.4 | 82 ± 299 | 100.0 ± 0.0 | 52.2 ± 158.2 | 61.6 ± 182.4 | 9.6 ± 2.1 | 0.0 ± 0.0 |
| 50 | without clustering | 19.5 ± 44.5 | 13.5 ± 44.5 | 4.0 ± 25.4 | 14 ± 178 | 100.0 ± 0.0 | 44.6 ± 117.8 | 51.2 ± 125.7 | 3.5 ± 4.8 | 71.6 ± 101.1 |
| 50 | without cluster-based forwarding | 20.5 ± 31.8 | 14.5 ± 31.8 | 5.0 ± 25.4 | 32 ± 0 | 100.0 ± 0.0 | 45.8 ± 162.5 | 54.2 ± 194.7 | 3.7 ± 5.2 | 69.3 ± 72.2 |
| 50 | without reputation | 17.0 ± 0.0 | 11.0 ± 0.0 | 0.0 ± 0.0 | 0 ± 0 | 100.0 ± 0.0 | 55.1 ± 129.5 | 62.4 ± 170.1 | 3.2 ± 1.4 | 77.3 ± 0.0 |
| 50 | without voting + BLS | 10.0 ± 25.4 | 10.0 ± 25.4 | 0.5 ± 6.4 | 10 ± 57 | 100.0 ± 0.0 | 18.0 ± 107.8 | 20.9 ± 125.2 | 1.7 ± 2.6 | 79.5 ± 57.8 |
| 100 | Proposed (full) | 26.5 ± 6.4 | 20.5 ± 6.4 | 6.5 ± 31.8 | 127 ± 305 | 100.0 ± 0.0 | 38.5 ± 60.1 | 45.6 ± 50.8 | 4.5 ± 1.2 | 78.1 ± 7.1 |
| 100 | without random delay | 32.0 ± 25.4 | 26.0 ± 25.4 | 10.5 ± 44.5 | 257 ± 457 | 100.0 ± 0.0 | 37.5 ± 4.1 | 47.2 ± 0.1 | 5.1 ± 3.3 | 71.9 ± 28.6 |
| 100 | without distance slots | 24.5 ± 19.1 | 18.5 ± 19.1 | 3.5 ± 6.4 | 58 ± 527 | 100.0 ± 0.0 | 32.7 ± 46.7 | 40.0 ± 52.8 | 4.5 ± 3.8 | 80.3 ± 21.4 |
| 100 | without coverage test | 96.0 ± 0.0 | 90.0 ± 0.0 | 76.5 ± 19.1 | 808 ± 2077 | 100.0 ± 0.0 | 41.2 ± 30.8 | 50.2 ± 91.1 | 17.0 ± 2.6 | 0.0 ± 0.0 |
| 100 | without clustering | 30.5 ± 19.1 | 24.5 ± 19.1 | 9.5 ± 19.1 | 102 ± 248 | 100.0 ± 0.0 | 34.6 ± 33.9 | 41.3 ± 38.2 | 5.8 ± 1.2 | 73.6 ± 21.4 |
| 100 | without cluster-based forwarding | 28.5 ± 6.4 | 22.5 ± 6.4 | 8.5 ± 19.1 | 92 ± 375 | 100.0 ± 0.0 | 35.3 ± 38.9 | 42.2 ± 87.7 | 5.1 ± 3.2 | 75.8 ± 7.1 |
| 100 | without reputation | 22.0 ± 0.0 | 16.5 ± 6.4 | 3.5 ± 6.4 | 82 ± 438 | 100.0 ± 0.0 | 40.0 ± 38.5 | 46.4 ± 17.3 | 3.8 ± 0.9 | 82.6 ± 7.1 |
| 100 | without voting + BLS | 15.5 ± 19.1 | 15.5 ± 19.1 | 4.0 ± 12.7 | 69 ± 597 | 100.0 ± 0.0 | 9.3 ± 32.3 | 15.1 ± 50.1 | 2.5 ± 3.4 | 83.7 ± 21.4 |
| 200 | Proposed (full) | 24.5 ± 44.5 | 18.5 ± 44.5 | 6.5 ± 6.4 | 102 ± 375 | 100.0 ± 0.0 | 32.4 ± 10.1 | 35.2 ± 4.5 | 3.9 ± 7.1 | 90.2 ± 24.8 |
| 200 | without random delay | 36.0 ± 38.1 | 30.0 ± 38.1 | 16.5 ± 44.5 | 599 ± 89 | 100.0 ± 0.0 | 32.2 ± 63.6 | 35.8 ± 82.1 | 5.2 ± 5.5 | 83.8 ± 21.3 |
| 200 | without distance slots | 31.0 ± 12.7 | 25.0 ± 12.7 | 6.0 ± 12.7 | 205 ± 470 | 100.0 ± 0.0 | 33.0 ± 26.1 | 36.0 ± 27.0 | 5.2 ± 1.1 | 86.6 ± 7.1 |
| 200 | without coverage test | 186.0 ± 0.0 | 180.0 ± 0.0 | 167.5 ± 6.4 | 6016 ± 7007 | 100.0 ± 0.0 | 35.6 ± 67.5 | 39.7 ± 79.4 | 24.2 ± 0.8 | 0.0 ± 0.0 |
| 200 | without clustering | 47.0 ± 228.7 | 41.0 ± 228.7 | 28.0 ± 177.9 | 1014 ± 10743 | 100.0 ± 0.0 | 30.9 ± 39.2 | 32.9 ± 56.6 | 7.4 ± 33.5 | 77.7 ± 127.8 |
| 200 | without cluster-based forwarding | 47.0 ± 63.5 | 41.0 ± 63.5 | 26.0 ± 38.1 | 1222 ± 1684 | 100.0 ± 0.0 | 32.1 ± 45.0 | 35.0 ± 44.9 | 7.3 ± 12.2 | 77.7 ± 35.5 |
| 200 | without reputation | 24.0 ± 38.1 | 18.0 ± 38.1 | 6.0 ± 38.1 | 35 ± 445 | 100.0 ± 0.0 | 35.2 ± 38.3 | 37.0 ± 33.8 | 3.7 ± 8.5 | 90.5 ± 21.3 |
| 200 | without voting + BLS | 16.5 ± 6.4 | 16.5 ± 6.4 | 7.0 ± 12.7 | 72 ± 407 | 100.0 ± 0.0 | 6.6 ± 9.3 | 7.9 ± 12.6 | 2.4 ± 0.3 | 91.3 ± 3.5 |
| 250 | Proposed (full) | 29.5 ± 69.9 | 23.5 ± 69.9 | 9.0 ± 38.1 | 224 ± 1391 | 100.0 ± 0.0 | 32.9 ± 26.7 | 39.5 ± 80.9 | 4.8 ± 8.8 | 90.0 ± 31.2 |
| 250 | without random delay | 54.0 ± 12.7 | 48.0 ± 12.7 | 32.0 ± 38.1 | 1953 ± 2605 | 100.0 ± 0.0 | 30.0 ± 28.0 | 36.2 ± 96.1 | 7.4 ± 10.3 | 79.0 ± 5.7 |
| 250 | without distance slots | 37.0 ± 25.4 | 31.0 ± 25.4 | 13.0 ± 50.8 | 534 ± 4187 | 100.0 ± 0.0 | 33.2 ± 51.5 | 36.9 ± 54.3 | 6.4 ± 9.2 | 86.6 ± 11.3 |
| 250 | without coverage test | 231.0 ± 0.0 | 225.0 ± 0.0 | 212.5 ± 31.8 | 10408 ± 14771 | 100.0 ± 0.0 | 32.7 ± 60.8 | 39.4 ± 78.9 | 29.0 ± 22.3 | 0.0 ± 0.0 |
| 250 | without clustering | 87.0 ± 241.4 | 81.0 ± 241.4 | 63.5 ± 235.1 | 4660 ± 24663 | 100.0 ± 0.0 | 31.0 ± 25.6 | 33.9 ± 45.0 | 11.2 ± 28.8 | 64.3 ± 107.8 |
| 250 | without cluster-based forwarding | 59.5 ± 95.3 | 53.5 ± 95.3 | 38.0 ± 88.9 | 2490 ± 12153 | 100.0 ± 0.0 | 30.8 ± 33.0 | 33.1 ± 27.5 | 9.1 ± 16.6 | 76.6 ± 42.5 |
| 250 | without reputation | 26.5 ± 31.8 | 21.0 ± 25.4 | 8.5 ± 6.4 | 71 ± 13 | 100.0 ± 0.0 | 34.3 ± 27.1 | 37.9 ± 29.7 | 4.4 ± 1.3 | 91.1 ± 11.3 |
| 250 | without voting + BLS | 20.5 ± 19.1 | 20.5 ± 19.1 | 9.0 ± 38.1 | 124 ± 820 | 100.0 ± 0.0 | 6.3 ± 2.7 | 12.6 ± 58.2 | 2.8 ± 5.4 | 91.3 ± 8.5 |

## Corroboration: cost for a genuine alert

| Vehicles | Genuine alerts that obtained a quorum (%) | Certified alert released at (ms) | Vote frames | Extra frames vs no voting | Extra time to 90 % vs no voting (ms) |
|---|---|---|---|---|---|
| 50 | 100.0 ± 0.0 | 12.1 ± 0.1 | 5.0 ± 0.0 | +7.0 | +31.1 |
| 100 | 100.0 ± 0.0 | 12.1 ± 0.0 | 5.0 ± 0.0 | +11.0 | +29.2 |
| 200 | 100.0 ± 0.0 | 12.1 ± 0.3 | 5.0 ± 0.0 | +8.0 | +25.7 |
| 250 | 100.0 ± 0.0 | 12.1 ± 0.2 | 5.0 ± 0.0 | +9.0 | +26.6 |

## Corroboration: the forged-alert test

On the same traffic, a misbehaving vehicle claims an accident that did not happen and its misbehaving neighbours endorse it. "Certificate formed" = the forger found at least 3 colluders in range.

| Vehicles | Protection | Runs | Certificate formed (%) | Honest vehicles accepting the forged alert (%) | Forged event registered by an RSU (%) |
|---|---|---|---|---|---|
| 50 | Voting + BLS + reputation (full) | 2 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| 50 | Voting + BLS, no reputation gate | 2 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| 50 | No voting | 2 | 0.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| 100 | Voting + BLS + reputation (full) | 2 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| 100 | Voting + BLS, no reputation gate | 2 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| 100 | No voting | 2 | 0.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| 200 | Voting + BLS + reputation (full) | 2 | 100.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| 200 | Voting + BLS, no reputation gate | 2 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| 200 | No voting | 2 | 0.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| 250 | Voting + BLS + reputation (full) | 2 | 100.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| 250 | Voting + BLS, no reputation gate | 2 | 100.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |
| 250 | No voting | 2 | 0.0 ± 0.0 | 100.0 ± 0.0 | 100.0 ± 0.0 |

## RSU delivery

All alerts: every incident where an RSU was reachable. Relayed alerts: incidents outside the direct range of both RSUs, which need vehicle relays (n = number of such incidents out of the runs).

| Vehicles | Scheme | RSU success, all (%) | RSU delay, all (ms) | Relayed: n | Relayed: success (%) | Relayed: delay (ms) | Relayed: frames until RSU | Duplicate copies at RSUs |
|---|---|---|---|---|---|---|---|---|
| 50 | Blind flooding | 100.0 ± 0.0 | 17.45 ± 4.71 | 1 | 100.0 ± 0.0 | 17.82 ± 0.00 | 45.0 ± 0.0 | 4.5 ± 19.1 |
| 50 | Slotted 1-persistence | 100.0 ± 0.0 | 19.66 ± 32.05 | 1 | 100.0 ± 0.0 | 22.18 ± 0.00 | 9.0 ± 0.0 | 2.0 ± 0.0 |
| 50 | Proposed (full) | 100.0 ± 0.0 | 20.34 ± 41.30 | 1 | 100.0 ± 0.0 | 23.59 ± 0.00 | 8.0 ± 0.0 | 7.0 ± 25.4 |
| 100 | Blind flooding | 100.0 ± 0.0 | 17.13 ± 0.25 | 0 | nan ± nan | nan ± nan | nan ± nan | 4.0 ± 25.4 |
| 100 | Slotted 1-persistence | 100.0 ± 0.0 | 17.11 ± 0.08 | 0 | nan ± nan | nan ± nan | nan ± nan | 5.0 ± 38.1 |
| 100 | Proposed (full) | 100.0 ± 0.0 | 17.08 ± 0.00 | 0 | nan ± nan | nan ± nan | nan ± nan | 9.5 ± 19.1 |
| 200 | Blind flooding | 100.0 ± 0.0 | 17.50 ± 4.63 | 1 | 100.0 ± 0.0 | 17.86 ± 0.00 | 103.0 ± 0.0 | 4.5 ± 19.1 |
| 200 | Slotted 1-persistence | 100.0 ± 0.0 | 19.61 ± 31.63 | 1 | 100.0 ± 0.0 | 22.10 ± 0.00 | 12.0 ± 0.0 | 8.5 ± 19.1 |
| 200 | Proposed (full) | 100.0 ± 0.0 | 22.12 ± 63.35 | 1 | 100.0 ± 0.0 | 27.11 ± 0.00 | 11.0 ± 0.0 | 11.0 ± 38.1 |
| 250 | Blind flooding | 100.0 ± 0.0 | 18.49 ± 18.42 | 1 | 100.0 ± 0.0 | 19.94 ± 0.00 | 168.0 ± 0.0 | 9.0 ± 12.7 |
| 250 | Slotted 1-persistence | 100.0 ± 0.0 | 19.97 ± 36.42 | 1 | 100.0 ± 0.0 | 22.84 ± 0.00 | 19.0 ± 0.0 | 4.0 ± 12.7 |
| 250 | Proposed (full) | 100.0 ± 0.0 | 20.03 ± 37.08 | 1 | 100.0 ± 0.0 | 22.95 ± 0.00 | 9.0 ± 0.0 | 12.0 ± 25.4 |

## Change relative to the baselines (means)

| Vehicles | Frames vs flooding | vs slotted 1-p | Collision losses vs flooding | vs slotted 1-p | t90 vs slotted 1-p |
|---|---|---|---|---|---|
| 50 | -66 % | +31 % | -99 % | -91 % | +nan ms |
| 100 | -72 % | +51 % | -95 % | +25 % | -0.9 ms |
| 200 | -86 % | -41 % | -99 % | -91 % | -0.5 ms |
| 250 | -87 % | -55 % | -99 % | -94 % | +2.9 ms |
