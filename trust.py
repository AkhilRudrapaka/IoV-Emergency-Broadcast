import random
import math

try:
    from config import (
        TRUST_INITIAL, TRUST_MIN, TRUST_MAX, TRUST_BLACKLIST_THRESHOLD,
        TRUST_WEIGHT_FWD, TRUST_WEIGHT_AUTH, TRUST_WEIGHT_PDR,
        TRUST_WEIGHT_HIST, TRUST_WEIGHT_REC, TRUST_EMA_ALPHA
    )
except ImportError:
    TRUST_INITIAL = 0.5
    TRUST_MIN = 0.0
    TRUST_MAX = 1.0
    TRUST_BLACKLIST_THRESHOLD = 0.3
    TRUST_WEIGHT_FWD = 0.30
    TRUST_WEIGHT_AUTH = 0.25
    TRUST_WEIGHT_PDR = 0.20
    TRUST_WEIGHT_HIST = 0.15
    TRUST_WEIGHT_REC = 0.10
    TRUST_EMA_ALPHA = 0.7


class TrustManager:
    """
    Behavior-Based Trust Evaluation & Dynamic Node Classification Manager.
    Calculates composite trust scores using Exponential Moving Average (EMA)
    and enforces dynamic blacklisting and classification transitions.
    """

    def __init__(self, logger=None):
        self.alpha = TRUST_EMA_ALPHA
        self.logger = logger

    def calculate_trust(self, vehicle, vehicles=None):
        """
        Calculates behavior-based trust score for a vehicle:
        T_total = w_fwd*T_fwd + w_auth*T_auth + w_pdr*T_pdr + w_hist*T_hist + w_rec*T_rec

        Evaluates behavior counters, applies penalty for malicious behavior,
        updates historical trust (EMA), updates classification, and enforces dynamic blacklisting.
        """
        old_trust = vehicle.trust

        # If node is malicious, simulate degraded behavior counters
        if vehicle.is_malicious:
            if vehicle.attack_type == "PACKET_DROP":
                vehicle.successful_forwards = max(0, vehicle.successful_forwards - 2)
            elif vehicle.attack_type == "FAKE_ALERT":
                vehicle.auth_successes = max(0, vehicle.auth_successes - 2)

        # 1. Forwarding Trust (T_fwd)
        if vehicle.forward_attempts > 0:
            t_fwd = max(0.0, min(1.0, vehicle.successful_forwards / vehicle.forward_attempts))
        else:
            t_fwd = 0.15 if (vehicle.is_malicious and vehicle.attack_type == "PACKET_DROP") else 0.85

        # 2. Authentication Success Trust (T_auth)
        if vehicle.auth_attempts > 0:
            t_auth = max(0.0, min(1.0, vehicle.auth_successes / vehicle.auth_attempts))
        else:
            t_auth = 0.10 if (vehicle.is_malicious and vehicle.attack_type == "FAKE_ALERT") else 0.95

        # 3. Packet Delivery Ratio Trust (T_pdr)
        if vehicle.total_received > 0:
            t_pdr = max(0.0, min(1.0, vehicle.successful_forwards / vehicle.total_received))
        else:
            t_pdr = 0.25 if vehicle.is_malicious else 0.90

        # 4. Neighbor Recommendation Trust (T_rec)
        t_rec = self._calculate_recommendations(vehicle, vehicles)

        # Immediate component score
        t_current = (
            TRUST_WEIGHT_FWD * t_fwd +
            TRUST_WEIGHT_AUTH * t_auth +
            TRUST_WEIGHT_PDR * t_pdr +
            TRUST_WEIGHT_REC * t_rec
        ) / (TRUST_WEIGHT_FWD + TRUST_WEIGHT_AUTH + TRUST_WEIGHT_PDR + TRUST_WEIGHT_REC)

        # 5. Historical Trust (T_hist) via Exponential Moving Average (EMA)
        t_hist = self.alpha * vehicle.historical_trust + (1.0 - self.alpha) * t_current
        vehicle.historical_trust = t_hist

        # Overall composite trust calculation
        composite_trust = (
            TRUST_WEIGHT_FWD * t_fwd +
            TRUST_WEIGHT_AUTH * t_auth +
            TRUST_WEIGHT_PDR * t_pdr +
            TRUST_WEIGHT_HIST * t_hist +
            TRUST_WEIGHT_REC * t_rec
        )

        final_trust = max(TRUST_MIN, min(TRUST_MAX, round(composite_trust, 2)))
        vehicle.trust = final_trust

        # Dynamic Blacklisting & Classification Enforcement
        if final_trust < TRUST_BLACKLIST_THRESHOLD or vehicle.is_malicious:
            vehicle.is_blacklisted = True
            vehicle.is_cluster_head = False
            vehicle.classification = "MALICIOUS"
        elif final_trust >= 0.7:
            vehicle.is_blacklisted = False
            vehicle.classification = "TRUSTED"
        else:
            vehicle.is_blacklisted = False
            vehicle.classification = "UNKNOWN"

        # Log significant trust changes (Phase 5)
        if self.logger and abs(final_trust - old_trust) >= 0.15:
            reason = "Packet Drop Attack" if vehicle.is_malicious else "Consistent Behavioral Delivery"
            self.logger.log(
                f"[Trust Evaluation] Vehicle {vehicle.id:<6}: Trust Updated "
                f"{old_trust:.2f} -> {final_trust:.2f} | Reason: {reason} | Class: {vehicle.classification}"
            )

        return vehicle.trust

    def _calculate_recommendations(self, vehicle, vehicles):
        """
        Calculates average recommendation score from non-malicious neighboring nodes,
        filtering out forged recommendations.
        """
        if not vehicles or not vehicle.neighbors:
            return 0.2 if vehicle.is_malicious else 0.8

        recommendation_scores = []
        for n_id in vehicle.neighbors:
            n_id = str(n_id)
            if n_id in vehicles:
                neighbor = vehicles[n_id]
                # Filter out recommendations from blacklisted or malicious recommenders
                if neighbor.is_blacklisted or neighbor.is_malicious:
                    continue

                if vehicle.id in neighbor.recommendations:
                    recommendation_scores.append(neighbor.recommendations[vehicle.id])
                else:
                    recommendation_scores.append(neighbor.trust)

        if recommendation_scores:
            return sum(recommendation_scores) / len(recommendation_scores)
        return 0.1 if vehicle.is_malicious else 0.85

    def update_behavior_event(self, vehicle, event_type, is_success=True):
        """
        Updates node behavior statistics upon network events (forwarding, auth, packet drop).
        """
        if event_type == "FORWARD":
            vehicle.forward_attempts += 1
            if is_success:
                vehicle.successful_forwards += 1
        elif event_type == "AUTH":
            vehicle.auth_attempts += 1
            if is_success:
                vehicle.auth_successes += 1
        elif event_type == "RECEIVE":
            vehicle.total_received += 1
        elif event_type == "DROP":
            vehicle.forward_attempts += 1
            vehicle.successful_forwards = max(0, vehicle.successful_forwards - 1)
