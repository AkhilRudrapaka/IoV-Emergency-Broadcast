import time
import math
import traci
from authentication import verify_signature

try:
    from config import RSU_LOCATIONS, RSU_TRUST_NUDGE
except ImportError:
    RSU_LOCATIONS = {
        "RSU_NORTH": (400.0, 750.0),
        "RSU_SOUTH": (400.0, 50.0),
        "RSU_EAST": (750.0, 400.0),
        "RSU_WEST": (50.0, 400.0),
        "RSU_CENTER": (400.0, 400.0)
    }
    RSU_TRUST_NUDGE = 0.05


class RSU:
    """
    Roadside Unit (RSU) Node in the 5x5 Urban Network.
    Renders high-visibility RSU polygons/towers in SUMO GUI and flashes bright Cyan/Yellow on packet receipt.
    Implements Phase 11 Processing Pipeline:
    Ingress Queue -> Authentication -> Decision Engine -> Analytics -> Trust Update -> Dissemination.
    """

    def __init__(self, rsu_id, position, logger=None):
        self.rsu_id = str(rsu_id)
        self.x = float(position[0])
        self.y = float(position[1])
        self.logger = logger

        # Analytics Counter (Phase 11)
        self.packets_received = 0
        self.packets_verified = 0
        self.packets_dropped = 0
        self.received_log = []
        self.flash_timer = 0

    @property
    def position(self):
        return (self.x, self.y)

    def trigger_flash(self, steps=15):
        self.flash_timer = steps
        poly_id = f"POLY_{self.rsu_id}"
        try:
            if traci.isLoaded() and poly_id in traci.polygon.getIDList():
                # Flash bright Cyan color on message packet receipt
                traci.polygon.setColor(poly_id, (0, 255, 255, 255))
        except Exception:
            pass

    def update_step(self):
        """
        Decays visual flash timer and resets RSU polygon color back to Green.
        """
        if self.flash_timer > 0:
            self.flash_timer -= 1
            if self.flash_timer == 0:
                poly_id = f"POLY_{self.rsu_id}"
                try:
                    if traci.isLoaded() and poly_id in traci.polygon.getIDList():
                        # Reset to Bright Green
                        traci.polygon.setColor(poly_id, (0, 255, 0, 255))
                except Exception:
                    pass

    def verify_sender(self, sender_id, vehicles=None):
        """
        Verifies sender identity and registration state.
        """
        if not sender_id:
            return False
        sender_id = str(sender_id)
        if vehicles is not None:
            if sender_id not in vehicles:
                return False
            vehicle = vehicles[sender_id]
            if getattr(vehicle, 'is_blacklisted', False) or vehicle.classification == "MALICIOUS":
                if self.logger:
                    self.logger.log(f"[RSU {self.rsu_id}] Rejected sender '{sender_id}' (Blacklisted/Malicious).")
                return False
            return True
        return isinstance(sender_id, str) and len(sender_id) > 0

    def receive_and_process_message(self, message, vehicles=None, cluster_heads=None, authenticator=None, metrics=None, auth_manager=None, trust_manager=None):
        """
        Phase 11 RSU Processing Pipeline:
        Ingress Queue -> Authentication -> Decision Engine -> Analytics -> Trust Update -> Dissemination.

        Args:
            auth_manager (bls_auth.AuthenticationManager, optional): when provided, the
                signature-validity decision (Priority 2) is delegated to it — supporting
                BLS individual/batch verification and trust-gating — instead of the
                original SHA-256/no-signature-present check below. When omitted (the
                default), behavior is exactly as before Priority 2.
            trust_manager (trust.TrustManager, optional): forwarded to auth_manager so
                every signer's real verification outcome updates their observed
                auth_attempts/auth_successes counters (Priority 3 integration point).
        """
        self.packets_received += 1
        self.trigger_flash(15)
        sender_id = getattr(message, 'sender', None)

        if self.logger:
            self.logger.log("\n" + "=" * 70)
            self.logger.log("PHASE 10 & 11: RSU INGRESS - AUTHENTICATION & DECISION ENGINE")
            self.logger.log("=" * 70)
            self.logger.log(f"[RSU {self.rsu_id}] Ingress Queue: Received Message '{message.message_id}' from '{sender_id}'")

        # Step 1: Authentication
        valid_sender = self.verify_sender(sender_id, vehicles)
        bls_perf = None

        if auth_manager is not None:
            valid_signature, bls_perf = auth_manager.verify_message(message, vehicles, trust_manager=trust_manager)
        elif hasattr(message, 'signature') and message.signature:
            if authenticator:
                valid_signature = authenticator.verify_signature(message)
            else:
                valid_signature = verify_signature(message)
        else:
            valid_signature = True

        auth_pass = valid_sender and valid_signature

        if metrics:
            metrics.record_auth_result(auth_pass)
            if bls_perf:
                metrics.record_bls_performance(bls_perf)

        # Step 2: Decision Engine (Accept / Reject / Ignore / Broadcast)
        if not auth_pass:
            self.packets_dropped += 1
            decision = "REJECTED"
            log_entry = {
                "rsu_id": self.rsu_id,
                "message_id": getattr(message, 'message_id', 'UNKNOWN'),
                "sender": sender_id,
                "location": getattr(message, 'location', (0, 0)),
                "severity": getattr(message, 'severity', 'HIGH'),
                "timestamp": time.time(),
                "status": "REJECTED",
                "decision": decision,
                "ack_sent": False
            }
            self.received_log.append(log_entry)
            if trust_manager and vehicles and sender_id in vehicles:
                trust_manager.apply_rsu_feedback(vehicles[sender_id], is_success=False, nudge=RSU_TRUST_NUDGE)
            if self.logger:
                self.logger.log(f"[RSU {self.rsu_id}] Authentication: FAIL | Decision: {decision}")
            return None

        self.packets_verified += 1
        decision = "ACCEPTED"

        if self.logger:
            self.logger.log(f"[RSU {self.rsu_id}] Authentication: PASS | Decision: {decision}")

        # Step 3: Analytics Update
        log_entry = {
            "rsu_id": self.rsu_id,
            "message_id": getattr(message, 'message_id', 'UNKNOWN'),
            "sender": sender_id,
            "location": getattr(message, 'location', (0, 0)),
            "severity": getattr(message, 'severity', 'HIGH'),
            "timestamp": time.time(),
            "status": "VERIFIED",
            "decision": decision,
            "ack_sent": True
        }
        self.received_log.append(log_entry)

        # Step 4: RSU Trust Feedback (Algorithm 1 RSU boost, Report CRITICAL S10.2).
        # Nudges the *persistent* vehicle.rsu_trust_assessment input, which
        # calculate_trust() blends in (0.80*vehicle + 0.20*RSU) on every subsequent
        # call -- unlike a direct vehicle.trust mutation, this survives to the next
        # step instead of being silently overwritten by the next recomputation.
        if vehicles and sender_id in vehicles and trust_manager:
            sender_veh = vehicles[sender_id]
            old_assessment = sender_veh.rsu_trust_assessment
            new_assessment = trust_manager.apply_rsu_feedback(sender_veh, is_success=True, nudge=RSU_TRUST_NUDGE)
            if self.logger:
                self.logger.log(
                    f"[RSU {self.rsu_id}] RSU Trust Assessment Updated: Vehicle {sender_id} "
                    f"{old_assessment:.2f} -> {new_assessment:.2f} | Reason: Successful RSU Authentication"
                )

        # Step 5: Send Acknowledgement (ACK)
        ack = self.send_acknowledgement(message)

        if self.logger:
            self.logger.log(
                f"[RSU {self.rsu_id}] Authentication: PASS -> Decision: {decision} -> "
                f"ACK Sent: '{ack['ack_id']}'"
            )

        # Step 6: Phase 12 Dissemination to Nearby Vehicles & Traffic Control Center (TCC)
        self.disseminate_to_tcc_and_network(message, vehicles)

        return ack

    def receive_message(self, message, vehicles=None, authenticator=None, metrics=None, auth_manager=None):
        return self.receive_and_process_message(message, vehicles=vehicles, authenticator=authenticator, metrics=metrics, auth_manager=auth_manager)

    def send_acknowledgement(self, message):
        ack = {
            "ack_id": f"ACK_{getattr(message, 'message_id', 'MSG')}",
            "target_sender": getattr(message, 'sender', None),
            "rsu_id": self.rsu_id,
            "timestamp": time.time(),
            "status": "DELIVERED"
        }
        if self.logger:
            self.logger.log(f"[RSU {self.rsu_id}] ACK Sent: '{ack['ack_id']}' delivered to '{ack['target_sender']}'")
        return ack

    def disseminate_to_tcc_and_network(self, message, vehicles):
        if self.logger:
            self.logger.log("\n" + "=" * 70)
            self.logger.log("PHASE 12: EMERGENCY DISSEMINATION & TRAFFIC CENTER ALERT")
            self.logger.log("=" * 70)
            self.logger.log(f"  └─> [Emergency Delivered] RSU '{self.rsu_id}' published warning to local V2X channel.")
            self.logger.log(f"  └─> [Traffic Warning] Speed limits reduced on surrounding edges.")
            self.logger.log(f"  └─> [Traffic Center Updated] Central TCC log updated for Incident #{message.message_id}")

    def get_log(self):
        return self.received_log


class RSUManager:
    """
    Multi-RSU Deployment & Topology Manager for 5x5 Urban Grid.
    """

    def __init__(self, logger=None, deploy_default_rsus=True):
        self.logger = logger
        self.rsus = {}
        # Cross-RSU/cross-CH event dedup (HIGH priority, Report S10.2): the same
        # accident UUID reported via multiple Cluster Heads or delivered to more
        # than one RSU must be verified only once.
        self.processed_message_ids = set()
        self.processed_acks = {}
        if deploy_default_rsus:
            self.deploy_default_network()

    def is_duplicate_event(self, message_id):
        return message_id in self.processed_message_ids

    def record_processed_event(self, message_id, ack):
        self.processed_message_ids.add(message_id)
        self.processed_acks[message_id] = ack

    def get_cached_ack(self, message_id):
        return self.processed_acks.get(message_id)

    def deploy_default_network(self):
        for rsu_id, pos in RSU_LOCATIONS.items():
            self.add_rsu(rsu_id, pos)

    def add_rsu(self, rsu_id, position):
        rsu = RSU(rsu_id, position, logger=self.logger)
        self.rsus[str(rsu_id)] = rsu
        return rsu

    def update_step(self):
        for rsu in self.rsus.values():
            rsu.update_step()

    def get_rsu(self, rsu_id):
        return self.rsus.get(str(rsu_id))

    def get_all_rsus(self):
        return self.rsus

    def get_nearest_rsu(self, location):
        if not self.rsus:
            return "RSU_CENTER", (400.0, 400.0), None

        min_dist = float('inf')
        nearest_rsu = None

        for rsu in self.rsus.values():
            dist = math.hypot(location[0] - rsu.x, location[1] - rsu.y)
            if dist < min_dist:
                min_dist = dist
                nearest_rsu = rsu

        return nearest_rsu.rsu_id, nearest_rsu.position, nearest_rsu
