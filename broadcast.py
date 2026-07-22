class BroadcastManager:

    def __init__(self):

        # Cache of already forwarded messages
        self.message_cache = set()

    def broadcast(self, message, cluster_heads):

        print("\n" + "=" * 70)
        print("Emergency Dissemination")
        print("=" * 70)

        print(message)

        for cluster_id, ch in cluster_heads.items():

            if message.message_id in self.message_cache:

                print(
                    f"[Duplicate Blocked] "
                    f"Cluster {cluster_id} ignored duplicate message."
                )

            else:

                self.message_cache.add(message.message_id)

                print(
                    f"[Forwarded] "
                    f"Cluster {cluster_id} "
                    f"CH -> Vehicle {ch}"
                )
