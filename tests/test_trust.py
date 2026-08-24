import unittest

from vehicle import Vehicle
from trust import TrustManager


class TestTrustModule(unittest.TestCase):
    """
    Regression coverage for trust.py's Bayesian Trust Model (Algorithm 1, Report-
    aligned): Trust(v) = 0.30*Tf + 0.25*Tc + 0.20*Ts + 0.25*Th, with a persistent
    RSU boost (0.80*Trust + 0.20*rsu_trust_assessment). Also proves the
    ground-truth oracle leak stays fixed -- is_malicious/attack_type must never be
    read by calculate_trust() or the classification logic.
    """

    def setUp(self):
        self.trust_manager = TrustManager()

    def test_no_observed_behavior_is_neutral_regardless_of_ground_truth(self):
        honest = Vehicle("v_honest")
        malicious = Vehicle("v_malicious")
        malicious.is_malicious = True
        malicious.attack_type = "PACKET_DROP"

        t_honest = self.trust_manager.calculate_trust(honest, {})
        t_malicious = self.trust_manager.calculate_trust(malicious, {})

        # With zero forward/message/speed events observed for either vehicle,
        # trust must be identical -- proving the score never reads is_malicious.
        self.assertEqual(t_honest, t_malicious)

    def test_classification_not_forced_by_is_malicious_flag(self):
        malicious = Vehicle("v_malicious")
        malicious.is_malicious = True
        malicious.attack_type = "FAKE_ALERT"

        self.trust_manager.calculate_trust(malicious, {})

        # A malicious vehicle with no observed misbehavior this run must not be
        # forced into the MALICIOUS classification (that would be the oracle leak).
        self.assertNotEqual(malicious.classification, "MALICIOUS")
        self.assertFalse(malicious.is_blacklisted)

    def test_observed_failures_reduce_trust_and_trigger_blacklist(self):
        v = Vehicle("v_dropper")
        v.is_malicious = True
        v.attack_type = "PACKET_DROP"

        # Simulate full compromise across every observable channel: forwarding
        # failures (Tf), a forged message location (Tc), erratic speed (Ts), and
        # repeated failed RSU verification, evaluated across several steps so the
        # EMA historical component converges -- mirrors real per-step usage.
        v.has_reported_message = True
        v.location_consistency_error_m = 500.0
        for i in range(15):
            self.trust_manager.update_behavior_event(v, "FORWARD", is_success=False)
            v.prev_speed = 0.0
            v.speed = 20.0 if i % 2 == 0 else 0.0  # erratic jump every step
            self.trust_manager.apply_rsu_feedback(v, is_success=False, nudge=0.05)
            self.trust_manager.calculate_trust(v, {})

        self.assertLess(v.trust, 0.3)
        self.assertEqual(v.classification, "MALICIOUS")
        self.assertTrue(v.is_blacklisted)

    def test_observed_successful_forwards_keep_trust_high(self):
        v = Vehicle("v_good_forwarder")
        for _ in range(10):
            self.trust_manager.update_behavior_event(v, "FORWARD", is_success=True)
            self.trust_manager.calculate_trust(v, {})

        self.assertGreaterEqual(v.trust, 0.7)
        self.assertEqual(v.classification, "TRUSTED")

    def test_update_behavior_event_counters(self):
        v = Vehicle("v1")
        self.trust_manager.update_behavior_event(v, "FORWARD", is_success=True)
        self.trust_manager.update_behavior_event(v, "FORWARD", is_success=False)
        self.trust_manager.update_behavior_event(v, "AUTH", is_success=True)
        self.trust_manager.update_behavior_event(v, "RECEIVE")

        self.assertEqual(v.forward_attempts, 2)
        self.assertEqual(v.successful_forwards, 1)
        self.assertEqual(v.auth_attempts, 1)
        self.assertEqual(v.auth_successes, 1)
        self.assertEqual(v.total_received, 1)

    def test_historical_trust_ema_smooths_toward_current_score(self):
        v = Vehicle("v1")
        v.historical_trust = 0.5

        for _ in range(3):
            self.trust_manager.update_behavior_event(v, "FORWARD", is_success=True)
        first = self.trust_manager.calculate_trust(v, {})
        second = self.trust_manager.calculate_trust(v, {})

        # Repeated good behavior should keep pushing historical (and therefore
        # composite) trust upward via EMA.
        self.assertGreaterEqual(second, first)

    def test_speed_plausibility_penalizes_erratic_speed_change(self):
        smooth = Vehicle("v_smooth")
        smooth.prev_speed = 10.0
        smooth.speed = 12.0  # delta=2.0, within MAX_SPEED_DELTA_PER_STEP_MPS

        erratic = Vehicle("v_erratic")
        erratic.prev_speed = 10.0
        erratic.speed = 0.0  # delta=10.0, well beyond the plausible bound

        t_smooth = self.trust_manager.calculate_trust(smooth, {})
        t_erratic = self.trust_manager.calculate_trust(erratic, {})

        self.assertGreater(t_smooth, t_erratic)

    def test_message_consistency_penalizes_location_forgery(self):
        honest_sender = Vehicle("v_honest_sender")
        honest_sender.has_reported_message = True
        honest_sender.location_consistency_error_m = 0.0

        forger = Vehicle("v_forger")
        forger.has_reported_message = True
        forger.location_consistency_error_m = 400.0  # well beyond tolerance

        t_honest = self.trust_manager.calculate_trust(honest_sender, {})
        t_forger = self.trust_manager.calculate_trust(forger, {})

        self.assertGreater(t_honest, t_forger)

    def test_message_consistency_neutral_when_no_message_reported(self):
        v = Vehicle("v_silent")
        # has_reported_message stays False -- no evidence yet, not penalized.
        trust_no_report = self.trust_manager.calculate_trust(v, {})

        v2 = Vehicle("v_consistent")
        v2.has_reported_message = True
        v2.location_consistency_error_m = 0.0
        trust_consistent = self.trust_manager.calculate_trust(v2, {})

        # A vehicle that hasn't reported anything should not score worse than one
        # that reported and was perfectly consistent.
        self.assertLessEqual(trust_no_report, trust_consistent)

    def test_rsu_feedback_persists_and_blends_into_trust(self):
        v = Vehicle("v1")
        self.assertEqual(v.rsu_trust_assessment, 0.5)

        for _ in range(5):
            self.trust_manager.apply_rsu_feedback(v, is_success=True, nudge=0.05)

        # The persistent assessment itself must have moved and stayed moved --
        # not been reset by anything else touching the vehicle.
        self.assertGreater(v.rsu_trust_assessment, 0.5)
        assessment_after_feedback = v.rsu_trust_assessment

        trust = self.trust_manager.calculate_trust(v, {})

        # calculate_trust() must not reset the persistent RSU assessment, and the
        # final trust must reflect its blend (0.80*Trust + 0.20*rsu_assessment).
        self.assertEqual(v.rsu_trust_assessment, assessment_after_feedback)
        self.assertGreater(trust, 0.5)


if __name__ == "__main__":
    unittest.main()
