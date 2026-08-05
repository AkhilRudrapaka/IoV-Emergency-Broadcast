class ClusterHeadManager:
    """
    Cluster Head (CH) Selection Manager.
    Elects CH for each spatial DBSCAN cluster based on a composite score:
      Score = 60% Trust Score + 40% Speed Stability
    Excludes blacklisted or malicious vehicles.
    """

    def __init__(self, logger=None):
        self.logger = logger

    def select_cluster_heads(self, vehicles, clusters):
        """
        Selects optimal Cluster Head for each active spatial cluster.

        Args:
            vehicles (dict): vehicle_id -> Vehicle instance.
            clusters (dict): cluster_id -> list of member vehicle_ids.

        Returns:
            dict: cluster_id -> elected CH vehicle_id.
        """
        cluster_heads = {}

        for cluster_id, members in clusters.items():
            if cluster_id == -1:  # Skip noise nodes
                continue

            best_vehicle = None
            best_score = -1.0
            best_trust = 0.0
            best_speed_stab = 0.0

            for vehicle_id in members:
                vehicle_id = str(vehicle_id)
                if vehicle_id not in vehicles:
                    continue

                vehicle = vehicles[vehicle_id]

                # Exclude blacklisted, malicious, or low-trust nodes from CH eligibility
                if getattr(vehicle, 'is_blacklisted', False) or getattr(vehicle, 'is_malicious', False) or vehicle.trust < 0.3:
                    vehicle.is_cluster_head = False
                    continue

                # Speed stability approximation (prefer steady velocity)
                speed_stability = max(0.0, 1.0 - (vehicle.speed / 22.0))

                # Composite Election Score (60% Trust, 40% Speed Stability)
                score = (0.6 * vehicle.trust) + (0.4 * speed_stability)

                if score > best_score:
                    best_score = score
                    best_vehicle = vehicle
                    best_trust = vehicle.trust
                    best_speed_stab = speed_stability

            if best_vehicle:
                best_vehicle.is_cluster_head = True
                cluster_heads[cluster_id] = best_vehicle.id

                if self.logger:
                    self.logger.log(
                        f"[CH Selection] Cluster {cluster_id:<3}: Elected CH Vehicle '{best_vehicle.id}' "
                        f"| Score: {best_score:.3f} (Trust: {best_trust:.2f}, SpeedStab: {best_speed_stab:.2f})"
                    )

        return cluster_heads
