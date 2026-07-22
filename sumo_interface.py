import os
import sys
import random
import traci

from vehicle import Vehicle
from clustering import ClusterManager
from trust import TrustManager
from cluster_head import ClusterHeadManager
from messaging import EmergencyMessage
from broadcast import BroadcastManager

# -------------------------------------------------------
# Locate SUMO
# -------------------------------------------------------

if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    sys.path.append(tools)
else:
    print("Please set SUMO_HOME")
    sys.exit()

# -------------------------------------------------------
# Start SUMO
# -------------------------------------------------------

SUMO_CFG = "network/simulation.sumocfg"

traci.start(["sumo-gui", "-c", SUMO_CFG])

# -------------------------------------------------------
# Managers
# -------------------------------------------------------

vehicles = {}

cluster_manager = ClusterManager(eps=120, min_samples=2)

trust_manager = TrustManager()

cluster_head_manager = ClusterHeadManager()

broadcast_manager = BroadcastManager()

# Emergency generated only once
emergency_generated = False

# -------------------------------------------------------
# Simulation Loop
# -------------------------------------------------------

for step in range(100):

    traci.simulationStep()

    ids = traci.vehicle.getIDList()

    # -------------------------
    # Update Vehicles
    # -------------------------

    for vid in ids:

        if vid not in vehicles:
            vehicles[vid] = Vehicle(vid)

        position = traci.vehicle.getPosition(vid)

        speed = traci.vehicle.getSpeed(vid)

        vehicles[vid].update(position, speed)

        trust_manager.calculate_trust(vehicles[vid])

    # -------------------------
    # Reset CH Flags
    # -------------------------

    for vehicle in vehicles.values():
        vehicle.is_cluster_head = False

    # -------------------------
    # Clustering
    # -------------------------

    clusters = cluster_manager.perform_clustering(vehicles)

    # -------------------------
    # Cluster Heads
    # -------------------------

    cluster_heads = cluster_head_manager.select_cluster_heads(
        vehicles,
        clusters
    )

    # -------------------------
    # Print Information
    # -------------------------

    print("\n")
    print("=" * 80)
    print(f"Simulation Step : {step}")
    print("=" * 80)

    for vehicle in vehicles.values():
        print(vehicle)

    print("\nClusters")

    for cid, members in clusters.items():

        if cid == -1:
            print(f"Noise : {members}")
        else:
            print(f"Cluster {cid}: {members}")

    print("\nCluster Heads")

    for cid, ch in cluster_heads.items():
        print(f"Cluster {cid} -> {ch}")

    # ====================================================
    # Emergency Generation
    # ====================================================

    if step == 50 and not emergency_generated:

        emergency_generated = True

        sender = random.choice(list(cluster_heads.values()))

        vehicle = vehicles[sender]

        message = EmergencyMessage(

            sender=sender,

            location=(vehicle.x, vehicle.y),

            severity="HIGH"

        )

        broadcast_manager.broadcast(

            message,

            cluster_heads

        )

traci.close()
