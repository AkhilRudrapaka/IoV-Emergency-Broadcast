import numpy as np

try:
    from config import (
        CLUSTERING_MODE, ENABLE_DYNAMIC_RECLUSTERING, RECLUSTER_MIN_INTERVAL_STEPS,
        RECLUSTER_TRUST_DELTA_THRESHOLD, RECLUSTER_MOBILITY_STD_THRESHOLD,
        RECLUSTER_STABILITY_SCORE_THRESHOLD, RECLUSTER_MEMBERSHIP_CHANGE_THRESHOLD
    )
except ImportError:
    CLUSTERING_MODE = "velocity_aware"
    ENABLE_DYNAMIC_RECLUSTERING = True
    RECLUSTER_MIN_INTERVAL_STEPS = 5
    RECLUSTER_TRUST_DELTA_THRESHOLD = 0.2
    RECLUSTER_MOBILITY_STD_THRESHOLD = 3.0
    RECLUSTER_STABILITY_SCORE_THRESHOLD = 0.5
    RECLUSTER_MEMBERSHIP_CHANGE_THRESHOLD = 0.3


class ClusterStabilityTracker:
    """
    Tracks cluster stability across simulation steps (Priority 1).

    DBSCAN cluster labels are not stable identifiers across steps (the same
    physical cluster can get a different integer label each run), so this
    tracker maintains its own persistent cluster identities via best-overlap
    (Jaccard) matching between consecutive steps, and derives:
      - average cluster lifetime (in steps)
      - Cluster Head (CH) change rate
      - average intra-cluster connectivity (actual neighbor links / possible pairs)
      - a composite stability score combining the two
    """

    def __init__(self, overlap_threshold=0.5, ch_change_rate_window=10):
        self.overlap_threshold = overlap_threshold
        self.ch_change_rate_window = ch_change_rate_window

        self.persistent_clusters = {}  # pid -> {members, formed_step, last_seen_step, ch_id, ch_changes}
        self._next_persistent_id = 0
        self.closed_lifetimes = []
        self.ch_change_history = []  # rolling window of per-step CH-change event counts

        self.last_snapshot = {
            "avg_cluster_lifetime_steps": 0.0,
            "active_persistent_clusters": 0,
            "ch_change_rate": 0.0,
            "avg_intra_cluster_connectivity": 1.0,
            "stability_score": 1.0
        }

    def update(self, step, clusters, cluster_heads, vehicles):
        """
        Advances stability tracking by one simulation step.

        Args:
            step (int): Current simulation step index.
            clusters (dict): cluster_label -> list of member vehicle IDs (from this step's clustering).
            cluster_heads (dict): cluster_label -> elected CH vehicle ID (from this step's clustering).
            vehicles (dict): vehicle_id -> Vehicle instance (used for neighbor connectivity).

        Returns:
            dict: Snapshot of current stability metrics (see `get_metrics_snapshot`).
        """
        valid_clusters = {cid: set(members) for cid, members in clusters.items() if cid != -1}
        ch_change_events = 0
        matched_persistent_ids = set()

        for label, members in valid_clusters.items():
            best_pid, best_overlap = None, 0.0
            for pid, pdata in self.persistent_clusters.items():
                if pid in matched_persistent_ids:
                    continue
                union = members | pdata["members"]
                if not union:
                    continue
                overlap = len(members & pdata["members"]) / len(union)
                if overlap > best_overlap:
                    best_overlap, best_pid = overlap, pid

            if best_pid is not None and best_overlap > self.overlap_threshold:
                pid = best_pid
                pdata = self.persistent_clusters[pid]
                pdata["members"] = members
                pdata["last_seen_step"] = step
            else:
                pid = self._next_persistent_id
                self._next_persistent_id += 1
                self.persistent_clusters[pid] = {
                    "members": members, "formed_step": step, "last_seen_step": step,
                    "ch_id": None, "ch_changes": 0
                }
                pdata = self.persistent_clusters[pid]

            matched_persistent_ids.add(pid)

            new_ch = cluster_heads.get(label)
            if pdata["ch_id"] is not None and new_ch is not None and pdata["ch_id"] != new_ch:
                pdata["ch_changes"] += 1
                ch_change_events += 1
            pdata["ch_id"] = new_ch

        # Close out persistent clusters that were not matched this step (dissolved)
        dissolved_ids = [pid for pid in self.persistent_clusters if pid not in matched_persistent_ids]
        for pid in dissolved_ids:
            pdata = self.persistent_clusters.pop(pid)
            self.closed_lifetimes.append(pdata["last_seen_step"] - pdata["formed_step"] + 1)

        # Average cluster lifetime: blend closed-cluster history with active clusters' current age
        active_ages = [step - pdata["formed_step"] + 1 for pdata in self.persistent_clusters.values()]
        all_lifetimes = self.closed_lifetimes + active_ages
        avg_lifetime = sum(all_lifetimes) / len(all_lifetimes) if all_lifetimes else 0.0

        # Intra-cluster connectivity: actual neighbor edges among members vs all possible pairs
        connectivity_scores = []
        for members in valid_clusters.values():
            members_list = list(members)
            m = len(members_list)
            if m < 2:
                continue
            possible_pairs = m * (m - 1) / 2.0
            actual_edges = 0
            for vid in members_list:
                v = vehicles.get(vid)
                if not v:
                    continue
                for nbr in v.neighbors:
                    if nbr in members and nbr > vid:
                        actual_edges += 1
            connectivity_scores.append(actual_edges / possible_pairs)
        avg_connectivity = sum(connectivity_scores) / len(connectivity_scores) if connectivity_scores else 1.0

        # CH change rate over a rolling window, normalized by active cluster count
        self.ch_change_history.append(ch_change_events)
        if len(self.ch_change_history) > self.ch_change_rate_window:
            self.ch_change_history.pop(0)
        active_cluster_count = max(1, len(valid_clusters))
        ch_change_rate = (sum(self.ch_change_history) / len(self.ch_change_history)) / active_cluster_count

        stability_score = max(0.0, min(1.0, 0.7 * avg_connectivity + 0.3 * (1.0 - min(1.0, ch_change_rate))))

        self.last_snapshot = {
            "avg_cluster_lifetime_steps": round(avg_lifetime, 2),
            "active_persistent_clusters": len(self.persistent_clusters),
            "ch_change_rate": round(ch_change_rate, 4),
            "avg_intra_cluster_connectivity": round(avg_connectivity, 4),
            "stability_score": round(stability_score, 4)
        }
        return self.last_snapshot

    def get_metrics_snapshot(self):
        """Returns the most recently computed stability metrics snapshot."""
        return self.last_snapshot


class ReclusteringController:
    """
    Decides, per simulation step, whether a full re-clustering pass should run
    or the previous cluster assignment should be reused (Priority 1).

    In "baseline" mode, or when dynamic re-clustering is disabled, this always
    triggers a full recluster every step — reproducing the original behavior
    exactly, for ablation studies.

    In "velocity_aware" mode with dynamic re-clustering enabled, re-clustering
    is skipped unless: the fleet's membership churned significantly, the
    minimum interval has elapsed AND at least one of (high mobility variance,
    a significant trust change, low cluster stability) is observed.
    """

    def __init__(self, logger=None, mode=None, enabled=None,
                 min_interval_steps=None, trust_delta_threshold=None,
                 mobility_std_threshold=None, stability_score_threshold=None,
                 membership_change_threshold=None):
        self.logger = logger
        self.mode = mode or CLUSTERING_MODE
        self.enabled = ENABLE_DYNAMIC_RECLUSTERING if enabled is None else enabled
        self.min_interval_steps = min_interval_steps if min_interval_steps is not None else RECLUSTER_MIN_INTERVAL_STEPS
        self.trust_delta_threshold = trust_delta_threshold if trust_delta_threshold is not None else RECLUSTER_TRUST_DELTA_THRESHOLD
        self.mobility_std_threshold = mobility_std_threshold if mobility_std_threshold is not None else RECLUSTER_MOBILITY_STD_THRESHOLD
        self.stability_score_threshold = stability_score_threshold if stability_score_threshold is not None else RECLUSTER_STABILITY_SCORE_THRESHOLD
        self.membership_change_threshold = membership_change_threshold if membership_change_threshold is not None else RECLUSTER_MEMBERSHIP_CHANGE_THRESHOLD

        self.last_recluster_step = None
        self.last_cluster_heads = {}
        self.last_vehicle_to_cluster = {}
        self.last_trust_snapshot = {}
        self.last_vehicle_ids = set()
        self.recluster_count = 0
        self.skipped_count = 0

    def decide(self, step, vehicles, stability_score=None):
        """
        Determines whether to run a full re-clustering pass this step.

        Returns:
            (bool, str): (should_recluster, human-readable reason)
        """
        if self.mode != "velocity_aware" or not self.enabled:
            return True, "always-recluster (baseline mode or dynamic reclustering disabled)"

        current_ids = set(vehicles.keys())
        union_ids = current_ids | self.last_vehicle_ids
        churn = (len(current_ids ^ self.last_vehicle_ids) / len(union_ids)) if union_ids else 0.0

        if churn > self.membership_change_threshold:
            reason = f"fleet membership churn {churn:.2f} exceeds threshold {self.membership_change_threshold:.2f}"
            self._log(step, True, reason)
            return True, reason

        if self.last_recluster_step is None or (step - self.last_recluster_step) < self.min_interval_steps:
            elapsed = 0 if self.last_recluster_step is None else step - self.last_recluster_step
            reason = f"minimum interval not yet elapsed ({elapsed} < {self.min_interval_steps} steps)"
            self._log(step, False, reason)
            return False, reason

        speeds = [v.speed for v in vehicles.values()]
        mobility_std = float(np.std(speeds)) if speeds else 0.0
        if mobility_std > self.mobility_std_threshold:
            reason = f"high mobility variance (speed std={mobility_std:.2f} > {self.mobility_std_threshold:.2f})"
            self._log(step, True, reason)
            return True, reason

        max_trust_delta = 0.0
        for vid, v in vehicles.items():
            if vid in self.last_trust_snapshot:
                max_trust_delta = max(max_trust_delta, abs(v.trust - self.last_trust_snapshot[vid]))
        if max_trust_delta > self.trust_delta_threshold:
            reason = f"significant trust change (max Δtrust={max_trust_delta:.2f} > {self.trust_delta_threshold:.2f})"
            self._log(step, True, reason)
            return True, reason

        if stability_score is not None and stability_score < self.stability_score_threshold:
            reason = f"cluster stability score low ({stability_score:.2f} < {self.stability_score_threshold:.2f})"
            self._log(step, True, reason)
            return True, reason

        reason = "no trigger condition met; reusing last cluster assignment"
        self._log(step, False, reason)
        return False, reason

    def record_recluster(self, step, vehicles, clusters, cluster_heads):
        """
        Records the outcome of a full re-clustering pass so future `decide()`
        and `reuse_last_clusters()` calls have a baseline to compare/reuse.
        """
        self.last_recluster_step = step
        self.last_cluster_heads = dict(cluster_heads)
        self.last_trust_snapshot = {vid: v.trust for vid, v in vehicles.items()}
        self.last_vehicle_ids = set(vehicles.keys())
        self.recluster_count += 1

        self.last_vehicle_to_cluster = {}
        for label, members in clusters.items():
            for vid in members:
                self.last_vehicle_to_cluster[vid] = label

        if self.logger:
            self.logger.log(f"[Reclustering] Step {step}: full re-clustering executed (total={self.recluster_count}).")

    def record_skip(self):
        """Increments the count of steps where re-clustering was skipped/reused."""
        self.skipped_count += 1

    def reuse_last_clusters(self, vehicles):
        """
        Reapplies the most recent cluster assignment to currently active vehicles.
        Vehicles absent from the last real clustering pass (new arrivals) are
        treated as noise (-1) until the next full re-clustering.
        """
        clusters = {}
        for vid, v in vehicles.items():
            label = self.last_vehicle_to_cluster.get(vid, -1)
            v.cluster = label
            clusters.setdefault(label, []).append(vid)
        return clusters

    def _log(self, step, will_recluster, reason):
        if self.logger:
            tag = "RECLUSTER" if will_recluster else "SKIP"
            self.logger.log(f"[Reclustering] Step {step}: {tag} — {reason}")
