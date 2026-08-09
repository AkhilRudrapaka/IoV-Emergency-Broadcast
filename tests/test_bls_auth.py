import unittest

from vehicle import Vehicle
from messaging import EmergencyMessage
from rsu import RSUManager
from authentication import sign_message, verify_signature as legacy_verify_signature
from bls_auth import BLSKeyPair, BLSAuthenticator, AuthenticationManager


class TestBLSAuthenticatorCore(unittest.TestCase):
    """Low-level BLS sign/verify/batch-verify correctness."""

    def test_sign_and_verify_roundtrip(self):
        bls = BLSAuthenticator()
        kp = BLSKeyPair()
        payload = b"emergency-alert-1"
        sig = bls.sign(payload, kp)

        self.assertEqual(len(sig), 96)
        self.assertTrue(bls.verify(payload, sig, kp.public_key))

    def test_tampered_payload_fails(self):
        bls = BLSAuthenticator()
        kp = BLSKeyPair()
        sig = bls.sign(b"original-payload", kp)

        self.assertFalse(bls.verify(b"tampered-payload", sig, kp.public_key))

    def test_verify_batch_all_valid(self):
        bls = BLSAuthenticator()
        kps = [BLSKeyPair() for _ in range(3)]
        payloads = [f"msg-{i}".encode() for i in range(3)]
        sigs = [bls.sign(p, kp) for p, kp in zip(payloads, kps)]
        pks = [kp.public_key for kp in kps]

        all_valid, per_item = bls.verify_batch(payloads, sigs, pks)
        self.assertTrue(all_valid)
        self.assertEqual(per_item, [True, True, True])

    def test_verify_batch_detects_tampered_member(self):
        bls = BLSAuthenticator()
        kps = [BLSKeyPair() for _ in range(3)]
        payloads = [f"msg-{i}".encode() for i in range(3)]
        sigs = [bls.sign(p, kp) for p, kp in zip(payloads, kps)]
        pks = [kp.public_key for kp in kps]

        # Verifier reconstructs a different payload for item 1 than what was actually signed
        tampered_payloads = list(payloads)
        tampered_payloads[1] = b"forged-message"

        all_valid, per_item = bls.verify_batch(tampered_payloads, sigs, pks)
        self.assertFalse(all_valid)
        self.assertEqual(per_item, [True, False, True])

    def test_performance_summary_tracks_calls(self):
        bls = BLSAuthenticator()
        kp = BLSKeyPair()
        sig = bls.sign(b"payload", kp)
        bls.verify(b"payload", sig, kp.public_key)

        summary = bls.get_performance_summary()
        self.assertEqual(summary["signature_size_bytes"], 96)
        self.assertEqual(summary["public_key_size_bytes"], 48)
        self.assertEqual(summary["total_signs"], 1)
        self.assertEqual(summary["total_individual_verifies"], 1)


class TestAuthenticationManagerModes(unittest.TestCase):

    def setUp(self):
        self.msg = EmergencyMessage(sender="v1", location=(10.0, 20.0), severity="HIGH")
        self.vehicles = {
            "v1": self._make_vehicle("v1", trust=0.9),
            "v2": self._make_vehicle("v2", trust=0.85),
            "v3": self._make_vehicle("v3", trust=0.2),  # low-trust
        }
        self.cluster_heads = {0: "v2", 1: "v3"}

    def _make_vehicle(self, vid, trust):
        v = Vehicle(vid)
        v.trust = trust
        return v

    def test_none_mode_always_passes(self):
        mgr = AuthenticationManager(mode="none")
        ok, perf = mgr.verify_message(self.msg, self.vehicles)
        self.assertTrue(ok)
        self.assertIsNone(perf)

    def test_baseline_mode_matches_legacy_authenticator(self):
        sign_message(self.msg)  # SHA-256 baseline signature, unchanged path
        mgr = AuthenticationManager(mode="baseline")

        ok, _ = mgr.verify_message(self.msg, self.vehicles)
        self.assertTrue(ok)
        self.assertTrue(legacy_verify_signature(self.msg))

        self.msg.location = (0.0, 0.0)  # tamper
        ok2, _ = mgr.verify_message(self.msg, self.vehicles)
        self.assertFalse(ok2)

    def test_sign_emergency_broadcast_populates_chain(self):
        mgr = AuthenticationManager(mode="bls_batch")
        mgr.sign_emergency_broadcast(
            self.msg, sender_vehicle_id="v1", cluster_heads=self.cluster_heads, vehicles=self.vehicles
        )

        self.assertEqual(len(self.msg.chain_signatures), 3)  # sender v1 + CH v2 + CH v3
        roles = {(e["signer_id"], e["role"]) for e in self.msg.chain_signatures}
        self.assertIn(("v1", "SENDER"), roles)
        self.assertIn(("v2", "FORWARDING_CH"), roles)
        self.assertIn(("v3", "FORWARDING_CH"), roles)

    def test_bls_individual_mode_validates_correctly(self):
        mgr = AuthenticationManager(mode="bls_individual")
        mgr.sign_emergency_broadcast(
            self.msg, sender_vehicle_id="v1", cluster_heads=self.cluster_heads, vehicles=self.vehicles
        )

        ok, perf = mgr.verify_message(self.msg, self.vehicles)
        self.assertTrue(ok)
        self.assertIsNotNone(perf)

        self.msg.severity = "LOW"  # tamper after signing
        ok2, _ = mgr.verify_message(self.msg, self.vehicles)
        self.assertFalse(ok2)

    def test_bls_batch_mode_trust_gating_individually_verifies_low_trust(self):
        mgr = AuthenticationManager(mode="bls_batch", trust_threshold=0.7, reject_low_trust=False)
        mgr.sign_emergency_broadcast(
            self.msg, sender_vehicle_id="v1", cluster_heads=self.cluster_heads, vehicles=self.vehicles
        )

        ok, perf = mgr.verify_message(self.msg, self.vehicles)
        self.assertTrue(ok)
        self.assertEqual(perf["high_trust_count"], 2)  # v1 (SENDER), v2 (CH)
        self.assertEqual(perf["low_trust_count"], 1)   # v3 (CH)

    def test_bls_batch_mode_rejects_low_trust_when_configured(self):
        mgr = AuthenticationManager(mode="bls_batch", trust_threshold=0.7, reject_low_trust=True)
        mgr.sign_emergency_broadcast(
            self.msg, sender_vehicle_id="v1", cluster_heads=self.cluster_heads, vehicles=self.vehicles
        )

        ok, _ = mgr.verify_message(self.msg, self.vehicles)
        self.assertFalse(ok)  # low-trust v3 rejected outright -> overall auth fails

    def test_bls_batch_mode_detects_tampering(self):
        mgr = AuthenticationManager(mode="bls_batch", trust_threshold=0.7, reject_low_trust=False)
        mgr.sign_emergency_broadcast(
            self.msg, sender_vehicle_id="v1", cluster_heads=self.cluster_heads, vehicles=self.vehicles
        )

        self.msg.location = (999.0, 999.0)  # tamper after signing
        ok, _ = mgr.verify_message(self.msg, self.vehicles)
        self.assertFalse(ok)


class TestRSUBLSIntegration(unittest.TestCase):
    """End-to-end: AuthenticationManager wired into RSU.receive_and_process_message."""

    def _make_vehicle(self, vid, trust, pos):
        v = Vehicle(vid)
        v.update(pos, speed=10.0)
        v.trust = trust
        return v

    def test_rsu_accepts_valid_bls_batch(self):
        vehicles = {
            "v1": self._make_vehicle("v1", trust=0.9, pos=(10.0, 10.0)),
            "v2": self._make_vehicle("v2", trust=0.9, pos=(20.0, 20.0)),
        }
        rsu = RSUManager(deploy_default_rsus=False).add_rsu("RSU_TEST", (0.0, 0.0))

        msg = EmergencyMessage(sender="v1", location=(10.0, 10.0), severity="HIGH")
        mgr = AuthenticationManager(mode="bls_batch")
        mgr.sign_emergency_broadcast(msg, sender_vehicle_id="v1", cluster_heads={0: "v2"}, vehicles=vehicles)

        ack = rsu.receive_and_process_message(msg, vehicles=vehicles, auth_manager=mgr)
        self.assertIsNotNone(ack)
        self.assertEqual(rsu.get_log()[0]["status"], "VERIFIED")

    def test_rsu_rejects_tampered_bls_batch(self):
        vehicles = {
            "v1": self._make_vehicle("v1", trust=0.9, pos=(10.0, 10.0)),
            "v2": self._make_vehicle("v2", trust=0.9, pos=(20.0, 20.0)),
        }
        rsu = RSUManager(deploy_default_rsus=False).add_rsu("RSU_TEST", (0.0, 0.0))

        msg = EmergencyMessage(sender="v1", location=(10.0, 10.0), severity="HIGH")
        mgr = AuthenticationManager(mode="bls_batch")
        mgr.sign_emergency_broadcast(msg, sender_vehicle_id="v1", cluster_heads={0: "v2"}, vehicles=vehicles)

        msg.location = (500.0, 500.0)  # tamper after signing, before RSU delivery
        ack = rsu.receive_and_process_message(msg, vehicles=vehicles, auth_manager=mgr)
        self.assertIsNone(ack)
        self.assertEqual(rsu.get_log()[0]["status"], "REJECTED")


class TestBatchPerformanceSanity(unittest.TestCase):
    """Correctness-equivalence: batch verification must agree with N individual verifies."""

    def test_batch_matches_individual_results(self):
        bls = BLSAuthenticator()
        kps = [BLSKeyPair() for _ in range(3)]
        payloads = [f"perf-msg-{i}".encode() for i in range(3)]
        sigs = [bls.sign(p, kp) for p, kp in zip(payloads, kps)]
        pks = [kp.public_key for kp in kps]

        individual_results = [bls.verify(p, s, pk) for p, s, pk in zip(payloads, sigs, pks)]
        batch_valid, batch_results = bls.verify_batch(payloads, sigs, pks)

        self.assertEqual(individual_results, [True, True, True])
        self.assertTrue(batch_valid)
        self.assertEqual(batch_results, individual_results)

        summary = bls.get_performance_summary()
        self.assertGreater(summary["total_individual_verifies"], 0)
        self.assertGreater(summary["total_batches"], 0)


if __name__ == "__main__":
    unittest.main()
