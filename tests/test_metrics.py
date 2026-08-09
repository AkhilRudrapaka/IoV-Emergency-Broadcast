import os
import csv
import unittest
from vehicle import Vehicle
from metrics import Metrics


class TestMetricsModule(unittest.TestCase):

    def setUp(self):
        self.csv_test_path = "outputs/logs/test_metrics.csv"
        self.metrics = Metrics(csv_filepath=self.csv_test_path)
        
        self.vehicles = {"v1": Vehicle("v1"), "v2": Vehicle("v2")}
        self.clusters = {0: ["v1"], 1: ["v2"], -1: []}
        self.cluster_heads = {0: "v1", 1: "v2"}

    def tearDown(self):
        if os.path.exists(self.csv_test_path):
            os.remove(self.csv_test_path)

    def test_step_metrics_recording(self):
        rec = self.metrics.update_step_metrics(step=1, vehicles=self.vehicles, clusters=self.clusters, cluster_heads=self.cluster_heads)
        
        self.assertEqual(rec["step"], 1)
        self.assertEqual(rec["vehicle_count"], 2)
        self.assertEqual(rec["cluster_count"], 2)
        self.assertEqual(rec["cluster_head_count"], 2)

    def test_counters(self):
        self.metrics.record_emergency_message()
        self.metrics.forwarded_message(hops=2)
        self.metrics.duplicate_message()
        self.metrics.record_auth_result(True)
        self.metrics.record_auth_result(False)

        self.assertEqual(self.metrics.emergency_messages, 1)
        self.assertEqual(self.metrics.forwarded, 1)
        self.assertEqual(self.metrics.routing_hops, 2)
        self.assertEqual(self.metrics.duplicates, 1)
        self.assertEqual(self.metrics.auth_success, 1)
        self.assertEqual(self.metrics.auth_failures, 1)

    def test_csv_export(self):
        self.metrics.update_step_metrics(step=10, vehicles=self.vehicles, clusters=self.clusters, cluster_heads=self.cluster_heads)
        self.metrics.record_emergency_message()
        self.metrics.record_auth_result(True)
        self.metrics.update_step_metrics(step=11, vehicles=self.vehicles, clusters=self.clusters, cluster_heads=self.cluster_heads)

        saved_path = self.metrics.save_to_csv(self.csv_test_path)
        self.assertTrue(os.path.exists(saved_path))

        with open(saved_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["step"], "10")
            self.assertEqual(rows[1]["step"], "11")
            self.assertEqual(rows[1]["emergency_messages"], "1")
            self.assertEqual(rows[1]["auth_success"], "1")


if __name__ == "__main__":
    unittest.main()
