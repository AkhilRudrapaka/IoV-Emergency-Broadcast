class Metrics:

    def __init__(self):

        self.total_messages = 0
        self.forwarded = 0
        self.duplicates = 0

    def forwarded_message(self):
        self.total_messages += 1
        self.forwarded += 1

    def duplicate_message(self):
        self.total_messages += 1
        self.duplicates += 1

    def show(self):

        print("\n")
        print("=" * 60)
        print("NETWORK METRICS")
        print("=" * 60)

        print(f"Total Messages      : {self.total_messages}")
        print(f"Forwarded Messages  : {self.forwarded}")
        print(f"Duplicate Messages  : {self.duplicates}")
