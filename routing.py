from utils import euclidean_distance


class RoutingEngine:
    """
    Multi-Hop Greedy Cluster Head Routing Engine.
    Discovers loop-free forwarding path from accident site -> CHs -> nearest RSU.
    Activates visual ORANGE highlights on active forwarding CH nodes.
    """

    def __init__(self, logger=None):
        self.logger = logger

    def find_route(self, accident_vehicle_id, vehicles, cluster_heads, rsu_pos=None, rsu_id="RSU_CENTER", rsu_manager=None):
        """
        Determines a loop-free, trust-aware path from Accident Vehicle to RSU.

        Flow: Accident Vehicle -> Current CH -> Next Hop CH(s) -> Nearest RSU
        """
        accident_vehicle_id = str(accident_vehicle_id)
        if accident_vehicle_id not in vehicles:
            if self.logger:
                self.logger.log(f"[RoutingEngine] Error: Vehicle {accident_vehicle_id} not found.")
            return []

        accident_vehicle = vehicles[accident_vehicle_id]
        acc_pos = (accident_vehicle.x, accident_vehicle.y)

        # Determine target RSU
        target_rsu_id = rsu_id
        target_rsu_pos = rsu_pos

        if rsu_manager is not None and rsu_pos is None and (rsu_id == "RSU_CENTER" or rsu_id == "RSU_1" or rsu_id is None):
            target_rsu_id, target_rsu_pos, _ = rsu_manager.get_nearest_rsu(acc_pos)

        if target_rsu_pos is None:
            target_rsu_pos = (400.0, 400.0)

        route = [f"Accident Vehicle ({accident_vehicle_id})"]
        visited_chs = set()

        # Find initial Cluster Head for accident vehicle
        current_ch_id = None
        vehicle_cluster = accident_vehicle.cluster

        if vehicle_cluster in cluster_heads and vehicle_cluster != -1:
            candidate = str(cluster_heads[vehicle_cluster])
            if candidate in vehicles and not getattr(vehicles[candidate], 'is_blacklisted', False):
                current_ch_id = candidate

        if current_ch_id is None:
            # Fallback: geographically closest non-blacklisted CH
            min_dist = float('inf')
            for cid, ch_id in cluster_heads.items():
                ch_id = str(ch_id)
                if ch_id in vehicles and not getattr(vehicles[ch_id], 'is_blacklisted', False):
                    dist = euclidean_distance(acc_pos, (vehicles[ch_id].x, vehicles[ch_id].y))
                    if dist < min_dist:
                        min_dist = dist
                        current_ch_id = ch_id

        if current_ch_id is None:
            route.append(f"RSU ({target_rsu_id})")
            return route

        # Multi-hop greedy forwarding across Cluster Heads with Loop Prevention
        all_ch_ids = list(set(str(v) for v in cluster_heads.values()))

        while current_ch_id is not None and current_ch_id not in visited_chs:
            visited_chs.add(current_ch_id)
            route.append(f"CH ({current_ch_id})")

            # Activate temporary ORANGE visual highlight for active forwarding CH
            if current_ch_id in vehicles:
                v = vehicles[current_ch_id]
                v.trigger_forwarding_highlight(duration_steps=12)

            ch_pos = (vehicles[current_ch_id].x, vehicles[current_ch_id].y)
            current_dist_to_rsu = euclidean_distance(ch_pos, target_rsu_pos)

            best_next_ch = None
            min_hop_dist = float('inf')

            for candidate_ch_id in all_ch_ids:
                candidate_ch_id = str(candidate_ch_id)
                if candidate_ch_id in visited_chs or candidate_ch_id not in vehicles:
                    continue

                candidate_veh = vehicles[candidate_ch_id]
                if getattr(candidate_veh, 'is_blacklisted', False) or candidate_veh.trust < 0.3:
                    continue

                candidate_pos = (candidate_veh.x, candidate_veh.y)
                candidate_dist_to_rsu = euclidean_distance(candidate_pos, target_rsu_pos)

                if candidate_dist_to_rsu < current_dist_to_rsu:
                    hop_dist = euclidean_distance(ch_pos, candidate_pos)
                    if hop_dist < min_hop_dist:
                        min_hop_dist = hop_dist
                        best_next_ch = candidate_ch_id

            current_ch_id = best_next_ch

        route.append(f"RSU ({target_rsu_id})")
        return route

    def route_message(self, message, vehicles, cluster_heads, rsu_pos=None, rsu_id="RSU_CENTER", broadcast_manager=None, rsu_manager=None, rsu_instance=None, metrics=None, auth_manager=None):
        """
        Computes routing path for EmergencyMessage, disseminates along route,
        and delivers message to target RSU for verification, processing, and ACK.

        Args:
            auth_manager (bls_auth.AuthenticationManager, optional): forwarded to the
                target RSU's verification step (Priority 2). Omitted by default, in
                which case RSU verification behaves exactly as before Priority 2.
        """
        route = self.find_route(
            accident_vehicle_id=message.sender,
            vehicles=vehicles,
            cluster_heads=cluster_heads,
            rsu_pos=rsu_pos,
            rsu_id=rsu_id,
            rsu_manager=rsu_manager
        )

        if metrics:
            metrics.record_emergency_message()
            metrics.record_routing(max(0, len(route) - 1))

        routing_str = " -> ".join(route)
        if self.logger:
            self.logger.log("\n" + "=" * 70)
            self.logger.log("ROUTING ENGINE - MULTI-HOP PATH DISCOVERY")
            self.logger.log("=" * 70)
            self.logger.log(f"Discovered Path: {routing_str}")

        if broadcast_manager:
            broadcast_manager.broadcast_route(message, route, metrics=metrics)

        # Deliver message to destination RSU
        ack = None
        target_rsu = rsu_instance
        target_rsu_id = rsu_id

        if route and route[-1].startswith("RSU ("):
            target_rsu_id = route[-1][5:-1]

        if target_rsu is None and rsu_manager is not None:
            target_rsu = rsu_manager.get_rsu(target_rsu_id)
            if target_rsu is None:
                target_rsu = rsu_manager.add_rsu(target_rsu_id, rsu_pos or (400.0, 400.0))

        if target_rsu is not None:
            ack = target_rsu.receive_and_process_message(
                message=message,
                vehicles=vehicles,
                cluster_heads=cluster_heads,
                metrics=metrics,
                auth_manager=auth_manager
            )

        return route, ack
