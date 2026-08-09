import unittest
from vehicle import Vehicle
from accident import AccidentManager
from messaging import EmergencyMessage


class TestAccidentManager(unittest.TestCase):

    def setUp(self):
        self.accident_mgr = AccidentManager()
        self.vehicles = {
            "v1": Vehicle("v1"),
            "v2": Vehicle("v2"),
            "v3": Vehicle("v3")
        }
        self.vehicles["v1"].update((100.0, 200.0), 15.5)
        self.vehicles["v2"].update((150.0, 250.0), 20.0)

    def test_trigger_accident_success(self):
        msg = self.accident_mgr.trigger_accident("v1", self.vehicles, step=10, severity="HIGH")

        self.assertIsNotNone(msg)
        self.assertIsInstance(msg, EmergencyMessage)
        self.assertEqual(msg.sender, "v1")
        self.assertEqual(msg.location, (100.0, 200.0))
        self.assertEqual(msg.severity, "HIGH")

        self.assertEqual(self.vehicles["v1"].speed, 0.0)
        self.assertTrue(self.vehicles["v1"].is_accident)
        self.assertTrue(self.accident_mgr.is_in_accident("v1"))

    def test_trigger_accident_invalid_vehicle(self):
        msg = self.accident_mgr.trigger_accident("v99", self.vehicles, step=5)
        self.assertIsNone(msg)
        self.assertFalse(self.accident_mgr.is_in_accident("v99"))

    def test_active_accidents_and_clear(self):
        self.accident_mgr.trigger_accident("v1", self.vehicles, step=10)
        self.accident_mgr.trigger_accident("v2", self.vehicles, step=12)

        active = self.accident_mgr.get_active_accidents()
        self.assertEqual(len(active), 2)
        self.assertIn("v1", active)
        self.assertIn("v2", active)

        self.accident_mgr.clear_accident("v1", self.vehicles)
        self.assertFalse(self.accident_mgr.is_in_accident("v1"))
        self.assertFalse(self.vehicles["v1"].is_accident)
        self.assertEqual(len(self.accident_mgr.get_active_accidents()), 1)


if __name__ == "__main__":
    unittest.main()
