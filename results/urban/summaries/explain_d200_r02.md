# One-run explainer: d200_r02 (Proposed (full))

Seed 30002 | 200 vehicles | 20 misbehaving (never relay) | RSUs: RSU-1 at (152, 605), RSU-2 at (630, 169)

## The emergency packet

```json
{
  "event_id": "EVT-30002-v164-1",
  "message_type": "ACCIDENT",
  "source_vehicle": "v164",
  "sequence_number": 1,
  "incident_position": [
    601.38,
    608.69
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
| 114.000 s | **v164** has the accident at (601.38, 608.69) on lane `D4D3_1`. This is the only incident of the run. |
| +0.000 ms | Alert **EVT-30002-v164-1** is created (type ACCIDENT, hop limit 10). From earlier beacons every vehicle knows its neighbours and their reputation; DBSCAN gave 22 clusters with 22 representatives, 39 isolated vehicles (bridges) and 139 members. Committee: v170, v156, v68, v90, v18. |
| +0.065 ms | **v164** (the crashed vehicle) broadcasts the PROPOSAL: the alert with its own BLS signature. Decoded by 56 nodes. The signature proves who sent it, not that the event is real. |
| +6.474 ms | **v170** VOTES yes (reputation 0.89): it observes the crash and signs the event digest. One BLS signature, one vote. |
| +6.981 ms | **v156** VOTES yes (reputation 0.91): it observes the crash and signs the event digest. One BLS signature, one vote. |
| +7.475 ms | **v68** VOTES yes (reputation 0.90): it observes the crash and signs the event digest. One BLS signature, one vote. |
| +7.982 ms | **v90** VOTES yes (reputation 0.88): it observes the crash and signs the event digest. One BLS signature, one vote. |
| +8.463 ms | **v18** VOTES yes (reputation 0.86): it observes the crash and signs the event digest. One BLS signature, one vote. |
| +12.129 ms | **v164** has 3 votes, a majority of the committee of 5. It aggregates 4 signatures into one BLS signature and broadcasts the CERTIFIED ALERT. Decoded by 56 nodes (56 accept it). |
| +18.122 ms | **v101** FORWARDS (BRIDGE, tier 0, reputation 0.85; accepted the copy from v164 280 m away, hop 1): 6 neighbour(s) not covered by the senders it heard (v164). Frame decoded by 36 nodes (6 new, 30 already had it), lost at 0. |
| +18.369 ms | **v58** SUPPRESSES: all 18 neighbours already covered by v164. |
| +20.046 ms | **v3** FORWARDS (CH, tier 0, reputation 0.87; accepted the copy from v164 279 m away, hop 1): 33 neighbour(s) not covered by the senders it heard (v101, v164). Frame decoded by 73 nodes (33 new, 40 already had it), lost at 0. |
| +20.787 ms | **v80** FORWARDS (CH, tier 0, reputation 0.89; accepted the copy from v164 263 m away, hop 1): 19 neighbour(s) not covered by the senders it heard (v101, v164). Frame decoded by 59 nodes (1 new, 58 already had it), lost at 0. |
| +21.125 ms | **v64** SUPPRESSES: all 37 neighbours already covered by v3, v101, v164. |
| +22.178 ms | **v0** FORWARDS (CH, tier 0, reputation 0.90; accepted the copy from v164 199 m away, hop 1): 21 neighbour(s) not covered by the senders it heard (v164). Frame decoded by 53 nodes (18 new, 35 already had it), lost at 0. |
| +22.399 ms | **v194** SUPPRESSES: all 28 neighbours already covered by v80, v101, v164. |
| +23.764 ms | **v89** FORWARDS (BRIDGE, tier 0, reputation 0.84; accepted the copy from v164 204 m away, hop 1): 1 neighbour(s) not covered by the senders it heard (v164). Frame decoded by 22 nodes (0 new, 22 already had it), lost at 0. |
| +24.856 ms | **v29** FORWARDS (BRIDGE, tier 0, reputation 0.89; accepted the copy from v164 226 m away, hop 1): 1 neighbour(s) not covered by the senders it heard (v0, v89, v164). Frame decoded by 30 nodes (1 new, 29 already had it), lost at 0. |
| +24.999 ms | **RSU-2** decodes the alert from v3 (hop 2): plausibility validation passes; event **EVT-30002-v164-1 REGISTERED** after 12 transmission(s); 95 vehicles had the alert by then. |
| +25.012 ms | **v37** SUPPRESSES: all 29 neighbours already covered by v0, v89, v164. |
| +25.584 ms | **v87** FORWARDS (CH, tier 0, reputation 0.82; accepted the copy from v164 239 m away, hop 1): 12 neighbour(s) not covered by the senders it heard (v0, v164). Frame decoded by 59 nodes (11 new, 48 already had it), lost at 0. |
| +25.779 ms | **v120** SUPPRESSES: all 32 neighbours already covered by v0, v29, v89, v164. |
| +26.013 ms | **v74** SUPPRESSES: all 41 neighbours already covered by v3, v80, v89, v101, v164. |
| +26.182 ms | **v181** FORWARDS (CH, tier 0, reputation 0.91; accepted the copy from v3 292 m away, hop 2): 8 neighbour(s) not covered by the senders it heard (v3, v80). Frame decoded by 18 nodes (5 new, 13 already had it), lost at 20. |
| +26.208 ms | **v43** SUPPRESSES: all 39 neighbours already covered by v3, v80, v89, v101, v164. |
| +26.754 ms | **v85** SUPPRESSES: all 25 neighbours already covered by v89, v101, v164. |
| +26.819 ms | **v53** FORWARDS (CH, tier 0, reputation 0.90; accepted the copy from v3 259 m away, hop 2): 46 neighbour(s) not covered by the senders it heard (v3). Frame decoded by 72 nodes (43 new, 29 already had it), lost at 20. |
| +27.131 ms | **RSU-1** decodes the alert from v0 (hop 2): same event ID, already registered, counted as a duplicate. |
| +27.768 ms | **v20** FORWARDS (CH, tier 0, reputation 0.91; accepted the copy from v0 252 m away, hop 2): 22 neighbour(s) not covered by the senders it heard (v0, v87). Frame decoded by 62 nodes (15 new, 47 already had it), lost at 0. |
| +29.887 ms | **v153** FORWARDS (BRIDGE, tier 0, reputation 0.95; accepted the copy from v0 297 m away, hop 2): 27 neighbour(s) not covered by the senders it heard (v0, v20). Frame decoded by 74 nodes (6 new, 68 already had it), lost at 0. |
| +32.877 ms | **v180** FORWARDS (CH, tier 0, reputation 0.83; accepted the copy from v53 241 m away, hop 3): 3 neighbour(s) not covered by the senders it heard (v53, v153). Frame decoded by 69 nodes (3 new, 66 already had it), lost at 0. |
| +32.903 ms | **v98** FORWARDS (BRIDGE, tier 0, reputation 0.88; accepted the copy from v3 224 m away, hop 2): 2 neighbour(s) not covered by the senders it heard (v3, v80, v181). Frame decoded by 48 nodes (3 new, 45 already had it), lost at 0. |
| +35.113 ms | **v44** FORWARDS (CH, tier 0, reputation 0.93; accepted the copy from v181 253 m away, hop 3): 19 neighbour(s) not covered by the senders it heard (v98, v181). Frame decoded by 47 nodes (0 new, 47 already had it), lost at 0. |
| +37.869 ms | **v57** FORWARDS (CH, tier 0, reputation 0.92; accepted the copy from v3 171 m away, hop 2): 2 neighbour(s) not covered by the senders it heard (v3, v44, v80, v98). Frame decoded by 74 nodes (0 new, 74 already had it), lost at 0. |
| | ... and 156 more vehicles suppress for the same kind of reason (all listed in the decision table below). |

## Final

```
================================================================
 EMERGENCY DISSEMINATION MONITOR | PROPOSED (FULL)
================================================================
Event        : EVT-30002-v164-1 (ACCIDENT)
Status       : COMPLETE
Source       : Vehicle v164   (run d200_r02, seed 30002)
Location     : (601.38, 608.69) at t = 114 s

Corroboration
-------------
Committee    : v170, v156, v68, v90, v18  (5 nearest reputable neighbours)
Votes        : 5 cast (v170, v156, v68, v90, v18); 3 of 5 needed
Certificate  : BLS aggregate of 4 signatures in 96 bytes: ACCEPTED (BLS aggregate valid, 3 of 3 endorsers counted)

Vehicles
--------
Total        : 200
Accepted     : 200 / 200  (100.0 %, 90 % within 32.7 ms)

Forwarding
----------
Forwarded    : 15
Suppressed   : 164
Misbehaving  : 20 received but never relay

Network
-------
Transmissions: 22  (1 proposal, 5 votes, 16 certified alerts; 3 reached nobody new)
Collisions   : 40 receptions lost  (3.2 % of receptions)

RSU
---
Status       : ALERT RECEIVED, validation passed, registered by RSU-2
Delay        : 25.00 ms after the alert was created (2 hop(s), 12 transmission(s))
Duplicates   : 8 further copies ignored (decoded by RSU-1, RSU-2)
================================================================
```

## The certificate

```json
{
  "signers": [
    "v164",
    "v170",
    "v156",
    "v68"
  ],
  "aggregate": "96a09cc41c2688c96803bbdb1f2a25fd8cf58ebef5dc49be9e95d119f729c006998210bb416e07fa8f816a434f2060640db6d49d0391fba3678a076a6c44dcab5635e042b2c6402bc23a8ec82809537bb0dfffb7efb4cc103bc7631044b8f3f6"
}
```

## Same incident, same vehicles, every scheme

| Scheme | Frames on air | Certified alerts | Redundant | Receptions lost to collisions | Reachability | 90 % reached (ms) | RSU registered at (ms) |
|---|---|---|---|---|---|---|---|
| Blind flooding | 177 | 171 | 153 | 9382 | 94.0 % | 25.7 | 17.84 (RSU-1) |
| Slotted 1-persistence | 42 | 36 | 23 | 1455 | 99.5 % | 27.9 | 22.85 (RSU-1) |
| Proposed (full) | 22 | 16 | 3 | 40 | 100.0 % | 32.7 | 25.00 (RSU-2) |
| without random delay | 48 | 42 | 29 | 1415 | 100.0 % | 32.2 | 22.13 (RSU-2) |
| without distance slots | 45 | 39 | 21 | 761 | 100.0 % | 30.8 | 23.18 (RSU-1) |
| without coverage test | 186 | 180 | 168 | 6048 | 100.0 % | 34.2 | 22.43 (RSU-2) |
| without clustering | 49 | 43 | 30 | 1484 | 100.0 % | 29.6 | 23.07 (RSU-2) |
| without cluster-based forwarding | 41 | 35 | 20 | 976 | 100.0 % | 30.8 | 23.23 (RSU-2) |
| without reputation | 24 | 18 | 6 | 2 | 100.0 % | 35.5 | 22.19 (RSU-2) |
| without voting + BLS | 19 | 19 | 6 | 91 | 100.0 % | 6.9 | 3.09 (RSU-2) |
| CH shortest-path delivery | 14 | 2 | 0 | 0 | 47.5 % | nan | 40.64 (RSU-2) |

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
| v164 | 0.00 | 0 | - | 0 | 56 | MEMBER | 1 | 0.87 | 7 | - | SOURCE | incident vehicle originates the alert |
| v0 | 17.08 | 1 | v164 | 199 | 53 | CH | 0 | 0.90 | 5 | 21 | FORWARD | 21 neighbour(s) not covered by the senders it heard (v164) |
| v1 | 17.08 | 1 | v164 | 276 | 54 | MEMBER | 1 | 0.01 | 5 | - | DROP | misbehaving vehicle: never relays |
| v3 | 17.08 | 1 | v164 | 279 | 73 | CH | 0 | 0.87 | 5 | 33 | FORWARD | 33 neighbour(s) not covered by the senders it heard (v101, v164) |
| v12 | 17.08 | 1 | v164 | 191 | 52 | MEMBER | 1 | 0.91 | 5 | 0 | SUPPRESS | all 52 neighbours already covered by v0, v20, v29, v87, v164 |
| v16 | 17.08 | 1 | v164 | 282 | 75 | MEMBER | 1 | 0.01 | 8 | - | DROP | misbehaving vehicle: never relays |
| v18 | 17.08 | 1 | v164 | 33 | 61 | MEMBER | 1 | 0.86 | 8 | 0 | SUPPRESS | all 61 neighbours already covered by v0, v3, v29, v80, v87, v89, v101, v164 |
| v21 | 17.08 | 1 | v164 | 230 | 65 | MEMBER | 1 | 0.91 | 6 | 0 | SUPPRESS | all 65 neighbours already covered by v0, v20, v29, v87, v153, v164 |
| v23 | 17.08 | 1 | v164 | 277 | 73 | MEMBER | 1 | 0.90 | 8 | 0 | SUPPRESS | all 73 neighbours already covered by v0, v3, v53, v57, v80, v87, v153, v164 |
| v24 | 17.08 | 1 | v164 | 174 | 65 | BRIDGE | 0 | 0.94 | 6 | 0 | SUPPRESS | all 65 neighbours already covered by v0, v3, v80, v101, v164 |
| v26 | 17.08 | 1 | v164 | 206 | 57 | MEMBER | 1 | 0.89 | 6 | 0 | SUPPRESS | all 57 neighbours already covered by v0, v20, v29, v87, v153, v164 |
| v29 | 17.08 | 1 | v164 | 226 | 30 | BRIDGE | 0 | 0.89 | 4 | 1 | FORWARD | 1 neighbour(s) not covered by the senders it heard (v0, v89, v164) |
| v30 | 17.08 | 1 | v164 | 245 | 67 | MEMBER | 1 | 0.88 | 7 | 0 | SUPPRESS | all 67 neighbours already covered by v3, v53, v57, v80, v98, v101, v164 |
| v32 | 17.08 | 1 | v164 | 272 | 72 | MEMBER | 1 | 0.89 | 6 | 0 | SUPPRESS | all 72 neighbours already covered by v3, v57, v80, v98, v101, v164 |
| v37 | 17.08 | 1 | v164 | 221 | 29 | BRIDGE | 0 | 0.88 | 5 | 0 | SUPPRESS | all 29 neighbours already covered by v0, v89, v164 |
| v39 | 17.08 | 1 | v164 | 272 | 71 | MEMBER | 1 | 0.01 | 6 | - | DROP | misbehaving vehicle: never relays |
| v40 | 17.08 | 1 | v164 | 157 | 33 | BRIDGE | 0 | 0.88 | 5 | 0 | SUPPRESS | all 33 neighbours already covered by v0, v29, v87, v89, v164 |
| v43 | 17.08 | 1 | v164 | 222 | 39 | BRIDGE | 0 | 0.91 | 5 | 0 | SUPPRESS | all 39 neighbours already covered by v3, v80, v89, v101, v164 |
| v45 | 17.08 | 1 | v164 | 215 | 65 | MEMBER | 1 | 0.91 | 7 | 0 | SUPPRESS | all 65 neighbours already covered by v3, v53, v57, v80, v98, v101, v164 |
| v46 | 17.08 | 1 | v164 | 291 | 81 | MEMBER | 1 | 0.94 | 7 | 0 | SUPPRESS | all 81 neighbours already covered by v0, v3, v53, v57, v80, v153, v164 |
| v49 | 17.08 | 1 | v164 | 201 | 23 | BRIDGE | 1 | 0.01 | 3 | - | DROP | misbehaving vehicle: never relays |
| v58 | 17.08 | 1 | v164 | 253 | 18 | BRIDGE | 0 | 0.88 | 2 | 0 | SUPPRESS | all 18 neighbours already covered by v164 |
| v64 | 17.08 | 1 | v164 | 262 | 37 | BRIDGE | 0 | 0.81 | 4 | 0 | SUPPRESS | all 37 neighbours already covered by v3, v101, v164 |
| v65 | 17.08 | 1 | v164 | 251 | 72 | MEMBER | 1 | 0.01 | 6 | - | DROP | misbehaving vehicle: never relays |
| v68 | 17.08 | 1 | v164 | 8 | 58 | CH | 0 | 0.90 | 8 | 0 | SUPPRESS | all 58 neighbours already covered by v0, v3, v29, v80, v87, v89, v101, v164 |
| v69 | 17.08 | 1 | v164 | 265 | 56 | MEMBER | 1 | 0.91 | 5 | 0 | SUPPRESS | all 56 neighbours already covered by v0, v20, v29, v87, v164 |
| v74 | 17.08 | 1 | v164 | 201 | 41 | BRIDGE | 0 | 0.86 | 5 | 0 | SUPPRESS | all 41 neighbours already covered by v3, v80, v89, v101, v164 |
| v80 | 17.08 | 1 | v164 | 263 | 59 | CH | 0 | 0.89 | 6 | 19 | FORWARD | 19 neighbour(s) not covered by the senders it heard (v101, v164) |
| v81 | 17.08 | 1 | v164 | 257 | 70 | MEMBER | 1 | 0.01 | 7 | - | DROP | misbehaving vehicle: never relays |
| v84 | 17.08 | 1 | v164 | 206 | 58 | MEMBER | 1 | 0.94 | 6 | 0 | SUPPRESS | all 58 neighbours already covered by v0, v20, v29, v87, v153, v164 |
| v85 | 17.08 | 1 | v164 | 202 | 25 | BRIDGE | 0 | 0.94 | 3 | 0 | SUPPRESS | all 25 neighbours already covered by v89, v101, v164 |
| v86 | 17.08 | 1 | v164 | 42 | 45 | MEMBER | 1 | 0.85 | 5 | 0 | SUPPRESS | all 45 neighbours already covered by v0, v29, v87, v89, v164 |
| v87 | 17.08 | 1 | v164 | 239 | 59 | CH | 0 | 0.82 | 4 | 12 | FORWARD | 12 neighbour(s) not covered by the senders it heard (v0, v164) |
| v89 | 17.08 | 1 | v164 | 204 | 22 | BRIDGE | 0 | 0.84 | 2 | 1 | FORWARD | 1 neighbour(s) not covered by the senders it heard (v164) |
| v90 | 17.08 | 1 | v164 | 16 | 54 | MEMBER | 1 | 0.88 | 8 | 0 | SUPPRESS | all 54 neighbours already covered by v0, v3, v29, v80, v87, v89, v101, v164 |
| v93 | 17.08 | 1 | v164 | 258 | 57 | MEMBER | 1 | 0.94 | 7 | 0 | SUPPRESS | all 57 neighbours already covered by v3, v57, v80, v98, v101, v164, v181 |
| v94 | 17.08 | 1 | v164 | 100 | 56 | BRIDGE | 0 | 0.92 | 6 | 0 | SUPPRESS | all 56 neighbours already covered by v0, v3, v80, v87, v101, v164 |
| v99 | 17.08 | 1 | v164 | 280 | 73 | MEMBER | 1 | 0.92 | 6 | 0 | SUPPRESS | all 73 neighbours already covered by v3, v57, v80, v98, v101, v164 |
| v101 | 17.08 | 1 | v164 | 280 | 36 | BRIDGE | 0 | 0.85 | 3 | 6 | FORWARD | 6 neighbour(s) not covered by the senders it heard (v164) |
| v104 | 17.08 | 1 | v164 | 264 | 69 | MEMBER | 1 | 0.94 | 7 | 0 | SUPPRESS | all 69 neighbours already covered by v3, v53, v57, v80, v98, v101, v164 |
| v110 | 17.08 | 1 | v164 | 287 | 73 | MEMBER | 1 | 0.90 | 6 | 0 | SUPPRESS | all 73 neighbours already covered by v3, v57, v80, v98, v101, v164 |
| v119 | 17.08 | 1 | v164 | 249 | 72 | MEMBER | 1 | 0.90 | 7 | 0 | SUPPRESS | all 72 neighbours already covered by v0, v3, v53, v80, v87, v153, v164 |
| v120 | 17.08 | 1 | v164 | 186 | 32 | BRIDGE | 0 | 0.91 | 5 | 0 | SUPPRESS | all 32 neighbours already covered by v0, v29, v89, v164 |
| v124 | 17.08 | 1 | v164 | 175 | 53 | MEMBER | 1 | 0.90 | 6 | 0 | SUPPRESS | all 53 neighbours already covered by v0, v20, v29, v87, v89, v164 |
| v136 | 17.08 | 1 | v164 | 264 | 69 | MEMBER | 1 | 0.90 | 7 | 0 | SUPPRESS | all 69 neighbours already covered by v3, v53, v57, v80, v98, v101, v164 |
| v142 | 17.08 | 1 | v164 | 59 | 54 | BRIDGE | 0 | 0.91 | 8 | 0 | SUPPRESS | all 54 neighbours already covered by v0, v3, v29, v80, v87, v89, v101, v164 |
| v150 | 17.08 | 1 | v164 | 217 | 60 | MEMBER | 1 | 0.92 | 6 | 0 | SUPPRESS | all 60 neighbours already covered by v0, v20, v29, v87, v153, v164 |
| v152 | 17.08 | 1 | v164 | 221 | 62 | MEMBER | 1 | 0.01 | 6 | - | DROP | misbehaving vehicle: never relays |
| v156 | 17.08 | 1 | v164 | 8 | 58 | MEMBER | 1 | 0.91 | 8 | 0 | SUPPRESS | all 58 neighbours already covered by v0, v3, v29, v80, v87, v89, v101, v164 |
| v158 | 17.08 | 1 | v164 | 261 | 56 | MEMBER | 1 | 0.85 | 7 | 0 | SUPPRESS | all 56 neighbours already covered by v3, v57, v80, v98, v101, v164, v181 |
| v160 | 17.08 | 1 | v164 | 128 | 45 | BRIDGE | 0 | 0.94 | 5 | 0 | SUPPRESS | all 45 neighbours already covered by v0, v29, v87, v89, v164 |
| v170 | 17.08 | 1 | v164 | 3 | 56 | MEMBER | 1 | 0.89 | 8 | 0 | SUPPRESS | all 56 neighbours already covered by v0, v3, v29, v80, v87, v89, v101, v164 |
| v174 | 17.08 | 1 | v164 | 257 | 70 | MEMBER | 1 | 0.91 | 7 | 0 | SUPPRESS | all 70 neighbours already covered by v3, v53, v57, v80, v98, v101, v164 |
| v175 | 17.08 | 1 | v164 | 265 | 76 | MEMBER | 1 | 0.88 | 8 | 0 | SUPPRESS | all 76 neighbours already covered by v0, v3, v53, v57, v80, v87, v153, v164 |
| v177 | 17.08 | 1 | v164 | 226 | 67 | MEMBER | 1 | 0.89 | 7 | 0 | SUPPRESS | all 67 neighbours already covered by v3, v53, v57, v80, v98, v101, v164 |
| v194 | 17.08 | 1 | v164 | 203 | 28 | BRIDGE | 0 | 0.93 | 4 | 0 | SUPPRESS | all 28 neighbours already covered by v80, v101, v164 |
| v197 | 17.08 | 1 | v164 | 35 | 61 | MEMBER | 1 | 0.94 | 8 | 0 | SUPPRESS | all 61 neighbours already covered by v0, v3, v29, v80, v87, v89, v101, v164 |
| v13 | 23.07 | 2 | v101 | 59 | 38 | BRIDGE | 0 | 0.88 | 5 | 0 | SUPPRESS | all 38 neighbours already covered by v3, v80, v98, v101, v181 |
| v66 | 23.07 | 2 | v101 | 277 | 47 | MEMBER | 1 | 0.86 | 7 | 0 | SUPPRESS | all 47 neighbours already covered by v3, v44, v57, v80, v98, v101, v181 |
| v79 | 23.07 | 2 | v101 | 106 | 46 | BRIDGE | 0 | 0.86 | 6 | 0 | SUPPRESS | all 46 neighbours already covered by v3, v57, v80, v98, v101, v181 |
| v122 | 23.07 | 2 | v101 | 184 | 43 | BRIDGE | 0 | 0.90 | 6 | 0 | SUPPRESS | all 43 neighbours already covered by v3, v80, v101, v181 |
| v130 | 23.07 | 2 | v101 | 88 | 39 | BRIDGE | 0 | 0.93 | 5 | 0 | SUPPRESS | all 39 neighbours already covered by v3, v80, v98, v101, v181 |
| v134 | 23.07 | 2 | v101 | 163 | 41 | BRIDGE | 0 | 0.89 | 6 | 0 | SUPPRESS | all 41 neighbours already covered by v3, v80, v98, v101, v181 |
| v10 | 25.00 | 2 | v3 | 193 | 69 | MEMBER | 1 | 0.01 | 5 | - | DROP | misbehaving vehicle: never relays |
| v11 | 25.00 | 2 | v3 | 230 | 83 | CH | 0 | 0.86 | 6 | 0 | SUPPRESS | all 83 neighbours already covered by v0, v3, v53, v80, v153 |
| v14 | 25.00 | 2 | v3 | 273 | 87 | MEMBER | 1 | 0.90 | 5 | 0 | SUPPRESS | all 87 neighbours already covered by v3, v44, v53, v57, v180 |
| v27 | 25.00 | 2 | v3 | 230 | 83 | MEMBER | 1 | 0.93 | 6 | 0 | SUPPRESS | all 83 neighbours already covered by v0, v3, v53, v57, v80, v153 |
| v34 | 25.00 | 2 | v3 | 261 | 92 | MEMBER | 1 | 0.01 | 4 | - | DROP | misbehaving vehicle: never relays |
| v38 | 25.00 | 2 | v3 | 166 | 72 | MEMBER | 1 | 0.87 | 5 | 0 | SUPPRESS | all 72 neighbours already covered by v3, v44, v57, v80, v98 |
| v48 | 25.00 | 2 | v3 | 277 | 86 | MEMBER | 1 | 0.91 | 5 | 0 | SUPPRESS | all 86 neighbours already covered by v3, v44, v53, v57, v180 |
| v53 | 25.00 | 2 | v3 | 259 | 92 | CH | 0 | 0.90 | 3 | 46 | FORWARD | 46 neighbour(s) not covered by the senders it heard (v3) |
| v57 | 25.00 | 2 | v3 | 171 | 74 | CH | 0 | 0.92 | 4 | 2 | FORWARD | 2 neighbour(s) not covered by the senders it heard (v3, v44, v80, v98) |
| v59 | 25.00 | 2 | v3 | 275 | 59 | MEMBER | 1 | 0.91 | 4 | 0 | SUPPRESS | all 59 neighbours already covered by v3, v44, v57, v98 |
| v60 | 25.00 | 2 | v3 | 261 | 88 | MEMBER | 1 | 0.91 | 5 | 0 | SUPPRESS | all 88 neighbours already covered by v3, v44, v53, v57, v180 |
| v63 | 25.00 | 2 | v3 | 264 | 91 | MEMBER | 1 | 0.84 | 5 | 0 | SUPPRESS | all 91 neighbours already covered by v3, v44, v53, v57, v180 |
| v73 | 25.00 | 2 | v3 | 176 | 67 | MEMBER | 1 | 0.88 | 5 | 0 | SUPPRESS | all 67 neighbours already covered by v3, v44, v57, v80, v98 |
| v76 | 25.00 | 2 | v3 | 267 | 43 | MEMBER | 1 | 0.90 | 6 | 0 | SUPPRESS | all 43 neighbours already covered by v3, v44, v57, v80, v98, v181 |
| v77 | 25.00 | 2 | v3 | 184 | 70 | MEMBER | 1 | 0.91 | 5 | 0 | SUPPRESS | all 70 neighbours already covered by v3, v44, v57, v80, v98 |
| v83 | 25.00 | 2 | v3 | 143 | 73 | MEMBER | 1 | 0.89 | 5 | 0 | SUPPRESS | all 73 neighbours already covered by v3, v44, v57, v80, v98 |
| v97 | 25.00 | 2 | v3 | 293 | 78 | MEMBER | 1 | 0.89 | 5 | 0 | SUPPRESS | all 78 neighbours already covered by v3, v44, v53, v57, v180 |
| v98 | 25.00 | 2 | v3 | 224 | 48 | BRIDGE | 0 | 0.88 | 5 | 2 | FORWARD | 2 neighbour(s) not covered by the senders it heard (v3, v80, v181) |
| v102 | 25.00 | 2 | v3 | 281 | 84 | MEMBER | 1 | 0.91 | 5 | 0 | SUPPRESS | all 84 neighbours already covered by v3, v44, v53, v57, v180 |
| v114 | 25.00 | 2 | v3 | 178 | 69 | MEMBER | 1 | 0.88 | 6 | 0 | SUPPRESS | all 69 neighbours already covered by v3, v44, v53, v57, v80, v98 |
| v126 | 25.00 | 2 | v3 | 151 | 72 | MEMBER | 1 | 0.90 | 5 | 0 | SUPPRESS | all 72 neighbours already covered by v3, v44, v57, v80, v98 |
| v128 | 25.00 | 2 | v3 | 252 | 45 | MEMBER | 1 | 0.89 | 6 | 0 | SUPPRESS | all 45 neighbours already covered by v3, v44, v57, v80, v98, v181 |
| v140 | 25.00 | 2 | v3 | 227 | 84 | MEMBER | 1 | 0.82 | 6 | 0 | SUPPRESS | all 84 neighbours already covered by v0, v3, v53, v57, v80, v153 |
| v147 | 25.00 | 2 | v3 | 296 | 78 | MEMBER | 1 | 0.90 | 5 | 0 | SUPPRESS | all 78 neighbours already covered by v3, v44, v53, v57, v180 |
| v148 | 25.00 | 2 | v3 | 262 | 91 | MEMBER | 1 | 0.01 | 5 | - | DROP | misbehaving vehicle: never relays |
| v151 | 25.00 | 2 | v3 | 262 | 87 | MEMBER | 1 | 0.91 | 5 | 0 | SUPPRESS | all 87 neighbours already covered by v3, v44, v53, v57, v180 |
| v155 | 25.00 | 2 | v3 | 273 | 91 | MEMBER | 1 | 0.86 | 5 | 0 | SUPPRESS | all 91 neighbours already covered by v3, v44, v53, v57, v180 |
| v157 | 25.00 | 2 | v3 | 296 | 53 | MEMBER | 1 | 0.93 | 4 | 0 | SUPPRESS | all 53 neighbours already covered by v3, v44, v57, v98 |
| v163 | 25.00 | 2 | v3 | 143 | 73 | CH | 0 | 0.92 | 5 | 0 | SUPPRESS | all 73 neighbours already covered by v3, v44, v57, v80, v98 |
| v181 | 25.00 | 2 | v3 | 292 | 38 | CH | 0 | 0.91 | 5 | 8 | FORWARD | 8 neighbour(s) not covered by the senders it heard (v3, v80) |
| v183 | 25.00 | 2 | v3 | 280 | 90 | MEMBER | 1 | 0.89 | 5 | 0 | SUPPRESS | all 90 neighbours already covered by v3, v44, v53, v57, v180 |
| v195 | 25.00 | 2 | v3 | 151 | 72 | MEMBER | 1 | 0.01 | 5 | - | DROP | misbehaving vehicle: never relays |
| v167 | 25.74 | 2 | v80 | 293 | 35 | MEMBER | 1 | 0.83 | 5 | 0 | SUPPRESS | all 35 neighbours already covered by v44, v57, v80, v98, v181 |
| v20 | 27.13 | 2 | v0 | 252 | 62 | CH | 0 | 0.91 | 3 | 22 | FORWARD | 22 neighbour(s) not covered by the senders it heard (v0, v87) |
| v31 | 27.13 | 2 | v0 | 260 | 65 | MEMBER | 1 | 0.94 | 4 | 0 | SUPPRESS | all 65 neighbours already covered by v0, v20, v87, v153 |
| v36 | 27.13 | 2 | v0 | 289 | 47 | MEMBER | 1 | 0.90 | 3 | 0 | SUPPRESS | all 47 neighbours already covered by v0, v20, v87 |
| v41 | 27.13 | 2 | v0 | 276 | 49 | MEMBER | 1 | 0.92 | 4 | 0 | SUPPRESS | all 49 neighbours already covered by v0, v20, v87, v153 |
| v50 | 27.13 | 2 | v0 | 222 | 43 | BRIDGE | 0 | 0.91 | 4 | 0 | SUPPRESS | all 43 neighbours already covered by v0, v20, v29, v87 |
| v61 | 27.13 | 2 | v0 | 178 | 64 | BRIDGE | 0 | 0.90 | 4 | 0 | SUPPRESS | all 64 neighbours already covered by v0, v20, v87, v153 |
| v96 | 27.13 | 2 | v0 | 211 | 43 | BRIDGE | 1 | 0.01 | 5 | - | DROP | misbehaving vehicle: never relays |
| v105 | 27.13 | 2 | v0 | 280 | 48 | MEMBER | 1 | 0.88 | 4 | 0 | SUPPRESS | all 48 neighbours already covered by v0, v20, v87, v153 |
| v117 | 27.13 | 2 | v0 | 269 | 49 | MEMBER | 1 | 0.01 | 4 | - | DROP | misbehaving vehicle: never relays |
| v118 | 27.13 | 2 | v0 | 247 | 46 | BRIDGE | 0 | 0.87 | 4 | 0 | SUPPRESS | all 46 neighbours already covered by v0, v20, v29, v87 |
| v133 | 27.13 | 2 | v0 | 198 | 65 | BRIDGE | 0 | 0.91 | 4 | 0 | SUPPRESS | all 65 neighbours already covered by v0, v20, v87, v153 |
| v153 | 27.13 | 2 | v0 | 297 | 74 | BRIDGE | 0 | 0.95 | 3 | 27 | FORWARD | 27 neighbour(s) not covered by the senders it heard (v0, v20) |
| v176 | 27.13 | 2 | v0 | 246 | 64 | MEMBER | 1 | 0.94 | 4 | 0 | SUPPRESS | all 64 neighbours already covered by v0, v20, v87, v153 |
| v179 | 27.13 | 2 | v0 | 264 | 49 | MEMBER | 1 | 0.90 | 4 | 0 | SUPPRESS | all 49 neighbours already covered by v0, v20, v87, v153 |
| v182 | 27.13 | 2 | v0 | 243 | 64 | MEMBER | 1 | 0.88 | 4 | 0 | SUPPRESS | all 64 neighbours already covered by v0, v20, v87, v153 |
| v189 | 27.13 | 2 | v0 | 250 | 64 | MEMBER | 1 | 0.92 | 4 | 0 | SUPPRESS | all 64 neighbours already covered by v0, v20, v87, v153 |
| v192 | 27.13 | 2 | v0 | 249 | 64 | MEMBER | 1 | 0.91 | 4 | 0 | SUPPRESS | all 64 neighbours already covered by v0, v20, v87, v153 |
| v193 | 29.81 | 2 | v29 | 296 | 43 | CH | 0 | 0.86 | 3 | 0 | SUPPRESS | all 43 neighbours already covered by v20, v29, v87 |
| v6 | 30.54 | 2 | v87 | 282 | 57 | MEMBER | 1 | 0.01 | 3 | - | DROP | misbehaving vehicle: never relays |
| v28 | 30.54 | 2 | v87 | 246 | 45 | MEMBER | 1 | 0.88 | 2 | 0 | SUPPRESS | all 45 neighbours already covered by v20, v87 |
| v56 | 30.54 | 2 | v87 | 257 | 42 | MEMBER | 1 | 0.01 | 2 | - | DROP | misbehaving vehicle: never relays |
| v103 | 30.54 | 2 | v87 | 254 | 42 | MEMBER | 1 | 0.88 | 2 | 0 | SUPPRESS | all 42 neighbours already covered by v20, v87 |
| v109 | 30.54 | 2 | v87 | 296 | 39 | MEMBER | 1 | 0.91 | 2 | 0 | SUPPRESS | all 39 neighbours already covered by v20, v87 |
| v115 | 30.54 | 2 | v87 | 260 | 38 | MEMBER | 1 | 0.89 | 2 | 0 | SUPPRESS | all 38 neighbours already covered by v20, v87 |
| v125 | 30.54 | 2 | v87 | 265 | 38 | MEMBER | 1 | 0.91 | 2 | 0 | SUPPRESS | all 38 neighbours already covered by v20, v87 |
| v127 | 30.54 | 2 | v87 | 265 | 39 | MEMBER | 1 | 0.95 | 2 | 0 | SUPPRESS | all 39 neighbours already covered by v20, v87 |
| v172 | 30.54 | 2 | v87 | 260 | 39 | MEMBER | 1 | 0.92 | 2 | 0 | SUPPRESS | all 39 neighbours already covered by v20, v87 |
| v173 | 30.54 | 2 | v87 | 274 | 39 | MEMBER | 1 | 0.90 | 2 | 0 | SUPPRESS | all 39 neighbours already covered by v20, v87 |
| v178 | 30.54 | 2 | v87 | 288 | 39 | MEMBER | 1 | 0.92 | 2 | 0 | SUPPRESS | all 39 neighbours already covered by v20, v87 |
| v25 | 31.14 | 3 | v181 | 135 | 25 | MEMBER | 1 | 0.89 | 3 | 0 | SUPPRESS | all 25 neighbours already covered by v44, v98, v181 |
| v44 | 31.14 | 3 | v181 | 253 | 47 | CH | 0 | 0.93 | 3 | 19 | FORWARD | 19 neighbour(s) not covered by the senders it heard (v98, v181) |
| v67 | 31.14 | 3 | v181 | 140 | 26 | CH | 0 | 0.91 | 3 | 0 | SUPPRESS | all 26 neighbours already covered by v44, v98, v181 |
| v82 | 31.14 | 3 | v181 | 118 | 26 | MEMBER | 1 | 0.85 | 3 | 0 | SUPPRESS | all 26 neighbours already covered by v44, v98, v181 |
| v111 | 31.14 | 3 | v181 | 190 | 28 | BRIDGE | 0 | 0.89 | 4 | 0 | SUPPRESS | all 28 neighbours already covered by v44, v57, v98, v181 |
| v4 | 31.77 | 3 | v53 | 299 | 55 | MEMBER | 1 | 0.89 | 3 | 0 | SUPPRESS | all 55 neighbours already covered by v53, v153, v180 |
| v5 | 31.77 | 3 | v53 | 120 | 71 | MEMBER | 1 | 0.95 | 4 | 0 | SUPPRESS | all 71 neighbours already covered by v44, v53, v57, v180 |
| v8 | 31.77 | 3 | v53 | 229 | 72 | MEMBER | 1 | 0.86 | 3 | 0 | SUPPRESS | all 72 neighbours already covered by v53, v153, v180 |
| v9 | 31.77 | 3 | v53 | 194 | 74 | MEMBER | 1 | 0.89 | 3 | 0 | SUPPRESS | all 74 neighbours already covered by v53, v153, v180 |
| v15 | 31.77 | 3 | v53 | 228 | 69 | MEMBER | 1 | 0.92 | 3 | 0 | SUPPRESS | all 69 neighbours already covered by v53, v153, v180 |
| v42 | 31.77 | 3 | v53 | 168 | 66 | CH | 0 | 0.91 | 4 | 0 | SUPPRESS | all 66 neighbours already covered by v44, v53, v57, v180 |
| v47 | 31.77 | 3 | v53 | 70 | 81 | BRIDGE | 0 | 0.90 | 3 | 0 | SUPPRESS | all 81 neighbours already covered by v53, v57, v180 |
| v51 | 31.77 | 3 | v53 | 227 | 74 | MEMBER | 1 | 0.92 | 3 | 0 | SUPPRESS | all 74 neighbours already covered by v53, v153, v180 |
| v52 | 31.77 | 3 | v53 | 263 | 81 | MEMBER | 1 | 0.89 | 4 | 0 | SUPPRESS | all 81 neighbours already covered by v20, v53, v153, v180 |
| v54 | 31.77 | 3 | v53 | 224 | 74 | BRIDGE | 0 | 0.93 | 3 | 0 | SUPPRESS | all 74 neighbours already covered by v53, v153, v180 |
| v70 | 31.77 | 3 | v53 | 146 | 72 | BRIDGE | 0 | 0.89 | 4 | 0 | SUPPRESS | all 72 neighbours already covered by v53, v57, v153, v180 |
| v71 | 31.77 | 3 | v53 | 222 | 71 | MEMBER | 1 | 0.91 | 3 | 0 | SUPPRESS | all 71 neighbours already covered by v53, v153, v180 |
| v72 | 31.77 | 3 | v53 | 277 | 77 | CH | 0 | 0.89 | 4 | 0 | SUPPRESS | all 77 neighbours already covered by v20, v53, v153, v180 |
| v75 | 31.77 | 3 | v53 | 298 | 70 | MEMBER | 1 | 0.90 | 4 | 0 | SUPPRESS | all 70 neighbours already covered by v20, v53, v153, v180 |
| v78 | 31.77 | 3 | v53 | 191 | 66 | MEMBER | 1 | 0.86 | 4 | 0 | SUPPRESS | all 66 neighbours already covered by v44, v53, v57, v180 |
| v88 | 31.77 | 3 | v53 | 186 | 66 | MEMBER | 1 | 0.89 | 4 | 0 | SUPPRESS | all 66 neighbours already covered by v44, v53, v57, v180 |
| v91 | 31.77 | 3 | v53 | 269 | 65 | BRIDGE | 0 | 0.93 | 2 | 0 | SUPPRESS | all 65 neighbours already covered by v53, v180 |
| v95 | 31.77 | 3 | v53 | 298 | 68 | MEMBER | 1 | 0.88 | 4 | 0 | SUPPRESS | all 68 neighbours already covered by v20, v53, v153, v180 |
| v106 | 31.77 | 3 | v53 | 194 | 61 | MEMBER | 1 | 0.89 | 4 | 0 | SUPPRESS | all 61 neighbours already covered by v44, v53, v57, v180 |
| v107 | 31.77 | 3 | v53 | 231 | 68 | MEMBER | 1 | 0.01 | 3 | - | DROP | misbehaving vehicle: never relays |
| v108 | 31.77 | 3 | v53 | 249 | 69 | MEMBER | 1 | 0.89 | 3 | 0 | SUPPRESS | all 69 neighbours already covered by v53, v153, v180 |
| v113 | 31.77 | 3 | v53 | 200 | 60 | MEMBER | 1 | 0.96 | 4 | 0 | SUPPRESS | all 60 neighbours already covered by v44, v53, v57, v180 |
| v121 | 31.77 | 3 | v53 | 216 | 71 | MEMBER | 1 | 0.90 | 3 | 0 | SUPPRESS | all 71 neighbours already covered by v53, v153, v180 |
| v135 | 31.77 | 3 | v53 | 237 | 45 | BRIDGE | 0 | 0.86 | 4 | 0 | SUPPRESS | all 45 neighbours already covered by v44, v53, v57, v98 |
| v138 | 31.77 | 3 | v53 | 296 | 70 | MEMBER | 1 | 0.91 | 4 | 0 | SUPPRESS | all 70 neighbours already covered by v20, v53, v153, v180 |
| v139 | 31.77 | 3 | v53 | 101 | 73 | MEMBER | 1 | 0.93 | 4 | 0 | SUPPRESS | all 73 neighbours already covered by v44, v53, v57, v180 |
| v141 | 31.77 | 3 | v53 | 288 | 55 | MEMBER | 1 | 0.86 | 2 | 0 | SUPPRESS | all 55 neighbours already covered by v53, v180 |
| v144 | 31.77 | 3 | v53 | 266 | 47 | MEMBER | 1 | 0.86 | 4 | 0 | SUPPRESS | all 47 neighbours already covered by v44, v53, v57, v98 |
| v145 | 31.77 | 3 | v53 | 268 | 68 | MEMBER | 1 | 0.88 | 3 | 0 | SUPPRESS | all 68 neighbours already covered by v53, v153, v180 |
| v146 | 31.77 | 3 | v53 | 267 | 56 | MEMBER | 1 | 0.90 | 2 | 0 | SUPPRESS | all 56 neighbours already covered by v53, v180 |
| v149 | 31.77 | 3 | v53 | 280 | 73 | MEMBER | 1 | 0.01 | 4 | - | DROP | misbehaving vehicle: never relays |
| v154 | 31.77 | 3 | v53 | 223 | 75 | MEMBER | 1 | 0.91 | 3 | 0 | SUPPRESS | all 75 neighbours already covered by v53, v153, v180 |
| v161 | 31.77 | 3 | v53 | 269 | 56 | MEMBER | 1 | 0.89 | 2 | 0 | SUPPRESS | all 56 neighbours already covered by v53, v180 |
| v162 | 31.77 | 3 | v53 | 209 | 72 | MEMBER | 1 | 0.93 | 3 | 0 | SUPPRESS | all 72 neighbours already covered by v53, v153, v180 |
| v165 | 31.77 | 3 | v53 | 261 | 69 | MEMBER | 1 | 0.91 | 3 | 0 | SUPPRESS | all 69 neighbours already covered by v53, v153, v180 |
| v166 | 31.77 | 3 | v53 | 195 | 65 | MEMBER | 1 | 0.91 | 4 | 0 | SUPPRESS | all 65 neighbours already covered by v44, v53, v57, v180 |
| v171 | 31.77 | 3 | v53 | 228 | 72 | MEMBER | 1 | 0.85 | 3 | 0 | SUPPRESS | all 72 neighbours already covered by v53, v153, v180 |
| v180 | 31.77 | 3 | v53 | 241 | 69 | CH | 0 | 0.83 | 2 | 3 | FORWARD | 3 neighbour(s) not covered by the senders it heard (v53, v153) |
| v184 | 31.77 | 3 | v53 | 226 | 72 | MEMBER | 1 | 0.83 | 3 | 0 | SUPPRESS | all 72 neighbours already covered by v53, v153, v180 |
| v186 | 31.77 | 3 | v53 | 202 | 73 | MEMBER | 1 | 0.85 | 3 | 0 | SUPPRESS | all 73 neighbours already covered by v53, v153, v180 |
| v190 | 31.77 | 3 | v53 | 193 | 73 | MEMBER | 1 | 0.88 | 3 | 0 | SUPPRESS | all 73 neighbours already covered by v53, v153, v180 |
| v198 | 31.77 | 3 | v53 | 272 | 74 | MEMBER | 1 | 0.91 | 4 | 0 | SUPPRESS | all 74 neighbours already covered by v20, v53, v153, v180 |
| v199 | 31.77 | 3 | v53 | 232 | 70 | MEMBER | 1 | 0.89 | 3 | 0 | SUPPRESS | all 70 neighbours already covered by v53, v153, v180 |
| v2 | 32.72 | 3 | v20 | 297 | 53 | MEMBER | 1 | 0.87 | 3 | 0 | SUPPRESS | all 53 neighbours already covered by v20, v153, v180 |
| v7 | 32.72 | 3 | v20 | 162 | 48 | MEMBER | 1 | 0.91 | 2 | 0 | SUPPRESS | all 48 neighbours already covered by v20, v153 |
| v17 | 32.72 | 3 | v20 | 262 | 55 | MEMBER | 1 | 0.91 | 3 | 0 | SUPPRESS | all 55 neighbours already covered by v20, v153, v180 |
| v19 | 32.72 | 3 | v20 | 250 | 33 | BRIDGE | 0 | 0.94 | 1 | 0 | SUPPRESS | all 33 neighbours already covered by v20 |
| v33 | 32.72 | 3 | v20 | 166 | 45 | CH | 0 | 0.89 | 2 | 0 | SUPPRESS | all 45 neighbours already covered by v20, v153 |
| v62 | 32.72 | 3 | v20 | 285 | 53 | CH | 0 | 0.91 | 3 | 0 | SUPPRESS | all 53 neighbours already covered by v20, v153, v180 |
| v123 | 32.72 | 3 | v20 | 76 | 50 | MEMBER | 1 | 0.90 | 2 | 0 | SUPPRESS | all 50 neighbours already covered by v20, v153 |
| v129 | 32.72 | 3 | v20 | 193 | 39 | MEMBER | 1 | 0.01 | 1 | - | DROP | misbehaving vehicle: never relays |
| v132 | 32.72 | 3 | v20 | 224 | 47 | BRIDGE | 1 | 0.01 | 3 | - | DROP | misbehaving vehicle: never relays |
| v143 | 32.72 | 3 | v20 | 78 | 50 | CH | 0 | 0.92 | 2 | 0 | SUPPRESS | all 50 neighbours already covered by v20, v153 |
| v168 | 32.72 | 3 | v20 | 190 | 36 | BRIDGE | 0 | 0.89 | 1 | 0 | SUPPRESS | all 36 neighbours already covered by v20 |
| v169 | 32.72 | 3 | v20 | 269 | 53 | MEMBER | 1 | 0.95 | 3 | 0 | SUPPRESS | all 53 neighbours already covered by v20, v153, v180 |
| v188 | 32.72 | 3 | v20 | 170 | 40 | MEMBER | 1 | 0.87 | 2 | 0 | SUPPRESS | all 40 neighbours already covered by v20, v153 |
| v191 | 32.72 | 3 | v20 | 245 | 34 | BRIDGE | 1 | 0.01 | 1 | - | DROP | misbehaving vehicle: never relays |
| v196 | 32.72 | 3 | v20 | 294 | 53 | MEMBER | 1 | 0.83 | 3 | 0 | SUPPRESS | all 53 neighbours already covered by v20, v153, v180 |
| v22 | 34.84 | 3 | v153 | 295 | 47 | MEMBER | 1 | 0.86 | 2 | 0 | SUPPRESS | all 47 neighbours already covered by v153, v180 |
| v100 | 34.84 | 3 | v153 | 269 | 47 | MEMBER | 1 | 0.92 | 2 | 0 | SUPPRESS | all 47 neighbours already covered by v153, v180 |
| v112 | 34.84 | 3 | v153 | 297 | 47 | MEMBER | 1 | 0.89 | 2 | 0 | SUPPRESS | all 47 neighbours already covered by v153, v180 |
| v131 | 34.84 | 3 | v153 | 290 | 47 | MEMBER | 1 | 0.91 | 2 | 0 | SUPPRESS | all 47 neighbours already covered by v153, v180 |
| v137 | 34.84 | 3 | v153 | 285 | 48 | CH | 0 | 0.93 | 2 | 0 | SUPPRESS | all 48 neighbours already covered by v153, v180 |
| v187 | 34.84 | 3 | v153 | 269 | 48 | MEMBER | 1 | 0.88 | 2 | 0 | SUPPRESS | all 48 neighbours already covered by v153, v180 |
| v92 | 37.83 | 4 | v180 | 175 | 42 | CH | 0 | 0.84 | 1 | 0 | SUPPRESS | all 42 neighbours already covered by v180 |
| v159 | 37.83 | 4 | v180 | 170 | 49 | MEMBER | 1 | 0.87 | 1 | 0 | SUPPRESS | all 49 neighbours already covered by v180 |
| v185 | 37.83 | 4 | v180 | 163 | 53 | MEMBER | 1 | 0.85 | 1 | 0 | SUPPRESS | all 53 neighbours already covered by v180 |
| v35 | 37.86 | 3 | v98 | 216 | 49 | MEMBER | 1 | 0.83 | 3 | 0 | SUPPRESS | all 49 neighbours already covered by v44, v57, v98 |
| v55 | 37.86 | 3 | v98 | 224 | 49 | MEMBER | 1 | 0.92 | 3 | 0 | SUPPRESS | all 49 neighbours already covered by v44, v57, v98 |
| v116 | 37.86 | 3 | v98 | 206 | 49 | MEMBER | 1 | 0.87 | 3 | 0 | SUPPRESS | all 49 neighbours already covered by v44, v57, v98 |
