import time


class EmergencyMessage:

    def __init__(self,
                 sender,
                 location,
                 severity):

        self.sender = sender

        self.location = location

        self.severity = severity

        self.timestamp = time.time()

        self.message_id = f"{sender}_{int(self.timestamp)}"

    def __str__(self):

        return (
            f"[Emergency]"
            f" ID={self.message_id}"
            f" Sender={self.sender}"
            f" Location={self.location}"
            f" Severity={self.severity}"
        )
