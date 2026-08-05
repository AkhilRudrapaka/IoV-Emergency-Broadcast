import unittest
from vehicle import Vehicle
from neighbor_discovery import NeighborManager, euclidean_distance


class TestNeighborDiscovery(unittest.TestCase):

    def setUp(self):
        self.neighbor_mgr = NeighborManager(comm_range=100.0)
        self.vehicles = {
            "v1": Vehicle("v1"),
            "v2": Vehicle("v2"),
            "v3": Vehicle("v3")
        }
        # v1 and v2 are 50m apart (within 100m)
        self.vehicles["v1"].update((0.0, 0.0), 10.0)
        self.vehicles["v2"].update((50.0, 0.0), 12.0)
        # v3 is 300m away from v1 (outside 100m)
        self.vehicles["v3"].update((300.0, 0.0), 15.0)

    def test_euclidean_distance(self):
        self.assertEqual(euclidean_distance((0, 0), (0, 50)), 50.0)

    def test_discover_neighbors(self):
        n_map = self.neighbor_mgr.discover_neighbors(self.vehicles)

        self.assertIn("v2", self.vehicles["v1"].neighbors)
        self.assertIn("v1", self.vehicles["v2"].neighbors)
        self.assertNotIn("v3", self.vehicles["v1"].neighbors)
        self.assertNotIn("v1", self.vehicles["v3"].neighbors)

        self.assertEqual(n_map["v1"], ["v2"])
        self.assertEqual(n_map["v2"], ["v1"])
        self.assertEqual(n_map["v3"], [])

    def test_get_neighbors(self):
        self.neighbor_mgr.discover_neighbors(self.vehicles)
        n = self.neighbor_mgr.get_neighbors("v1", self.vehicles)
        self.assertEqual(n, ["v2"])


if __name__ == "__main__":
    unittest.main()
