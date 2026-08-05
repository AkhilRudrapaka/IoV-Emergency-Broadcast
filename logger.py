import os

class SimulationLogger:
    """
    Simulation Logger for IoV Broadcast Storm Mitigation Research Project.
    Provides clean structured console logging for IEEE project demonstration
    and optional file logging.
    """

    def __init__(self, log_filepath=None):
        self.log_filepath = log_filepath
        if self.log_filepath:
            os.makedirs(os.path.dirname(self.log_filepath), exist_ok=True)
            with open(self.log_filepath, "w", encoding="utf-8") as f:
                f.write("=== IoV Emergency Message Dissemination Simulation Log ===\n\n")

    def log(self, message):
        print(message)
        if self.log_filepath:
            with open(self.log_filepath, "a", encoding="utf-8") as f:
                f.write(message + "\n")

    def print_banner(self, title):
        banner = "\n" + "=" * 70 + "\n" + f"{title.center(70)}\n" + "=" * 70
        self.log(banner)

    def print_step_header(self, step, total_vehicles, active_clusters, noise_vehicles, ch_count, trusted, unknown, malicious):
        header = f"""
----------------------------------------------------------------------
Simulation Step : {step}
Vehicles        : {total_vehicles}
Clusters        : {active_clusters}
Noise Vehicles  : {noise_vehicles}
Cluster Heads   : {ch_count}
Vehicle Verification Completed:
  - Trusted     : {trusted}
  - Unknown     : {unknown}
  - Malicious   : {malicious}
----------------------------------------------------------------------"""
        self.log(header)
