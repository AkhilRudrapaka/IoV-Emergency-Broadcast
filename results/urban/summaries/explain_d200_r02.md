# One-run explainer: d200_r02 (Proposed (full))

Seed 30002 | 200 vehicles | 20 misbehaving (never relay) | RSUs: RSU-1 at (160, 590), RSU-2 at (610, 170)

## The emergency packet

```json
{
  "event_id": "EVT-30002-v164-1",
  "message_type": "ACCIDENT",
  "source_vehicle": "v164",
  "sequence_number": 1,
  "incident_position": [
    683.67,
    588.4
  ],
  "incident_time_s": 114.0,
  "created_s": 114.0,
  "hop_limit": 10
}
```

## Timeline

Traffic time is in seconds. The radio events take milliseconds, so they are given as time after the alert was created.

| Time | Event |
|---|---|
| 114.000 s | **v164** has the accident at (683.67, 588.4) on lane `D3E3_1`. This is the only incident of the run. |
| +0.000 ms | Alert **EVT-30002-v164-1** is created (type ACCIDENT, hop limit 10). From earlier beacons every vehicle knows its neighbours and their reputation; DBSCAN gave 20 clusters with 20 representatives, 37 isolated vehicles (bridges) and 143 members. Committee: v156, v160, v142, v18, v197. |
| +0.065 ms | **v164** (the crashed vehicle) broadcasts the PROPOSAL: the alert with its own BLS signature. Decoded by 50 nodes. The signature proves who sent it, not that the event is real. |
| +6.474 ms | **v156** VOTES yes (reputation 0.94): it observes the crash and signs the event digest. One BLS signature, one vote. |
| +6.981 ms | **v160** VOTES yes (reputation 0.86): it observes the crash and signs the event digest. One BLS signature, one vote. |
| +7.475 ms | **v142** VOTES yes (reputation 0.88): it observes the crash and signs the event digest. One BLS signature, one vote. |
| +7.982 ms | **v18** VOTES yes (reputation 0.83): it observes the crash and signs the event digest. One BLS signature, one vote. |
| +8.463 ms | **v197** VOTES yes (reputation 0.90): it observes the crash and signs the event digest. One BLS signature, one vote. |
| +12.129 ms | **v164** has 3 votes, a majority of the committee of 5. It aggregates 4 signatures into one BLS signature and broadcasts the CERTIFIED ALERT. Decoded by 50 nodes (50 accept it). |
| +17.524 ms | **v32** FORWARDS (CH, tier 0, reputation 0.91; accepted the copy from v164 260 m away, hop 1): 39 neighbour(s) not covered by the senders it heard (v164). Frame decoded by 64 nodes (39 new, 25 already had it), lost at 0. |
| +19.825 ms | **v37** FORWARDS (BRIDGE, tier 0, reputation 0.92; accepted the copy from v164 292 m away, hop 1): 12 neighbour(s) not covered by the senders it heard (v164). Frame decoded by 38 nodes (12 new, 26 already had it), lost at 0. |
| +22.087 ms | **v0** SUPPRESSES: all 37 neighbours already covered by v37, v164. |
| +22.178 ms | **v120** SUPPRESSES: all 24 neighbours already covered by v164. |
| +22.477 ms | **RSU-2** decodes the alert from v32 (hop 2): plausibility validation passes; event **EVT-30002-v164-1 REGISTERED** after 8 transmission(s); 89 vehicles had the alert by then. |
| +22.737 ms | **v128** FORWARDS (BRIDGE, tier 0, reputation 0.92; accepted the copy from v32 243 m away, hop 2): 8 neighbour(s) not covered by the senders it heard (v32). Frame decoded by 39 nodes (8 new, 31 already had it), lost at 0. |
| +23.283 ms | **v24** SUPPRESSES: all 34 neighbours already covered by v32, v164. |
| +25.480 ms | **v89** SUPPRESSES: all 26 neighbours already covered by v37, v164. |
| +26.143 ms | **v158** SUPPRESSES: all 56 neighbours already covered by v32, v128, v164. |
| +27.014 ms | **v79** SUPPRESSES: all 40 neighbours already covered by v32, v128. |
| +27.391 ms | **v114** FORWARDS (CH, tier 0, reputation 0.86; accepted the copy from v32 282 m away, hop 2): 43 neighbour(s) not covered by the senders it heard (v32). Frame decoded by 71 nodes (42 new, 29 already had it), lost at 12. |
| +27.521 ms | **v194** SUPPRESSES: all 29 neighbours already covered by v164. |
| +27.638 ms | **v86** FORWARDS (CH, tier 0, reputation 0.87; accepted the copy from v37 247 m away, hop 2): 38 neighbour(s) not covered by the senders it heard (v37). Frame decoded by 57 nodes (25 new, 32 already had it), lost at 12. |
| +28.587 ms | **v134** FORWARDS (BRIDGE, tier 0, reputation 0.92; accepted the copy from v32 211 m away, hop 2): 4 neighbour(s) not covered by the senders it heard (v32, v128). Frame decoded by 38 nodes (0 new, 38 already had it), lost at 0. |
| +29.029 ms | **v115** SUPPRESSES: all 41 neighbours already covered by v37, v86, v164. |
| +30.173 ms | **v135** FORWARDS (CH, tier 0, reputation 0.91; accepted the copy from v32 220 m away, hop 2): 47 neighbour(s) not covered by the senders it heard (v32). Frame decoded by 63 nodes (2 new, 61 already had it), lost at 27. |
| +30.303 ms | **v44** FORWARDS (BRIDGE, tier 0, reputation 0.91; accepted the copy from v32 190 m away, hop 2): 2 neighbour(s) not covered by the senders it heard (v32, v128, v134). Frame decoded by 18 nodes (0 new, 18 already had it), lost at 27. |
| +32.591 ms | **RSU-1** decodes the alert from v86 (hop 3): same event ID, already registered, counted as a duplicate. |
| +33.059 ms | **v4** FORWARDS (CH, tier 0, reputation 0.84; accepted the copy from v86 283 m away, hop 3): 20 neighbour(s) not covered by the senders it heard (v86, v135). Frame decoded by 62 nodes (12 new, 50 already had it), lost at 24. |
| +33.488 ms | **v71** FORWARDS (CH, tier 0, reputation 0.90; accepted the copy from v114 277 m away, hop 3): 8 neighbour(s) not covered by the senders it heard (v114). Frame decoded by 25 nodes (4 new, 21 already had it), lost at 24. |
| +33.865 ms | **v28** FORWARDS (BRIDGE, tier 0, reputation 0.88; accepted the copy from v37 193 m away, hop 2): 3 neighbour(s) not covered by the senders it heard (v37, v86). Frame decoded by 43 nodes (3 new, 40 already had it), lost at 0. |
| +35.048 ms | **v57** FORWARDS (BRIDGE, tier 0, reputation 0.91; accepted the copy from v128 221 m away, hop 3): 6 neighbour(s) not covered by the senders it heard (v44, v128). Frame decoded by 26 nodes (0 new, 26 already had it), lost at 6. |
| +35.581 ms | **v8** FORWARDS (BRIDGE, tier 0, reputation 0.89; accepted the copy from v114 253 m away, hop 3): 1 neighbour(s) not covered by the senders it heard (v71, v114). Frame decoded by 51 nodes (4 new, 47 already had it), lost at 6. |
| +37.622 ms | **v181** FORWARDS (BRIDGE, tier 0, reputation 0.86; accepted the copy from v128 236 m away, hop 3): 1 neighbour(s) not covered by the senders it heard (v44, v57, v128). Frame decoded by 34 nodes (0 new, 34 already had it), lost at 0. |
| +38.272 ms | **v162** FORWARDS (CH, tier 0, reputation 0.91; accepted the copy from v114 190 m away, hop 3): 3 neighbour(s) not covered by the senders it heard (v8, v114, v135). Frame decoded by 75 nodes (0 new, 75 already had it), lost at 0. |
| +43.277 ms | **v31** FORWARDS (BRIDGE, tier 0, reputation 0.85; accepted the copy from v28 295 m away, hop 3): 9 neighbour(s) not covered by the senders it heard (v28). Frame decoded by 30 nodes (0 new, 30 already had it), lost at 0. |
| +46.488 ms | **v75** FORWARDS (BRIDGE, tier 0, reputation 0.89; accepted the copy from v8 204 m away, hop 4): 2 neighbour(s) not covered by the senders it heard (v8, v162). Frame decoded by 49 nodes (0 new, 49 already had it), lost at 0. |
| +48.139 ms | **v68** FORWARDS (MEMBER, tier 1, reputation 0.87; accepted the copy from v164 187 m away, hop 1): 2 neighbour(s) not covered by the senders it heard (v32, v134, v164). Frame decoded by 67 nodes (0 new, 67 already had it), lost at 0. |
| +48.711 ms | **v100** FORWARDS (BRIDGE, tier 0, reputation 0.91; accepted the copy from v8 224 m away, hop 4): 1 neighbour(s) not covered by the senders it heard (v8, v75, v162). Frame decoded by 50 nodes (0 new, 50 already had it), lost at 0. |
| +50.700 ms | **v175** FORWARDS (MEMBER, tier 1, reputation 0.91; accepted the copy from v32 240 m away, hop 2): 1 neighbour(s) not covered by the senders it heard (v4, v32, v68, v135). Frame decoded by 89 nodes (0 new, 89 already had it), lost at 0. |
| +60.866 ms | **v185** FORWARDS (MEMBER, tier 1, reputation 0.93; accepted the copy from v114 259 m away, hop 3): 3 neighbour(s) not covered by the senders it heard (v8, v75, v100, v114, v135, v162, v175). Frame decoded by 84 nodes (0 new, 84 already had it), lost at 0. |
| | ... and 150 more vehicles suppress for the same kind of reason (all listed in the decision table below). |

## Final

```
================================================================
 EMERGENCY DISSEMINATION MONITOR | PROPOSED (FULL)
================================================================
Event        : EVT-30002-v164-1 (ACCIDENT)
Status       : COMPLETE
Source       : Vehicle v164   (run d200_r02, seed 30002)
Location     : (683.67, 588.4) at t = 114 s

Corroboration
-------------
Committee    : v156, v160, v142, v18, v197  (5 nearest reputable neighbours)
Votes        : 5 cast (v156, v160, v142, v18, v197); 3 of 5 needed
Certificate  : BLS aggregate of 4 signatures in 96 bytes: ACCEPTED (BLS aggregate valid, 3 of 3 endorsers counted)

Vehicles
--------
Total        : 200
Accepted     : 200 / 200  (100.0 %, 90 % within 38.0 ms)

Forwarding
----------
Forwarded    : 21
Suppressed   : 158
Misbehaving  : 20 received but never relay

Network
-------
Transmissions: 28  (1 proposals, 5 votes, 22 certified alerts; 11 reached nobody new)
Collisions   : 138 receptions lost  (8.7 % of receptions)

RSU
---
Status       : ALERT RECEIVED, validation passed, registered by RSU-2
Delay        : 22.48 ms after the alert was created (2 hop(s), 8 transmission(s))
Duplicates   : 12 further copies ignored (decoded by RSU-1, RSU-2)
================================================================
```

## The certificate

```json
{
  "signers": [
    "v164",
    "v156",
    "v160",
    "v142"
  ],
  "aggregate": "945885ec021a28eb2914961c7b6f6caa001b487ce92330f16e0d784276ef47535c68491621e5e0206571cb47d8377b560a62653e026056ca6d08758cf1387c5e5142b4670dda76d8f4d3d54d495f1b2ee9c96db33f18bdcd0fcf8df750b91c11"
}
```

## Same incident, same vehicles, every scheme

| Scheme | Frames on air | Certified alerts | Redundant | Receptions lost to collisions | Reachability | 90 % reached (ms) | RSU registered at (ms) |
|---|---|---|---|---|---|---|---|
| Blind flooding | 182 | 176 | 162 | 9971 | 98.0 % | 27.9 | 24.28 (RSU-1) |
| Slotted 1-persistence | 37 | 31 | 17 | 775 | 100.0 % | 28.6 | 22.14 (RSU-2) |
| Proposed (full) | 28 | 22 | 11 | 138 | 100.0 % | 38.0 | 22.48 (RSU-2) |
| without random delay | 47 | 41 | 30 | 966 | 100.0 % | 32.2 | 22.13 (RSU-2) |
| without distance slots | 32 | 26 | 10 | 130 | 100.0 % | 32.6 | 22.92 (RSU-2) |
| without coverage test | 186 | 180 | 169 | 6062 | 100.0 % | 35.3 | 24.26 (RSU-2) |
| without clustering | 41 | 35 | 23 | 837 | 100.0 % | 29.0 | 22.16 (RSU-2) |
| without cluster-based forwarding | 32 | 26 | 16 | 545 | 100.0 % | 29.0 | 22.48 (RSU-2) |
| without reputation | 22 | 16 | 4 | 16 | 100.0 % | 42.4 | 28.24 (RSU-2) |
| without voting + BLS | 21 | 21 | 10 | 124 | 100.0 % | 8.6 | 4.15 (RSU-2) |
| CH shortest-path delivery | 14 | 2 | 0 | 0 | 44.5 % | nan | 40.64 (RSU-2) |
| Flooding + random delay | 186 | 180 | 163 | 9407 | 100.0 % | 30.3 | 22.92 (RSU-1) |
| Slotted 1-p + random delay | 26 | 20 | 10 | 268 | 100.0 % | 31.1 | 22.98 (RSU-1) |

## Forged-alert test on the same traffic

Forger v34 claims an accident that did not happen (`python run.py explain d200_r02 --forged voting_reputation`).

| Protection | Certificate | Honest vehicles that accepted it | RSU registered it |
|---|---|---|---|
| Voting + BLS + reputation (full) | formed, rejected: only 0 reputable endorser(s), 3 needed | 0 of 180 | no |
| Voting + BLS, no reputation gate | formed, accepted | 180 of 180 | yes |
| No voting | not required | 180 of 180 | yes |

## Every vehicle's message state and decision (Proposed (full))

| Vehicle | Accepted (ms) | Hop | From | Distance (m) | Neighbours | Role | Tier | Reputation | Copies heard | Uncovered | Decision | Reason |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v164 | 0.00 | 0 | - | 0 | 50 | BRIDGE | 0 | 0.88 | 3 | - | SOURCE | incident vehicle originates the alert |
| v0 | 17.08 | 1 | v164 | 235 | 37 | CH | 0 | 0.88 | 4 | 0 | SUPPRESS | all 37 neighbours already covered by v37, v164 |
| v3 | 17.08 | 1 | v164 | 244 | 71 | MEMBER | 1 | 0.87 | 7 | 0 | SUPPRESS | all 71 neighbours already covered by v28, v37, v86, v135, v164 |
| v10 | 17.08 | 1 | v164 | 247 | 65 | MEMBER | 1 | 0.01 | 7 | - | DROP | misbehaving vehicle: never relays |
| v13 | 17.08 | 1 | v164 | 138 | 35 | CH | 0 | 0.90 | 3 | 0 | SUPPRESS | all 35 neighbours already covered by v134, v164 |
| v18 | 17.08 | 1 | v164 | 62 | 61 | MEMBER | 1 | 0.83 | 6 | 0 | SUPPRESS | all 61 neighbours already covered by v32, v37, v68, v86, v164, v175 |
| v21 | 17.08 | 1 | v164 | 218 | 69 | MEMBER | 1 | 0.92 | 6 | 0 | SUPPRESS | all 69 neighbours already covered by v32, v68, v128, v134, v164 |
| v24 | 17.08 | 1 | v164 | 185 | 34 | CH | 0 | 0.94 | 5 | 0 | SUPPRESS | all 34 neighbours already covered by v32, v164 |
| v26 | 17.08 | 1 | v164 | 265 | 69 | MEMBER | 1 | 0.89 | 7 | 0 | SUPPRESS | all 69 neighbours already covered by v28, v37, v86, v135, v164 |
| v32 | 17.08 | 1 | v164 | 260 | 64 | CH | 0 | 0.91 | 6 | 39 | FORWARD | 39 neighbour(s) not covered by the senders it heard (v164) |
| v37 | 17.08 | 1 | v164 | 292 | 38 | BRIDGE | 0 | 0.92 | 3 | 12 | FORWARD | 12 neighbour(s) not covered by the senders it heard (v164) |
| v40 | 17.08 | 1 | v164 | 136 | 43 | MEMBER | 1 | 0.93 | 4 | 0 | SUPPRESS | all 43 neighbours already covered by v37, v68, v86, v164 |
| v43 | 17.08 | 1 | v164 | 166 | 68 | MEMBER | 1 | 0.89 | 6 | 0 | SUPPRESS | all 68 neighbours already covered by v32, v68, v86, v134, v164, v175 |
| v45 | 17.08 | 1 | v164 | 217 | 69 | MEMBER | 1 | 0.82 | 6 | 0 | SUPPRESS | all 69 neighbours already covered by v32, v68, v128, v134, v164 |
| v49 | 17.08 | 1 | v164 | 218 | 26 | BRIDGE | 1 | 0.01 | 2 | - | DROP | misbehaving vehicle: never relays |
| v58 | 17.08 | 1 | v164 | 207 | 29 | MEMBER | 1 | 0.88 | 2 | 0 | SUPPRESS | all 29 neighbours already covered by v37, v164 |
| v64 | 17.08 | 1 | v164 | 138 | 33 | MEMBER | 1 | 0.90 | 3 | 0 | SUPPRESS | all 33 neighbours already covered by v68, v134, v164 |
| v66 | 17.08 | 1 | v164 | 176 | 34 | MEMBER | 1 | 0.90 | 4 | 0 | SUPPRESS | all 34 neighbours already covered by v32, v68, v134, v164 |
| v68 | 17.08 | 1 | v164 | 187 | 67 | MEMBER | 1 | 0.87 | 4 | 2 | FORWARD | 2 neighbour(s) not covered by the senders it heard (v32, v134, v164) |
| v69 | 17.08 | 1 | v164 | 229 | 33 | MEMBER | 1 | 0.89 | 2 | 0 | SUPPRESS | all 33 neighbours already covered by v37, v164 |
| v73 | 17.08 | 1 | v164 | 282 | 66 | MEMBER | 1 | 0.88 | 7 | 0 | SUPPRESS | all 66 neighbours already covered by v32, v114, v128, v134, v164 |
| v74 | 17.08 | 1 | v164 | 199 | 34 | MEMBER | 1 | 0.86 | 5 | 0 | SUPPRESS | all 34 neighbours already covered by v32, v68, v128, v134, v164 |
| v81 | 17.08 | 1 | v164 | 277 | 65 | MEMBER | 1 | 0.01 | 7 | - | DROP | misbehaving vehicle: never relays |
| v82 | 17.08 | 1 | v164 | 210 | 69 | MEMBER | 1 | 0.86 | 6 | 0 | SUPPRESS | all 69 neighbours already covered by v32, v128, v134, v164 |
| v85 | 17.08 | 1 | v164 | 119 | 34 | MEMBER | 1 | 0.85 | 3 | 0 | SUPPRESS | all 34 neighbours already covered by v68, v134, v164 |
| v89 | 17.08 | 1 | v164 | 222 | 26 | BRIDGE | 0 | 0.93 | 2 | 0 | SUPPRESS | all 26 neighbours already covered by v37, v164 |
| v93 | 17.08 | 1 | v164 | 273 | 65 | MEMBER | 1 | 0.88 | 7 | 0 | SUPPRESS | all 65 neighbours already covered by v32, v114, v128, v134, v164 |
| v94 | 17.08 | 1 | v164 | 85 | 69 | MEMBER | 1 | 0.88 | 6 | 0 | SUPPRESS | all 69 neighbours already covered by v32, v37, v68, v86, v164, v175 |
| v101 | 17.08 | 1 | v164 | 140 | 35 | MEMBER | 1 | 0.87 | 3 | 0 | SUPPRESS | all 35 neighbours already covered by v68, v134, v164 |
| v104 | 17.08 | 1 | v164 | 244 | 65 | MEMBER | 1 | 0.88 | 7 | 0 | SUPPRESS | all 65 neighbours already covered by v32, v114, v128, v134, v164 |
| v110 | 17.08 | 1 | v164 | 214 | 32 | MEMBER | 1 | 0.90 | 2 | 0 | SUPPRESS | all 32 neighbours already covered by v37, v164 |
| v115 | 17.08 | 1 | v164 | 159 | 41 | CH | 0 | 0.91 | 3 | 0 | SUPPRESS | all 41 neighbours already covered by v37, v86, v164 |
| v120 | 17.08 | 1 | v164 | 226 | 24 | BRIDGE | 0 | 0.92 | 1 | 0 | SUPPRESS | all 24 neighbours already covered by v164 |
| v124 | 17.08 | 1 | v164 | 282 | 68 | MEMBER | 1 | 0.90 | 7 | 0 | SUPPRESS | all 68 neighbours already covered by v28, v37, v86, v135, v164 |
| v125 | 17.08 | 1 | v164 | 275 | 69 | MEMBER | 1 | 0.92 | 7 | 0 | SUPPRESS | all 69 neighbours already covered by v28, v37, v86, v135, v164 |
| v130 | 17.08 | 1 | v164 | 221 | 34 | MEMBER | 1 | 0.88 | 6 | 0 | SUPPRESS | all 34 neighbours already covered by v32, v44, v128, v134, v164 |
| v142 | 17.08 | 1 | v164 | 58 | 59 | MEMBER | 1 | 0.88 | 6 | 0 | SUPPRESS | all 59 neighbours already covered by v32, v37, v68, v86, v164, v175 |
| v150 | 17.08 | 1 | v164 | 289 | 66 | MEMBER | 1 | 0.90 | 7 | 0 | SUPPRESS | all 66 neighbours already covered by v28, v37, v86, v135, v164 |
| v152 | 17.08 | 1 | v164 | 295 | 66 | MEMBER | 1 | 0.01 | 7 | - | DROP | misbehaving vehicle: never relays |
| v155 | 17.08 | 1 | v164 | 76 | 67 | MEMBER | 1 | 0.86 | 6 | 0 | SUPPRESS | all 67 neighbours already covered by v32, v37, v68, v86, v164, v175 |
| v156 | 17.08 | 1 | v164 | 48 | 44 | BRIDGE | 0 | 0.94 | 4 | 0 | SUPPRESS | all 44 neighbours already covered by v32, v134, v164 |
| v158 | 17.08 | 1 | v164 | 220 | 56 | BRIDGE | 0 | 0.95 | 5 | 0 | SUPPRESS | all 56 neighbours already covered by v32, v128, v164 |
| v160 | 17.08 | 1 | v164 | 55 | 58 | MEMBER | 1 | 0.86 | 6 | 0 | SUPPRESS | all 58 neighbours already covered by v32, v37, v68, v86, v164, v175 |
| v168 | 17.08 | 1 | v164 | 239 | 36 | MEMBER | 1 | 0.92 | 3 | 0 | SUPPRESS | all 36 neighbours already covered by v28, v37, v164 |
| v170 | 17.08 | 1 | v164 | 118 | 69 | MEMBER | 1 | 0.90 | 6 | 0 | SUPPRESS | all 69 neighbours already covered by v32, v37, v68, v86, v164, v175 |
| v174 | 17.08 | 1 | v164 | 251 | 65 | MEMBER | 1 | 0.92 | 7 | 0 | SUPPRESS | all 65 neighbours already covered by v32, v114, v128, v134, v164 |
| v177 | 17.08 | 1 | v164 | 292 | 68 | MEMBER | 1 | 0.91 | 7 | 0 | SUPPRESS | all 68 neighbours already covered by v28, v37, v86, v135, v164 |
| v179 | 17.08 | 1 | v164 | 267 | 69 | MEMBER | 1 | 0.89 | 7 | 0 | SUPPRESS | all 69 neighbours already covered by v28, v37, v86, v135, v164 |
| v193 | 17.08 | 1 | v164 | 134 | 43 | MEMBER | 1 | 0.93 | 4 | 0 | SUPPRESS | all 43 neighbours already covered by v37, v68, v86, v164 |
| v194 | 17.08 | 1 | v164 | 146 | 29 | BRIDGE | 0 | 0.91 | 1 | 0 | SUPPRESS | all 29 neighbours already covered by v164 |
| v197 | 17.08 | 1 | v164 | 67 | 62 | CH | 0 | 0.90 | 6 | 0 | SUPPRESS | all 62 neighbours already covered by v32, v37, v86, v164 |
| v5 | 22.48 | 2 | v32 | 174 | 64 | MEMBER | 1 | 0.88 | 7 | 0 | SUPPRESS | all 64 neighbours already covered by v32, v57, v68, v114, v128, v134, v181 |
| v16 | 22.48 | 2 | v32 | 150 | 66 | MEMBER | 1 | 0.01 | 7 | - | DROP | misbehaving vehicle: never relays |
| v23 | 22.48 | 2 | v32 | 228 | 86 | MEMBER | 1 | 0.93 | 7 | 0 | SUPPRESS | all 86 neighbours already covered by v4, v32, v68, v135, v162, v175 |
| v27 | 22.48 | 2 | v32 | 221 | 89 | MEMBER | 1 | 0.95 | 7 | 0 | SUPPRESS | all 89 neighbours already covered by v4, v32, v68, v135, v162, v175 |
| v35 | 22.48 | 2 | v32 | 272 | 85 | MEMBER | 1 | 0.80 | 8 | 0 | SUPPRESS | all 85 neighbours already covered by v8, v32, v71, v114, v135, v162 |
| v39 | 22.48 | 2 | v32 | 218 | 68 | BRIDGE | 1 | 0.01 | 7 | - | DROP | misbehaving vehicle: never relays |
| v44 | 22.48 | 2 | v32 | 190 | 45 | BRIDGE | 0 | 0.91 | 6 | 2 | FORWARD | 2 neighbour(s) not covered by the senders it heard (v32, v128, v134) |
| v46 | 22.48 | 2 | v32 | 212 | 89 | MEMBER | 1 | 0.92 | 7 | 0 | SUPPRESS | all 89 neighbours already covered by v4, v32, v68, v135, v162, v175 |
| v52 | 22.48 | 2 | v32 | 185 | 85 | MEMBER | 1 | 0.89 | 6 | 0 | SUPPRESS | all 85 neighbours already covered by v4, v32, v68, v135, v175 |
| v53 | 22.48 | 2 | v32 | 268 | 85 | MEMBER | 1 | 0.93 | 8 | 0 | SUPPRESS | all 85 neighbours already covered by v8, v32, v71, v114, v135, v162 |
| v63 | 22.48 | 2 | v32 | 231 | 86 | MEMBER | 1 | 0.90 | 7 | 0 | SUPPRESS | all 86 neighbours already covered by v4, v32, v68, v135, v162, v175 |
| v65 | 22.48 | 2 | v32 | 233 | 83 | MEMBER | 1 | 0.01 | 7 | - | DROP | misbehaving vehicle: never relays |
| v76 | 22.48 | 2 | v32 | 276 | 84 | MEMBER | 1 | 0.88 | 7 | 0 | SUPPRESS | all 84 neighbours already covered by v8, v32, v71, v114, v162, v175 |
| v77 | 22.48 | 2 | v32 | 291 | 81 | MEMBER | 1 | 0.92 | 8 | 0 | SUPPRESS | all 81 neighbours already covered by v8, v32, v71, v114, v135, v162 |
| v78 | 22.48 | 2 | v32 | 298 | 80 | MEMBER | 1 | 0.84 | 8 | 0 | SUPPRESS | all 80 neighbours already covered by v8, v32, v71, v114, v135, v162 |
| v79 | 22.48 | 2 | v32 | 251 | 40 | BRIDGE | 0 | 0.89 | 6 | 0 | SUPPRESS | all 40 neighbours already covered by v32, v128 |
| v83 | 22.48 | 2 | v32 | 165 | 67 | MEMBER | 1 | 0.86 | 7 | 0 | SUPPRESS | all 67 neighbours already covered by v32, v57, v68, v114, v128, v134, v181 |
| v88 | 22.48 | 2 | v32 | 251 | 54 | MEMBER | 1 | 0.87 | 6 | 0 | SUPPRESS | all 54 neighbours already covered by v32, v44, v57, v114, v128, v181 |
| v97 | 22.48 | 2 | v32 | 257 | 84 | MEMBER | 1 | 0.89 | 6 | 0 | SUPPRESS | all 84 neighbours already covered by v8, v32, v114, v162, v175 |
| v98 | 22.48 | 2 | v32 | 164 | 64 | MEMBER | 1 | 0.90 | 7 | 0 | SUPPRESS | all 64 neighbours already covered by v32, v57, v68, v114, v128, v134, v181 |
| v99 | 22.48 | 2 | v32 | 165 | 62 | MEMBER | 1 | 0.87 | 7 | 0 | SUPPRESS | all 62 neighbours already covered by v32, v57, v68, v114, v128, v134, v181 |
| v114 | 22.48 | 2 | v32 | 282 | 83 | CH | 0 | 0.86 | 7 | 43 | FORWARD | 43 neighbour(s) not covered by the senders it heard (v32) |
| v116 | 22.48 | 2 | v32 | 175 | 66 | MEMBER | 1 | 0.91 | 7 | 0 | SUPPRESS | all 66 neighbours already covered by v32, v57, v68, v114, v128, v134, v181 |
| v119 | 22.48 | 2 | v32 | 230 | 85 | MEMBER | 1 | 0.89 | 6 | 0 | SUPPRESS | all 85 neighbours already covered by v4, v32, v68, v135, v175 |
| v122 | 22.48 | 2 | v32 | 205 | 38 | BRIDGE | 0 | 0.88 | 5 | 0 | SUPPRESS | all 38 neighbours already covered by v32, v128, v134 |
| v126 | 22.48 | 2 | v32 | 267 | 51 | MEMBER | 1 | 0.90 | 6 | 0 | SUPPRESS | all 51 neighbours already covered by v32, v44, v57, v114, v128, v181 |
| v128 | 22.48 | 2 | v32 | 243 | 39 | BRIDGE | 0 | 0.92 | 5 | 8 | FORWARD | 8 neighbour(s) not covered by the senders it heard (v32) |
| v134 | 22.48 | 2 | v32 | 211 | 38 | BRIDGE | 0 | 0.92 | 4 | 4 | FORWARD | 4 neighbour(s) not covered by the senders it heard (v32, v128) |
| v135 | 22.48 | 2 | v32 | 220 | 90 | CH | 0 | 0.91 | 6 | 47 | FORWARD | 47 neighbour(s) not covered by the senders it heard (v32) |
| v136 | 22.48 | 2 | v32 | 168 | 63 | CH | 0 | 0.82 | 7 | 0 | SUPPRESS | all 63 neighbours already covered by v32, v114, v128, v134 |
| v140 | 22.48 | 2 | v32 | 217 | 90 | MEMBER | 1 | 0.88 | 7 | 0 | SUPPRESS | all 90 neighbours already covered by v4, v32, v68, v135, v162, v175 |
| v148 | 22.48 | 2 | v32 | 264 | 87 | MEMBER | 1 | 0.01 | 8 | - | DROP | misbehaving vehicle: never relays |
| v149 | 22.48 | 2 | v32 | 202 | 87 | MEMBER | 1 | 0.01 | 7 | - | DROP | misbehaving vehicle: never relays |
| v151 | 22.48 | 2 | v32 | 174 | 65 | MEMBER | 1 | 0.87 | 7 | 0 | SUPPRESS | all 65 neighbours already covered by v32, v57, v68, v114, v128, v134, v181 |
| v163 | 22.48 | 2 | v32 | 190 | 65 | MEMBER | 1 | 0.85 | 7 | 0 | SUPPRESS | all 65 neighbours already covered by v32, v57, v68, v114, v128, v134, v181 |
| v165 | 22.48 | 2 | v32 | 266 | 85 | MEMBER | 1 | 0.95 | 8 | 0 | SUPPRESS | all 85 neighbours already covered by v8, v32, v71, v114, v162, v181 |
| v175 | 22.48 | 2 | v32 | 240 | 89 | MEMBER | 1 | 0.91 | 5 | 1 | FORWARD | 1 neighbour(s) not covered by the senders it heard (v4, v32, v68, v135) |
| v195 | 22.48 | 2 | v32 | 212 | 59 | MEMBER | 1 | 0.01 | 8 | - | DROP | misbehaving vehicle: never relays |
| v11 | 24.78 | 2 | v37 | 265 | 68 | MEMBER | 1 | 0.91 | 6 | 0 | SUPPRESS | all 68 neighbours already covered by v4, v28, v37, v86, v135, v175 |
| v28 | 24.78 | 2 | v37 | 193 | 43 | BRIDGE | 0 | 0.88 | 3 | 3 | FORWARD | 3 neighbour(s) not covered by the senders it heard (v37, v86) |
| v29 | 24.78 | 2 | v37 | 269 | 69 | MEMBER | 1 | 0.87 | 6 | 0 | SUPPRESS | all 69 neighbours already covered by v4, v28, v37, v86, v135, v175 |
| v41 | 24.78 | 2 | v37 | 102 | 47 | BRIDGE | 0 | 0.91 | 3 | 0 | SUPPRESS | all 47 neighbours already covered by v28, v37, v86 |
| v50 | 24.78 | 2 | v37 | 238 | 67 | MEMBER | 1 | 0.91 | 7 | 0 | SUPPRESS | all 67 neighbours already covered by v4, v28, v37, v68, v86, v135, v175 |
| v56 | 24.78 | 2 | v37 | 27 | 37 | BRIDGE | 1 | 0.01 | 3 | - | DROP | misbehaving vehicle: never relays |
| v61 | 24.78 | 2 | v37 | 98 | 44 | BRIDGE | 0 | 0.90 | 3 | 0 | SUPPRESS | all 44 neighbours already covered by v28, v37, v86 |
| v86 | 24.78 | 2 | v37 | 247 | 69 | CH | 0 | 0.87 | 5 | 38 | FORWARD | 38 neighbour(s) not covered by the senders it heard (v37) |
| v87 | 24.78 | 2 | v37 | 132 | 56 | BRIDGE | 0 | 0.88 | 4 | 0 | SUPPRESS | all 56 neighbours already covered by v28, v37, v86 |
| v90 | 24.78 | 2 | v37 | 242 | 69 | MEMBER | 1 | 0.93 | 7 | 0 | SUPPRESS | all 69 neighbours already covered by v4, v28, v37, v68, v86, v135 |
| v96 | 24.78 | 2 | v37 | 258 | 70 | MEMBER | 1 | 0.01 | 6 | - | DROP | misbehaving vehicle: never relays |
| v133 | 24.78 | 2 | v37 | 277 | 71 | MEMBER | 1 | 0.94 | 6 | 0 | SUPPRESS | all 71 neighbours already covered by v4, v28, v37, v86, v135, v175 |
| v14 | 27.69 | 3 | v128 | 171 | 24 | CH | 0 | 0.87 | 4 | 0 | SUPPRESS | all 24 neighbours already covered by v44, v57, v128, v181 |
| v25 | 27.69 | 3 | v128 | 187 | 26 | BRIDGE | 0 | 0.88 | 4 | 0 | SUPPRESS | all 26 neighbours already covered by v44, v128 |
| v47 | 27.69 | 3 | v128 | 167 | 24 | MEMBER | 1 | 0.92 | 4 | 0 | SUPPRESS | all 24 neighbours already covered by v44, v57, v128, v181 |
| v57 | 27.69 | 3 | v128 | 221 | 32 | BRIDGE | 0 | 0.91 | 3 | 6 | FORWARD | 6 neighbour(s) not covered by the senders it heard (v44, v128) |
| v67 | 27.69 | 3 | v128 | 80 | 28 | BRIDGE | 0 | 0.91 | 5 | 0 | SUPPRESS | all 28 neighbours already covered by v44, v57, v128, v134, v181 |
| v111 | 27.69 | 3 | v128 | 171 | 25 | MEMBER | 1 | 0.86 | 4 | 0 | SUPPRESS | all 25 neighbours already covered by v44, v57, v128, v181 |
| v167 | 27.69 | 3 | v128 | 170 | 24 | MEMBER | 1 | 0.85 | 4 | 0 | SUPPRESS | all 24 neighbours already covered by v44, v57, v128, v181 |
| v181 | 27.69 | 3 | v128 | 236 | 34 | BRIDGE | 0 | 0.86 | 3 | 1 | FORWARD | 1 neighbour(s) not covered by the senders it heard (v44, v57, v128) |
| v8 | 32.34 | 3 | v114 | 253 | 57 | BRIDGE | 0 | 0.89 | 6 | 1 | FORWARD | 1 neighbour(s) not covered by the senders it heard (v71, v114) |
| v15 | 32.34 | 3 | v114 | 270 | 83 | MEMBER | 1 | 0.96 | 9 | 0 | SUPPRESS | all 83 neighbours already covered by v4, v8, v75, v100, v114, v135, v162, v175 |
| v30 | 32.34 | 3 | v114 | 279 | 88 | MEMBER | 1 | 0.95 | 9 | 0 | SUPPRESS | all 88 neighbours already covered by v4, v8, v75, v100, v114, v135, v162, v175 |
| v34 | 32.34 | 3 | v114 | 37 | 74 | MEMBER | 1 | 0.01 | 8 | - | DROP | misbehaving vehicle: never relays |
| v38 | 32.34 | 3 | v114 | 38 | 82 | MEMBER | 1 | 0.88 | 6 | 0 | SUPPRESS | all 82 neighbours already covered by v8, v114, v135, v162, v175, v185 |
| v42 | 32.34 | 3 | v114 | 60 | 81 | MEMBER | 1 | 0.94 | 6 | 0 | SUPPRESS | all 81 neighbours already covered by v8, v114, v135, v162, v175, v185 |
| v48 | 32.34 | 3 | v114 | 158 | 77 | MEMBER | 1 | 0.91 | 8 | 0 | SUPPRESS | all 77 neighbours already covered by v8, v75, v100, v114, v135, v162, v175, v185 |
| v51 | 32.34 | 3 | v114 | 238 | 68 | MEMBER | 1 | 0.92 | 7 | 0 | SUPPRESS | all 68 neighbours already covered by v8, v75, v100, v114, v135, v162, v185 |
| v54 | 32.34 | 3 | v114 | 291 | 89 | MEMBER | 1 | 0.87 | 9 | 0 | SUPPRESS | all 89 neighbours already covered by v4, v8, v75, v100, v114, v135, v162, v175 |
| v55 | 32.34 | 3 | v114 | 209 | 49 | BRIDGE | 0 | 0.93 | 4 | 0 | SUPPRESS | all 49 neighbours already covered by v8, v71, v114, v162 |
| v59 | 32.34 | 3 | v114 | 139 | 58 | MEMBER | 1 | 0.82 | 4 | 0 | SUPPRESS | all 58 neighbours already covered by v71, v114, v162, v181 |
| v60 | 32.34 | 3 | v114 | 214 | 70 | MEMBER | 1 | 0.86 | 7 | 0 | SUPPRESS | all 70 neighbours already covered by v8, v75, v100, v114, v135, v162, v185 |
| v70 | 32.34 | 3 | v114 | 237 | 68 | MEMBER | 1 | 0.88 | 7 | 0 | SUPPRESS | all 68 neighbours already covered by v8, v75, v100, v114, v135, v162, v185 |
| v71 | 32.34 | 3 | v114 | 277 | 49 | CH | 0 | 0.90 | 6 | 8 | FORWARD | 8 neighbour(s) not covered by the senders it heard (v114) |
| v91 | 32.34 | 3 | v114 | 237 | 67 | MEMBER | 1 | 0.88 | 6 | 0 | SUPPRESS | all 67 neighbours already covered by v8, v75, v100, v114, v162, v185 |
| v102 | 32.34 | 3 | v114 | 176 | 76 | MEMBER | 1 | 0.90 | 7 | 0 | SUPPRESS | all 76 neighbours already covered by v8, v75, v100, v114, v135, v162, v185 |
| v106 | 32.34 | 3 | v114 | 166 | 57 | CH | 0 | 0.91 | 4 | 0 | SUPPRESS | all 57 neighbours already covered by v71, v114, v162, v181 |
| v107 | 32.34 | 3 | v114 | 130 | 76 | MEMBER | 1 | 0.01 | 8 | - | DROP | misbehaving vehicle: never relays |
| v108 | 32.34 | 3 | v114 | 278 | 49 | MEMBER | 1 | 0.88 | 7 | 0 | SUPPRESS | all 49 neighbours already covered by v8, v71, v75, v100, v114, v162 |
| v113 | 32.34 | 3 | v114 | 279 | 48 | MEMBER | 1 | 0.95 | 6 | 0 | SUPPRESS | all 48 neighbours already covered by v8, v71, v75, v100, v114, v162 |
| v118 | 32.34 | 3 | v114 | 283 | 90 | MEMBER | 1 | 0.92 | 9 | 0 | SUPPRESS | all 90 neighbours already covered by v4, v8, v75, v100, v114, v135, v162, v175 |
| v121 | 32.34 | 3 | v114 | 207 | 73 | MEMBER | 1 | 0.90 | 7 | 0 | SUPPRESS | all 73 neighbours already covered by v8, v75, v100, v114, v135, v162, v185 |
| v131 | 32.34 | 3 | v114 | 174 | 52 | MEMBER | 1 | 0.87 | 4 | 0 | SUPPRESS | all 52 neighbours already covered by v71, v114, v162, v181 |
| v139 | 32.34 | 3 | v114 | 64 | 68 | MEMBER | 1 | 0.92 | 5 | 0 | SUPPRESS | all 68 neighbours already covered by v71, v114, v135, v162, v181 |
| v141 | 32.34 | 3 | v114 | 199 | 40 | BRIDGE | 0 | 0.85 | 4 | 0 | SUPPRESS | all 40 neighbours already covered by v44, v57, v114, v181 |
| v146 | 32.34 | 3 | v114 | 270 | 50 | MEMBER | 1 | 0.91 | 7 | 0 | SUPPRESS | all 50 neighbours already covered by v8, v71, v75, v100, v114, v162, v185 |
| v154 | 32.34 | 3 | v114 | 234 | 73 | MEMBER | 1 | 0.87 | 8 | 0 | SUPPRESS | all 73 neighbours already covered by v8, v75, v100, v114, v135, v162, v175, v185 |
| v157 | 32.34 | 3 | v114 | 109 | 63 | MEMBER | 1 | 0.88 | 5 | 0 | SUPPRESS | all 63 neighbours already covered by v71, v114, v135, v162, v181 |
| v159 | 32.34 | 3 | v114 | 245 | 67 | MEMBER | 1 | 0.93 | 6 | 0 | SUPPRESS | all 67 neighbours already covered by v8, v75, v100, v114, v162 |
| v161 | 32.34 | 3 | v114 | 228 | 43 | BRIDGE | 0 | 0.91 | 4 | 0 | SUPPRESS | all 43 neighbours already covered by v44, v57, v114, v181 |
| v162 | 32.34 | 3 | v114 | 190 | 75 | CH | 0 | 0.91 | 6 | 3 | FORWARD | 3 neighbour(s) not covered by the senders it heard (v8, v114, v135) |
| v166 | 32.34 | 3 | v114 | 172 | 56 | MEMBER | 1 | 0.89 | 4 | 0 | SUPPRESS | all 56 neighbours already covered by v71, v114, v162, v181 |
| v171 | 32.34 | 3 | v114 | 273 | 63 | MEMBER | 1 | 0.89 | 6 | 0 | SUPPRESS | all 63 neighbours already covered by v8, v75, v100, v114, v162 |
| v180 | 32.34 | 3 | v114 | 289 | 45 | MEMBER | 1 | 0.83 | 6 | 0 | SUPPRESS | all 45 neighbours already covered by v8, v71, v75, v100, v114, v162 |
| v183 | 32.34 | 3 | v114 | 156 | 77 | MEMBER | 1 | 0.89 | 8 | 0 | SUPPRESS | all 77 neighbours already covered by v8, v75, v100, v114, v135, v162, v175, v185 |
| v184 | 32.34 | 3 | v114 | 230 | 74 | MEMBER | 1 | 0.88 | 7 | 0 | SUPPRESS | all 74 neighbours already covered by v8, v75, v100, v114, v135, v162, v185 |
| v185 | 32.34 | 3 | v114 | 259 | 84 | MEMBER | 1 | 0.93 | 7 | 3 | FORWARD | 3 neighbour(s) not covered by the senders it heard (v8, v75, v100, v114, v135, v162, v175) |
| v186 | 32.34 | 3 | v114 | 199 | 75 | MEMBER | 1 | 0.86 | 7 | 0 | SUPPRESS | all 75 neighbours already covered by v8, v75, v100, v114, v135, v162, v185 |
| v187 | 32.34 | 3 | v114 | 286 | 90 | MEMBER | 1 | 0.85 | 9 | 0 | SUPPRESS | all 90 neighbours already covered by v4, v8, v75, v100, v114, v135, v162, v175 |
| v190 | 32.34 | 3 | v114 | 245 | 67 | MEMBER | 1 | 0.93 | 6 | 0 | SUPPRESS | all 67 neighbours already covered by v8, v75, v100, v114, v162, v185 |
| v198 | 32.34 | 3 | v114 | 214 | 72 | MEMBER | 1 | 0.85 | 7 | 0 | SUPPRESS | all 72 neighbours already covered by v8, v75, v100, v114, v135, v162, v185 |
| v199 | 32.34 | 3 | v114 | 288 | 90 | MEMBER | 1 | 0.90 | 9 | 0 | SUPPRESS | all 90 neighbours already covered by v4, v8, v75, v100, v114, v135, v162, v175 |
| v1 | 32.59 | 3 | v86 | 168 | 72 | MEMBER | 1 | 0.01 | 6 | - | DROP | misbehaving vehicle: never relays |
| v4 | 32.59 | 3 | v86 | 283 | 86 | CH | 0 | 0.84 | 7 | 20 | FORWARD | 20 neighbour(s) not covered by the senders it heard (v86, v135) |
| v6 | 32.59 | 3 | v86 | 187 | 72 | MEMBER | 1 | 0.01 | 6 | - | DROP | misbehaving vehicle: never relays |
| v7 | 32.59 | 3 | v86 | 290 | 52 | MEMBER | 1 | 0.87 | 3 | 0 | SUPPRESS | all 52 neighbours already covered by v4, v31, v86 |
| v12 | 32.59 | 3 | v86 | 180 | 72 | MEMBER | 1 | 0.88 | 6 | 0 | SUPPRESS | all 72 neighbours already covered by v4, v28, v31, v86, v175, v185 |
| v20 | 32.59 | 3 | v86 | 199 | 69 | MEMBER | 1 | 0.94 | 6 | 0 | SUPPRESS | all 69 neighbours already covered by v4, v28, v31, v86, v175, v185 |
| v36 | 32.59 | 3 | v86 | 225 | 64 | MEMBER | 1 | 0.85 | 5 | 0 | SUPPRESS | all 64 neighbours already covered by v4, v28, v31, v86, v185 |
| v80 | 32.59 | 3 | v86 | 280 | 86 | MEMBER | 1 | 0.95 | 8 | 0 | SUPPRESS | all 86 neighbours already covered by v4, v75, v86, v100, v135, v162, v175 |
| v84 | 32.59 | 3 | v86 | 187 | 71 | MEMBER | 1 | 0.88 | 6 | 0 | SUPPRESS | all 71 neighbours already covered by v4, v28, v31, v86, v175, v185 |
| v103 | 32.59 | 3 | v86 | 217 | 66 | MEMBER | 1 | 0.90 | 6 | 0 | SUPPRESS | all 66 neighbours already covered by v4, v28, v31, v86, v175, v185 |
| v105 | 32.59 | 3 | v86 | 223 | 54 | CH | 0 | 0.93 | 4 | 0 | SUPPRESS | all 54 neighbours already covered by v4, v28, v86 |
| v117 | 32.59 | 3 | v86 | 215 | 57 | MEMBER | 1 | 0.01 | 4 | - | DROP | misbehaving vehicle: never relays |
| v123 | 32.59 | 3 | v86 | 210 | 67 | MEMBER | 1 | 0.96 | 6 | 0 | SUPPRESS | all 67 neighbours already covered by v4, v28, v31, v86, v175, v185 |
| v127 | 32.59 | 3 | v86 | 295 | 52 | MEMBER | 1 | 0.93 | 3 | 0 | SUPPRESS | all 52 neighbours already covered by v4, v31, v86 |
| v132 | 32.59 | 3 | v86 | 196 | 66 | MEMBER | 1 | 0.01 | 5 | - | DROP | misbehaving vehicle: never relays |
| v138 | 32.59 | 3 | v86 | 286 | 87 | MEMBER | 1 | 0.91 | 8 | 0 | SUPPRESS | all 87 neighbours already covered by v4, v75, v86, v100, v135, v162, v175 |
| v143 | 32.59 | 3 | v86 | 218 | 66 | MEMBER | 1 | 0.90 | 6 | 0 | SUPPRESS | all 66 neighbours already covered by v4, v28, v31, v86, v175, v185 |
| v145 | 32.59 | 3 | v86 | 277 | 86 | MEMBER | 1 | 0.90 | 8 | 0 | SUPPRESS | all 86 neighbours already covered by v4, v75, v86, v100, v135, v162, v175 |
| v153 | 32.59 | 3 | v86 | 288 | 86 | MEMBER | 1 | 0.93 | 8 | 0 | SUPPRESS | all 86 neighbours already covered by v4, v75, v86, v100, v135, v162, v175 |
| v172 | 32.59 | 3 | v86 | 210 | 67 | MEMBER | 1 | 0.96 | 6 | 0 | SUPPRESS | all 67 neighbours already covered by v4, v28, v31, v86, v175, v185 |
| v176 | 32.59 | 3 | v86 | 194 | 72 | MEMBER | 1 | 0.83 | 6 | 0 | SUPPRESS | all 72 neighbours already covered by v4, v28, v31, v86, v175, v185 |
| v182 | 32.59 | 3 | v86 | 179 | 72 | CH | 0 | 0.83 | 6 | 0 | SUPPRESS | all 72 neighbours already covered by v4, v28, v86 |
| v189 | 32.59 | 3 | v86 | 229 | 64 | MEMBER | 1 | 0.86 | 5 | 0 | SUPPRESS | all 64 neighbours already covered by v4, v28, v31, v86, v185 |
| v192 | 32.59 | 3 | v86 | 214 | 56 | MEMBER | 1 | 0.84 | 4 | 0 | SUPPRESS | all 56 neighbours already covered by v4, v28, v31, v86 |
| v72 | 35.13 | 3 | v135 | 222 | 93 | MEMBER | 1 | 0.92 | 7 | 0 | SUPPRESS | all 93 neighbours already covered by v4, v75, v100, v135, v162, v175, v185 |
| v95 | 35.13 | 3 | v135 | 265 | 80 | MEMBER | 1 | 0.93 | 8 | 0 | SUPPRESS | all 80 neighbours already covered by v4, v8, v75, v100, v135, v162, v175, v185 |
| v2 | 38.01 | 4 | v4 | 153 | 58 | MEMBER | 1 | 0.91 | 4 | 0 | SUPPRESS | all 58 neighbours already covered by v4, v75, v100, v185 |
| v17 | 38.01 | 4 | v4 | 170 | 50 | MEMBER | 1 | 0.90 | 4 | 0 | SUPPRESS | all 50 neighbours already covered by v4, v75, v100, v185 |
| v19 | 38.01 | 4 | v4 | 278 | 41 | MEMBER | 1 | 0.90 | 2 | 0 | SUPPRESS | all 41 neighbours already covered by v4, v31 |
| v33 | 38.01 | 4 | v4 | 246 | 47 | MEMBER | 1 | 0.89 | 2 | 0 | SUPPRESS | all 47 neighbours already covered by v4, v31 |
| v62 | 38.01 | 4 | v4 | 219 | 49 | BRIDGE | 0 | 0.85 | 3 | 0 | SUPPRESS | all 49 neighbours already covered by v4, v31 |
| v112 | 38.01 | 4 | v4 | 152 | 63 | MEMBER | 1 | 0.88 | 5 | 0 | SUPPRESS | all 63 neighbours already covered by v4, v75, v100, v162, v185 |
| v169 | 38.01 | 4 | v4 | 157 | 61 | MEMBER | 1 | 0.89 | 5 | 0 | SUPPRESS | all 61 neighbours already covered by v4, v75, v100, v162, v185 |
| v173 | 38.01 | 4 | v4 | 246 | 47 | MEMBER | 1 | 0.88 | 2 | 0 | SUPPRESS | all 47 neighbours already covered by v4, v31 |
| v178 | 38.01 | 4 | v4 | 238 | 49 | CH | 0 | 0.87 | 2 | 0 | SUPPRESS | all 49 neighbours already covered by v4, v31 |
| v188 | 38.01 | 4 | v4 | 187 | 48 | BRIDGE | 0 | 0.91 | 4 | 0 | SUPPRESS | all 48 neighbours already covered by v4, v31 |
| v191 | 38.01 | 4 | v4 | 255 | 46 | MEMBER | 1 | 0.01 | 2 | - | DROP | misbehaving vehicle: never relays |
| v196 | 38.01 | 4 | v4 | 138 | 63 | CH | 0 | 0.92 | 5 | 0 | SUPPRESS | all 63 neighbours already covered by v4, v75, v100, v162 |
| v9 | 38.44 | 4 | v71 | 182 | 42 | MEMBER | 1 | 0.90 | 6 | 0 | SUPPRESS | all 42 neighbours already covered by v8, v71, v75, v100, v162, v185 |
| v137 | 38.44 | 4 | v71 | 172 | 33 | BRIDGE | 0 | 0.88 | 6 | 0 | SUPPRESS | all 33 neighbours already covered by v8, v71, v75, v100, v162 |
| v144 | 38.44 | 4 | v71 | 57 | 38 | BRIDGE | 0 | 0.94 | 5 | 0 | SUPPRESS | all 38 neighbours already covered by v8, v71, v75, v100, v162 |
| v147 | 38.44 | 4 | v71 | 128 | 31 | BRIDGE | 0 | 0.92 | 5 | 0 | SUPPRESS | all 31 neighbours already covered by v8, v71, v75, v100, v162 |
| v31 | 38.82 | 3 | v28 | 295 | 30 | BRIDGE | 0 | 0.85 | 1 | 9 | FORWARD | 9 neighbour(s) not covered by the senders it heard (v28) |
| v109 | 38.82 | 3 | v28 | 166 | 35 | BRIDGE | 0 | 0.95 | 2 | 0 | SUPPRESS | all 35 neighbours already covered by v28, v31 |
| v129 | 38.82 | 3 | v28 | 277 | 30 | BRIDGE | 1 | 0.01 | 2 | - | DROP | misbehaving vehicle: never relays |
| v22 | 40.53 | 4 | v8 | 182 | 49 | MEMBER | 1 | 0.89 | 5 | 0 | SUPPRESS | all 49 neighbours already covered by v8, v75, v100, v162, v185 |
| v75 | 40.53 | 4 | v8 | 204 | 49 | BRIDGE | 0 | 0.89 | 4 | 2 | FORWARD | 2 neighbour(s) not covered by the senders it heard (v8, v162) |
| v92 | 40.53 | 4 | v8 | 168 | 49 | CH | 0 | 0.91 | 5 | 0 | SUPPRESS | all 49 neighbours already covered by v8, v75, v100, v162 |
| v100 | 40.53 | 4 | v8 | 224 | 50 | BRIDGE | 0 | 0.91 | 4 | 1 | FORWARD | 1 neighbour(s) not covered by the senders it heard (v8, v75, v162) |
