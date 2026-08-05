import time
import uuid


class EmergencyMessage:
    """
    Emergency Message Data Model for IoV Dissemination.
    Contains UUID, sender ID, location coordinates, severity level, timestamp, and digital signature.
    """

    def __init__(self, sender, location, severity="HIGH"):
        self.sender = str(sender)
        self.location = location
        self.severity = severity
        self.timestamp = time.time()
        # Unique UUID message identifier for duplicate suppression (Phase 8)
        self.uuid = str(uuid.uuid4())[:8]
        self.message_id = f"MSG_{self.sender}_{self.uuid}"

        self.ttl = 30
        self.radius = 350.0
        self.signature = None

        # BLS chain-of-custody attestations (Priority 2): populated by
        # AuthenticationManager.sign_emergency_broadcast() in BLS modes; each entry is
        # {"signer_id", "role", "signature", "public_key"}. Empty/unused in baseline/none modes.
        self.chain_signatures = []

    def __str__(self):
        sig_short = f"{self.signature[:8]}..." if self.signature else "None"
        return (
            f"[Emergency Message]"
            f" ID={self.message_id}"
            f" Sender={self.sender}"
            f" Location=({self.location[0]:.2f}, {self.location[1]:.2f})"
            f" Severity={self.severity}"
            f" Sig={sig_short}"
        )
