class BroadcastManager:
    """
    Controlled Broadcast & Duplicate Message Suppression Manager.
    Maintains a message UUID cache to prevent broadcast storm flooding and duplicate loops.
    """

    def __init__(self, logger=None):
        # Cache of already forwarded message IDs
        self.message_cache = set()
        self.logger = logger

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

    def broadcast(self, message, cluster_heads, metrics=None):
        """
        Controlled Broadcast via Cluster Heads.
        """
        if self.logger:
            self.logger.log("\n" + "=" * 70)
            self.logger.log("CONTROLLED EMERGENCY BROADCAST")
            self.logger.log("=" * 70)
            self.logger.log(str(message))

        for cluster_id, ch in cluster_heads.items():
            if message.message_id in self.message_cache:
                if metrics:
                    metrics.duplicate_message()
                if self.logger:
                    self.logger.log(f"  └─> [Duplicate Blocked] Cluster {cluster_id} ignored duplicate message.")
            else:
                self.message_cache.add(message.message_id)
                if metrics:
                    metrics.forwarded_message()
                if self.logger:
                    self.logger.log(f"  └─> [Forwarded] Cluster {cluster_id} CH '{ch}' transmitted packet.")

    def broadcast_route(self, message, path, metrics=None):
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
        """
        if self.logger:
            self.logger.log("\n" + "=" * 70)
            self.logger.log("CONTROLLED ROUTE DISSEMINATION")
            self.logger.log("=" * 70)
            self.logger.log(f"Path: {' -> '.join(path)}")

        self.message_cache.add(message.message_id)
        for step in path:
            if metrics:
                metrics.forwarded_message()
            if self.logger:
                self.logger.log(f"  └─> [Forwarded] Transmitted to node '{step}'")
