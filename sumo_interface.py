import os
import sys
import random
import traci

from vehicle import Vehicle
from clustering import ClusterManager
from cluster_stability import ClusterStabilityTracker, ReclusteringController
from trust import TrustManager
from cluster_head import ClusterHeadManager
from messaging import EmergencyMessage
from broadcast import BroadcastManager
from accident import AccidentManager
from routing import RoutingEngine
from rsu import RSUManager
from metrics import Metrics
from neighbor_discovery import NeighborManager
from graphs import GraphGenerator
from logger import SimulationLogger
from utils import sumo_angle_to_radians
from bls_auth import AuthenticationManager

try:
    from config import (
        COMM_RANGE, DBSCAN_EPS, DBSCAN_MIN_SAMPLES,
        COLOR_TRUSTED, COLOR_UNKNOWN, COLOR_MALICIOUS,
        COLOR_CLUSTER_HEAD, COLOR_FORWARDING, COLOR_ACCIDENT, COLOR_RSU
    )
except ImportError:
    COMM_RANGE = 150.0
    DBSCAN_EPS = 80.0
    DBSCAN_MIN_SAMPLES = 2

if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.path.abspath(os.environ["SUMO_HOME"]), "tools")
    if tools not in sys.path:
        sys.path.append(tools)


def add_visual_rsus_to_sumo(rsu_manager):
    """
    Renders high-visibility Green RSU Tower Polygons (25m x 25m) on the green roadside grass area
    beside the road network in SUMO GUI (Phase 10 & 13).
    """
    if not traci.isLoaded():
        return

    for rsu in rsu_manager.get_all_rsus().values():
        poly_id = f"POLY_{rsu.rsu_id}"
        poi_id = f"POI_{rsu.rsu_id}"

        # 25m x 25m green roadside tower polygon shape
        half_size = 12.5
        shape = [
            (rsu.x - half_size, rsu.y - half_size),
            (rsu.x + half_size, rsu.y - half_size),
            (rsu.x + half_size, rsu.y + half_size),
            (rsu.x - half_size, rsu.y + half_size)
        ]

        try:
            if poly_id not in traci.polygon.getIDList():
                # Add filled Green RSU roadside tower building polygon on grass terrain
                traci.polygon.add(
                    polygonID=poly_id,
                    shape=shape,
                    color=(0, 255, 0, 255),
                    fill=True,
                    layer=100,
                    polygonType="RSU"
                )

            if poi_id not in traci.poi.getIDList():
                # Add central text label for RSU
                traci.poi.add(
                    poiID=poi_id,
                    x=rsu.x,
                    y=rsu.y,
                    color=(255, 255, 255, 255),
                    poiType="RSU_LABEL"
                )
        except Exception:
            pass


def run_sumo_simulation(density=250, steps=200, use_gui=False, route_file=None):
    """
    Orchestrates the complete IEEE IoV Simulation Pipeline across 15 Phases:
    Vehicle Verification -> Classification -> DBSCAN Clustering -> Trust Evaluation ->
    Cluster Head Selection -> 2-Vehicle Crash Simulation -> Duplicate Filtering -> Controlled Broadcast ->
    Multi-Hop Routing -> RSU Ingress Processing -> Decision Engine -> Analytics -> TCC Dissemination.
    """
    sumo_binary = "sumo-gui" if use_gui else "sumo"
    cfg_file = "network/simulation.sumocfg"
    r_file = route_file or f"network/routes_{density}.rou.xml"

    if not os.path.exists(r_file):
        r_file = "network/routes.rou.xml"

    cmd = [sumo_binary, "-c", cfg_file, "--route-files", r_file, "--no-step-log", "true", "--no-warnings", "true"]
    traci.start(cmd)

    # Initialize Logger and Managers
    logger = SimulationLogger(log_filepath="outputs/logs/simulation_run.log")
    logger.print_banner(f"IEEE IoV SIMULATION PIPELINE (DENSITY = {density} VEHICLES)")

    vehicles = {}
    cluster_manager = ClusterManager(eps=DBSCAN_EPS, min_samples=DBSCAN_MIN_SAMPLES)
    stability_tracker = ClusterStabilityTracker()
    reclustering_controller = ReclusteringController(logger=logger)
    trust_manager = TrustManager(logger=logger)
    cluster_head_manager = ClusterHeadManager(logger=logger)
    broadcast_manager = BroadcastManager(logger=logger)
    accident_manager = AccidentManager(logger=logger)
    routing_engine = RoutingEngine(logger=logger)
    neighbor_manager = NeighborManager(comm_range=COMM_RANGE)
    graph_generator = GraphGenerator(output_dir="outputs/graphs")
    rsu_manager = RSUManager(logger=logger, deploy_default_rsus=True)
    metrics = Metrics(csv_filepath="outputs/logs/simulation_metrics.csv")
    auth_manager = AuthenticationManager(logger=logger)

    # Add Green RSU roadside tower polygons and POI markers to SUMO map
    add_visual_rsus_to_sumo(rsu_manager)

    emergency_generated = False

    for step in range(steps):
        traci.simulationStep()
        ids = traci.vehicle.getIDList()

        # Update RSU visual flash animation
        rsu_manager.update_step()

        # Step 1 & 2: Update active vehicles, classify and verify (Phase 3)
        for vid in ids:
            if vid not in vehicles:
                v = Vehicle(vid)
                if random.random() < 0.15:
                    v.is_malicious = True
                    v.attack_type = random.choice(["PACKET_DROP", "FAKE_ALERT", "FORGED_RECOMMENDATION"])
                vehicles[vid] = v

            pos = traci.vehicle.getPosition(vid)
            speed = traci.vehicle.getSpeed(vid)
            heading = sumo_angle_to_radians(traci.vehicle.getAngle(vid))
            v = vehicles[vid]
            v.update(pos, speed, heading=heading)

            # Classify & verify vehicle
            v.classify_and_verify()

            # Continuous Trust Evaluation (Phase 5)
            trust_manager.calculate_trust(v, vehicles)

        # Remove departed vehicles
        active_v_ids = set(ids)
        departed = [vid for vid in vehicles if vid not in active_v_ids]
        for vid in departed:
            del vehicles[vid]

        # Step 3: Neighbor Discovery
        neighbor_manager.discover_neighbors(vehicles)

        for v in vehicles.values():
            v.is_cluster_head = False

        # Step 4 & 5: Velocity-Aware DBSCAN Clustering & Cluster Head Selection (Phases 4 & 6, Priority 1)
        should_recluster, recluster_reason = reclustering_controller.decide(
            step, vehicles, stability_score=stability_tracker.get_metrics_snapshot()["stability_score"]
        )

        if should_recluster:
            clusters = cluster_manager.perform_clustering(vehicles)
            cluster_heads = cluster_head_manager.select_cluster_heads(vehicles, clusters)
            reclustering_controller.record_recluster(step, vehicles, clusters, cluster_heads)
        else:
            clusters = reclustering_controller.reuse_last_clusters(vehicles)
            cluster_heads = reclustering_controller.last_cluster_heads
            reclustering_controller.record_skip()
            for cid, ch_id in cluster_heads.items():
                if ch_id in vehicles:
                    vehicles[ch_id].is_cluster_head = True

        active_clusters_count, noise_count = cluster_manager.get_cluster_stats(clusters)
        stability_snapshot = stability_tracker.update(step, clusters, cluster_heads, vehicles)

        active_chs = {v.cluster: v.id for v in vehicles.values() if v.is_cluster_head and v.cluster != -1}

        # Step 6: Visual Colors & Highlights Enforcer (Phase 13)
        for vid in ids:
            if vid in vehicles:
                v = vehicles[vid]
                try:
                    # Set RGBA color according to vehicle role/classification
                    traci.vehicle.setColor(vid, v.get_color())

                    # Visual highlight ring indicators in SUMO GUI
                    if v.is_accident:
                        traci.vehicle.highlight(vid, color=(255, 0, 0, 255), size=30.0)
                    elif v.is_forwarding:
                        traci.vehicle.highlight(vid, color=(255, 165, 0, 255), size=18.0)
                    elif v.is_cluster_head:
                        traci.vehicle.highlight(vid, color=(0, 0, 255, 255), size=12.0)
                except Exception:
                    pass

        # Update step telemetry
        step_record = metrics.update_step_metrics(
            step, vehicles, clusters, active_chs,
            stability_snapshot=stability_snapshot,
            recluster_count=reclustering_controller.recluster_count,
            reclustering_skipped_count=reclustering_controller.skipped_count
        )

        # Print Real-Time Structured Terminal Logs (Phase 14)
        if step % 20 == 0 or step == 50:
            logger.print_step_header(
                step=step,
                total_vehicles=len(vehicles),
                active_clusters=active_clusters_count,
                noise_vehicles=noise_count,
                ch_count=len(active_chs),
                trusted=step_record["trusted_count"],
                unknown=step_record["unknown_count"],
                malicious=step_record["malicious_count"]
            )

        # Step 50: Phase 7 Collision & Emergency Dissemination Workflow
        if step == 50 and not emergency_generated and active_chs:
            emergency_generated = True

            # Phase 7: Trigger 2-Vehicle Collision & Queue Congestion
            msg = accident_manager.trigger_accident(
                vehicles=vehicles,
                step=step,
                severity="HIGH"
            )

            if msg:
                # Priority 2: BLS chain-of-custody signing — sender + every active CH co-signs
                auth_manager.sign_emergency_broadcast(
                    msg, sender_vehicle_id=msg.sender, cluster_heads=active_chs, vehicles=vehicles
                )

                # Phase 8, 9, 10, 11, 12: Route discovery, Controlled Broadcast, RSU Processing, Dissemination
                route, ack = routing_engine.route_message(
                    message=msg,
                    vehicles=vehicles,
                    cluster_heads=active_chs,
                    broadcast_manager=broadcast_manager,
                    rsu_manager=rsu_manager,
                    metrics=metrics,
                    auth_manager=auth_manager
                )
                if ack:
                    metrics.record_delivery(delay_ms=15.0 + len(route) * 2.0)

                metrics.record_bls_performance(auth_manager.get_summary())

    traci.close()

    # Priority 2: BLS individual-vs-batch performance benchmark (controlled synthetic sweep)
    logger.print_banner("PRIORITY 2: BLS BATCH AUTHENTICATION — PERFORMANCE BENCHMARK")
    benchmark_results = auth_manager.run_performance_benchmark()
    auth_manager.save_benchmark_csv(benchmark_results, filepath="outputs/logs/bls_benchmark.csv")

    # Save metrics and generate IEEE graphs (Phase 15)
    metrics.show()
    csv_file = metrics.save_to_csv("outputs/logs/simulation_metrics.csv")
    metrics.save_to_csv("outputs/metrics.csv")
    graph_generator.generate_all_graphs(csv_filepath=csv_file, vehicles=vehicles)

    return metrics, vehicles


if __name__ == "__main__":
    gui_env = os.environ.get("SUMO_GUI", "0") == "1"
    run_sumo_simulation(density=250, steps=200, use_gui=gui_env)
