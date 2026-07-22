from sklearn.cluster import DBSCAN
import numpy as np


class ClusterManager:

    def __init__(self, eps=60, min_samples=2):
        self.eps = eps
        self.min_samples = min_samples

    def perform_clustering(self, vehicles):

        if len(vehicles) == 0:
            return {}

        positions = []

        ids = []

        for v in vehicles.values():

            positions.append([v.x, v.y])

            ids.append(v.id)

        positions = np.array(positions)

        db = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples
        )

        labels = db.fit_predict(positions)

        clusters = {}

        for vehicle_id, label in zip(ids, labels):

            clusters.setdefault(label, []).append(vehicle_id)

            vehicles[vehicle_id].cluster = label

        return clusters
