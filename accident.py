import traci
import math
import random
from messaging import EmergencyMessage
from authentication import sign_message

try:
    from config import FAKE_ALERT_LOCATION_OFFSET_RANGE_M
except ImportError:
    FAKE_ALERT_LOCATION_OFFSET_RANGE_M = (200.0, 500.0)


class AccidentManager:
    """
    Accident Simulation & TraCI Congestion Propagation Manager (Phase 7).
    Triggers a realistic TWO-VEHICLE crash collision:
    - Identifies a lead vehicle (V_lead) and a trailing vehicle (V_follow) on the same road edge.
    - Forces immediate collision halt (speed = 0) on BOTH crash vehicles.
    - Turns BOTH vehicles BRIGHT RED with glowing highlight rings in SUMO GUI.
    - Causes follower vehicles behind the crash site to brake, queue, and form heavy traffic congestion.
    - Formulates Emergency Message with severity specs.
    """

    SEVERITY_CONFIG = {
        "LOW": {"decel": 4.0, "ttl": 10, "radius": 150.0, "brake_time": 3.0},
        "MEDIUM": {"decel": 6.0, "ttl": 20, "radius": 250.0, "brake_time": 2.0},
        "HIGH": {"decel": 8.0, "ttl": 30, "radius": 400.0, "brake_time": 1.5},
        "CRITICAL": {"decel": 9.5, "ttl": 50, "radius": 600.0, "brake_time": 1.0}
    }

    def __init__(self, logger=None):
        self.active_accidents = {}
        self.logger = logger

    def find_collision_pair(self, vehicles):
        """
        Finds a realistic 2-vehicle pair (lead_vehicle, follow_vehicle) driving on the same road edge.
        """
        if not traci.isLoaded():
            keys = [vid for vid in vehicles if not vehicles[vid].is_malicious]
            if len(keys) >= 2:
                return keys[0], keys[1]
            elif keys:
                return keys[0], None
            return None, None

        edge_map = {}
        for vid in traci.vehicle.getIDList():
            if vid in vehicles and not vehicles[vid].is_accident and not vehicles[vid].is_malicious:
                edge = traci.vehicle.getRoadID(vid)
                if edge and not edge.startswith(":"):
                    lane_pos = traci.vehicle.getLanePosition(vid)
                    edge_map.setdefault(edge, []).append((lane_pos, vid))

        best_lead = None
        best_follow = None
        max_edge_count = 0

        for edge, v_tuples in edge_map.items():
            if len(v_tuples) >= 2:
                v_tuples.sort(key=lambda item: item[0], reverse=True)
                for i in range(len(v_tuples) - 1):
                    lead_pos, lead_id = v_tuples[i]
                    follow_pos, follow_id = v_tuples[i + 1]
                    dist = lead_pos - follow_pos
                    if 2.0 <= dist <= 50.0:
                        return lead_id, follow_id

                if len(v_tuples) > max_edge_count:
                    max_edge_count = len(v_tuples)
                    best_lead = v_tuples[0][1]
                    best_follow = v_tuples[1][1]

        if best_lead and best_follow:
            return best_lead, best_follow

        keys = [vid for vid in vehicles if not vehicles[vid].is_malicious]
        if len(keys) >= 2:
            return keys[0], keys[1]
        elif keys:
            return keys[0], None

        return None, None

    def trigger_accident(self, vehicle_id=None, vehicles=None, step=0, severity="HIGH"):
        """
        Triggers realistic 2-vehicle crash collision.
        If explicit vehicle_id is provided but not present in vehicles, returns None.
        """
        if vehicles is None or len(vehicles) == 0:
            return None

        if vehicle_id is not None and str(vehicle_id) not in vehicles:
            if self.logger:
                self.logger.log(f"[AccidentManager] Vehicle {vehicle_id} not found in active vehicles.")
            return None

        lead_vid = vehicle_id
        follow_vid = None

        if lead_vid is None:
            lead_vid, follow_vid = self.find_collision_pair(vehicles)

        if not lead_vid or str(lead_vid) not in vehicles:
            return None

        lead_vid = str(lead_vid)

        severity = severity.upper()
        if severity not in self.SEVERITY_CONFIG:
            severity = "HIGH"

        config = self.SEVERITY_CONFIG[severity]

        # Halt Lead Vehicle
        v_lead = vehicles[lead_vid]
        v_lead.speed = 0.0
        v_lead.is_accident = True

        # Halt Follower Vehicle if available
        v_follow = None
        if follow_vid and str(follow_vid) in vehicles and str(follow_vid) != lead_vid:
            v_follow = vehicles[str(follow_vid)]
            v_follow.speed = 0.0
            v_follow.is_accident = True

        target_edge = ""
        target_lane_idx = 0

        # TraCI interaction
        try:
            if traci.isLoaded():
                if lead_vid in traci.vehicle.getIDList():
                    try:
                        traci.vehicle.slowDown(lead_vid, 0.0, 0.5)
                    except Exception:
                        pass
                    traci.vehicle.setSpeedMode(lead_vid, 0)
                    traci.vehicle.setSpeed(lead_vid, 0.0)
                    traci.vehicle.setColor(lead_vid, (255, 0, 0, 255))
                    try:
                        traci.vehicle.highlight(lead_vid, color=(255, 0, 0, 255), size=35.0)
                    except Exception:
                        pass

                    target_edge = traci.vehicle.getRoadID(lead_vid)
                    lane_id = traci.vehicle.getLaneID(lead_vid)
                    if "_" in lane_id:
                        target_lane_idx = int(lane_id.split("_")[-1])

                if follow_vid and str(follow_vid) in traci.vehicle.getIDList():
                    try:
                        traci.vehicle.slowDown(str(follow_vid), 0.0, 0.5)
                    except Exception:
                        pass
                    traci.vehicle.setSpeedMode(str(follow_vid), 0)
                    traci.vehicle.setSpeed(str(follow_vid), 0.0)
                    traci.vehicle.setColor(str(follow_vid), (255, 0, 0, 255))
                    try:
                        traci.vehicle.highlight(str(follow_vid), color=(255, 0, 0, 255), size=30.0)
                    except Exception:
                        pass
        except Exception as e:
            if self.logger:
                self.logger.log(f"[AccidentManager] TraCI vehicle control note: {e}")

        affected_followers = self._apply_emergency_braking_and_queue(
            target_vid=lead_vid,
            follow_vid=follow_vid,
            target_edge=target_edge,
            target_lane_idx=target_lane_idx,
            target_pos=(v_lead.x, v_lead.y),
            vehicles=vehicles,
            decel=config["decel"],
            radius=config["radius"],
            brake_time=config["brake_time"]
        )

        # Message Consistency (Tc, Algorithm 1): an honest sender reports its true
        # location. A FAKE_ALERT attacker forges a claimed location offset from its
        # real position -- a real, disclosed attack-simulation action (mirrors the
        # existing PACKET_DROP behavior model in broadcast.py), not a fabricated
        # detection result. The true offset is stored on the vehicle so trust.py can
        # honestly observe it next time it computes Tc for this vehicle.
        claimed_location = (v_lead.x, v_lead.y)
        if getattr(v_lead, 'is_malicious', False) and getattr(v_lead, 'attack_type', None) == "FAKE_ALERT":
            offset_m = random.uniform(*FAKE_ALERT_LOCATION_OFFSET_RANGE_M)
            offset_angle = random.uniform(0, 2 * math.pi)
            claimed_location = (
                v_lead.x + offset_m * math.cos(offset_angle),
                v_lead.y + offset_m * math.sin(offset_angle)
            )
            v_lead.location_consistency_error_m = offset_m
        else:
            v_lead.location_consistency_error_m = 0.0
        v_lead.has_reported_message = True

        message = EmergencyMessage(
            sender=lead_vid,
            location=claimed_location,
            severity=severity
        )
        message.ttl = config["ttl"]
        message.radius = config["radius"]
        sign_message(message)

        accident_record = {
            "lead_vehicle": lead_vid,
            "follow_vehicle": follow_vid,
            "location": (v_lead.x, v_lead.y),
            "step": step,
            "severity": severity,
            "message": message,
            "affected_followers": affected_followers,
            "edge": target_edge
        }

        self.active_accidents[lead_vid] = accident_record
        if follow_vid:
            self.active_accidents[str(follow_vid)] = accident_record

        if self.logger:
            if affected_followers:
                shown = affected_followers[:8]
                affected_str = ", ".join(shown) + (
                    f", +{len(affected_followers) - 8} more" if len(affected_followers) > 8 else ""
                )
            else:
                affected_str = "None"

            self.logger.log("\n" + "=" * 70)
            self.logger.log("PHASE 7: TWO-VEHICLE CRASH COLLISION DETECTED")
            self.logger.log("=" * 70)
            self.logger.log(
                f"  └─> Lead Crash Vehicle   : {lead_vid} (HALTED RED)\n"
                f"  └─> Rear Crash Vehicle   : {follow_vid or 'N/A'} (COLLIDED RED)\n"
                f"  └─> Crash Location       : ({v_lead.x:.2f}, {v_lead.y:.2f})\n"
                f"  └─> Road Edge            : {target_edge or 'Urban Edge'}\n"
                f"  └─> Traffic Congestion   : {len(affected_followers)} trailing vehicles braking in queue (ORANGE): {affected_str}"
            )

        return message

    def _apply_emergency_braking_and_queue(self, target_vid, follow_vid, target_edge, target_lane_idx, target_pos, vehicles, decel, radius, brake_time):
        affected = []
        crash_vids = {str(target_vid), str(follow_vid)}

        for vid, v in vehicles.items():
            if str(vid) in crash_vids or v.is_accident:
                continue

            dist = math.hypot(v.x - target_pos[0], v.y - target_pos[1])
            if dist <= radius:
                new_speed = max(0.0, v.speed - decel)
                v.speed = new_speed
                affected.append(vid)
                v.trigger_braking_highlight(duration_steps=20)

                try:
                    if traci.isLoaded() and vid in traci.vehicle.getIDList():
                        traci.vehicle.slowDown(vid, new_speed, brake_time)
                        if target_edge and traci.vehicle.getRoadID(vid) == target_edge:
                            num_lanes = traci.edge.getLaneNumber(target_edge)
                            if num_lanes > 1:
                                target_alt_lane = (target_lane_idx + 1) % num_lanes
                                traci.vehicle.changeLane(vid, target_alt_lane, 5.0)
                except Exception:
                    pass

        return affected

    def clear_accident(self, vehicle_id, vehicles):
        vehicle_id = str(vehicle_id)
        if vehicle_id in self.active_accidents:
            rec = self.active_accidents.pop(vehicle_id)
            lead = rec.get("lead_vehicle")
            follow = rec.get("follow_vehicle")
            for vid in [lead, follow]:
                if vid and str(vid) in vehicles:
                    vehicles[str(vid)].is_accident = False
                try:
                    if traci.isLoaded() and vid and str(vid) in traci.vehicle.getIDList():
                        traci.vehicle.setSpeedMode(str(vid), 31)
                except Exception:
                    pass

    def is_in_accident(self, vehicle_id):
        return str(vehicle_id) in self.active_accidents

    def get_active_accidents(self):
        return self.active_accidents
