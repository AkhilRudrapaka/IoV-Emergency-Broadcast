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

        # RSU within GPSR's 300m wireless range of v1 (10.0, 10.0) -- routes beyond
        # that range are correctly Store-Carry-Forward, not a magic direct hop.
        msg = EmergencyMessage(sender="v1", location=(10.0, 10.0), severity="HIGH")
        route, ack = routing_engine.route_message(
            message=msg,
            vehicles=self.vehicles,
            cluster_heads=cluster_heads,
            rsu_pos=(150.0, 150.0),
            rsu_id="RSU_NORTH",
            rsu_manager=self.rsu_manager
        )

        self.assertIsNotNone(ack)
        self.assertEqual(ack["rsu_id"], "RSU_NORTH")
        self.assertIn("RSU (RSU_NORTH)", route)


if __name__ == "__main__":
    unittest.main()
