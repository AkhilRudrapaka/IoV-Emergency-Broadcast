import math
import unittest

from vehicle import Vehicle
from clustering import ClusterManager
from cluster_stability import ClusterStabilityTracker, ReclusteringController


class TestBaselineClustering(unittest.TestCase):
    """Regression safety net: baseline mode must reproduce plain Euclidean DBSCAN grouping."""

    def setUp(self):
        self.vehicles = {
            "a1": Vehicle("a1"), "a2": Vehicle("a2"),
            "b1": Vehicle("b1"), "b2": Vehicle("b2")
        }
        # Pair A: close together near origin
        self.vehicles["a1"].update((0.0, 0.0), speed=0.0)
        self.vehicles["a2"].update((10.0, 0.0), speed=0.0)
        # Pair B: close together, far from pair A
        self.vehicles["b1"].update((500.0, 500.0), speed=0.0)
        self.vehicles["b2"].update((510.0, 500.0), speed=0.0)

    def test_two_distinct_clusters_form(self):
        mgr = ClusterManager(eps=80.0, min_samples=2, mode="baseline")
        clusters = mgr.perform_clustering(self.vehicles)

        valid_clusters = {cid: members for cid, members in clusters.items() if cid != -1}
        self.assertEqual(len(valid_clusters), 2)

        self.assertEqual(self.vehicles["a1"].cluster, self.vehicles["a2"].cluster)
        self.assertEqual(self.vehicles["b1"].cluster, self.vehicles["b2"].cluster)
        self.assertNotEqual(self.vehicles["a1"].cluster, self.vehicles["b1"].cluster)


class TestVelocityAwareClustering(unittest.TestCase):
    """Directional/predictive distance metric and heading-gate behavior."""

    def test_same_heading_vehicles_cluster_together(self):
        vehicles = {"v1": Vehicle("v1"), "v2": Vehicle("v2")}
        vehicles["v1"].update((0.0, 0.0), speed=15.0, heading=0.0)
        vehicles["v2"].update((5.0, 0.0), speed=15.0, heading=0.1)

        mgr = ClusterManager(eps=80.0, min_samples=2, mode="velocity_aware")
        clusters = mgr.perform_clustering(vehicles)

        self.assertEqual(vehicles["v1"].cluster, vehicles["v2"].cluster)
        self.assertNotEqual(vehicles["v1"].cluster, -1)

    def test_opposite_heading_fast_vehicles_are_gated_apart(self):
        vehicles = {"v1": Vehicle("v1"), "v2": Vehicle("v2")}
        vehicles["v1"].update((0.0, 0.0), speed=15.0, heading=0.0)
        vehicles["v2"].update((5.0, 0.0), speed=15.0, heading=math.pi)

        mgr = ClusterManager(eps=80.0, min_samples=2, mode="velocity_aware")
        clusters = mgr.perform_clustering(vehicles)

        # Directional gate should push them apart -> neither has a same-eps neighbor -> both noise
        self.assertEqual(vehicles["v1"].cluster, -1)
        self.assertEqual(vehicles["v2"].cluster, -1)

    def test_stationary_vehicles_ignore_heading_gate(self):
        # Simulates a post-accident queue: near-zero speed, stale/divergent headings
        # from before the vehicles stopped. The gate must not fragment this cluster.
        vehicles = {"v1": Vehicle("v1"), "v2": Vehicle("v2")}
        vehicles["v1"].update((0.0, 0.0), speed=0.0, heading=0.0)
        vehicles["v2"].update((10.0, 0.0), speed=0.0, heading=math.pi)

        mgr = ClusterManager(eps=80.0, min_samples=2, mode="velocity_aware")
        clusters = mgr.perform_clustering(vehicles)

        self.assertEqual(vehicles["v1"].cluster, vehicles["v2"].cluster)
        self.assertNotEqual(vehicles["v1"].cluster, -1)

    def test_predictive_projection_separates_diverging_vehicles(self):
        # Close now, but moving apart quickly (perpendicular headings) should widen
        # the effective distance relative to two vehicles moving in parallel.
        converging = {"v1": Vehicle("v1"), "v2": Vehicle("v2")}
        converging["v1"].update((0.0, 0.0), speed=10.0, heading=0.0)
        converging["v2"].update((5.0, 0.0), speed=10.0, heading=0.0)

        diverging = {"v1": Vehicle("v1"), "v2": Vehicle("v2")}
        diverging["v1"].update((0.0, 0.0), speed=10.0, heading=0.0)
        diverging["v2"].update((5.0, 0.0), speed=10.0, heading=math.pi / 2)

        mgr = ClusterManager(eps=80.0, min_samples=2, mode="velocity_aware")
        matrix_converging = mgr._compute_mobility_distance_matrix(converging, ["v1", "v2"])
        matrix_diverging = mgr._compute_mobility_distance_matrix(diverging, ["v1", "v2"])

        self.assertGreater(matrix_diverging[0, 1], matrix_converging[0, 1])


class TestReclusteringController(unittest.TestCase):

    def _make_vehicle(self, vid, x, y, speed=5.0, trust=0.5):
        v = Vehicle(vid)
        v.update((x, y), speed=speed)
        v.trust = trust
        return v

    def test_baseline_mode_always_reclusters(self):
        controller = ReclusteringController(mode="baseline", enabled=True)
        vehicles = {"v1": self._make_vehicle("v1", 0, 0)}
        for step in range(3):
            should, _ = controller.decide(step, vehicles)
            self.assertTrue(should)

    def test_skips_within_minimum_interval(self):
        controller = ReclusteringController(
            mode="velocity_aware", enabled=True, min_interval_steps=5,
            trust_delta_threshold=0.2, mobility_std_threshold=3.0,
            stability_score_threshold=0.5, membership_change_threshold=0.3
        )
        vehicles = {"v1": self._make_vehicle("v1", 0, 0, speed=5.0), "v2": self._make_vehicle("v2", 10, 0, speed=5.0)}
        controller.record_recluster(0, vehicles, {0: ["v1", "v2"]}, {0: "v1"})

        should, reason = controller.decide(2, vehicles, stability_score=1.0)
        self.assertFalse(should)
        self.assertIn("interval", reason)

    def test_forces_recluster_on_membership_churn(self):
        controller = ReclusteringController(
            mode="velocity_aware", enabled=True, min_interval_steps=5,
            membership_change_threshold=0.3
        )
        original = {"v1": self._make_vehicle("v1", 0, 0), "v2": self._make_vehicle("v2", 10, 0)}
        controller.record_recluster(0, original, {0: ["v1", "v2"]}, {0: "v1"})

        churned = {"v3": self._make_vehicle("v3", 0, 0), "v4": self._make_vehicle("v4", 10, 0)}
        should, reason = controller.decide(1, churned, stability_score=1.0)
        self.assertTrue(should)
        self.assertIn("churn", reason)

    def test_forces_recluster_on_significant_trust_delta(self):
        controller = ReclusteringController(
            mode="velocity_aware", enabled=True, min_interval_steps=2,
            trust_delta_threshold=0.2, mobility_std_threshold=100.0,
            stability_score_threshold=0.0, membership_change_threshold=1.0
        )
        vehicles = {"v1": self._make_vehicle("v1", 0, 0, trust=0.5), "v2": self._make_vehicle("v2", 10, 0, trust=0.5)}
        controller.record_recluster(0, vehicles, {0: ["v1", "v2"]}, {0: "v1"})

        vehicles["v1"].trust = 0.9  # delta of 0.4 > threshold
        should, reason = controller.decide(3, vehicles, stability_score=1.0)
        self.assertTrue(should)
        self.assertIn("trust", reason)

    def test_reuse_last_clusters_applies_stored_labels(self):
        controller = ReclusteringController(mode="velocity_aware", enabled=True)
        vehicles = {"v1": self._make_vehicle("v1", 0, 0), "v2": self._make_vehicle("v2", 10, 0)}
        controller.record_recluster(0, vehicles, {0: ["v1", "v2"]}, {0: "v1"})

        vehicles["v3"] = self._make_vehicle("v3", 20, 20)  # new arrival, unseen at last recluster
        reused = controller.reuse_last_clusters(vehicles)

        self.assertEqual(vehicles["v1"].cluster, 0)
        self.assertEqual(vehicles["v2"].cluster, 0)
        self.assertEqual(vehicles["v3"].cluster, -1)
        self.assertIn("v3", reused[-1])


class TestClusterStabilityTracker(unittest.TestCase):

    def test_persistent_cluster_lifetime_grows_across_stable_steps(self):
        tracker = ClusterStabilityTracker()
        vehicles = {"v1": Vehicle("v1"), "v2": Vehicle("v2")}
        vehicles["v1"].neighbors = ["v2"]
        vehicles["v2"].neighbors = ["v1"]

        clusters = {0: ["v1", "v2"]}
        cluster_heads = {0: "v1"}

        tracker.update(0, clusters, cluster_heads, vehicles)
        snapshot = tracker.update(5, clusters, cluster_heads, vehicles)

        self.assertEqual(snapshot["active_persistent_clusters"], 1)
        self.assertGreaterEqual(snapshot["avg_cluster_lifetime_steps"], 5)
        self.assertEqual(snapshot["avg_intra_cluster_connectivity"], 1.0)

    def test_ch_change_is_detected(self):
        tracker = ClusterStabilityTracker()
        vehicles = {"v1": Vehicle("v1"), "v2": Vehicle("v2")}
        vehicles["v1"].neighbors = ["v2"]
        vehicles["v2"].neighbors = ["v1"]
        clusters = {0: ["v1", "v2"]}

        tracker.update(0, clusters, {0: "v1"}, vehicles)
        snapshot = tracker.update(1, clusters, {0: "v2"}, vehicles)

        self.assertGreater(snapshot["ch_change_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
