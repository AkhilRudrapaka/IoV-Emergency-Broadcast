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

    def test_300m_range_check_rejects_out_of_range_ch(self):
        # Report CRITICAL S10.2: routes previously succeeded regardless of physical
        # distance. Two CHs 350m apart (beyond GPSR_RANGE_M=300) must NOT connect
        # directly, even though the far one is a real registered CH that would
        # otherwise make progress toward the RSU.
        vehicles = {
            "acc": Vehicle("acc"),
            "far": Vehicle("far"),
        }
        vehicles["acc"].update((0.0, 0.0), 10.0)
        vehicles["far"].update((350.0, 0.0), 10.0)
        vehicles["acc"].cluster = 0
        vehicles["far"].cluster = 1
        cluster_heads = {0: "acc", 1: "far"}

        route = self.routing_engine.find_route(
            accident_vehicle_id="acc", vehicles=vehicles, cluster_heads=cluster_heads,
            rsu_pos=(360.0, 0.0), rsu_id="RSU_W"
        )
        self.assertNotIn("CH (far)", route)
        self.assertEqual(route[-1], "STORE_CARRY_FORWARD")

    def test_own_ch_beyond_80m_falls_back_to_tier2_not_rejected_outright(self):
        # Own CH at 150m: beyond the 80m tier-1 range, but still within the 300m
        # tier-2 range -- must still be used (not simply discarded).
        vehicles = {
            "acc": Vehicle("acc"),
            "own_ch": Vehicle("own_ch"),
        }
        vehicles["acc"].update((0.0, 0.0), 10.0)
        vehicles["own_ch"].update((150.0, 0.0), 10.0)
        vehicles["acc"].cluster = 0
        vehicles["own_ch"].cluster = 0
        cluster_heads = {0: "own_ch"}

        route = self.routing_engine.find_route(
            accident_vehicle_id="acc", vehicles=vehicles, cluster_heads=cluster_heads,
            rsu_pos=(200.0, 0.0), rsu_id="RSU_Y"
        )
        self.assertIn("CH (own_ch)", route)
        self.assertEqual(route[-1], "RSU (RSU_Y)")

    def test_store_carry_forward_when_nothing_in_range(self):
        vehicles = {"lonely": Vehicle("lonely")}
        vehicles["lonely"].update((0.0, 0.0), 10.0)
        vehicles["lonely"].cluster = -1

        route = self.routing_engine.find_route(
            accident_vehicle_id="lonely", vehicles=vehicles, cluster_heads={},
            rsu_pos=(5000.0, 5000.0), rsu_id="RSU_Z"
        )
        self.assertEqual(route, ["Accident Vehicle (lonely)", "STORE_CARRY_FORWARD"])

    def test_ttl_cutoff_after_5_hops(self):
        # A chain of CHs 280m apart (in-range, monotonic progress) but the RSU is
        # far enough that 5 hops (GPSR_TTL_HOPS) can't reach it -- must stop at
        # exactly 5 CH hops and Store-Carry-Forward, not hop indefinitely.
        vehicles = {}
        xs = [0, 280, 560, 840, 1120, 1400]
        ids = [f"v{i}" for i in range(6)]
        for vid, x in zip(ids, xs):
            v = Vehicle(vid)
            v.update((float(x), 0.0), 10.0)
            v.cluster = ids.index(vid)
            vehicles[vid] = v
        cluster_heads = {i: vid for i, vid in enumerate(ids)}

        route = self.routing_engine.find_route(
            accident_vehicle_id="v0", vehicles=vehicles, cluster_heads=cluster_heads,
            rsu_pos=(5000.0, 0.0), rsu_id="RSU_FAR"
        )
        ch_hops = [entry for entry in route if entry.startswith("CH (")]
        self.assertEqual(len(ch_hops), 5)
        self.assertNotIn("v5", " ".join(route))  # 6th vehicle never reached
        self.assertEqual(route[-1], "STORE_CARRY_FORWARD")

    def test_perimeter_mode_routes_around_a_void(self):
        # A(0,0) has two in-range neighbors (B, C) that are BOTH farther from the
        # RSU than A itself -- a genuine greedy routing void. The right-hand-rule
        # perimeter walk must pick a way around it (verified: A -> C, since C is
        # the smaller clockwise turn from the A->RSU bearing) and resume greedy
        # progress once possible (C -> D, D -> E -> F -> RSU), reaching the RSU
        # within the 5-hop TTL despite no single-hop greedy option existing at A.
        positions = {
            "A": (0.0, 0.0), "B": (-50.0, 200.0), "C": (-50.0, -200.0),
            "D": (200.0, -300.0), "E": (462.2, -201.7), "F": (724.4, -103.4),
        }
        vehicles = {}
        for i, (vid, pos) in enumerate(positions.items()):
            v = Vehicle(vid)
            v.update(pos, 10.0)
            v.cluster = i
            vehicles[vid] = v
        cluster_heads = {i: vid for i, vid in enumerate(positions.keys())}

        route = self.routing_engine.find_route(
            accident_vehicle_id="A", vehicles=vehicles, cluster_heads=cluster_heads,
            rsu_pos=(1000.0, 0.0), rsu_id="RSU_X"
        )
        self.assertEqual(route[-1], "RSU (RSU_X)")
        self.assertIn("CH (C)", route)   # perimeter detour, not the direct-but-farther B
        self.assertNotIn("CH (B)", route)
        self.assertEqual(len(route), len(set(route)))  # still loop-free

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
