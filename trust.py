import random
import math

try:
    from config import (
        TRUST_INITIAL, TRUST_MIN, TRUST_MAX, TRUST_BLACKLIST_THRESHOLD, TRUST_THRESHOLD_TRUSTED,
        TRUST_WEIGHT_FWD, TRUST_WEIGHT_CONSISTENCY, TRUST_WEIGHT_SPEED, TRUST_WEIGHT_HIST,
        TRUST_EMA_ALPHA, TRUST_EMA_CURRENT_WEIGHT,
        RSU_TRUST_BLEND_VEHICLE_WEIGHT, RSU_TRUST_BLEND_RSU_WEIGHT,
        MAX_SPEED_DELTA_PER_STEP_MPS, MAX_SPEED_MPS, MESSAGE_LOCATION_TOLERANCE_M
    )
    NEUTRAL_TRUST = TRUST_INITIAL
except ImportError:
    TRUST_INITIAL = 0.5
    TRUST_MIN = 0.0
    TRUST_MAX = 1.0
    TRUST_BLACKLIST_THRESHOLD = 0.3
    TRUST_THRESHOLD_TRUSTED = 0.7
    TRUST_WEIGHT_FWD = 0.30
    TRUST_WEIGHT_CONSISTENCY = 0.25
    TRUST_WEIGHT_SPEED = 0.20
    TRUST_WEIGHT_HIST = 0.25
    TRUST_EMA_ALPHA = 0.85
    TRUST_EMA_CURRENT_WEIGHT = 0.15
    RSU_TRUST_BLEND_VEHICLE_WEIGHT = 0.80
    RSU_TRUST_BLEND_RSU_WEIGHT = 0.20
    MAX_SPEED_DELTA_PER_STEP_MPS = 4.5
    MAX_SPEED_MPS = 22.0
    MESSAGE_LOCATION_TOLERANCE_M = 50.0
    NEUTRAL_TRUST = TRUST_INITIAL


class TrustManager:
    """
    Bayesian Trust Model (Algorithm 1): behavior-based trust from four weighted
    factors -- Forwarding Behaviour (Tf), Message Consistency (Tc), Speed
    Plausibility (Ts), and EMA-decayed Historical Trust (Th) -- plus a persistent
    RSU-assessment blend.

    Tf is real and event-driven (update_behavior_event(), fed by broadcast.py/
    bls_auth.py). Tc and Ts are computed from real per-step simulation state
    (claimed-vs-actual message location; kinematic speed-change plausibility) using
    this session's standard-VANET-trust-literature interpretation of the factor
    names -- no external formula for them was available (see config.py), so treat
    their exact thresholds as provisional pending the source report.

    is_malicious/attack_type are simulation-only ground truth used to decide what a
    simulated attacker's real actions look like (broadcast.py's PACKET_DROP,
    accident.py's FAKE_ALERT location forgery); they are never read here.
    """

    def __init__(self, logger=None):
        self.alpha = TRUST_EMA_ALPHA
        self.current_weight = TRUST_EMA_CURRENT_WEIGHT
        self.logger = logger

    def calculate_trust(self, vehicle, vehicles=None):
        """
        t_current = (0.30*Tf + 0.25*Tc + 0.20*Ts) / 0.75
        New_Th    = 0.85*Old_Th + 0.15*t_current
        Trust(v)  = 0.30*Tf + 0.25*Tc + 0.20*Ts + 0.25*Th
        Final     = 0.80*Trust(v) + 0.20*rsu_trust_assessment
        """
        old_trust = vehicle.trust

        # 1. Forwarding Behaviour (Tf) -- real, event-driven. A vehicle with zero
        # observed interactions this run is honestly "unknown," not pre-scored.
        if vehicle.forward_attempts > 0:
            t_fwd = max(0.0, min(1.0, vehicle.successful_forwards / vehicle.forward_attempts))
        else:
            t_fwd = NEUTRAL_TRUST

        # 2. Message Consistency (Tc) -- claimed-vs-actual location error at the
        # moment this vehicle last sent/reported an emergency message (set by
        # accident.py). No message reported yet this run -> neutral default.
        if vehicle.has_reported_message:
            if vehicle.location_consistency_error_m <= MESSAGE_LOCATION_TOLERANCE_M:
                t_c = 1.0
            else:
                excess = vehicle.location_consistency_error_m - MESSAGE_LOCATION_TOLERANCE_M
                t_c = max(0.0, 1.0 - excess / MESSAGE_LOCATION_TOLERANCE_M)
        else:
            t_c = NEUTRAL_TRUST

        # 3. Speed Plausibility (Ts) -- kinematic feasibility: is this step's speed
        # change within a physically realistic bound (matches the SUMO vType's own
        # decel bound, network/routes*.xml), and is speed within maxSpeed?
        if vehicle.speed > MAX_SPEED_MPS:
            t_s = max(0.0, 1.0 - (vehicle.speed - MAX_SPEED_MPS) / MAX_SPEED_MPS)
        else:
            speed_delta = abs(vehicle.speed - vehicle.prev_speed)
            if speed_delta <= MAX_SPEED_DELTA_PER_STEP_MPS:
                t_s = 1.0
            else:
                excess = speed_delta - MAX_SPEED_DELTA_PER_STEP_MPS
                t_s = max(0.0, 1.0 - excess / MAX_SPEED_DELTA_PER_STEP_MPS)

        # Immediate component score, normalized over the three non-historical weights
        t_current = (
            TRUST_WEIGHT_FWD * t_fwd +
            TRUST_WEIGHT_CONSISTENCY * t_c +
            TRUST_WEIGHT_SPEED * t_s
        ) / (TRUST_WEIGHT_FWD + TRUST_WEIGHT_CONSISTENCY + TRUST_WEIGHT_SPEED)

        # 4. Historical Trust (Th) via EMA decay
        t_h = self.alpha * vehicle.historical_trust + self.current_weight * t_current
        vehicle.historical_trust = t_h

        composite_trust = (
            TRUST_WEIGHT_FWD * t_fwd +
            TRUST_WEIGHT_CONSISTENCY * t_c +
            TRUST_WEIGHT_SPEED * t_s +
            TRUST_WEIGHT_HIST * t_h
        )

        # RSU boost: a persistent blend (vehicle.rsu_trust_assessment is nudged by
        # rsu.py on each verification outcome and carried across steps), not a
        # one-off mutation that the next calculate_trust() call would silently erase.
        final_trust_raw = (
            RSU_TRUST_BLEND_VEHICLE_WEIGHT * composite_trust +
            RSU_TRUST_BLEND_RSU_WEIGHT * vehicle.rsu_trust_assessment
        )

        final_trust = max(TRUST_MIN, min(TRUST_MAX, round(final_trust_raw, 2)))
        vehicle.trust = final_trust

        # Dynamic Blacklisting & Classification Enforcement -- derived from the
        # observed trust score alone. is_malicious/attack_type are simulation-only
        # ground truth used to decide what an attacker's real behavior events look
        # like (see broadcast.py, bls_auth.py); they must never leak into what the
        # trust system concludes about a vehicle.
        if final_trust < TRUST_BLACKLIST_THRESHOLD:
            vehicle.is_blacklisted = True
            vehicle.is_cluster_head = False
            vehicle.classification = "MALICIOUS"
        elif final_trust >= TRUST_THRESHOLD_TRUSTED:
            vehicle.is_blacklisted = False
            vehicle.classification = "TRUSTED"
        else:
            vehicle.is_blacklisted = False
            vehicle.classification = "UNKNOWN"

        # Log significant trust changes (Phase 5)
        if self.logger and abs(final_trust - old_trust) >= 0.15:
            reason = "Observed Forwarding/Consistency/Speed Anomaly" if final_trust < old_trust else "Consistent Behavioral Delivery"
            self.logger.log(
                f"[Trust Evaluation] Vehicle {vehicle.id:<6}: Trust Updated "
                f"{old_trust:.2f} -> {final_trust:.2f} | Reason: {reason} | Class: {vehicle.classification}"
            )

        return vehicle.trust

    def apply_rsu_feedback(self, vehicle, is_success, nudge):
        """
        Persistently nudges vehicle.rsu_trust_assessment on an RSU verification
        outcome (called from rsu.py). This is the RSU-boost *input*, blended into
        the formula by calculate_trust() on every subsequent call -- unlike a direct
        vehicle.trust mutation, it survives to the next step instead of being
        silently overwritten by the next recomputation (CRITICAL fix, Report S10.2).
        """
        delta = nudge if is_success else -nudge
        vehicle.rsu_trust_assessment = max(TRUST_MIN, min(TRUST_MAX, round(vehicle.rsu_trust_assessment + delta, 2)))
        return vehicle.rsu_trust_assessment

    def update_behavior_event(self, vehicle, event_type, is_success=True):
        """
        Updates node behavior statistics upon network events (forwarding, auth, packet drop).
        auth_attempts/auth_successes/total_received are retained as real diagnostic
        counters (still populated by bls_auth.py/broadcast.py) but are no longer
        direct inputs to calculate_trust() -- the Report's 4-factor model uses Tf/Tc/
        Ts/Th only; authentication outcome instead *consumes* trust (as the tiered
        verification gate in bls_auth.py), rather than feeding it.
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
