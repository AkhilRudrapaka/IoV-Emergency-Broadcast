import os
import csv
import shutil
import unittest
from vehicle import Vehicle
from graphs import GraphGenerator


class TestGraphGenerator(unittest.TestCase):

    def setUp(self):
        self.test_dir = "outputs/graphs_test"
        self.csv_file = "outputs/test_metrics_graph.csv"
        os.makedirs(os.path.dirname(self.csv_file), exist_ok=True)

        # Create dummy CSV file
        with open(self.csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["step", "timestamp", "vehicle_count", "cluster_count", "cluster_head_count", "emergency_messages", "forwarded", "duplicates", "routing_hops", "auth_success", "auth_failures", "pdr", "avg_delay_ms", "broadcast_overhead", "ch_changes", "throughput_kbps", "auth_success_rate", "avg_legitimate_trust", "avg_malicious_trust"])
            writer.writerow([0, 1000, 50, 2, 2, 0, 0, 0, 0, 0, 0, 100, 15, 0, 0, 45, 100, 0.85, 0.2])
            writer.writerow([50, 1050, 50, 3, 3, 1, 1, 4, 3, 1, 0, 100, 15, 1, 0, 45, 100, 0.85, 0.2])
            writer.writerow([100, 1100, 50, 2, 2, 1, 1, 4, 3, 1, 0, 100, 15, 1, 0, 45, 100, 0.85, 0.2])

        self.vehicles = {
            "v1": Vehicle("v1"),
            "v2": Vehicle("v2")
        }
        self.vehicles["v1"].trust = 0.85
        self.vehicles["v2"].trust = 0.72

        self.graph_gen = GraphGenerator(output_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if os.path.exists(self.csv_file):
            os.remove(self.csv_file)

    def test_generate_all_graphs(self):
        files = self.graph_gen.generate_all_graphs(csv_filepath=self.csv_file, vehicles=self.vehicles)

        self.assertGreaterEqual(len(files), 5)
        for filepath in files:
            self.assertTrue(os.path.exists(filepath))
            self.assertGreater(os.path.getsize(filepath), 0)


if __name__ == "__main__":
    unittest.main()
