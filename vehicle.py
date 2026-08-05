import math


class Vehicle:
    """
    Vehicle node entity in the IoV network representation.
    Tracks state, position, velocity, classification, trust, role, and visual GUI attributes.
    """

    def __init__(self, vehicle_id):
        self.id = str(vehicle_id)

        # Spatial Attributes
        self.x = 0.0
        self.y = 0.0
        self.speed = 0.0

        # Mobility Attributes (Priority 1: velocity-aware clustering)
        self.heading = 0.0  # radians, standard math convention (0=+x axis, CCW)
        self.prev_x = 0.0
        self.prev_y = 0.0

        # Classification & Verification Attributes (Phase 3)
        self.classification = "UNKNOWN"  # 'TRUSTED', 'UNKNOWN', 'MALICIOUS'
        self.auth_state = False           # Verified / Authenticated flag

        # Trust & Role Attributes
        self.trust = 0.5
        self.historical_trust = 0.5
        self.cluster = -1
        self.is_cluster_head = False
        self.is_accident = False
        self.is_forwarding = False
        self.forwarding_timer = 0
        self.is_malicious = False
        self.attack_type = None  # 'FAKE_ALERT', 'PACKET_DROP', 'FORGED_RECOMMENDATION'
        self.is_blacklisted = False

        # Behavior Counters for Trust Evaluation
        self.successful_forwards = 0
        self.total_received = 0
        self.forward_attempts = 0
        self.auth_successes = 0
        self.auth_attempts = 0
        self.recommendations = {}

        # Connectivity Neighbor Table
        self.neighbors = []

    def update(self, position, speed, heading=None):
        """
        Updates position coordinates, speed, and heading from a simulation step.

        Args:
            position: (x, y) tuple.
            speed: scalar speed in m/s.
            heading: optional heading in radians (standard math convention,
                0=+x axis, counter-clockwise). If omitted, heading is inferred
                from the position delta since the last update; when the
                vehicle is effectively stationary (near-zero displacement),
                the previously known heading is retained rather than
                recomputed from noise.
        """
        self.prev_x = self.x
        self.prev_y = self.y

        new_x = float(position[0])
        new_y = float(position[1])
        self.speed = float(speed)

        if heading is not None:
            self.heading = float(heading)
        else:
            dx = new_x - self.prev_x
            dy = new_y - self.prev_y
            if math.hypot(dx, dy) > 1e-3:
                self.heading = math.atan2(dy, dx)
            # else: keep last known heading (avoids noisy heading when stopped)

        self.x = new_x
        self.y = new_y

        # Decay temporary forwarding visual highlight
        if self.forwarding_timer > 0:
            self.forwarding_timer -= 1
            if self.forwarding_timer == 0:
                self.is_forwarding = False

    def velocity_vector(self):
        """
        Returns the (vx, vy) velocity vector decomposed from speed and heading.
        """
        return (self.speed * math.cos(self.heading), self.speed * math.sin(self.heading))

    def classify_and_verify(self):
        """
        Classifies node state based on trust score and malicious flag (Phase 3).
        - Malicious / Blacklisted -> 'MALICIOUS'
        - Trust >= 0.7 -> 'TRUSTED'
        - Trust < 0.7 -> 'UNKNOWN'
        """
        if self.is_malicious or self.is_blacklisted or self.trust < 0.3:
            self.classification = "MALICIOUS"
            self.auth_state = False
        elif self.trust >= 0.7:
            self.classification = "TRUSTED"
            self.auth_state = True
        else:
            self.classification = "UNKNOWN"
            self.auth_state = False

        return self.classification

    def trigger_forwarding_highlight(self, duration_steps=10):
        """
        Activates temporary ORANGE visual highlight for active forwarding CHs.
        """
        self.is_forwarding = True
        self.forwarding_timer = duration_steps

    def get_color(self):
        """
        Returns RGBA color tuple according to Phase 13 SUMO visual standards:
        - Red (255, 0, 0, 255): Accident vehicle
        - Black (0, 0, 0, 255): Malicious / Blacklisted vehicle
        - Orange (255, 165, 0, 255): Active Forwarding Cluster Head
        - Blue (0, 0, 255, 255): Cluster Head
        - Yellow (255, 255, 0, 255): Unknown / Unverified vehicle
        - White (255, 255, 255, 255): Trusted vehicle
        """
        if self.is_accident:
            return (255, 0, 0, 255)       # Red: Collision site
        elif self.is_malicious or self.is_blacklisted or self.classification == "MALICIOUS":
            return (0, 0, 0, 255)         # Black: Malicious
        elif self.is_forwarding:
            return (255, 165, 0, 255)     # Orange: Active Dissemination
        elif self.is_cluster_head:
            return (0, 0, 255, 255)       # Blue: Cluster Head
        elif self.classification == "UNKNOWN":
            return (255, 255, 0, 255)     # Yellow: Unknown
        else:
            return (255, 255, 255, 255)   # White: Trusted

    def __str__(self):
        role_str = "Accident" if self.is_accident else ("Forwarding" if self.is_forwarding else ("CH" if self.is_cluster_head else self.classification))
        return (
            f"ID={self.id:<6}"
            f" Pos=({self.x:7.2f},{self.y:7.2f})"
            f" Speed={self.speed:5.2f}"
            f" Trust={self.trust:.2f}"
            f" Cluster={self.cluster}"
            f" Class={self.classification:<9}"
            f" Role={role_str:<10}"
        )
