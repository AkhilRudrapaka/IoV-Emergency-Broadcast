import unittest
from messaging import EmergencyMessage
from authentication import Authenticator, sign_message, verify_signature


class TestAuthenticationModule(unittest.TestCase):

    def setUp(self):
        self.auth = Authenticator(secret_key="test_secret_key")
        self.msg = EmergencyMessage(sender="v1", location=(100.0, 200.0), severity="HIGH")

    def test_sign_and_verify_message(self):
        sig = sign_message(self.msg)

        self.assertIsNotNone(sig)
        self.assertEqual(self.msg.signature, sig)
        self.assertTrue(verify_signature(self.msg))

    def test_tampered_message_verification_fails(self):
        sign_message(self.msg)
        # Modify location payload after signing
        self.msg.location = (999.0, 999.0)

        self.assertFalse(verify_signature(self.msg))

    def test_invalid_signature_fails(self):
        sign_message(self.msg)
        self.msg.signature = "invalid_hash_signature_value"

        self.assertFalse(verify_signature(self.msg))

    def test_dict_payload_signing_and_verification(self):
        payload = {
            "sender": "v2",
            "event": "ACCIDENT",
            "severity": "CRITICAL"
        }
        sig = self.auth.sign_message(payload)

        self.assertIsNotNone(sig)
        self.assertEqual(payload["signature"], sig)
        self.assertTrue(self.auth.verify_signature(payload))

        # Tamper payload
        payload["severity"] = "LOW"
        self.assertFalse(self.auth.verify_signature(payload))

    def test_batch_verification(self):
        msg1 = EmergencyMessage("v1", (10.0, 10.0), "HIGH")
        msg2 = EmergencyMessage("v2", (20.0, 20.0), "MEDIUM")

        self.auth.sign_message(msg1)
        self.auth.sign_message(msg2)

        batch = [msg1, msg2]
        self.assertTrue(self.auth.verify_batch(batch))

        # Tamper one item in batch
        msg2.severity = "LOW"
        self.assertFalse(self.auth.verify_batch(batch))


if __name__ == "__main__":
    unittest.main()
