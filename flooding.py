import math
import time


class FloodingEngine:
    """
    Baseline Flooding Dissemination Engine.
    Every receiving vehicle unconditionally re-broadcasts the emergency message 
    to all neighboring nodes within communication range without clustering or trust filtering.
    """

    def __init__(self, comm_range=150.0):
        self.comm_range = comm_range

    def disseminate(self, message, source_vehicle_id, vehicles, rsu_manager=None, metrics=None):
        """
        Executes pure flooding broadcast starting from source_vehicle_id.
        Tracks forwarded messages, duplicate messages, hop count, and RSU delivery.
        """
        source_vehicle_id = str(source_vehicle_id)
        if source_vehicle_id not in vehicles:
            print(f"[FloodingEngine] Error: Source vehicle {source_vehicle_id} not found.")
            return False, 0, 0, 0

        received_nodes = {source_vehicle_id}
        message_cache = set()
        queue = [(source_vehicle_id, 0)]  # (vehicle_id, hop_count)

        total_forwarded = 0
        total_duplicates = 0
        max_hops = 0
        rsu_delivered = False

        if metrics:
            metrics.record_emergency_message()

        while queue:
            curr_id, current_hops = queue.pop(0)
            max_hops = max(max_hops, current_hops)

            if curr_id not in vehicles:
                continue

            curr_veh = vehicles[curr_id]

            # Malicious packet dropping behavior (Blackhole attack in Flooding)
            if getattr(curr_veh, 'is_malicious', False) and curr_veh.attack_type == "PACKET_DROP":
                print(f"[FloodingEngine] Malicious Vehicle '{curr_id}' DROPPED packet.")
                continue

            # Find all neighbors within communication range
            neighbors = curr_veh.neighbors
            if not neighbors:
                # Calculate dynamically if neighbor list empty
                neighbors = []
                for vid, v in vehicles.items():
                    if vid != curr_id:
                        dist = math.hypot(curr_veh.x - v.x, curr_veh.y - v.y)
                        if dist <= self.comm_range:
                            neighbors.append(vid)

            for nbr_id in neighbors:
                nbr_id = str(nbr_id)
                if nbr_id in received_nodes:
                    total_duplicates += 1
                    if metrics:
                        metrics.duplicate_message()
                else:
                    received_nodes.add(nbr_id)
                    total_forwarded += 1
                    if metrics:
                        metrics.forwarded_message(hops=1)
                    queue.append((nbr_id, current_hops + 1))

            # Check reachability to any deployed RSU
            if rsu_manager:
                for rsu in rsu_manager.get_all_rsus().values():
                    dist_rsu = math.hypot(curr_veh.x - rsu.x, curr_veh.y - rsu.y)
                    if dist_rsu <= self.comm_range:
                        rsu_delivered = True
                        rsu.receive_message(message, vehicles=vehicles, metrics=metrics)

        print(
            f"[FloodingEngine] BROADCAST COMPLETE: Delivered={rsu_delivered} "
            f"Forwarded={total_forwarded} Duplicates={total_duplicates} MaxHops={max_hops}"
        )

        return rsu_delivered, total_forwarded, total_duplicates, max_hops
