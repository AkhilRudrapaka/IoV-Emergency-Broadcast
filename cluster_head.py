try:
    from config import TRUST_THRESHOLD_TRUSTED, TRUST_BLACKLIST_THRESHOLD
except ImportError:
    TRUST_THRESHOLD_TRUSTED = 0.7
    TRUST_BLACKLIST_THRESHOLD = 0.3


class ClusterHeadManager:
    """
    Cluster Head (CH) Selection Manager.
    Elects CH for each spatial DBSCAN cluster based on a composite score:
      Score = 60% Trust Score + 40% Speed Stability
    CH election is restricted to TRUSTED vehicles (T>=0.7).

    PROOF-OF-WORK
    --------------
    Following [Chen & Wu, 2024, Sec. 4.3] "The most suitable CH is selected by
    ... vehicle nodes" using a composite scoring approach for CH candidacy, and
    [Azizi & Shokrollahi, 2024 (RTRV), Table 2] which weights *multiple* factors
    (angle, distance, two-hop neighbor info, trust: w'_1..w'_4) when selecting
    its "monitoring" relay node -- trust is one weighted factor among several,
    the same structural pattern this 0.6*Trust + 0.4*SpeedStability score
    follows. Two further papers independently confirm weighted multi-factor CH
    scoring as this field's standard pattern: [Darabkh et al., 2025, Eq. 3]
    weights Lifetime/Distance/Speed, and [Khan et al., 2026, Eq. 2] weights
    Connectivity-Lifespan/Degree/Past-CH-Lifetime -- found in a second literature
    folder (base papers/Research paper-set1/) after the original two-paper
    grounding above was already in place. Neither uses trust as a factor, so
    this project's Trust term is a security-motivated extension beyond all four
    papers now surveyed; none of the four publishes this exact 60/40 split or a
    "TRUSTED-only" eligibility gate verbatim -- the specific weights and the
    trust-tier restriction remain this project's own tuning of that shared
    trust-weighted-selection pattern. Full citations: docs/ALGORITHMS.md.

    Bootstrap fallback (this project's own contribution, not from any paper): trust starts neutral (0.5) for every vehicle and only
    rises through real forwarding/RSU evidence -- which requires *being* a CH to
    generate in the first place. Taking "TRUSTED-only" literally with no fallback
    creates a permanent deadlock (verified analytically: with zero real events,
    composite trust asymptotically caps around ~0.61, strictly below 0.7, so no
    vehicle would ever become CH-eligible and the whole pipeline would silently
    produce zero Cluster Heads forever). So: prefer TRUSTED candidates; only when
    a cluster has none does it fall back to UNKNOWN (T>=0.3) candidates, letting
    the system bootstrap real evidence. Blacklisted/malicious-by-trust (T<0.3)
    vehicles are never eligible either way.
    """

    def __init__(self, logger=None):
        self.logger = logger

    def select_cluster_heads(self, vehicles, clusters):
        """
        Selects optimal Cluster Head for each active spatial cluster.

        Args:
            vehicles (dict): vehicle_id -> Vehicle instance.
            clusters (dict): cluster_id -> list of member vehicle_ids.

        Returns:
            dict: cluster_id -> elected CH vehicle_id.
        """
        cluster_heads = {}

        for cluster_id, members in clusters.items():
            if cluster_id == -1:  # Skip noise nodes
                continue

            # Pass 1: TRUSTED candidates only (T >= 0.7), per the Report.
            # Pass 2 (bootstrap fallback): UNKNOWN candidates (0.3 <= T < 0.7),
            # only used if pass 1 found nobody in this cluster.
            best_vehicle, best_score, best_trust, best_speed_stab = self._elect_best(
                members, vehicles, min_trust=TRUST_THRESHOLD_TRUSTED
            )
            bootstrap = False
            if best_vehicle is None:
                best_vehicle, best_score, best_trust, best_speed_stab = self._elect_best(
                    members, vehicles, min_trust=TRUST_BLACKLIST_THRESHOLD
                )
                bootstrap = best_vehicle is not None

            if best_vehicle:
                best_vehicle.is_cluster_head = True
                cluster_heads[cluster_id] = best_vehicle.id

                if self.logger:
                    tag = " [BOOTSTRAP: no TRUSTED candidate available]" if bootstrap else ""
                    self.logger.log(
                        f"[CH Selection] Cluster {cluster_id:<3}: Elected CH Vehicle '{best_vehicle.id}' "
                        f"| Score: {best_score:.3f} (Trust: {best_trust:.2f}, SpeedStab: {best_speed_stab:.2f}){tag}"
                    )

        return cluster_heads

    def _elect_best(self, members, vehicles, min_trust):
        """
        Finds the highest composite-score (60% Trust + 40% Speed Stability)
        candidate among `members` with trust >= min_trust and not blacklisted.
        """
        best_vehicle = None
        best_score = -1.0
        best_trust = 0.0
        best_speed_stab = 0.0

        for vehicle_id in members:
            vehicle_id = str(vehicle_id)
            if vehicle_id not in vehicles:
                continue

            vehicle = vehicles[vehicle_id]

            # Exclude blacklisted or sub-threshold nodes (trust-derived, not ground
            # truth -- a vehicle is excluded because of what it's observed to have
            # done, not because the simulator secretly knows it's malicious).
            if getattr(vehicle, 'is_blacklisted', False) or vehicle.trust < min_trust:
                if vehicle.trust < TRUST_BLACKLIST_THRESHOLD:
                    vehicle.is_cluster_head = False
                continue

            speed_stability = max(0.0, 1.0 - (vehicle.speed / 22.0))
            score = (0.6 * vehicle.trust) + (0.4 * speed_stability)

            if score > best_score:
                best_score = score
                best_vehicle = vehicle
                best_trust = vehicle.trust
                best_speed_stab = speed_stability

        return best_vehicle, best_score, best_trust, best_speed_stab
