import os
import csv
import math
import random
import numpy as np

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
from flooding import FloodingEngine
from generate_routes import generate_route_file
from bls_auth import AuthenticationManager
from utils import compute_delay_ms

try:
    from config import VEHICLE_DENSITIES, COMM_RANGE, DBSCAN_EPS, DBSCAN_MIN_SAMPLES, COMPARISON_CSV, MALICIOUS_RATIO, EMERGENCY_EVENTS_PER_RUN
except ImportError:
    VEHICLE_DENSITIES = [50, 100, 200, 300, 500]
    COMM_RANGE = 150.0
    DBSCAN_EPS = 80.0
    DBSCAN_MIN_SAMPLES = 2
    EMERGENCY_EVENTS_PER_RUN = 5
    COMPARISON_CSV = "outputs/logs/comparison_results.csv"
    MALICIOUS_RATIO = 0.15


class ComparisonEngine:
    """
    IEEE Comparative Evaluation Framework.
    Runs both Proposed Algorithm (Trust-Aware Clustering + Multi-hop RSU Routing)
    and Baseline Flooding Algorithm under identical 5x5 traffic densities and collision scenarios.
    Automatically generates IEEE comparison tables and percentage improvement metrics.
    """

    def __init__(self, output_dir="outputs/logs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def run_density_simulation(self, density, algorithm="PROPOSED", steps=100, seed=42,
                                clustering_mode=None, authentication_mode=None):
        """
        Simulates a specific traffic density for either PROPOSED or FLOODING algorithm across 5x5 grid bounds.

        Args:
            clustering_mode (str, optional): "baseline" | "velocity_aware" (Priority 1 ablation
                switch). Defaults to config.CLUSTERING_MODE when omitted.
            authentication_mode (str, optional): "none" | "baseline" | "bls_individual" |
                "bls_batch" (Priority 2 ablation switch). Defaults to config.AUTHENTICATION_MODE
                when omitted.
        """
        random.seed(seed)
        np.random.seed(seed)

        # Initialize network components
        vehicles = {}
        cluster_manager = ClusterManager(eps=DBSCAN_EPS, min_samples=DBSCAN_MIN_SAMPLES, mode=clustering_mode)
        stability_tracker = ClusterStabilityTracker()
        reclustering_controller = ReclusteringController()
        trust_manager = TrustManager()
        cluster_head_manager = ClusterHeadManager()
        broadcast_manager = BroadcastManager()
        accident_manager = AccidentManager()
        routing_engine = RoutingEngine()
        neighbor_manager = NeighborManager(comm_range=COMM_RANGE)
        rsu_manager = RSUManager(deploy_default_rsus=True)
        flooding_engine = FloodingEngine(comm_range=COMM_RANGE)
        metrics = Metrics()
        auth_manager = AuthenticationManager(mode=authentication_mode)

        # Seed synthetic vehicle grid across 5x5 urban road network bounds (50, 750)
        grid_dim = int(np.ceil(np.sqrt(density)))
        x_coords = np.linspace(50, 750, grid_dim)
        y_coords = np.linspace(50, 750, grid_dim)

        v_idx = 0
        drift_angles = {}
        for x in x_coords:
            for y in y_coords:
                if v_idx >= density:
                    break
                vid = f"v{v_idx}"
                v = Vehicle(vid)
                v.update((x + random.uniform(-10, 10), y + random.uniform(-10, 10)), speed=random.uniform(5, 15))
                # Persistent per-vehicle drift heading, so synthetic movement carries a
                # consistent direction signal for velocity-aware clustering (not pure noise).
                drift_angles[vid] = random.uniform(0, 2 * math.pi)

                # Malicious vehicles, sampled at config.MALICIOUS_RATIO
                if v_idx > 0 and random.random() < MALICIOUS_RATIO:
                    v.is_malicious = True
                    v.attack_type = random.choice(["PACKET_DROP", "FAKE_ALERT", "FORGED_RECOMMENDATION"])

                v.classify_and_verify()
                vehicles[vid] = v
                v_idx += 1

        # Emergency events per run (MEDIUM, Report S10.2): multiple independent
        # accidents spaced across the run, each on a freshly-selected non-malicious
        # vehicle, so PDR aggregates over real repeated delivery attempts instead
        # of one binary 0%/100% outcome.
        n_events = min(EMERGENCY_EVENTS_PER_RUN, max(1, density))
        event_steps = sorted(set(
            max(1, int(steps * (i + 1) / (n_events + 1))) for i in range(n_events)
        ))
        events_triggered = 0
        routing_delay_samples = []
        verification_delay_samples = []

        for step in range(steps):
            # Move vehicles slightly, drifting along a persistent per-vehicle heading with jitter
            for v in vehicles.values():
                if not v.is_accident:
                    angle = drift_angles.get(v.id, 0.0)
                    dx = math.cos(angle) * 0.8 + random.uniform(-0.3, 0.3)
                    dy = math.sin(angle) * 0.8 + random.uniform(-0.3, 0.3)
                    v.update((v.x + dx, v.y + dy), v.speed)
                    v.classify_and_verify()
                    trust_manager.calculate_trust(v, vehicles)

            neighbor_manager.discover_neighbors(vehicles)

            for v in vehicles.values():
                v.is_cluster_head = False

            should_recluster, _ = reclustering_controller.decide(
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

            stability_snapshot = stability_tracker.update(step, clusters, cluster_heads, vehicles)

            metrics.update_step_metrics(
                step, vehicles, clusters, cluster_heads,
                stability_snapshot=stability_snapshot,
                recluster_count=reclustering_controller.recluster_count,
                reclustering_skipped_count=reclustering_controller.skipped_count
            )

            # Trigger the next scheduled emergency event, if any, this step
            if step in event_steps and events_triggered < n_events:
                # Accident vehicle must never be malicious (Report CRITICAL S10.2),
                # and must not already be mid-accident from an earlier event.
                candidates = [vid for vid, v in vehicles.items() if not v.is_malicious and not v.is_accident]
                if candidates:
                    events_triggered += 1
                    target_vid = random.choice(candidates)
                    msg = accident_manager.trigger_accident(target_vid, vehicles, step=step, severity="HIGH")

                    if msg:
                        if algorithm == "PROPOSED":
                            # Priority 2: BLS chain-of-custody signing — sender + every active CH co-signs
                            auth_manager.sign_emergency_broadcast(
                                msg, sender_vehicle_id=msg.sender, cluster_heads=cluster_heads, vehicles=vehicles
                            )
                            route, ack = routing_engine.route_message(
                                message=msg,
                                vehicles=vehicles,
                                cluster_heads=cluster_heads,
                                broadcast_manager=broadcast_manager,
                                rsu_manager=rsu_manager,
                                metrics=metrics,
                                auth_manager=auth_manager,
                                trust_manager=trust_manager,
                                clusters=clusters
                            )
                            bls_summary = auth_manager.get_summary()
                            if ack:
                                verify_ms = bls_summary.get("avg_batch_verify_time_ms") or bls_summary.get("avg_individual_verify_time_ms", 0.0)
                                event_routing_ms = compute_delay_ms(
                                    hops=max(0, len(route) - 1),
                                    signature_bytes=bls_summary.get("signature_size_bytes", 0)
                                )
                                routing_delay_samples.append(event_routing_ms)
                                verification_delay_samples.append(verify_ms)
                                metrics.record_delivery(delay_ms=event_routing_ms + verify_ms)
                            metrics.record_bls_performance(bls_summary)
                        else:  # FLOODING Baseline
                            delivered, fwd, dups, hops = flooding_engine.disseminate(
                                message=msg,
                                source_vehicle_id=target_vid,
                                vehicles=vehicles,
                                rsu_manager=rsu_manager,
                                metrics=metrics
                            )
                            if delivered:
                                event_routing_ms = compute_delay_ms(hops=hops)
                                routing_delay_samples.append(event_routing_ms)
                                verification_delay_samples.append(0.0)
                                metrics.record_delivery(delay_ms=event_routing_ms)

        avg_routing_ms = sum(routing_delay_samples) / len(routing_delay_samples) if routing_delay_samples else 0.0
        avg_verify_ms = sum(verification_delay_samples) / len(verification_delay_samples) if verification_delay_samples else 0.0

        return {
            "density": density,
            "algorithm": algorithm,
            "pdr": metrics.pdr,
            "delay_ms": metrics.avg_delay_ms,
            # Delay breakdown, averaged across this run's emergency events:
            # routing_delay_ms is the hop/transmission analytic cost
            # (compute_delay_ms); verification_delay_ms is the real measured BLS
            # verify time (0 for FLOODING, which does no authentication). Reported
            # separately because the py_ecc pure-Python pairing cost dominates the
            # blended delay_ms figure -- see RESULTS_SUMMARY.md for the full caveat.
            "routing_delay_ms": round(avg_routing_ms, 3),
            "verification_delay_ms": round(avg_verify_ms, 3),
            "overhead": metrics.broadcast_overhead,
            "duplicates": metrics.duplicates,
            "hops": max(1, metrics.routing_hops // max(1, metrics.emergency_messages)),
            "throughput_kbps": metrics.throughput_kbps,
            "auth_success_rate": metrics.auth_success_rate,
            "ch_changes": metrics.ch_changes,
            "events_triggered": events_triggered
        }

    def run_all_comparisons(self, densities=VEHICLE_DENSITIES, runs=5, steps=100,
                             clustering_mode=None, authentication_mode=None):
        """
        Executes full comparative evaluation matrix across all densities.

        Args:
            runs (int): repetitions per density, averaged with reported std dev and
                95% CI (not a bare mean over 2 runs -- see _average_metrics).
            clustering_mode / authentication_mode (str, optional): ablation switches,
                forwarded unchanged to run_density_simulation for both arms.
        """
        results_proposed = []
        results_flooding = []

        print("\n" + "=" * 80)
        print("STARTING IEEE COMPARATIVE EVALUATION EXPERIMENTAL SUITE (5x5 GRID)")
        print(f"runs={runs} per density, steps={steps}, clustering_mode={clustering_mode or '(config default)'}, "
              f"authentication_mode={authentication_mode or '(config default)'}")
        print("=" * 80)

        for d in densities:
            print(f"\n[ComparisonEngine] Executing evaluation for density = {d} vehicles...")
            prop_runs = []
            flood_runs = []

            for r in range(runs):
                seed = 42 + r * 10
                prop_res = self.run_density_simulation(
                    d, algorithm="PROPOSED", steps=steps, seed=seed,
                    clustering_mode=clustering_mode, authentication_mode=authentication_mode
                )
                flood_res = self.run_density_simulation(
                    d, algorithm="FLOODING", steps=steps, seed=seed,
                    clustering_mode=clustering_mode, authentication_mode=authentication_mode
                )
                prop_runs.append(prop_res)
                flood_runs.append(flood_res)

            # Average metrics across runs, with dispersion (std dev + 95% CI)
            avg_prop = self._average_metrics(prop_runs)
            avg_flood = self._average_metrics(flood_runs)

            results_proposed.append(avg_prop)
            results_flooding.append(avg_flood)

        # Generate comparison tables
        summary_table, csv_file = self.generate_comparison_table(results_proposed, results_flooding)
        return summary_table, csv_file

    def _average_metrics(self, run_list):
        """
        Mean, sample std dev, and 95% CI half-width (normal approximation,
        1.96 * std / sqrt(n)) across `run_list` repetitions of the same density/arm.
        """
        keys = ["pdr", "delay_ms", "routing_delay_ms", "verification_delay_ms",
                "overhead", "duplicates", "hops", "throughput_kbps", "auth_success_rate"]
        n = len(run_list)
        avg_dict = {
            "density": run_list[0]["density"],
            "algorithm": run_list[0]["algorithm"],
            "runs": n
        }
        for k in keys:
            values = [r[k] for r in run_list]
            mean = sum(values) / n
            variance = sum((v - mean) ** 2 for v in values) / max(1, n - 1)
            std = variance ** 0.5
            ci95 = 1.96 * std / (n ** 0.5) if n > 0 else 0.0
            avg_dict[k] = round(mean, 2)
            avg_dict[f"{k}_std"] = round(std, 2)
            avg_dict[f"{k}_ci95"] = round(ci95, 2)
        return avg_dict

    def generate_comparison_table(self, proposed_list, flooding_list):
        """
        Produces formatted IEEE comparison table with % improvement calculation.
        """
        csv_path = os.path.join(self.output_dir, "comparison_results.csv")

        table_rows = []
        for prop, flood in zip(proposed_list, flooding_list):
            d = prop["density"]

            # Calculate % Improvements
            pdr_imp = ((prop["pdr"] - flood["pdr"]) / max(1.0, flood["pdr"])) * 100.0
            delay_imp = ((flood["delay_ms"] - prop["delay_ms"]) / max(1.0, flood["delay_ms"])) * 100.0
            overhead_imp = ((flood["overhead"] - prop["overhead"]) / max(1.0, flood["overhead"])) * 100.0
            dups_imp = ((flood["duplicates"] - prop["duplicates"]) / max(1.0, flood["duplicates"])) * 100.0
            tp_imp = ((prop["throughput_kbps"] - flood["throughput_kbps"]) / max(1.0, flood["throughput_kbps"])) * 100.0

            row = {
                "Density": d,
                "Runs": prop.get("runs", 1),
                "Baseline Flooding PDR (%)": flood["pdr"],
                "Proposed PDR (%)": prop["pdr"],
                "PDR Improvement (%)": round(pdr_imp, 2),
                "Baseline Delay (ms)": flood["delay_ms"],
                "Baseline Delay 95% CI (ms)": flood.get("delay_ms_ci95", 0.0),
                "Proposed Delay (ms)": prop["delay_ms"],
                "Proposed Delay 95% CI (ms)": prop.get("delay_ms_ci95", 0.0),
                "Delay Reduction (%)": round(delay_imp, 2),
                "Proposed Routing-Only Delay (ms)": prop.get("routing_delay_ms", 0.0),
                "Proposed BLS Verification Delay (ms)": prop.get("verification_delay_ms", 0.0),
                "Baseline Routing-Only Delay (ms)": flood.get("routing_delay_ms", 0.0),
                "Baseline Overhead": flood["overhead"],
                "Proposed Overhead": prop["overhead"],
                "Overhead Reduction (%)": round(overhead_imp, 2),
                "Baseline Duplicates": flood["duplicates"],
                "Proposed Duplicates": prop["duplicates"],
                "Duplicate Reduction (%)": round(dups_imp, 2),
                "Baseline Throughput (Kbps)": flood["throughput_kbps"],
                "Proposed Throughput (Kbps)": prop["throughput_kbps"],
                "Throughput Gain (%)": round(tp_imp, 2)
            }
            table_rows.append(row)

        # Write to CSV
        fieldnames = list(table_rows[0].keys())
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(table_rows)

        # Format Markdown Table for User & Paper
        md_lines = [
            "### IEEE Comparative Performance Summary: Baseline Flooding vs Proposed Algorithm",
            "",
            "| Density | Metric | Baseline Flooding | Proposed Algorithm | Percentage Improvement |",
            "|---|---|---|---|---|",
        ]

        for r in table_rows:
            d = r["Density"]
            md_lines.append(f"| **{d} Vehicles** (n={r['Runs']} runs) | **Packet Delivery Ratio (PDR)** | {r['Baseline Flooding PDR (%)']:.2f}% | {r['Proposed PDR (%)']:.2f}% | **+{r['PDR Improvement (%)']:.2f}%** |")
            md_lines.append(f"| | **End-to-End Delay (total)** | {r['Baseline Delay (ms)']:.2f} ± {r['Baseline Delay 95% CI (ms)']:.2f} ms | {r['Proposed Delay (ms)']:.2f} ± {r['Proposed Delay 95% CI (ms)']:.2f} ms | **+{r['Delay Reduction (%)']:.2f}%** |")
            md_lines.append(f"| | &nbsp;&nbsp;↳ routing-only component | {r['Baseline Routing-Only Delay (ms)']:.2f} ms | {r['Proposed Routing-Only Delay (ms)']:.2f} ms | (fewer hops via CH-only routing) |")
            md_lines.append(f"| | &nbsp;&nbsp;↳ BLS verification component | 0.00 ms (no auth) | {r['Proposed BLS Verification Delay (ms)']:.2f} ms | (pure-Python py_ecc pairing cost, see caveat) |")
            md_lines.append(f"| | **Broadcast Overhead** | {r['Baseline Overhead']:.2f} | {r['Proposed Overhead']:.2f} | **+{r['Overhead Reduction (%)']:.2f}%** |")
            md_lines.append(f"| | **Duplicate Messages** | {r['Baseline Duplicates']} | {r['Proposed Duplicates']} | **+{r['Duplicate Reduction (%)']:.2f}%** |")
            md_lines.append(f"| | **Throughput** | {r['Baseline Throughput (Kbps)']:.2f} Kbps | {r['Proposed Throughput (Kbps)']:.2f} Kbps | **+{r['Throughput Gain (%)']:.2f}%** |")
            md_lines.append("|---|---|---|---|---|")

        summary_md = "\n".join(md_lines)
        print("\n" + summary_md + "\n")
        print(f"[ComparisonEngine] Saved IEEE comparison CSV to '{csv_path}'")

        return summary_md, csv_path
