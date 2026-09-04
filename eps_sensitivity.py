"""
DBSCAN eps (epsilon) sensitivity check on this project's own road network.

Chen & Wu (2024), "Dynamic Networking Method of Vehicles in VANET" (Table 2),
test eps in {20, 40} m on a 3-lane, 3000 m single highway and find eps=20 m
gives the lowest noise ratio for that scenario. This project's road network is
a 5x5 urban grid (700 m x 700 m) with intersections, not a dense single-lane
highway -- a materially different topology and inter-vehicle spacing. This
script re-runs the same style of noise-ratio measurement Chen & Wu use, on
this project's own network and density range, rather than assuming their
absolute eps value transfers.

Real, reproducible: run `python3 eps_sensitivity.py`. No fabricated numbers --
every row here is measured. See docs/ALGORITHMS.md and the paper's Ablation
Study section for the write-up of what this shows.
"""
import csv
import random

import numpy as np

from vehicle import Vehicle
from clustering import ClusterManager


def build_fleet(density, seed):
    random.seed(seed)
    np.random.seed(seed)
    vehicles = {}
    grid_dim = int(np.ceil(np.sqrt(density)))
    xs = np.linspace(50, 750, grid_dim)
    ys = np.linspace(50, 750, grid_dim)
    idx = 0
    for x in xs:
        for y in ys:
            if idx >= density:
                break
            v = Vehicle(f"v{idx}")
            v.update((x + random.uniform(-10, 10), y + random.uniform(-10, 10)), speed=random.uniform(5, 15))
            v.heading = random.uniform(0, 2 * np.pi)
            vehicles[f"v{idx}"] = v
            idx += 1
    return vehicles


def main():
    rows = []
    for eps in (20.0, 40.0, 80.0):
        for density in (50, 100, 200, 300, 500):
            noise_pcts, cluster_counts, avg_sizes = [], [], []
            for seed in (42, 52, 62, 72, 82):
                vehicles = build_fleet(density, seed)
                cm = ClusterManager(eps=eps, min_samples=2, mode="velocity_aware")
                clusters = cm.perform_clustering(vehicles)
                noise = len(clusters.get(-1, []))
                real_clusters = {k: v for k, v in clusters.items() if k != -1}
                noise_pcts.append(100.0 * noise / density)
                cluster_counts.append(len(real_clusters))
                sizes = [len(m) for m in real_clusters.values()]
                avg_sizes.append(sum(sizes) / len(sizes) if sizes else 0.0)

            row = {
                "eps_m": eps,
                "density": density,
                "avg_cluster_count": round(sum(cluster_counts) / len(cluster_counts), 2),
                "avg_noise_pct": round(sum(noise_pcts) / len(noise_pcts), 2),
                "avg_cluster_size": round(sum(avg_sizes) / len(avg_sizes), 2),
            }
            rows.append(row)
            print(row)

    with open("outputs/logs/eps_sensitivity.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print("\nSaved outputs/logs/eps_sensitivity.csv")


if __name__ == "__main__":
    main()
