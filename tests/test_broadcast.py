import unittest

from vehicle import Vehicle
from messaging import EmergencyMessage
from broadcast import BroadcastManager
from trust import TrustManager


class TestMajorityVoteConfirmation(unittest.TestCase):
    """
    HIGH priority, Report S10.2: a Cluster Head must withhold forwarding unless
    more than 50% of its own cluster members corroborate the event (within the
    message's real alert radius, or themselves reacting to it).
    """

    def setUp(self):
        self.bm = BroadcastManager()
        self.trust_manager = TrustManager()

    def _make_cluster(self, ch_pos=(0.0, 0.0), member_positions=(), n_far=0):
        vehicles = {"ch": Vehicle("ch")}
        vehicles["ch"].update(ch_pos, 10.0)
        vehicles["ch"].cluster = 0
        vehicles["ch"].trust = 0.8
        member_ids = []
        for i, pos in enumerate(member_positions):
            vid = f"m{i}"
            v = Vehicle(vid)
            v.update(pos, 10.0)
            vehicles[vid] = v
            member_ids.append(vid)
        clusters = {0: ["ch"] + member_ids}
        return vehicles, clusters

    def test_majority_confirmed_forwards(self):
        # 3 of 4 members within the alert radius -> majority confirms, CH forwards.
        vehicles, clusters = self._make_cluster(member_positions=[
            (10.0, 0.0), (20.0, 0.0), (30.0, 0.0), (5000.0, 5000.0)
        ])
        msg = EmergencyMessage(sender="ch", location=(0.0, 0.0), severity="HIGH")  # radius=400
        forwarded = self.bm.broadcast_route(msg, ["CH (ch)"], vehicles=vehicles, clusters=clusters)
        self.assertTrue(forwarded)

    def test_minority_confirmed_withholds(self):
        # Only 1 of 4 members within range -> no majority, CH withholds.
        vehicles, clusters = self._make_cluster(member_positions=[
            (10.0, 0.0), (5000.0, 5000.0), (5000.0, -5000.0), (-5000.0, 5000.0)
        ])
        msg = EmergencyMessage(sender="ch", location=(0.0, 0.0), severity="HIGH")
        forwarded = self.bm.broadcast_route(msg, ["CH (ch)"], vehicles=vehicles, clusters=clusters)
        self.assertFalse(forwarded)

    def test_braking_members_count_as_confirming(self):
        # Members far away geographically, but already reacting to the accident
        # (is_braking, real congestion state from accident.py) still confirm.
        vehicles, clusters = self._make_cluster(member_positions=[
            (5000.0, 5000.0), (5000.0, -5000.0), (-5000.0, 5000.0)
        ])
        for vid in ("m0", "m1", "m2"):
            vehicles[vid].is_braking = True
        msg = EmergencyMessage(sender="ch", location=(0.0, 0.0), severity="HIGH")
        forwarded = self.bm.broadcast_route(msg, ["CH (ch)"], vehicles=vehicles, clusters=clusters)
        self.assertTrue(forwarded)

    def test_no_cluster_info_does_not_block(self):
        # Backward compatibility: omitting `clusters` (e.g. older call sites)
        # must not silently block every forward.
        vehicles = {"ch": Vehicle("ch")}
        vehicles["ch"].update((0.0, 0.0), 10.0)
        msg = EmergencyMessage(sender="ch", location=(0.0, 0.0), severity="HIGH")
        forwarded = self.bm.broadcast_route(msg, ["CH (ch)"], vehicles=vehicles, clusters=None)
        self.assertTrue(forwarded)

    def test_unclustered_ch_not_blocked(self):
        vehicles = {"ch": Vehicle("ch")}
        vehicles["ch"].update((0.0, 0.0), 10.0)
        vehicles["ch"].cluster = -1
        msg = EmergencyMessage(sender="ch", location=(0.0, 0.0), severity="HIGH")
        forwarded = self.bm.broadcast_route(msg, ["CH (ch)"], vehicles=vehicles, clusters={})
        self.assertTrue(forwarded)


if __name__ == "__main__":
    unittest.main()
