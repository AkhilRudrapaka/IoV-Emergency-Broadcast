"""
Every experimental parameter lives here, with its source. Nothing numeric that
changes an outcome is defined anywhere else. Full justification table:
PROJECT_GUIDE.md section 13.
"""

TITLE = "Trust-Aware Cluster-Based Broadcast Suppression for Real-Time Vehicular Emergency Alerts"

# ---------------------------------------------------------------- scenario
NET_FILE = "network/urban.net.xml"   # curved streets, landscaped blocks and a central boulevard
DENSITIES = [50, 100, 200, 250, 300, 500]  # includes all requested populations
RUNS_PER_DENSITY = 30                 # independent seeds per density; 30 keeps every 95 % CI narrow vs. the effects (RESULTS.md)
BASE_SEED = 10_000                    # seed(d, r) = BASE_SEED + 100*d + r  -> unique, reproducible
DEPART_WINDOW_S = 30                  # all vehicles inserted uniformly at random within the first 30 s
ROUTE_EDGES = 30                      # ~5.4 km random walk: no vehicle finishes its trip before the incident window ends
INCIDENT_WINDOW_S = (60, 120)         # incident time ~ U{60..120}: >=30 s after last insertion (traffic mixed, >=30 trust observations)

# ---------------------------------------------------------- infrastructure
# Two road-side units at intersections B3 and D1. Intersections are the preferred
# RSU sites (Trullols et al. 2010): line of sight along four road arms and the densest traffic.
# Two units on opposite quadrants cover much of the road network in one radio hop; the far corners
# are deliberately NOT covered, so those alerts must be relayed vehicle-to-vehicle to reach an RSU.
RSU_POSITIONS = {"RSU-1": (200.0, 600.0), "RSU-2": (600.0, 200.0)}
HOP_LIMIT = 10             # ETSI EN 302 636-4-1 itsGnDefaultHopLimit: a copy is not relayed beyond 10 hops
# The fixed scenario for ./run_demo.sh, the explainer and the dashboard showcase. Chosen once, by rule:
# among the 200-vehicle incidents outside direct RSU range (so the alert must be relayed to reach an
# RSU), the run whose proposed-scheme transmission count is closest to the median (ties: lowest run).
DEMO_DENSITY, DEMO_RUN = 200, 2

# ------------------------------------------------------------ misbehaviour
MALICIOUS_RATIO = 0.10     # fraction of vehicles that receive but never relay (selfish/black-hole); experimental assumption
WATCHDOG_MISS_PROB = 0.10  # P(watchdog misses an honest relay, e.g. due to a collision) -> false accusation (Marti et al. 2000); assumption
TRUST_CH_THRESHOLD = 0.7   # Beta-reputation trust needed to be prioritised as a relay (project Algorithm 1 threshold)

# ------------------------------------------------------ radio (IEEE 802.11p / ITS-G5, 10 MHz @ 5.9 GHz)
COMM_RANGE_M = 300.0       # decode = carrier-sense = interference range (unit disk, a simplification); 300 m used by both base papers (Chen 2024, Kaur 2024)
SLOT_US = 13               # 802.11p (10 MHz) slot time
SIFS_US = 32               # 802.11p SIFS
AIFSN = 2                  # AC_VO (emergency) - IEEE 802.11 Table 9-138, dot11OCBActivated
CW_MIN = 3                 # AC_VO: (aCWmin+1)/4 - 1 = 3; broadcast frames are never ACKed so CW never grows
DATA_RATE_MBPS = 6         # default ITS-G5 control-channel rate (QPSK 1/2): 48 data bits per 8 us OFDM symbol
PAYLOAD_BYTES = 300        # emergency alert payload (DENM / SAE J2735 scale)
MAC_OVERHEAD_BYTES = 38    # QoS MAC header 26 + LLC/SNAP 8 + FCS 4
CBR_WINDOW_MS = 100        # ETSI TS 102 687: CBR is the busy fraction over T_CBR = 100 ms

# ------------------------------------------------ forwarding (slotted 1-persistence, Wisitpongphan et al. 2007)
N_SLOTS = 5                # paper's rush-hour recommendation
TAU_MS = 5.0               # one slot = WAIT_TIME = 5 ms (paper: >= 95th-percentile MAC delay)

RAD_MS = 5.0               # random assessment delay ~ U[0, RAD_MS): one slot wide, so it never reorders distance slots

# ------------------------------------------------ corroboration: voting + BLS12-381 signatures
# An alert is accepted only with a BLS aggregate signature from a quorum of reputable endorsers.
COMMITTEE_SIZE = 5         # the 5 nearest reputable neighbours of the incident may vote (smallest committee tolerating 2 faults)
QUORUM = 3                 # majority of the committee: 3 of 5 endorsements needed
SIGNATURE_BYTES = 96       # BLS12-381 signature (G2, compressed); an aggregate has the same size
VOTE_BYTES = 132           # a vote frame: 32 B event digest + 4 B signer ID + 96 B signature
SIGNER_ID_BYTES = 4        # per endorser listed in the certificate
BLS_SIGN_MS = 1.4          # processing time charged per signature  (measured native BLS12-381: Zhang et al. 2021, arXiv:2106.04030)
BLS_VERIFY_MS = 4.3        # processing time charged per verification (same source); experimental assumption for an on-board unit
VOTE_SLOT_MS = 0.5         # committee members answer in rank order, one vote frame (0.3 ms on air) per slot, so votes never collide

# ------------------------------------------------ clustering (Chen & Wu 2024, Table 2)
DBSCAN_EPS_M = 40.0        # paper uses eps in (20, 40) m
DBSCAN_MIN_PTS = 3         # paper's MinPts

# ------------------------------------------------ outputs
RESULTS_DIR = "results/urban"
BASELINES = ["flooding", "slotted1p", "proposed"]   # the headline comparison
ABLATIONS = ["no_rad", "no_slots", "no_coverage", "no_clustering", "no_cluster_forwarding", "no_reputation", "no_security"]
PROTOCOLS = BASELINES + ABLATIONS + ["ch_route"]
LABELS = {
    "ch_route": "CH shortest-path delivery",
    "flooding": "Blind flooding",
    "slotted1p": "Slotted 1-persistence",
    "proposed": "Proposed (full)",
    "no_rad": "without random delay",
    "no_slots": "without distance slots",
    "no_coverage": "without coverage test",
    "no_clustering": "without clustering",
    "no_cluster_forwarding": "without cluster-based forwarding",
    "no_reputation": "without reputation",
    "no_security": "without voting + BLS",
}
# Forged-alert test: the same proposed scheme with three levels of protection.
FORGERY = {"voting_reputation": "Voting + BLS + reputation (full)", "voting_only": "Voting + BLS, no reputation gate",
           "no_voting": "No voting"}

# Sensitivity runs override a parameter through the environment, e.g.
#   EXP_COMM_RANGE_M=150 EXP_RESULTS_DIR=results/sensitivity/range_150 python run.py experiment
# The override is recorded in that run's experiment_config.json.
import os as _os
for _k, _v in _os.environ.items():
    if _k.startswith("EXP_") and _k[4:] in globals():
        globals()[_k[4:]] = type(globals()[_k[4:]])(_v)

# Place the RSUs on actual intersections in whichever network is selected.
import xml.etree.ElementTree as _ET
_junctions = {j.get("id"): j for j in _ET.parse(NET_FILE).getroot().findall("junction")}
RSU_POSITIONS = {name: (float(_junctions[j].get("x")), float(_junctions[j].get("y")))
                 for name, j in (("RSU-1", "B3"), ("RSU-2", "D1"))}
