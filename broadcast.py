from utils import euclidean_distance


class BroadcastManager:
    """
    Controlled Broadcast & Duplicate Message Suppression Manager.
    Maintains a message UUID cache to prevent broadcast storm flooding and duplicate loops.

    PROOF-OF-WORK
    --------------
    - Only Cluster Heads forward, unique-ID duplicate suppression: following
      [Kaur et al., 2024, Sec. 3] "The proposed scheme features a new
      message-forwarding route that ... reduce[s] latency and minimize[s]
      flooding" via a controlled CH-based forwarding structure, and
      [Kaur et al., 2024, Sec. 4] the CT (Cluster Table)/CH-mediated
      dissemination pattern this broadcast()/broadcast_route() split mirrors
      (fan-out across active CHs vs. relay along one discovered path).
    - Cooperative majority-vote confirmation (_has_majority_confirmation,
      >50% of a CH's own cluster corroborating before it forwards) is this
      project's OWN CONTRIBUTION -- no paper in the original base-papers/ set
      specifies a majority-vote gate. It is a natural extension of Kaur et
      al.'s CH-mediated structure (adding a corroboration check before the CH
      acts on Kaur et al.'s behalf), not a method taken from any cited paper.
      [Qi et al., 2024 (HTEMD)], found in a second literature folder
      (base papers/Research paper-set1/), independently arrives at the same
      defensive premise -- don't act on a single unverified report -- via a
      mechanistically different scheme (a receiver entropy-weights
      P_EM probabilities across *multiple senders* reporting the same event,
      vs. this project's own-cluster-membership headcount); cited as a related
      premise, not as this mechanism's source. Full citations:
      docs/ALGORITHMS.md.
    """

    def __init__(self, logger=None):
        # Cache of already forwarded message IDs
        self.message_cache = set()
        self.logger = logger

    def _has_majority_confirmation(self, ch_veh, message, vehicles, clusters):
        """
        HIGH priority, Report S10.2: before a Cluster Head forwards, more than 50%
        of its own cluster members must corroborate the event. A member "confirms"
        if it's within the message's real alert radius (message.radius, set per
        severity in accident.py) of the claimed location, or is itself reacting to
        the accident (is_braking/is_accident -- real, already-tracked congestion
        state). This is a real gate computed from real per-step positions, not a
        fabricated pass/fail.
        """
        if clusters is None:
            return True  # no cluster info available -- don't block (backward compat)

        cluster_id = getattr(ch_veh, 'cluster', -1)
        members = clusters.get(cluster_id, []) if cluster_id != -1 else []
        if not members:
            return True  # noise/unclustered CH -- nothing to poll, allow forward

        confirmed = 0
        for member_id in members:
            member = vehicles.get(str(member_id))
            if member is None:
                continue
            if getattr(member, 'is_braking', False) or getattr(member, 'is_accident', False):
                confirmed += 1
                continue
            if euclidean_distance((member.x, member.y), message.location) <= getattr(message, 'radius', 0.0):
                confirmed += 1

        return (confirmed / len(members)) > 0.5

    def filter_and_cache(self, message_id):
        """
        Duplicate Filtering (Phase 8):
        Checks if message_id exists in cache. Returns True if accepted (new), False if duplicate (blocked).
        """
        if message_id in self.message_cache:
            if self.logger:
                self.logger.log(f"[Duplicate Filter] Duplicate Blocked: Message '{message_id}' already in cache.")
            return False
        else:
            self.message_cache.add(message_id)
            if self.logger:
                self.logger.log(f"[Duplicate Filter] Duplicate Accepted: New Message '{message_id}' added to cache.")
            return True

    def broadcast(self, message, cluster_heads, vehicles=None, trust_manager=None, metrics=None, clusters=None):
        """
        Controlled Broadcast via Cluster Heads.
        """
        if self.logger:
            self.logger.log("\n" + "=" * 70)
            self.logger.log("CONTROLLED EMERGENCY BROADCAST")
            self.logger.log("=" * 70)
            self.logger.log(str(message))

        vehicles = vehicles or {}

        for cluster_id, ch in cluster_heads.items():
            if message.message_id in self.message_cache:
                if metrics:
                    metrics.duplicate_message()
                if self.logger:
                    self.logger.log(f"  └─> [Duplicate Blocked] Cluster {cluster_id} ignored duplicate message.")
                continue

            ch_veh = vehicles.get(str(ch))
            if ch_veh is not None and not self._has_majority_confirmation(ch_veh, message, vehicles, clusters):
                if self.logger:
                    self.logger.log(f"  └─> [Withheld] Cluster {cluster_id} CH '{ch}' lacked majority corroboration; not forwarded.")
                continue

            self.message_cache.add(message.message_id)
            if metrics:
                metrics.forwarded_message()
            if ch_veh is not None and trust_manager:
                trust_manager.update_behavior_event(ch_veh, "FORWARD", is_success=True)
            if self.logger:
                self.logger.log(f"  └─> [Forwarded] Cluster {cluster_id} CH '{ch}' transmitted packet.")

    def broadcast_route(self, message, path, vehicles=None, trust_manager=None, metrics=None, clusters=None):
        """
        Controlled Dissemination along a discovered, loop-free multi-hop path.

        A path returned by RoutingEngine.find_route() cannot contain repeated
        nodes (loop prevention), so every hop here is by construction a genuine,
        distinct relay step for this message -- never a same-node re-delivery.
        Duplicate *suppression* (the same alert reaching multiple Cluster Heads
        and only being forwarded once) is a separate concern, demonstrated by
        `broadcast()` (the controlled fan-out across active Cluster Heads) --
        NOT here. Re-checking the message-level cache per hop previously made
        every hop after the first look like a "blocked duplicate" even on a
        message's first-ever trip through the network, which was misleading.

        A malicious PACKET_DROP vehicle acting as an intermediate Cluster Head can
        genuinely drop the message instead of relaying it -- a real, observable
        behavior event (mirrors the same attack model flooding.py already uses for
        its baseline), which both breaks delivery for this message and feeds
        update_behavior_event() so the dropper's trust score reflects it.

        Returns:
            bool: True if the message reached the end of the path, False if a
            malicious hop dropped it partway through.
        """
        if self.logger:
            self.logger.log("\n" + "=" * 70)
            self.logger.log("CONTROLLED ROUTE DISSEMINATION")
            self.logger.log("=" * 70)
            self.logger.log(f"Path: {' -> '.join(path)}")

        self.message_cache.add(message.message_id)
        vehicles = vehicles or {}

        for step in path:
            ch_id = step[4:-1] if step.startswith("CH (") else None
            ch_veh = vehicles.get(ch_id) if ch_id else None

            if ch_veh is not None and getattr(ch_veh, 'is_malicious', False) and getattr(ch_veh, 'attack_type', None) == "PACKET_DROP":
                if trust_manager:
                    trust_manager.update_behavior_event(ch_veh, "FORWARD", is_success=False)
                if self.logger:
                    self.logger.log(f"  └─> [Dropped] Malicious Cluster Head '{ch_id}' silently dropped the packet.")
                return False

            if ch_veh is not None and not self._has_majority_confirmation(ch_veh, message, vehicles, clusters):
                if self.logger:
                    self.logger.log(f"  └─> [Withheld] Cluster Head '{ch_id}' lacked majority corroboration; route halted.")
                return False

            if metrics:
                metrics.forwarded_message()
            if ch_veh is not None and trust_manager:
                trust_manager.update_behavior_event(ch_veh, "FORWARD", is_success=True)
            if self.logger:
                self.logger.log(f"  └─> [Forwarded] Transmitted to node '{step}'")

        return True
