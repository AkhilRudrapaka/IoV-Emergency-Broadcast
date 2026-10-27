# One-run explainer: d200_r02 (FORGED ALERT | Voting + BLS + reputation (full))

Seed 30002 | 200 vehicles | 20 misbehaving (never relay) | RSUs: RSU-1 at (152, 605), RSU-2 at (630, 169)

## The emergency packet

```json
{
  "event_id": "EVT-30002-v34-1",
  "message_type": "ACCIDENT",
  "source_vehicle": "v34",
  "sequence_number": 1,
  "incident_position": [
    401.8,
    216.83
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
| 114.000 s | **v34** claims an accident at (401.8, 216.83). **No accident happened**: this is the forged-alert test. |
| +0.000 ms | Alert **EVT-30002-v34-1** is created (type ACCIDENT, hop limit 10). From earlier beacons every vehicle knows its neighbours and their reputation; DBSCAN gave 22 clusters with 22 representatives, 39 isolated vehicles (bridges) and 139 members. Committee: v53, v63, v155, v60, v183. |
| +0.065 ms | **v34** (the forger: no accident happened) broadcasts the PROPOSAL: the alert with its own BLS signature. Decoded by 92 nodes. The signature proves who sent it, not that the event is real. |
| +6.448 ms | **v148** VOTES yes (reputation 0.01): it colludes and signs the false claim. One BLS signature, one vote. |
| +6.981 ms | **v16** VOTES yes (reputation 0.01): it colludes and signs the false claim. One BLS signature, one vote. |
| +7.488 ms | **v107** VOTES yes (reputation 0.01): it colludes and signs the false claim. One BLS signature, one vote. |
| +7.995 ms | **v195** VOTES yes (reputation 0.01): it colludes and signs the false claim. One BLS signature, one vote. |
| +8.463 ms | **v65** VOTES yes (reputation 0.01): it colludes and signs the false claim. One BLS signature, one vote. |
| +12.155 ms | **v34** has 3 votes, a majority of the committee of 5. It aggregates 4 signatures into one BLS signature and broadcasts the CERTIFIED ALERT. Decoded by 92 nodes (0 accept it). |
| +17.108 ms | **91 vehicles** verify the certificate and REJECT the alert: only 0 reputable endorser(s), 3 needed. Nobody forwards it. |
| +17.108 ms | **RSU-2** decodes the alert from v34 (hop 1): plausibility validation FAILS (not corroborated). The event is not recorded. |

## Final

```
================================================================
 EMERGENCY DISSEMINATION MONITOR | FORGED ALERT | VOTING + BLS + REPUTATION (FULL)
================================================================
Event        : EVT-30002-v34-1 (ACCIDENT)
Status       : COMPLETE
Source       : Vehicle v34   (run d200_r02, seed 30002)
Location     : (401.8, 216.83) at t = 114 s

Corroboration
-------------
Committee    : v53, v63, v155, v60, v183  (5 nearest reputable neighbours)
Votes        : 5 cast (v148, v16, v107, v195, v65, colluders outside the committee); 3 of 5 needed
Certificate  : BLS aggregate of 4 signatures in 96 bytes: REJECTED (only 0 reputable endorser(s), 3 needed)

Vehicles
--------
Total        : 180
Accepted     : 0 / 180 honest vehicles; 91 received it and rejected it

Forwarding
----------
Forwarded    : 0
Suppressed   : 0
Misbehaving  : 0 received but never relay

Network
-------
Transmissions: 7  (1 proposal, 5 votes, 1 certified alerts; 1 reached nobody new)
Collisions   : 0 receptions lost  (0.0 % of receptions)

RSU
---
Status       : ALERT REJECTED by plausibility validation: not corroborated
Delay        : -
Duplicates   : -
================================================================
```

## The certificate

```json
{
  "signers": [
    "v34",
    "v148",
    "v16",
    "v107"
  ],
  "aggregate": "a5171bd4e56d443de0bab35c744760c696dec7d3bd92846b4e743a6e2cd640af505de433de81f536e314216470bc799012b3a7447ae563cd7ad2a04af45a174eb99020578827876ccaa6da81cc5df8ac5d90bdbe80f747f49119dbd97b468476"
}
```


## Every vehicle's message state and decision (FORGED ALERT | Voting + BLS + reputation (full))

| Vehicle | Accepted (ms) | Hop | From | Distance (m) | Neighbours | Role | Tier | Reputation | Copies heard | Uncovered | Decision | Reason |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v34 | 0.00 | 0 | - | 0 | 92 | MEMBER | 1 | 0.01 | 0 | - | SOURCE | incident vehicle originates the alert |
| v3 | - | -1 | - | 0 | 73 | CH | 0 | 0.87 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v4 | - | -1 | - | 0 | 55 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v5 | - | -1 | - | 0 | 71 | MEMBER | 1 | 0.95 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v8 | - | -1 | - | 0 | 72 | MEMBER | 1 | 0.86 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v9 | - | -1 | - | 0 | 74 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v10 | - | -1 | - | 0 | 69 | MEMBER | 1 | 0.01 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v11 | - | -1 | - | 0 | 83 | CH | 0 | 0.86 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v14 | - | -1 | - | 0 | 87 | MEMBER | 1 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v15 | - | -1 | - | 0 | 69 | MEMBER | 1 | 0.92 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v16 | - | -1 | - | 0 | 75 | MEMBER | 1 | 0.01 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v23 | - | -1 | - | 0 | 73 | MEMBER | 1 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v27 | - | -1 | - | 0 | 83 | MEMBER | 1 | 0.93 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v30 | - | -1 | - | 0 | 67 | MEMBER | 1 | 0.88 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v32 | - | -1 | - | 0 | 72 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v35 | - | -1 | - | 0 | 49 | MEMBER | 1 | 0.83 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v38 | - | -1 | - | 0 | 72 | MEMBER | 1 | 0.87 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v39 | - | -1 | - | 0 | 71 | MEMBER | 1 | 0.01 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v42 | - | -1 | - | 0 | 66 | CH | 0 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v45 | - | -1 | - | 0 | 65 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v46 | - | -1 | - | 0 | 81 | MEMBER | 1 | 0.94 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v47 | - | -1 | - | 0 | 81 | BRIDGE | 0 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v48 | - | -1 | - | 0 | 86 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v51 | - | -1 | - | 0 | 74 | MEMBER | 1 | 0.92 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v52 | - | -1 | - | 0 | 81 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v53 | - | -1 | - | 0 | 92 | CH | 0 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v54 | - | -1 | - | 0 | 74 | BRIDGE | 0 | 0.93 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v55 | - | -1 | - | 0 | 49 | MEMBER | 1 | 0.92 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v57 | - | -1 | - | 0 | 74 | CH | 0 | 0.92 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v59 | - | -1 | - | 0 | 59 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v60 | - | -1 | - | 0 | 88 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v63 | - | -1 | - | 0 | 91 | MEMBER | 1 | 0.84 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v65 | - | -1 | - | 0 | 72 | MEMBER | 1 | 0.01 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v70 | - | -1 | - | 0 | 72 | BRIDGE | 0 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v71 | - | -1 | - | 0 | 71 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v72 | - | -1 | - | 0 | 77 | CH | 0 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v73 | - | -1 | - | 0 | 67 | MEMBER | 1 | 0.88 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v75 | - | -1 | - | 0 | 70 | MEMBER | 1 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v77 | - | -1 | - | 0 | 70 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v78 | - | -1 | - | 0 | 66 | MEMBER | 1 | 0.86 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v81 | - | -1 | - | 0 | 70 | MEMBER | 1 | 0.01 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v83 | - | -1 | - | 0 | 73 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v88 | - | -1 | - | 0 | 66 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v91 | - | -1 | - | 0 | 65 | BRIDGE | 0 | 0.93 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v95 | - | -1 | - | 0 | 68 | MEMBER | 1 | 0.88 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v97 | - | -1 | - | 0 | 78 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v99 | - | -1 | - | 0 | 73 | MEMBER | 1 | 0.92 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v102 | - | -1 | - | 0 | 84 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v104 | - | -1 | - | 0 | 69 | MEMBER | 1 | 0.94 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v106 | - | -1 | - | 0 | 61 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v107 | - | -1 | - | 0 | 68 | MEMBER | 1 | 0.01 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v108 | - | -1 | - | 0 | 69 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v110 | - | -1 | - | 0 | 73 | MEMBER | 1 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v113 | - | -1 | - | 0 | 60 | MEMBER | 1 | 0.96 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v114 | - | -1 | - | 0 | 69 | MEMBER | 1 | 0.88 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v116 | - | -1 | - | 0 | 49 | MEMBER | 1 | 0.87 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v119 | - | -1 | - | 0 | 72 | MEMBER | 1 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v121 | - | -1 | - | 0 | 71 | MEMBER | 1 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v126 | - | -1 | - | 0 | 72 | MEMBER | 1 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v135 | - | -1 | - | 0 | 45 | BRIDGE | 0 | 0.86 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v136 | - | -1 | - | 0 | 69 | MEMBER | 1 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v138 | - | -1 | - | 0 | 70 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v139 | - | -1 | - | 0 | 73 | MEMBER | 1 | 0.93 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v140 | - | -1 | - | 0 | 84 | MEMBER | 1 | 0.82 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v141 | - | -1 | - | 0 | 55 | MEMBER | 1 | 0.86 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v144 | - | -1 | - | 0 | 47 | MEMBER | 1 | 0.86 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v145 | - | -1 | - | 0 | 68 | MEMBER | 1 | 0.88 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v146 | - | -1 | - | 0 | 56 | MEMBER | 1 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v147 | - | -1 | - | 0 | 78 | MEMBER | 1 | 0.90 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v148 | - | -1 | - | 0 | 91 | MEMBER | 1 | 0.01 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v149 | - | -1 | - | 0 | 73 | MEMBER | 1 | 0.01 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v151 | - | -1 | - | 0 | 87 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v154 | - | -1 | - | 0 | 75 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v155 | - | -1 | - | 0 | 91 | MEMBER | 1 | 0.86 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v157 | - | -1 | - | 0 | 53 | MEMBER | 1 | 0.93 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v161 | - | -1 | - | 0 | 56 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v162 | - | -1 | - | 0 | 72 | MEMBER | 1 | 0.93 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v163 | - | -1 | - | 0 | 73 | CH | 0 | 0.92 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v165 | - | -1 | - | 0 | 69 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v166 | - | -1 | - | 0 | 65 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v171 | - | -1 | - | 0 | 72 | MEMBER | 1 | 0.85 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v174 | - | -1 | - | 0 | 70 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v175 | - | -1 | - | 0 | 76 | MEMBER | 1 | 0.88 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v177 | - | -1 | - | 0 | 67 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v180 | - | -1 | - | 0 | 69 | CH | 0 | 0.83 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v183 | - | -1 | - | 0 | 90 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v184 | - | -1 | - | 0 | 72 | MEMBER | 1 | 0.83 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v186 | - | -1 | - | 0 | 73 | MEMBER | 1 | 0.85 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v190 | - | -1 | - | 0 | 73 | MEMBER | 1 | 0.88 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v195 | - | -1 | - | 0 | 72 | MEMBER | 1 | 0.01 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v198 | - | -1 | - | 0 | 74 | MEMBER | 1 | 0.91 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
| v199 | - | -1 | - | 0 | 70 | MEMBER | 1 | 0.89 | 1 | - | REJECT | only 0 reputable endorser(s), 3 needed |
