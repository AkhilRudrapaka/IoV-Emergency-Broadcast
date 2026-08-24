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
            "v3": self._make_vehicle("v3", trust=0.5),  # mid-trust (0.3 <= T < 0.7)
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

    def test_max_chain_signers_cap_prefers_highest_trust(self):
        # Report S6: CH pre-screening limit (~14 signers, 100ms deadline / ~7ms per
        # signature). With more active CHs than the cap allows, only the
        # highest-trust ones (plus the sender) get to co-sign.
        vehicles = {"v1": self._make_vehicle("v1", trust=0.9)}
        cluster_heads = {}
        for i in range(20):
            vid = f"ch{i}"
            vehicles[vid] = self._make_vehicle(vid, trust=round(0.5 + i * 0.01, 2))
            cluster_heads[i] = vid

        mgr = AuthenticationManager(mode="bls_batch")
        msg = EmergencyMessage(sender="v1", location=(0.0, 0.0), severity="HIGH")
        mgr.sign_emergency_broadcast(msg, sender_vehicle_id="v1", cluster_heads=cluster_heads, vehicles=vehicles)

        self.assertEqual(len(msg.chain_signatures), 14)  # sender + 13 highest-trust CHs
        signer_ids = {e["signer_id"] for e in msg.chain_signatures}
        self.assertIn("v1", signer_ids)
        self.assertIn("ch19", signer_ids)  # highest trust (0.69)
        self.assertNotIn("ch0", signer_ids)  # lowest trust (0.50), should be excluded

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

    def test_bls_batch_mode_trust_gating_individually_verifies_mid_trust(self):
        # Report Algorithm 4's 3-tier verification: 0.3 <= T < 0.7 -> individual
        # verify (not aggregate-batched with the high-trust signers).
        mgr = AuthenticationManager(mode="bls_batch", trust_threshold=0.7)
        mgr.sign_emergency_broadcast(
            self.msg, sender_vehicle_id="v1", cluster_heads=self.cluster_heads, vehicles=self.vehicles
        )

        ok, perf = mgr.verify_message(self.msg, self.vehicles)
        self.assertTrue(ok)
        self.assertEqual(perf["high_trust_count"], 2)  # v1 (SENDER), v2 (CH)
        self.assertEqual(perf["mid_trust_count"], 1)   # v3 (CH)
        self.assertEqual(perf["rejected_count"], 0)

    def test_bls_batch_mode_rejects_sub_030_trust_unconditionally(self):
        # Report Algorithm 4: T < 0.3 is rejected immediately, no verify attempt,
        # unconditionally (no configuration flag needed).
        vehicles = dict(self.vehicles)
        vehicles["v4"] = self._make_vehicle("v4", trust=0.2)
        cluster_heads = dict(self.cluster_heads)
        cluster_heads[2] = "v4"

        mgr = AuthenticationManager(mode="bls_batch", trust_threshold=0.7)
        mgr.sign_emergency_broadcast(
            self.msg, sender_vehicle_id="v1", cluster_heads=cluster_heads, vehicles=vehicles
        )

        verifies_before = mgr.bls.individual_verify_time_samples[:]
        ok, perf = mgr.verify_message(self.msg, vehicles)
        self.assertFalse(ok)  # rejected signer -> overall auth fails
        self.assertEqual(perf["rejected_count"], 1)
        # No verify attempt at all was made for the rejected signer specifically:
        # only v3 (mid-trust) should have added an individual-verify sample.
        self.assertEqual(len(mgr.bls.individual_verify_time_samples) - len(verifies_before), 1)

    def test_bls_batch_mode_detects_tampering(self):
        mgr = AuthenticationManager(mode="bls_batch", trust_threshold=0.7)
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
