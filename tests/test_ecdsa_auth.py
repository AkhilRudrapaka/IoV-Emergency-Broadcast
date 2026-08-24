import unittest

from ecdsa_auth import ECDSAKeyPair, ECDSAAuthenticator


class TestECDSAAuthenticatorCore(unittest.TestCase):
    """Real ECDSA (P-256) sign/verify correctness -- the ablation counterpart to
    bls_auth.py's BLSAuthenticator, used for the honest BLS-vs-ECDSA comparison."""

    def test_sign_and_verify_roundtrip(self):
        ecdsa = ECDSAAuthenticator()
        kp = ECDSAKeyPair()
        payload = b"emergency-alert-1"
        sig = ecdsa.sign(payload, kp)

        self.assertGreater(len(sig), 0)
        self.assertTrue(ecdsa.verify(payload, sig, kp.public_key))

    def test_tampered_payload_fails(self):
        ecdsa = ECDSAAuthenticator()
        kp = ECDSAKeyPair()
        sig = ecdsa.sign(b"original-payload", kp)

        self.assertFalse(ecdsa.verify(b"tampered-payload", sig, kp.public_key))

    def test_wrong_key_fails(self):
        ecdsa = ECDSAAuthenticator()
        kp1 = ECDSAKeyPair()
        kp2 = ECDSAKeyPair()
        sig = ecdsa.sign(b"payload", kp1)

        self.assertFalse(ecdsa.verify(b"payload", sig, kp2.public_key))

    def test_verify_batch_all_valid(self):
        ecdsa = ECDSAAuthenticator()
        kps = [ECDSAKeyPair() for _ in range(3)]
        payloads = [f"msg-{i}".encode() for i in range(3)]
        sigs = [ecdsa.sign(p, kp) for p, kp in zip(payloads, kps)]
        pks = [kp.public_key for kp in kps]

        all_valid, per_item = ecdsa.verify_batch(payloads, sigs, pks)
        self.assertTrue(all_valid)
        self.assertEqual(per_item, [True, True, True])

    def test_verify_batch_detects_tampered_member(self):
        ecdsa = ECDSAAuthenticator()
        kps = [ECDSAKeyPair() for _ in range(3)]
        payloads = [f"msg-{i}".encode() for i in range(3)]
        sigs = [ecdsa.sign(p, kp) for p, kp in zip(payloads, kps)]
        pks = [kp.public_key for kp in kps]

        tampered_payloads = list(payloads)
        tampered_payloads[1] = b"forged-message"

        all_valid, per_item = ecdsa.verify_batch(tampered_payloads, sigs, pks)
        self.assertFalse(all_valid)
        self.assertEqual(per_item, [True, False, True])

    def test_performance_summary_tracks_calls(self):
        ecdsa = ECDSAAuthenticator()
        kp = ECDSAKeyPair()
        sig = ecdsa.sign(b"payload", kp)
        ecdsa.verify(b"payload", sig, kp.public_key)

        summary = ecdsa.get_performance_summary()
        self.assertEqual(summary["public_key_size_bytes"], 33)
        self.assertGreater(summary["signature_size_bytes"], 0)
        self.assertEqual(summary["total_signs"], 1)
        self.assertEqual(summary["total_individual_verifies"], 1)

    def test_benchmark_shows_no_aggregation_speedup_or_compression(self):
        # Central honest contrast with BLS: ECDSA has no native aggregation, so
        # signature bytes don't compress and there's no pairing-based speedup.
        ecdsa = ECDSAAuthenticator()
        results = ecdsa.run_performance_benchmark(batch_sizes=[5])
        row = results[0]
        self.assertEqual(row["signature_bytes_individual"], row["signature_bytes_aggregated"])
        self.assertTrue(row["batch_valid"])


if __name__ == "__main__":
    unittest.main()
