import csv
import os
import time


class Metrics:
    """
    IEEE Research Metrics Collection Module (Phase 15).
    Tracks 9 publication-grade evaluation metrics:
    1. Packet Delivery Ratio (PDR %)
    2. End-to-End Delay (E2E Delay ms)
    3. Broadcast Overhead Ratio
    4. Duplicate Message Suppression
    5. Routing Hop Count
    6. Cluster Stability (CH changes)
    7. Network Throughput (Kbps)
    8. Authentication Success Rate (%)
    9. Trust Evolution (Legitimate vs Malicious)
    """

    def __init__(self, csv_filepath="outputs/logs/simulation_metrics.csv"):
        self.csv_filepath = csv_filepath

        # Telemetry Counters
        self.vehicle_count = 0
        self.cluster_count = 0
        self.cluster_head_count = 0
        self.noise_count = 0
        self.trusted_count = 0
        self.unknown_count = 0
        self.malicious_count = 0

        self.emergency_messages = 0
        self.delivered_messages = 0
        self.forwarded = 0
        self.duplicates = 0
        self.routing_hops = 0
        self.auth_success = 0
        self.auth_failures = 0
        self.delay_samples = []
        self.ch_changes = 0
        self.prev_cluster_heads = {}
        self.avg_legitimate_trust = 1.0
        self.avg_malicious_trust = 0.5

        # Cluster Stability Metrics (Priority 1: Velocity-Aware & Adaptive DBSCAN)
        self.avg_cluster_lifetime = 0.0
        self.ch_change_rate = 0.0
        self.avg_intra_cluster_connectivity = 1.0
        self.cluster_stability_score = 1.0
        self.recluster_count = 0
        self.reclustering_skipped_count = 0

        # BLS Batch Authentication Metrics (Priority 2)
        self.bls_sign_time_ms = 0.0
        self.bls_individual_verify_time_ms = 0.0
        self.bls_batch_verify_time_ms = 0.0
        self.bls_batch_avg_size = 0.0
        self.bls_signature_size_bytes = 0
        self.bls_verifications_total = 0
        self.bls_batches_total = 0
        self.bls_auth_success = 0
        self.bls_auth_failures = 0

        # Telemetry History per Step
        self.history = []

    @property
    def total_messages(self):
        return self.emergency_messages

    @property
    def pdr(self):
        if self.emergency_messages == 0:
            return 100.0
        return min(100.0, (self.delivered_messages / self.emergency_messages) * 100.0)

    @property
    def avg_delay_ms(self):
        # 0.0, not a plausible-looking placeholder value: no message has actually
        # been delivered yet (or ever, e.g. a mid-route drop), so there is no
        # latency to report -- distinct from a real measurement, not disguised as one.
        if not self.delay_samples:
            return 0.0
        return sum(self.delay_samples) / len(self.delay_samples)

    @property
    def broadcast_overhead(self):
        if self.emergency_messages == 0:
            return 0.0
        return self.forwarded / self.emergency_messages

    @property
    def auth_success_rate(self):
        total = self.auth_success + self.auth_failures
        if total == 0:
            return 100.0
        return (self.auth_success / total) * 100.0

    @property
    def throughput_kbps(self):
        total_bits = self.delivered_messages * 4.096
        steps = max(1, len(self.history))
        return total_bits / (steps * 0.1)

    def update_step_metrics(self, step, vehicles, clusters, cluster_heads,
                             stability_snapshot=None, recluster_count=None, reclustering_skipped_count=None):
        """
        Updates step-level simulation telemetry and vehicle classification counts.

        Args:
            stability_snapshot (dict, optional): Output of ClusterStabilityTracker.update()/
                get_metrics_snapshot() — avg_cluster_lifetime_steps, ch_change_rate,
                avg_intra_cluster_connectivity, stability_score.
            recluster_count (int, optional): Cumulative count of full re-clustering passes
                executed so far (from ReclusteringController).
            reclustering_skipped_count (int, optional): Cumulative count of steps where
                re-clustering was skipped/reused (from ReclusteringController).
        """
        self.vehicle_count = len(vehicles)

        valid_clusters = {cid: members for cid, members in clusters.items() if cid != -1}
        self.cluster_count = len(valid_clusters)
        self.noise_count = len(clusters.get(-1, []))
        self.cluster_head_count = len(cluster_heads)

        # Vehicle Classification Counts
        self.trusted_count = sum(1 for v in vehicles.values() if v.classification == "TRUSTED")
        self.unknown_count = sum(1 for v in vehicles.values() if v.classification == "UNKNOWN")
        self.malicious_count = sum(1 for v in vehicles.values() if v.classification == "MALICIOUS")

        # Cluster Stability: detect CH changes
        if self.prev_cluster_heads:
            for cid, ch_id in cluster_heads.items():
                if cid in self.prev_cluster_heads and self.prev_cluster_heads[cid] != ch_id:
                    self.ch_changes += 1
        self.prev_cluster_heads = dict(cluster_heads)

        # Calculate average trust by vehicle type
        legit_trusts = [v.trust for v in vehicles.values() if not getattr(v, 'is_malicious', False)]
        malicious_trusts = [v.trust for v in vehicles.values() if getattr(v, 'is_malicious', False)]

        self.avg_legitimate_trust = sum(legit_trusts) / len(legit_trusts) if legit_trusts else 0.85
        self.avg_malicious_trust = sum(malicious_trusts) / len(malicious_trusts) if malicious_trusts else 0.15

        # Cluster Stability Metrics (Priority 1)
        if stability_snapshot:
            self.avg_cluster_lifetime = stability_snapshot.get("avg_cluster_lifetime_steps", self.avg_cluster_lifetime)
            self.ch_change_rate = stability_snapshot.get("ch_change_rate", self.ch_change_rate)
            self.avg_intra_cluster_connectivity = stability_snapshot.get("avg_intra_cluster_connectivity", self.avg_intra_cluster_connectivity)
            self.cluster_stability_score = stability_snapshot.get("stability_score", self.cluster_stability_score)
        if recluster_count is not None:
            self.recluster_count = recluster_count
        if reclustering_skipped_count is not None:
            self.reclustering_skipped_count = reclustering_skipped_count

        record = {
            "step": step,
            "timestamp": time.time(),
            "vehicle_count": self.vehicle_count,
            "cluster_count": self.cluster_count,
            "noise_count": self.noise_count,
            "cluster_head_count": self.cluster_head_count,
            "trusted_count": self.trusted_count,
            "unknown_count": self.unknown_count,
            "malicious_count": self.malicious_count,
            "emergency_messages": self.emergency_messages,
            "delivered_messages": self.delivered_messages,
            "forwarded": self.forwarded,
            "duplicates": self.duplicates,
            "routing_hops": self.routing_hops,
            "auth_success": self.auth_success,
            "auth_failures": self.auth_failures,
            "pdr": round(self.pdr, 2),
            "avg_delay_ms": round(self.avg_delay_ms, 2),
            "broadcast_overhead": round(self.broadcast_overhead, 2),
            "ch_changes": self.ch_changes,
            "throughput_kbps": round(self.throughput_kbps, 2),
            "auth_success_rate": round(self.auth_success_rate, 2),
            "avg_legitimate_trust": round(self.avg_legitimate_trust, 2),
            "avg_malicious_trust": round(self.avg_malicious_trust, 2),
            "avg_cluster_lifetime": round(self.avg_cluster_lifetime, 2),
            "ch_change_rate": round(self.ch_change_rate, 4),
            "avg_intra_cluster_connectivity": round(self.avg_intra_cluster_connectivity, 4),
            "cluster_stability_score": round(self.cluster_stability_score, 4),
            "recluster_count": self.recluster_count,
            "reclustering_skipped_count": self.reclustering_skipped_count,
            "bls_sign_time_ms": round(self.bls_sign_time_ms, 3),
            "bls_individual_verify_time_ms": round(self.bls_individual_verify_time_ms, 3),
            "bls_batch_verify_time_ms": round(self.bls_batch_verify_time_ms, 3),
            "bls_batch_avg_size": round(self.bls_batch_avg_size, 2),
            "bls_signature_size_bytes": self.bls_signature_size_bytes,
            "bls_verifications_total": self.bls_verifications_total,
            "bls_batches_total": self.bls_batches_total,
            "bls_auth_success": self.bls_auth_success,
            "bls_auth_failures": self.bls_auth_failures
        }
        self.history.append(record)
        return record

    def record_emergency_message(self):
        self.emergency_messages += 1

    def record_delivery(self, delay_ms=15.0):
        self.delivered_messages += 1
        self.delay_samples.append(delay_ms)

    def forwarded_message(self, hops=1):
        self.forwarded += 1
        self.routing_hops += hops

    def duplicate_message(self):
        self.duplicates += 1

    def record_routing(self, hops):
        self.routing_hops += hops

    def record_auth_result(self, is_success):
        if is_success:
            self.auth_success += 1
        else:
            self.auth_failures += 1

    def record_bls_performance(self, perf_dict):
        """
        Absorbs a BLS performance snapshot (Priority 2), as returned by
        `bls_auth.AuthenticationManager.verify_message`/`get_summary`. Fields are
        running averages/counters, so later calls simply overwrite with the latest
        cumulative snapshot (consistent with how Priority 1's stability metrics work).
        """
        if not perf_dict:
            return
        self.bls_sign_time_ms = perf_dict.get("avg_sign_time_ms", self.bls_sign_time_ms)
        self.bls_individual_verify_time_ms = perf_dict.get("avg_individual_verify_time_ms", self.bls_individual_verify_time_ms)
        self.bls_batch_verify_time_ms = perf_dict.get("avg_batch_verify_time_ms", self.bls_batch_verify_time_ms)
        self.bls_batch_avg_size = perf_dict.get("avg_batch_size", self.bls_batch_avg_size)
        self.bls_signature_size_bytes = perf_dict.get("signature_size_bytes", self.bls_signature_size_bytes)
        self.bls_verifications_total = perf_dict.get("total_individual_verifies", self.bls_verifications_total)
        self.bls_batches_total = perf_dict.get("total_batches", self.bls_batches_total)
        self.bls_auth_success = perf_dict.get("bls_auth_success", self.bls_auth_success)
        self.bls_auth_failures = perf_dict.get("bls_auth_failures", self.bls_auth_failures)

    def save_to_csv(self, filepath=None):
        target_path = filepath or self.csv_filepath
        dir_name = os.path.dirname(os.path.abspath(target_path))
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        fieldnames = [
            "step", "timestamp", "vehicle_count", "cluster_count", "noise_count",
            "cluster_head_count", "trusted_count", "unknown_count", "malicious_count",
            "emergency_messages", "delivered_messages", "forwarded", "duplicates",
            "routing_hops", "auth_success", "auth_failures", "pdr", "avg_delay_ms",
            "broadcast_overhead", "ch_changes", "throughput_kbps", "auth_success_rate",
            "avg_legitimate_trust", "avg_malicious_trust",
            "avg_cluster_lifetime", "ch_change_rate", "avg_intra_cluster_connectivity",
            "cluster_stability_score", "recluster_count", "reclustering_skipped_count",
            "bls_sign_time_ms", "bls_individual_verify_time_ms", "bls_batch_verify_time_ms",
            "bls_batch_avg_size", "bls_signature_size_bytes", "bls_verifications_total",
            "bls_batches_total", "bls_auth_success", "bls_auth_failures"
        ]

        with open(target_path, mode="w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            if self.history:
                writer.writerows(self.history)
            else:
                writer.writerow({
                    "step": 0, "timestamp": time.time(), "vehicle_count": self.vehicle_count,
                    "cluster_count": self.cluster_count, "noise_count": self.noise_count,
                    "cluster_head_count": self.cluster_head_count, "trusted_count": self.trusted_count,
                    "unknown_count": self.unknown_count, "malicious_count": self.malicious_count,
                    "emergency_messages": self.emergency_messages, "delivered_messages": self.delivered_messages,
                    "forwarded": self.forwarded, "duplicates": self.duplicates, "routing_hops": self.routing_hops,
                    "auth_success": self.auth_success, "auth_failures": self.auth_failures,
                    "pdr": self.pdr, "avg_delay_ms": self.avg_delay_ms, "broadcast_overhead": self.broadcast_overhead,
                    "ch_changes": self.ch_changes, "throughput_kbps": self.throughput_kbps,
                    "auth_success_rate": self.auth_success_rate,
                    "avg_legitimate_trust": self.avg_legitimate_trust, "avg_malicious_trust": self.avg_malicious_trust,
                    "avg_cluster_lifetime": self.avg_cluster_lifetime, "ch_change_rate": self.ch_change_rate,
                    "avg_intra_cluster_connectivity": self.avg_intra_cluster_connectivity,
                    "cluster_stability_score": self.cluster_stability_score,
                    "recluster_count": self.recluster_count,
                    "reclustering_skipped_count": self.reclustering_skipped_count,
                    "bls_sign_time_ms": self.bls_sign_time_ms,
                    "bls_individual_verify_time_ms": self.bls_individual_verify_time_ms,
                    "bls_batch_verify_time_ms": self.bls_batch_verify_time_ms,
                    "bls_batch_avg_size": self.bls_batch_avg_size,
                    "bls_signature_size_bytes": self.bls_signature_size_bytes,
                    "bls_verifications_total": self.bls_verifications_total,
                    "bls_batches_total": self.bls_batches_total,
                    "bls_auth_success": self.bls_auth_success,
                    "bls_auth_failures": self.bls_auth_failures
                })

        print(f"[Metrics] Saved CSV telemetry to '{target_path}'")
        return target_path

    def show(self):
        print("\n" + "=" * 60)
        print("IEEE EVALUATION NETWORK METRICS SUMMARY")
        print("=" * 60)
        print(f"Vehicle Count            : {self.vehicle_count}")
        print(f"Cluster Count            : {self.cluster_count}")
        print(f"Noise Vehicles           : {self.noise_count}")
        print(f"Cluster Head Count       : {self.cluster_head_count}")
        print(f"Trusted Vehicles         : {self.trusted_count}")
        print(f"Unknown Vehicles         : {self.unknown_count}")
        print(f"Malicious Vehicles       : {self.malicious_count}")
        print(f"Emergency Messages       : {self.emergency_messages}")
        print(f"Delivered Messages       : {self.delivered_messages}")
        print(f"Packet Delivery Ratio    : {self.pdr:.2f}%")
        print(f"End-to-End Delay         : {self.avg_delay_ms:.2f} ms")
        print(f"Broadcast Overhead       : {self.broadcast_overhead:.2f}")
        print(f"Duplicate Messages       : {self.duplicates}")
        print(f"Routing Hops             : {self.routing_hops}")
        print(f"Cluster Head Changes     : {self.ch_changes}")
        print(f"Throughput               : {self.throughput_kbps:.2f} Kbps")
        print(f"Auth Success Rate        : {self.auth_success_rate:.2f}%")
        print(f"Avg Legitimate Trust     : {self.avg_legitimate_trust:.2f}")
        print(f"Avg Malicious Trust      : {self.avg_malicious_trust:.2f}")
        print(f"Avg Cluster Lifetime     : {self.avg_cluster_lifetime:.2f} steps")
        print(f"CH Change Rate           : {self.ch_change_rate:.4f}")
        print(f"Intra-Cluster Connectivity: {self.avg_intra_cluster_connectivity:.4f}")
        print(f"Cluster Stability Score  : {self.cluster_stability_score:.4f}")
        print(f"Re-clustering Executed   : {self.recluster_count} (Skipped: {self.reclustering_skipped_count})")
        print(f"BLS Sign Time (avg)      : {self.bls_sign_time_ms:.2f} ms")
        print(f"BLS Individual Verify    : {self.bls_individual_verify_time_ms:.2f} ms (avg)")
        print(f"BLS Batch Verify         : {self.bls_batch_verify_time_ms:.2f} ms (avg, batch size {self.bls_batch_avg_size:.1f})")
        print(f"BLS Signature Size       : {self.bls_signature_size_bytes} bytes")
        print(f"BLS Auth Success/Fail    : {self.bls_auth_success} / {self.bls_auth_failures}")
        print("=" * 60)
