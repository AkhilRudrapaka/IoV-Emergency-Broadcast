from sklearn.cluster import DBSCAN
import numpy as np

from utils import angle_diff_deg

try:
    from config import (
        CLUSTERING_MODE, VELOCITY_PREDICTION_HORIZON,
        VELOCITY_WEIGHT_POSITION, VELOCITY_WEIGHT_MOBILITY,
        MAX_HEADING_DIFF_DEG, MIN_SPEED_FOR_HEADING_GATE
    )
except ImportError:
    CLUSTERING_MODE = "velocity_aware"
    VELOCITY_PREDICTION_HORIZON = 2.0
    VELOCITY_WEIGHT_POSITION = 0.6
    VELOCITY_WEIGHT_MOBILITY = 0.4
    MAX_HEADING_DIFF_DEG = 120.0
    MIN_SPEED_FOR_HEADING_GATE = 1.0

# Large penalty added to the precomputed distance matrix to push directionally
# incompatible vehicle pairs beyond `eps`, effectively excluding them as neighbors.
_HEADING_GATE_PENALTY = 1.0e6


class ClusterManager:
    """
    DBSCAN Spatial Clustering Manager for IoV Vehicles.
    Groups vehicles dynamically into spatial clusters.
    Label -1 indicates unclustered (noise) vehicles.

    Supports two ablation modes (Priority 1):
      - "baseline": plain Euclidean DBSCAN on raw (x, y) positions (original behavior).
      - "velocity_aware": DBSCAN over a mobility-aware precomputed distance matrix
        that blends current position distance with a short-horizon predicted-position
        distance (derived from speed + heading), plus a directional compatibility gate
        that prevents clustering vehicles moving in substantially different directions.
    """

    def __init__(self, eps=80.0, min_samples=2, mode=None,
                 prediction_horizon=None, weight_position=None, weight_mobility=None,
                 max_heading_diff_deg=None, min_speed_for_heading_gate=None):
        self.eps = eps
        self.min_samples = min_samples
        self.mode = mode or CLUSTERING_MODE
        self.prediction_horizon = prediction_horizon if prediction_horizon is not None else VELOCITY_PREDICTION_HORIZON
        self.weight_position = weight_position if weight_position is not None else VELOCITY_WEIGHT_POSITION
        self.weight_mobility = weight_mobility if weight_mobility is not None else VELOCITY_WEIGHT_MOBILITY
        self.max_heading_diff_deg = max_heading_diff_deg if max_heading_diff_deg is not None else MAX_HEADING_DIFF_DEG
        self.min_speed_for_heading_gate = min_speed_for_heading_gate if min_speed_for_heading_gate is not None else MIN_SPEED_FOR_HEADING_GATE

    def perform_clustering(self, vehicles):
        """
        Executes DBSCAN clustering on active vehicles, dispatching to the
        baseline or velocity-aware distance computation based on `self.mode`.

        Args:
            vehicles (dict): Dictionary of vehicle_id -> Vehicle object.

        Returns:
            dict: Mapping of cluster_id -> list of member vehicle IDs.
        """
        if len(vehicles) == 0:
            return {}

        ids = list(vehicles.keys())

        if self.mode == "velocity_aware":
            distance_matrix = self._compute_mobility_distance_matrix(vehicles, ids)
            db = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric="precomputed")
            labels = db.fit_predict(distance_matrix)
        else:
            positions = np.array([[vehicles[vid].x, vehicles[vid].y] for vid in ids])
            db = DBSCAN(eps=self.eps, min_samples=self.min_samples)
            labels = db.fit_predict(positions)

        clusters = {}

        for vehicle_id, label in zip(ids, labels):
            label = int(label)
            clusters.setdefault(label, []).append(vehicle_id)
            vehicles[vehicle_id].cluster = label

        return clusters

    def _compute_mobility_distance_matrix(self, vehicles, ids):
        """
        Builds a symmetric precomputed distance matrix combining current spatial
        distance with predicted-position distance after `prediction_horizon`
        seconds, plus a directional compatibility gate.
        """
        n = len(ids)
        positions = np.array([[vehicles[vid].x, vehicles[vid].y] for vid in ids])
        velocities = np.array([vehicles[vid].velocity_vector() for vid in ids])
        speeds = np.array([vehicles[vid].speed for vid in ids])
        headings_deg = np.degrees([vehicles[vid].heading for vid in ids])

        predicted = positions + velocities * self.prediction_horizon

        matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):
                pos_dist = np.linalg.norm(positions[i] - positions[j])
                pred_dist = np.linalg.norm(predicted[i] - predicted[j])
                distance = self.weight_position * pos_dist + self.weight_mobility * pred_dist

                if speeds[i] > self.min_speed_for_heading_gate and speeds[j] > self.min_speed_for_heading_gate:
                    heading_diff = angle_diff_deg(headings_deg[i], headings_deg[j])
                    if heading_diff > self.max_heading_diff_deg:
                        distance += _HEADING_GATE_PENALTY

                matrix[i, j] = distance
                matrix[j, i] = distance

        return matrix

    def get_cluster_stats(self, clusters):
        """
        Returns cluster metrics: (active_cluster_count, noise_vehicle_count).
        """
        valid_clusters = {cid: members for cid, members in clusters.items() if cid != -1}
        noise_count = len(clusters.get(-1, []))
        return len(valid_clusters), noise_count
