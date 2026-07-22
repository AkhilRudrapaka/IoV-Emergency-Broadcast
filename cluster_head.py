class ClusterHeadManager:

    def __init__(self):
        pass

    def select_cluster_heads(self, vehicles, clusters):

        cluster_heads = {}

        for cluster_id, members in clusters.items():

            if cluster_id == -1:
                continue

            best_vehicle = None
            best_score = -1

            for vehicle_id in members:

                vehicle = vehicles[vehicle_id]

                # Speed stability (simple approximation)
                speed_stability = max(0, 1 - (vehicle.speed / 20))

                score = (
                    0.6 * vehicle.trust +
                    0.4 * speed_stability
                )

                if score > best_score:
                    best_score = score
                    best_vehicle = vehicle

            if best_vehicle:

                best_vehicle.is_cluster_head = True

                cluster_heads[cluster_id] = best_vehicle.id

        return cluster_heads
