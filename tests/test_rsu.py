import unittest
from vehicle import Vehicle
from messaging import EmergencyMessage
from rsu import RSU, RSUManager
from routing import RoutingEngine


class TestRSUModule(unittest.TestCase):

    def setUp(self):
        self.rsu_manager = RSUManager()
        self.rsu1 = self.rsu_manager.add_rsu("RSU_NORTH", (200.0, 400.0))
        self.rsu2 = self.rsu_manager.add_rsu("RSU_SOUTH", (200.0, 0.0))

        self.vehicles = {
            "v1": Vehicle("v1"),
            "v2": Vehicle("v2")
        }
        self.vehicles["v1"].update((10.0, 10.0), 10.0)
        self.vehicles["v2"].update((100.0, 100.0), 12.0)

    def test_fixed_rsu_positions(self):
        self.assertEqual(self.rsu1.position, (200.0, 400.0))
        self.assertEqual(self.rsu2.position, (200.0, 0.0))

    def test_verify_sender_valid(self):
        self.assertTrue(self.rsu1.verify_sender("v1", self.vehicles))

    def test_verify_sender_invalid(self):
        self.assertFalse(self.rsu1.verify_sender("v999", self.vehicles))

    def test_receive_message_and_ack(self):
        msg = EmergencyMessage(sender="v1", location=(10.0, 10.0), severity="HIGH")
        ack = self.rsu1.receive_message(msg, vehicles=self.vehicles)

        self.assertIsNotNone(ack)
        self.assertEqual(ack["status"], "DELIVERED")
        self.assertEqual(ack["target_sender"], "v1")
        self.assertEqual(ack["rsu_id"], "RSU_NORTH")

        log = self.rsu1.get_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["status"], "VERIFIED")
        self.assertTrue(log[0]["ack_sent"])

    def test_reject_unverified_sender(self):
        msg = EmergencyMessage(sender="unregistered_vehicle", location=(10.0, 10.0), severity="HIGH")
        ack = self.rsu1.receive_message(msg, vehicles=self.vehicles)

        self.assertIsNone(ack)
        log = self.rsu1.get_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["status"], "REJECTED")
        self.assertFalse(log[0]["ack_sent"])

    def test_cross_rsu_dedup_by_message_id(self):
        # HIGH priority, Report S10.2: the same accident UUID must be verified
        # only once, even if it's reported/delivered more than once.
        self.assertFalse(self.rsu_manager.is_duplicate_event("MSG_v1_abc123"))

        msg = EmergencyMessage(sender="v1", location=(10.0, 10.0), severity="HIGH")
        first_ack = self.rsu1.receive_message(msg, vehicles=self.vehicles)
        self.rsu_manager.record_processed_event(msg.message_id, first_ack)

        self.assertTrue(self.rsu_manager.is_duplicate_event(msg.message_id))
        self.assertEqual(self.rsu_manager.get_cached_ack(msg.message_id), first_ack)

    def test_routing_engine_integration(self):
        routing_engine = RoutingEngine()
        cluster_heads = {0: "v1"}
        self.vehicles["v1"].cluster = 0

        # v1 sits at (10, 10). Of the RSUs this manager actually deploys, only
        # RSU_SOUTH (200, 0) is inside GPSR's 300 m range (190.3 m); RSU_NORTH
        # (200, 400) is 433.8 m away and genuinely unreachable. The engine
        # delivers to the nearest RSU that is really in range, rather than to a
        # caller-supplied hint that contradicts the deployment -- routes beyond
        # range stay Store-Carry-Forward, never a magic direct hop.
        msg = EmergencyMessage(sender="v1", location=(10.0, 10.0), severity="HIGH")
        route, ack = routing_engine.route_message(
            message=msg,
            vehicles=self.vehicles,
            cluster_heads=cluster_heads,
            rsu_manager=self.rsu_manager
        )

        self.assertIsNotNone(ack)
        self.assertEqual(ack["rsu_id"], "RSU_SOUTH")
        self.assertIn("RSU (RSU_SOUTH)", route)

    def test_delivers_to_reachable_rsu_not_preselected_one(self):
        """
        Regression test for the multi-RSU delivery defect: find_route() picks its
        greedy/perimeter target RSU once, from the ACCIDENT's position. A message
        that hops into a DIFFERENT RSU's coverage must be delivered there rather
        than declared Store-Carry-Forward. Measured before the fix: at density 150,
        5 of 5 SCF failures had another RSU within 300 m of the dead route's end.
        """
        routing_engine = RoutingEngine()

        # Geometry (verified numerically, not eyeballed):
        #   v1 (445, 780) is out of range of EVERY RSU -- nearest is RSU_CENTER at
        #     335.0 m -- so RSU_CENTER becomes the preselected greedy target and
        #     the direct RSU-as-CH tier correctly cannot fire.
        #   v2 (200, 690) is a Cluster Head 261.0 m from v1, so tier 2 selects it.
        #   From v2, the PRESELECTED RSU_CENTER is 346.5 m away (out of range) --
        #     the old single-target check declared Store-Carry-Forward here -- but
        #     RSU_WEST is 287.3 m away and genuinely reachable.
        self.vehicles["v1"].update((445.0, 780.0), 10.0)
        self.vehicles["v2"].update((200.0, 690.0), 10.0)
        self.vehicles["v2"].trust = 0.9
        self.vehicles["v1"].cluster = 0
        cluster_heads = {0: "v2"}

        route = routing_engine.find_route(
            accident_vehicle_id="v1",
            vehicles=self.vehicles,
            cluster_heads=cluster_heads,
            rsu_manager=self.rsu_manager
        )

        self.assertIn("CH (v2)", route)
        self.assertEqual(route[-1], "RSU (RSU_WEST)")
        self.assertNotIn("STORE_CARRY_FORWARD", route)


if __name__ == "__main__":
    unittest.main()
