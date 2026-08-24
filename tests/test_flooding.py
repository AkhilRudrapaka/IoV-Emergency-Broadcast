import unittest

from vehicle import Vehicle
from messaging import EmergencyMessage
from flooding import FloodingEngine
from metrics import Metrics


class TestFloodingModule(unittest.TestCase):
    """
    Baseline flooding comparator coverage -- every "% improvement" figure in the
    evaluation harness is measured against this module, so it needs its own tests.
    """

    def setUp(self):
        self.vehicles = {}
        # 3x3 grid, 100m spacing, comm_range=150 -> every vehicle reaches its
        # orthogonal/diagonal neighbors, giving a fully connected small network.
        idx = 0
        for x in (0.0, 100.0, 200.0):
            for y in (0.0, 100.0, 200.0):
                v = Vehicle(f"v{idx}")
                v.update((x, y), speed=10.0)
                self.vehicles[f"v{idx}"] = v
                idx += 1
        self.engine = FloodingEngine(comm_range=150.0)

    def test_disseminate_reaches_all_reachable_nodes(self):
        msg = EmergencyMessage(sender="v0", location=(0.0, 0.0), severity="HIGH")
        metrics = Metrics()
        delivered, forwarded, duplicates, hops = self.engine.disseminate(
            msg, source_vehicle_id="v0", vehicles=self.vehicles, rsu_manager=None, metrics=metrics
        )
        # 8 other vehicles in a connected grid should all receive the flood.
        self.assertEqual(forwarded, 8)
        self.assertGreaterEqual(hops, 1)

    def test_unknown_source_returns_false(self):
        msg = EmergencyMessage(sender="ghost", location=(0.0, 0.0), severity="HIGH")
        delivered, forwarded, duplicates, hops = self.engine.disseminate(
            msg, source_vehicle_id="ghost", vehicles=self.vehicles
        )
        self.assertFalse(delivered)
        self.assertEqual(forwarded, 0)

    def test_packet_drop_attacker_halts_propagation_past_itself(self):
        # Linear chain v0 -> v1 -> v2 -> v3, spacing 100m, comm_range 110m: v1 is
        # the sole relay between v0 and {v2, v3}, so it's a genuine cut vertex.
        chain = {}
        for i in range(4):
            v = Vehicle(f"c{i}")
            v.update((i * 100.0, 0.0), speed=10.0)
            chain[f"c{i}"] = v
        chain["c1"].is_malicious = True
        chain["c1"].attack_type = "PACKET_DROP"

        tight_engine = FloodingEngine(comm_range=110.0)
        msg = EmergencyMessage(sender="c0", location=(0.0, 0.0), severity="HIGH")
        metrics = Metrics()
        delivered, forwarded, duplicates, hops = tight_engine.disseminate(
            msg, source_vehicle_id="c0", vehicles=chain, rsu_manager=None, metrics=metrics
        )
        # c1 receives the flood but drops it instead of relaying to c2/c3.
        self.assertEqual(forwarded, 1)  # only c0 -> c1 succeeds
        self.assertFalse(delivered)

    def test_duplicate_messages_are_counted(self):
        msg = EmergencyMessage(sender="v0", location=(0.0, 0.0), severity="HIGH")
        metrics = Metrics()
        self.engine.disseminate(msg, source_vehicle_id="v0", vehicles=self.vehicles, metrics=metrics)
        # A fully connected grid guarantees re-discovery of already-received nodes.
        self.assertGreater(metrics.duplicates, 0)


if __name__ == "__main__":
    unittest.main()
