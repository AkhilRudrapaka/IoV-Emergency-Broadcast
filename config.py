import os

# Central Configuration for IoV Broadcast Storm Mitigation Research Project
#
# PROOF-OF-WORK: parameters below are grounded against the actual "Simulation
# Parameters" / "Simulation Setup" tables of the four papers in base papers/
# (verified by direct PDF text extraction, not recalled from memory) rather
# than an external trace dataset (no NGSIM/TAPAS Cologne/VeReMi files exist on
# this machine -- see docs/ALGORITHMS.md's Proof-of-Work Mapping for the full
# per-parameter citation). Where a value diverges from a paper's own number,
# that is stated explicitly, not silently rounded to match.

# Vehicle Densities for Evaluation.
# [50, 100, 150, 200] match [Kaur et al., 2024, Table 2] "Number of nodes/
# Vehicle Density: 50, 100, 150, 200, 250" exactly; 250 is included below to
# complete that exact match, and 300/500 extend beyond Kaur et al.'s own
# tested range to probe higher-density behavior.
VEHICLE_DENSITIES = [50, 100, 150, 200, 250, 300, 500]

# SUMO Simulation Settings
SUMO_NET_FILE = "network/road.net.xml"
SUMO_ROUTING_DIR = "network"
SIMULATION_STEPS = 200

# Communication Parameters
COMM_RANGE = 150.0  # Communication range in meters (neighbor discovery / flooding baseline only -- see GPSR_RANGE_M below for the routing-specific 300m value)

# Clustering Parameters (DBSCAN)
# eps=80.0m: [Chen & Wu, 2024, Table 2] test eps in {20,40}m on a dense
# highway (3 lanes, 3000m) and prefer 20m THERE. That does not transfer to
# this project's sparser urban intersection grid -- measured directly
# (eps_sensitivity.py, docs/ALGORITHMS.md Sec 2.5): eps=20/40m produce
# 70-100% noise (no clustering) on this network. eps=80.0 is this project's
# own value for its own topology, not Chen & Wu's number reused unverified.
DBSCAN_EPS = 80.0
DBSCAN_MIN_SAMPLES = 2

# Velocity-Aware Clustering (Priority 1 — ablation switch)
CLUSTERING_MODE = "velocity_aware"     # "baseline" | "velocity_aware"
VELOCITY_PREDICTION_HORIZON = 2.0      # seconds, forward-projection horizon
VELOCITY_WEIGHT_POSITION = 0.6
VELOCITY_WEIGHT_MOBILITY = 0.4
MAX_HEADING_DIFF_DEG = 120.0           # directional gate threshold
MIN_SPEED_FOR_HEADING_GATE = 1.0       # m/s; below this, heading is unreliable

# Dynamic Re-clustering (Priority 1)
ENABLE_DYNAMIC_RECLUSTERING = True
RECLUSTER_MIN_INTERVAL_STEPS = 5
RECLUSTER_TRUST_DELTA_THRESHOLD = 0.15
RECLUSTER_MOBILITY_STD_THRESHOLD = 3.0        # speed stddev (m/s) trigger
RECLUSTER_STABILITY_SCORE_THRESHOLD = 0.7
RECLUSTER_MEMBERSHIP_CHANGE_THRESHOLD = 0.2   # fraction of fleet churned forces recluster

# Trust Evaluation & Classification Parameters
TRUST_INITIAL = 0.5
TRUST_MIN = 0.0
TRUST_MAX = 1.0
TRUST_BLACKLIST_THRESHOLD = 0.3

# Vehicle Classification Thresholds
TRUST_THRESHOLD_TRUSTED = 0.7
TRUST_THRESHOLD_UNKNOWN_MIN = 0.3

# Bayesian Trust Model (Algorithm 1): Trust(v) = w_fwd*Tf + w_c*Tc + w_s*Ts + w_h*Th
# Tf=Forwarding Behaviour, Tc=Message Consistency, Ts=Speed Plausibility, Th=Historical Trust.
# Tc and Ts have no external formula available this session (source report not on disk) --
# see trust.py for their standard-VANET-literature definitions and the explicit caveat
# that they are this session's interpretation of the factor names, not verified against
# the original report text.
TRUST_WEIGHT_FWD = 0.30
TRUST_WEIGHT_CONSISTENCY = 0.25
TRUST_WEIGHT_SPEED = 0.20
TRUST_WEIGHT_HIST = 0.25
TRUST_EMA_ALPHA = 0.85          # New_Th = 0.85*Old_Th + 0.15*current
TRUST_EMA_CURRENT_WEIGHT = 0.15

# RSU trust boost: Final Trust = 0.80*vehicle_assessment + 0.20*rsu_assessment.
# rsu_assessment is a persistent per-vehicle value nudged by RSU verification outcomes
# (rsu.py), blended in on every calculate_trust() call -- not a one-off mutation that
# gets silently overwritten by the next step's recomputation.
RSU_TRUST_BLEND_VEHICLE_WEIGHT = 0.80
RSU_TRUST_BLEND_RSU_WEIGHT = 0.20
RSU_TRUST_NUDGE = 0.05          # per-event move applied to the persistent rsu_assessment

# Speed Plausibility (Ts): kinematic-feasibility check. Bound matches the existing SUMO
# vType's decel="4.5" (network/routes*.xml) -- not an invented constant.
MAX_SPEED_DELTA_PER_STEP_MPS = 4.5
MAX_SPEED_MPS = 22.0            # matches vType maxSpeed

# Message Consistency (Tc): claimed-vs-actual sender location at message creation time.
MESSAGE_LOCATION_TOLERANCE_M = 50.0             # GPS-class tolerance before penalizing
FAKE_ALERT_LOCATION_OFFSET_RANGE_M = (200.0, 500.0)  # simulated FAKE_ALERT forgery magnitude

# BLS Batch Authentication (Priority 2 — ablation switch)
AUTHENTICATION_MODE = "bls_batch"     # "bls_batch" | "bls_individual" | "baseline" | "none"
BLS_TRUST_THRESHOLD = 0.7             # T >= 0.7: aggregate/batch verify
BLS_MID_TRUST_THRESHOLD = 0.3         # 0.3 <= T < 0.7: individual verify; T < 0.3: reject immediately, no verify attempt
BLS_BENCHMARK_BATCH_SIZES = [1, 2, 5, 10, 20]
MAX_CHAIN_SIGNERS = 14                # CH pre-screening cap: ~7ms/signature under a 100ms deadline

# GPSR Geographic Forwarding (Algorithm 3)
GPSR_RANGE_M = 300.0            # wireless range enforced on every hop (greedy + perimeter)
GPSR_OWN_CH_RANGE_M = 80.0      # fallback tier 1: own CH must be within this range
GPSR_TTL_HOPS = 5

# Multi-event evaluation (Evaluation Harness)
EMERGENCY_EVENTS_PER_RUN = 5    # emergency alerts injected per comparison-harness run, so PDR is meaningful

# Malicious Vehicle Settings
# 0.15 (15%) sits inside the 0-25% range [Azizi & Shokrollahi, 2024 (RTRV),
# Table 2] itself evaluates against ("Number of malicious Vehicle: 0, 33, 66,
# 99, 132, 165" out of ~660 total, i.e. 0%-25%).
MALICIOUS_RATIO = 0.15  # 15% malicious vehicles by default
ATTACK_TYPES = ["FAKE_ALERT", "PACKET_DROP", "FORGED_RECOMMENDATION"]

# Analytic End-to-End Delay Model (Evaluation Harness)
# IEEE 802.11p-typical 10 MHz / QPSK-1/2 channel and SAE-J2735-scale payload size.
# Applied identically to PROPOSED and FLOODING arms -- the delay difference between
# them is a consequence of real per-run quantities (hop count, measured BLS verify
# time, real signature bytes), not a per-algorithm tuned constant. Does not model
# MAC-layer contention/collision, so it is a conservative (likely-understated)
# estimate of flooding's real disadvantage under broadcast-storm conditions.
V2V_DATA_RATE_BPS = 6_000_000   # 802.11p 6 Mbps PHY rate
BASE_MESSAGE_SIZE_BYTES = 300   # SAE J2735-scale emergency alert payload
PER_HOP_PROCESSING_MS = 1.0     # routing/queuing decision overhead per hop, symmetric both arms

# Roadside RSU Locations (Positioned on the green roadside grass area beside roads)
RSU_LOCATIONS = {
    "RSU_NORTH": (445.0, 750.0),
    "RSU_SOUTH": (445.0, 50.0),
    "RSU_EAST": (750.0, 445.0),
    "RSU_WEST": (50.0, 445.0),
    "RSU_CENTER": (445.0, 445.0)
}

# SUMO Visualization Colors (RGBA)
COLOR_TRUSTED = (255, 255, 255, 255)       # White: Trusted Vehicles
COLOR_UNKNOWN = (255, 255, 0, 255)        # Yellow: Unknown / Unverified Vehicles
COLOR_MALICIOUS = (0, 0, 0, 255)         # Black: Malicious Vehicles
COLOR_CLUSTER_HEAD = (0, 0, 255, 255)    # Blue: Cluster Head
COLOR_FORWARDING = (255, 165, 0, 255)    # Orange: Active Forwarding CH
COLOR_ACCIDENT = (255, 0, 0, 255)        # Red: Collision Site Vehicles
COLOR_RSU = (0, 255, 0, 255)             # Green: Roadside RSU Tower Polygon

# Output Paths
OUTPUT_DIR = "outputs"
GRAPHS_DIR = os.path.join(OUTPUT_DIR, "graphs")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")
METRICS_CSV = os.path.join(LOGS_DIR, "simulation_metrics.csv")
COMPARISON_CSV = os.path.join(LOGS_DIR, "comparison_results.csv")
