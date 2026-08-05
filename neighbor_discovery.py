from utils import euclidean_distance


class NeighborManager:
    """
    Neighbor Discovery module for IoV communication.
    Discovers vehicles within a configurable communication range (comm_range = 150.0m)
    and updates per-vehicle neighbor tables.
    """

    def __init__(self, comm_range=150.0):
        self.comm_range = comm_range

    def discover_neighbors(self, vehicles):
        """
        Discovers and updates neighbor lists for all active vehicles based on Euclidean distance.

        Args:
            vehicles (dict): Dictionary mapping vehicle_id -> Vehicle instance.

        Returns:
            dict: Mapping vehicle_id -> list of neighbor vehicle IDs.
        """
        neighbors_map = {vid: [] for vid in vehicles}

        v_list = list(vehicles.values())
        num_v = len(v_list)

        # Clear existing neighbor lists
        for v in v_list:
            v.neighbors = []

        for i in range(num_v):
            v1 = v_list[i]
            for j in range(i + 1, num_v):
                v2 = v_list[j]
                dist = euclidean_distance((v1.x, v1.y), (v2.x, v2.y))

                if dist <= self.comm_range:
                    v1.neighbors.append(v2.id)
                    v2.neighbors.append(v1.id)
                    neighbors_map[v1.id].append(v2.id)
                    neighbors_map[v2.id].append(v1.id)

        return neighbors_map

    def get_neighbors(self, vehicle_id, vehicles):
        """
        Returns list of neighbor vehicle IDs for a given vehicle.
        """
        if vehicle_id in vehicles:
            return vehicles[vehicle_id].neighbors
        return []
