import unittest
from vehicle import Vehicle
from accident import AccidentManager
from routing import RoutingEngine, euclidean_distance
from broadcast import BroadcastManager
from messaging import EmergencyMessage


class TestRoutingEngine(unittest.TestCase):

    def setUp(self):
        self.routing_engine = RoutingEngine()
        self.broadcast_mgr = BroadcastManager()
        self.accident_mgr = AccidentManager()

        # Create test vehicles positioned along a corridor towards RSU (400, 400)
        self.vehicles = {
            "v0": Vehicle("v0"),  # Accident vehicle in Cluster 0
            "v1": Vehicle("v1"),  # Other vehicle in Cluster 0
            "v2": Vehicle("v2"),  # CH of Cluster 1
            "v3": Vehicle("v3"),  # CH of Cluster 2
        }

        self.vehicles["v0"].update((10.0, 10.0), 0.0)
        self.vehicles["v1"].update((20.0, 20.0), 10.0)
        self.vehicles["v2"].update((150.0, 150.0), 12.0)
        self.vehicles["v3"].update((300.0, 300.0), 14.0)

        # Cluster setup: Cluster 0 -> CH v0, Cluster 1 -> CH v2, Cluster 2 -> CH v3
        self.cluster_heads = {
            0: "v0",
            1: "v2",
            2: "v3"
        }
        self.vehicles["v0"].cluster = 0
        self.vehicles["v1"].cluster = 0
        self.vehicles["v2"].cluster = 1
        self.vehicles["v3"].cluster = 2

        self.rsu_pos = (400.0, 400.0)

    def test_euclidean_distance(self):
        d = euclidean_distance((0, 0), (3, 4))
        self.assertEqual(d, 5.0)

    def test_find_route_flow(self):
        # Route should flow: Accident Vehicle (v0) -> CH (v0) -> CH (v2) -> CH (v3) -> RSU (RSU_1)
        route = self.routing_engine.find_route(
            accident_vehicle_id="v0",
            vehicles=self.vehicles,
            cluster_heads=self.cluster_heads,
            rsu_pos=self.rsu_pos,
            rsu_id="RSU_1"
        )

        expected = [
            "Accident Vehicle (v0)",
            "CH (v0)",
            "CH (v2)",
            "CH (v3)",
            "RSU (RSU_1)"
        ]
        self.assertEqual(route, expected)

    def test_loop_avoidance(self):
        # Add candidate CH that could create potential loop if visited twice
        route = self.routing_engine.find_route(
            accident_vehicle_id="v0",
            vehicles=self.vehicles,
            cluster_heads=self.cluster_heads,
            rsu_pos=self.rsu_pos,
            rsu_id="RSU_1"
        )
        # Check no duplicate node entries in route
        self.assertEqual(len(route), len(set(route)))

    def test_route_message_and_broadcast_integration(self):
        msg = self.accident_mgr.trigger_accident("v0", self.vehicles, step=1)
        route, ack = self.routing_engine.route_message(
            message=msg,
            vehicles=self.vehicles,
            cluster_heads=self.cluster_heads,
            rsu_pos=self.rsu_pos,
            rsu_id="RSU_1",
            broadcast_manager=self.broadcast_mgr
        )
        self.assertIn("RSU (RSU_1)", route)
        self.assertIn(msg.message_id, self.broadcast_mgr.message_cache)

        # Test duplicate message broadcast handling
        route2, ack2 = self.routing_engine.route_message(
            message=msg,
            vehicles=self.vehicles,
            cluster_heads=self.cluster_heads,
            rsu_pos=self.rsu_pos,
            rsu_id="RSU_1",
            broadcast_manager=self.broadcast_mgr
        )



if __name__ == "__main__":
    unittest.main()
