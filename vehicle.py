class Vehicle:

    def __init__(self, vehicle_id):

        self.id = vehicle_id

        self.x = 0.0
        self.y = 0.0

        self.speed = 0.0

        self.trust = 0.5

        self.cluster = -1

        self.is_cluster_head = False

    def update(self, position, speed):

        self.x = position[0]
        self.y = position[1]
        self.speed = speed

    def __str__(self):

        return (
            f"{self.id:<6}"
            f" Position=({self.x:7.2f},{self.y:7.2f})"
            f" Speed={self.speed:6.2f}"
            f" Trust={self.trust:.2f}"
            f" Cluster={self.cluster}"
            f" CH={self.is_cluster_head}"
        )
