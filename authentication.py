import hashlib
import json


class Authenticator:
    """
    Authentication module for IoV emergency message signing and verification.
    Currently uses SHA-256 placeholder signatures, with a modular design 
    that allows seamless replacement with BLS Batch Authentication.
    """

    def __init__(self, secret_key="iov_secret_key"):
        self.secret_key = secret_key

    def sign_message(self, message, private_key=None):
        """
        Generates a signature for an emergency message or payload.
        Attaches the signature to the message object/dict and returns it.

        Args:
            message: EmergencyMessage instance or dictionary payload.
            private_key: Optional node/vehicle private key.

        Returns:
            str: Generated signature hex string.
        """
        key = private_key or self.secret_key
        payload_str = self._serialize_message(message)
        raw_data = f"{payload_str}:{key}".encode('utf-8')
        signature = hashlib.sha256(raw_data).hexdigest()

        # Attach signature to message object/dict
        if hasattr(message, 'signature'):
            message.signature = signature
        elif isinstance(message, dict):
            message['signature'] = signature

        return signature

    def verify_signature(self, message, signature=None, public_key=None):
        """
        Verifies the signature of a message payload.

        Args:
            message: EmergencyMessage instance or dictionary payload.
            signature: Optional explicit signature string.
            public_key: Optional public key for verification.

        Returns:
            bool: True if signature is valid, False otherwise.
        """
        sig_to_check = signature or getattr(message, 'signature', None)
        if sig_to_check is None and isinstance(message, dict):
            sig_to_check = message.get('signature')

        if not sig_to_check:
            return False

        key = public_key or self.secret_key
        payload_str = self._serialize_message(message)
        expected_raw = f"{payload_str}:{key}".encode('utf-8')
        expected_sig = hashlib.sha256(expected_raw).hexdigest()

        return sig_to_check == expected_sig

    def verify_batch(self, messages_and_signatures, public_keys=None):
        """
        Batch signature verification interface for future BLS Batch Authentication integration.

        Args:
            messages_and_signatures: List of (message, signature) tuples or signed message objects.
            public_keys: Optional list of public keys matching the batch.

        Returns:
            bool: True if all signatures in the batch are valid.
        """
        for item in messages_and_signatures:
            if isinstance(item, tuple):
                msg, sig = item[0], item[1]
            else:
                msg, sig = item, None
            if not self.verify_signature(msg, sig):
                return False
        return True

    def _serialize_message(self, message):
        """
        Serializes message data into a consistent canonical string format.
        Excludes signature property to maintain deterministic output.
        """
        if hasattr(message, 'message_id'):
            return f"{message.message_id}_{message.sender}_{message.location}_{message.severity}"
        elif isinstance(message, dict):
            clean_dict = {k: v for k, v in message.items() if k != 'signature'}
            return json.dumps(clean_dict, sort_keys=True)
        else:
            return str(message)


# Convenience module-level helper functions matching signature requirements
default_authenticator = Authenticator()


def sign_message(message, private_key=None):
    return default_authenticator.sign_message(message, private_key)


def verify_signature(message, signature=None, public_key=None):
    return default_authenticator.verify_signature(message, signature, public_key)
