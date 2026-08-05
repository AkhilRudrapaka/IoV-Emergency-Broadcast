import os

# Central Configuration for IoV Broadcast Storm Mitigation Research Project

# Vehicle Densities for Evaluation
VEHICLE_DENSITIES = [50, 100, 200, 300, 500]

# SUMO Simulation Settings
SUMO_NET_FILE = "network/road.net.xml"
SUMO_ROUTING_DIR = "network"
SIMULATION_STEPS = 200

# Communication Parameters
COMM_RANGE = 150.0  # Communication range in meters

# Clustering Parameters (DBSCAN)
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
RECLUSTER_TRUST_DELTA_THRESHOLD = 0.2
RECLUSTER_MOBILITY_STD_THRESHOLD = 3.0        # speed stddev (m/s) trigger
RECLUSTER_STABILITY_SCORE_THRESHOLD = 0.5
RECLUSTER_MEMBERSHIP_CHANGE_THRESHOLD = 0.3   # fraction of fleet churned forces recluster

# Trust Evaluation & Classification Parameters
TRUST_INITIAL = 0.5
TRUST_MIN = 0.0
TRUST_MAX = 1.0
TRUST_BLACKLIST_THRESHOLD = 0.3

# Vehicle Classification Thresholds
TRUST_THRESHOLD_TRUSTED = 0.7
TRUST_THRESHOLD_UNKNOWN_MIN = 0.4

TRUST_WEIGHT_FWD = 0.30
TRUST_WEIGHT_AUTH = 0.25
TRUST_WEIGHT_PDR = 0.20
TRUST_WEIGHT_HIST = 0.15
TRUST_WEIGHT_REC = 0.10
TRUST_EMA_ALPHA = 0.7  # Smoothing factor for historical trust

# BLS Batch Authentication (Priority 2 — ablation switch)
AUTHENTICATION_MODE = "bls_batch"     # "bls_batch" | "bls_individual" | "baseline" | "none"
BLS_TRUST_THRESHOLD = 0.7
BLS_REJECT_LOW_TRUST = False          # False: individually verify low-trust signers; True: reject outright
BLS_BENCHMARK_BATCH_SIZES = [1, 2, 5, 10, 20]

# Malicious Vehicle Settings
MALICIOUS_RATIO = 0.15  # 15% malicious vehicles by default
ATTACK_TYPES = ["FAKE_ALERT", "PACKET_DROP", "FORGED_RECOMMENDATION"]

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
