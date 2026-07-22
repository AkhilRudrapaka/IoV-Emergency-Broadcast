import random


class TrustManager:

    def __init__(self):
        pass

    def calculate_trust(self, vehicle):

        # Simulated values
        direct = random.uniform(0.6, 1.0)

        historical = random.uniform(0.5, 1.0)

        recommendation = random.uniform(0.5, 1.0)

        trust = (
            0.5 * direct +
            0.3 * historical +
            0.2 * recommendation
        )

        vehicle.trust = round(trust, 2)

        return vehicle.trust
