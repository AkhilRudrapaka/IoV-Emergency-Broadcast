import os
import sys
import argparse

from generate_routes import generate_all_route_files
from comparison import ComparisonEngine
from graphs import GraphGenerator
from config import VEHICLE_DENSITIES, GRAPHS_DIR, LOGS_DIR
from sumo_interface import run_sumo_simulation


def main():
    parser = argparse.ArgumentParser(description="IEEE IoV Broadcast Storm Mitigation Research Simulation")
    parser.add_argument("--gui", action="store_true", help="Launch SUMO GUI for visual demonstration")
    parser.add_argument("--density", type=int, default=250, help="Vehicle density (50, 100, 200, 300, 500)")
    parser.add_argument("--steps", type=int, default=200, help="Simulation step count")
    parser.add_argument("--eval-only", action="store_true", help="Run comparative benchmark evaluation only")
    parser.add_argument("--seed", type=int, default=None, help="Seed for reproducible malicious-vehicle assignment (demo rehearsal)")
    args = parser.parse_args()

    print("=" * 80)
    print("IEEE RESEARCH PROJECT EVALUATION & DEMONSTRATION RUNNER")
    print("Mitigation of Broadcast Storm Problem for Reliable Emergency Message Dissemination")
    print("in Internet of Vehicles using Trust-Aware Clustering and Batch Authentication")
    print("=" * 80)

    # Step 1: Ensure SUMO route files exist for 5x5 urban grid
    print("\n[Step 1/3] Generating traffic density route files for 5x5 urban grid...")
    generate_all_route_files(VEHICLE_DENSITIES)

    if not args.eval_only:
        # Step 2: Run End-to-End Simulation with Real-Time Terminal & GUI Visualization (Phases 1-14)
        gui_flag = args.gui or (os.environ.get("SUMO_GUI", "0") == "1")
        print(f"\n[Step 2/3] Running End-to-End SUMO Simulation (Density={args.density}, GUI={gui_flag}, Seed={args.seed})...")
        run_sumo_simulation(density=args.density, steps=args.steps, use_gui=gui_flag, seed=args.seed)

    # Step 3: Run Full Comparative Experimental Suite & Generate Graphs (Phase 15)
    print("\n[Step 3/3] Executing Comparative Evaluation & Generating IEEE Analytical Graphs...")
    comparison_engine = ComparisonEngine(output_dir=LOGS_DIR)
    summary_md, csv_file = comparison_engine.run_all_comparisons(densities=VEHICLE_DENSITIES, runs=5, steps=100)

    graph_gen = GraphGenerator(output_dir=GRAPHS_DIR)
    metrics_csv = os.path.join(LOGS_DIR, "simulation_metrics.csv")
    graphs = graph_gen.generate_all_graphs(csv_filepath=metrics_csv)

    print("\n" + "=" * 80)
    print("EVALUATION & DEMONSTRATION COMPLETE SUCCESSFULLY!")
    print(f"- Summary Comparison CSV : {csv_file}")
    print(f"- IEEE Analytical Graphs : {GRAPHS_DIR} ({len(graphs)} graphs generated)")
    print("=" * 80)


if __name__ == "__main__":
    main()
