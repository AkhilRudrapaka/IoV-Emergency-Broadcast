"""
What every vehicle does with an emergency alert.

1. Corroboration (corroboration.py), identical under every forwarding rule:
     source broadcasts a signed PROPOSAL -> committee members who observe the event
     each broadcast one VOTE (a BLS signature) -> with QUORUM votes the source
     broadcasts the certified ALERT (one aggregate signature).
   A receiver verifies the certificate before it accepts the alert. A rejected
   alert is not acted on and not forwarded.

2. Forwarding rule: each vehicle decides ONCE, on the first certified copy it accepts.
     Flooding    rebroadcast immediately                                (Ni et al. 1999)
     Slotted1P   wait S(D)*tau (far first); any duplicate -> suppress    (Wisitpongphan et al. 2007)
     Proposed    wait (tier*Ns + S(D))*tau + RAD; then rebroadcast only if some beacon
                 neighbour is still uncovered by every sender heard so far
                 (coverage test after Peng & Lu 2000; tiers from clustering.py)

Under every rule:
  * a vehicle keeps per-event state (has it, when, from whom, hop, decision), so a
    duplicate copy is never treated as new and nobody rebroadcasts twice
  * misbehaving vehicles receive but never relay
  * a copy that has already travelled HOP_LIMIT hops is not relayed further
  * road-side units only receive: they are the alert's endpoint, not a relay
"""
import math
import numpy as np

import corroboration
from channel import ms_to_slots, frame_slots, FRAME_SLOTS
from config import (COMM_RANGE_M, N_SLOTS, TAU_MS, RAD_MS, HOP_LIMIT, QUORUM, PAYLOAD_BYTES, SIGNATURE_BYTES,
                    VOTE_BYTES, SIGNER_ID_BYTES, BLS_SIGN_MS, BLS_VERIFY_MS, VOTE_SLOT_MS)

TAU_SLOTS = ms_to_slots(TAU_MS)


def distance_slot(d):
    """Wisitpongphan Eq. 6 (distance form): S = Ns - ceil(Ns * min(D,R)/R).
    Farthest receivers get slot 0 and so rebroadcast first. (The printed Eq. 3 is
    degenerate as typeset -- ceil of a value in (0,1] is always 1.)"""
    return min(N_SLOTS - 1, max(0, N_SLOTS - math.ceil(N_SLOTS * min(d, COMM_RANGE_M) / COMM_RANGE_M)))


class Protocol:
    def __init__(self, dist, adj, malicious, rsu=None, security=None):
        n = len(adj)
        self.dist, self.adj, self.malicious = dist, adj, malicious
        self.rsu = np.zeros(n, bool) if rsu is None else rsu
        self.sec = security                          # corroboration plan, or None (ablation: no voting, no BLS)
        self.verify = ms_to_slots(BLS_VERIFY_MS) if security else 0
        self.has = np.zeros(n, bool)                 # holds an ACCEPTED alert
        self.seen = np.zeros(n, bool)                # has processed a certified copy (accepted or rejected)
        self.first_rx = np.full(n, -1)               # slot at which the alert was accepted
        self.first_from = np.full(n, -1)
        self.hop = np.full(n, -1)                    # hops the accepted copy had travelled
        self.heard = [set() for _ in range(n)]      # every sender of a certified copy this node decoded
        self.rsu_rx = []                             # (rsu, sender, slot, hop) for every copy an RSU decoded
        self.timers = {}                             # vehicle -> slot of its forwarding decision
        self.vote_at, self.votes, self.vote_log = {}, [], []
        self.release_at, self.cert, self.cert_ok, self.cert_reason = None, None, security is None, "no corroboration"
        self.rec = {}                                # vehicle -> decision record (for the explainer)
        self.names = None                            # optional node IDs, for readable reasons
        self.now = 0

    def name(self, *vs):
        return ", ".join(str(self.names[v] if self.names else v) for v in sorted(vs))

    def bind(self, ch):
        self.ch = ch

    def decide(self, v, decision, reason):
        self.rec.setdefault(v, {}).update(decision=decision, reason=reason, t=self.now)
        if decision == "FORWARD":
            self.ch.enqueue(v, "ALERT", self.alert_slots)

    # ---------------------------------------------------------------- corroboration
    def originate(self, source):
        self.source = source
        self.has[source] = self.seen[source] = True
        self.first_rx[source] = self.hop[source] = 0
        self.rec[source] = {"decision": "SOURCE", "reason": "incident vehicle originates the alert", "t": 0}
        if self.sec is None:
            self.alert_slots = FRAME_SLOTS
            self.ch.enqueue(source, "ALERT", self.alert_slots)
        else:
            self.ch.enqueue(source, "PROPOSAL", frame_slots(PAYLOAD_BYTES + SIGNATURE_BYTES))

    def on_receive(self, v, s, t, tx):
        self.now = t
        if tx["kind"] == "PROPOSAL":
            if v in self.sec["voters"]:              # checks the source's signature, then signs its own vote
                rank = self.sec["voters"].index(v)
                self.vote_at[v] = t + ms_to_slots(BLS_VERIFY_MS + BLS_SIGN_MS + rank * VOTE_SLOT_MS)
            return None
        if tx["kind"] == "VOTE":
            if v == self.source and self.release_at is None:
                self.votes.append(s)
                if len(self.votes) >= QUORUM:        # a majority of the committee has endorsed
                    self.release_at = t + self.verify
            return None
        return self.on_alert(v, s, t)

    def release(self, t):
        """The source aggregates the endorsements (real BLS) and broadcasts the certified alert."""
        sec = self.sec
        self.cert = corroboration.certificate(sec["alert"], self.names[self.source], [self.names[v] for v in self.votes])
        reputation = dict(zip(self.names, sec["reputation"]))
        self.cert_ok, self.cert_reason = corroboration.accept(sec["alert"], self.cert, reputation.get, sec["use_reputation"])
        self.alert_slots = frame_slots(PAYLOAD_BYTES + SIGNATURE_BYTES + SIGNER_ID_BYTES * len(self.cert["signers"]))
        self.rec[self.source]["released"] = t
        self.ch.enqueue(self.source, "ALERT", self.alert_slots)

    # ---------------------------------------------------------------- reception of a certified alert
    def on_alert(self, v, s, t):
        self.heard[v].add(s)
        if self.rsu[v]:
            self.rsu_rx.append((v, s, t + self.verify, int(self.hop[s]) + 1))
        if self.seen[v]:
            if self.has[v]:
                self.duplicate(v, s, t)
                return "dup"
            return None
        self.seen[v] = True
        self.now = accepted_at = t + self.verify      # the receiver verifies the certificate first
        if not self.cert_ok:
            if not self.rsu[v]:
                self.decide(v, "REJECT", self.cert_reason)
            return None
        self.has[v] = True
        self.first_rx[v], self.first_from[v], self.hop[v] = accepted_at, s, self.hop[s] + 1
        if self.rsu[v]:
            return "new"                              # endpoint: registers the event (rsu.py), never relays
        if self.malicious[v]:
            self.decide(v, "DROP", "misbehaving vehicle: never relays")
        elif self.hop[v] >= HOP_LIMIT:
            self.decide(v, "EXPIRED", f"hop limit {HOP_LIMIT} reached")
        else:
            self.first_copy(v, s, accepted_at)
        return "new"

    def fire_timers(self, t):
        self.now = t
        for v in [v for v, due in self.vote_at.items() if due <= t]:
            del self.vote_at[v]
            self.vote_log.append((v, t))
            self.ch.enqueue(v, "VOTE", frame_slots(VOTE_BYTES))
        if self.release_at is not None and self.release_at <= t and self.cert is None:
            self.release(t)
        for v in [v for v, due in self.timers.items() if due <= t]:
            del self.timers[v]
            self.expire(v, t)

    def next_timer(self):
        pending = list(self.timers.values()) + list(self.vote_at.values())
        if self.release_at is not None and self.cert is None:
            pending.append(self.release_at)
        return min(pending, default=None)

    def duplicate(self, v, s, t):
        pass


class CHRoute(Protocol):
    """Forward only along the selected CH route; other vehicles receive silently."""
    def __init__(self, dist, adj, malicious, route, rsu=None, security=None, clusters=None, reputation=None):
        super().__init__(dist, adj, malicious, rsu, security)
        self.route = route
        self.clusters, self.reputation = clusters, reputation
        self.rounds, self.local_timers = {}, {}

    def first_copy(self, v, s, t):
        if v in self.route[1:-1]:
            voters = [i for i in range(len(self.clusters))
                      if i != v and i != self.source and self.adj[v, i]
                      and self.clusters[i] == self.clusters[v]
                      and self.reputation[i] >= corroboration.TRUST_CH_THRESHOLD
                      and not self.malicious[i]][:corroboration.COMMITTEE_SIZE]
            # The head's signed proposal counts as its own distinct endorsement.
            self.rounds[v] = {'voters': [v, *voters], 'received': {v}, 'certificate': None}
            self.local_timers[('proposal', v, v)] = t + TAU_SLOTS + ms_to_slots(BLS_SIGN_MS)
        else:
            self.decide(v, "SUPPRESS", "outside the selected cluster-head route")

    def on_receive(self, v, s, t, tx):
        kind = tx['kind']
        if kind.startswith('CPROPOSAL:'):
            head = int(kind.split(':')[1])
            voters = self.rounds[head]['voters']
            if v in voters:
                self.local_timers[('vote', head, v)] = t + ms_to_slots(BLS_SIGN_MS + BLS_VERIFY_MS + voters.index(v) * VOTE_SLOT_MS)
            return None
        if kind.startswith('CVOTE:'):
            head = int(kind.split(':')[1])
            round_ = self.rounds[head]
            if v == head and s in round_['voters'] and round_['certificate'] is None:
                round_['received'].add(s)
                if len(round_['received']) >= QUORUM:
                    cert = corroboration.certificate(self.sec['alert'], self.names[self.source],
                                                    [self.names[i] for i in sorted(round_['received'])])
                    ok, reason = corroboration.accept(self.sec['alert'], cert, dict(zip(self.names, self.reputation)).get)
                    round_['certificate'], round_['accepted'], round_['reason'] = cert, ok, reason
                    if ok:
                        self.timers[head] = t + self.verify
            return None
        return super().on_receive(v, s, t, tx)

    def fire_timers(self, t):
        super().fire_timers(t)
        for key, due in list(self.local_timers.items()):
            if due > t:
                continue
            del self.local_timers[key]
            action, head, sender = key
            kind = f'CPROPOSAL:{head}' if action == 'proposal' else f'CVOTE:{head}'
            self.ch.enqueue(sender, kind, frame_slots(PAYLOAD_BYTES + SIGNATURE_BYTES if action == 'proposal' else VOTE_BYTES))

    def next_timer(self):
        timers = list(self.local_timers.values())
        base = super().next_timer()
        if base is not None:
            timers.append(base)
        return min(timers, default=None)

    def expire(self, v, t):
        self.decide(v, "FORWARD", "authenticated cluster head on the shortest available route")


class Flooding(Protocol):
    def first_copy(self, v, s, t):
        self.decide(v, "FORWARD", "blind flooding: every new copy is rebroadcast")


class Slotted1P(Protocol):
    def first_copy(self, v, s, t):
        k = distance_slot(self.dist[v, s])
        self.rec[v] = {"slot": k}
        self.timers[v] = t + k * TAU_SLOTS

    def duplicate(self, v, s, t):
        if v in self.timers:
            del self.timers[v]
            self.decide(v, "SUPPRESS", f"heard a duplicate from {self.name(s)} before its slot")

    def expire(self, v, t):
        self.decide(v, "FORWARD", f"no duplicate heard before slot {self.rec[v]['slot']}")


class Proposed(Protocol):
    """tier: 0 = reputable cluster representative or bridge, 1 = everyone else.
    rad / slots / coverage switch off one mechanism each, for the ablations."""

    def __init__(self, dist, adj, malicious, tier, rsu=None, security=None, rad=True, slots=True, coverage=True):
        super().__init__(dist, adj, malicious, rsu, security)
        self.tier, self.rad, self.slots, self.coverage = tier, rad, slots, coverage

    def first_copy(self, v, s, t):
        k = distance_slot(self.dist[v, s]) if self.slots else 0
        self.rec[v] = {"slot": k, "tier": int(self.tier[v])}
        # Random assessment delay inside the slot (Ni et al. 1999): without it every
        # vehicle in the same distance slot decides at the same instant, before it can
        # hear the others, and they all rebroadcast. Uniform [0, RAD_MS) keeps slot order.
        rad = int(self.ch.rng.integers(0, ms_to_slots(RAD_MS))) if self.rad else 0
        self.timers[v] = t + (self.tier[v] * N_SLOTS + k) * TAU_SLOTS + rad

    def expire(self, v, t):
        if not self.coverage:
            return self.decide(v, "FORWARD", "coverage test disabled: forwards when its wait ends")
        # Neighbours (vehicles and RSUs, known from their beacons) not within range of
        # any sender this vehicle has heard. An uncovered RSU counts like any neighbour,
        # which is what carries the alert to the infrastructure without a routing protocol.
        covered = np.zeros(len(self.adj), bool)
        for h in self.heard[v]:
            covered |= self.adj[h]
            covered[h] = True
        uncovered = np.flatnonzero(self.adj[v] & ~covered)
        uncovered = uncovered[uncovered != v]
        self.rec[v]["uncovered"] = int(uncovered.size)
        if uncovered.size:
            self.decide(v, "FORWARD", f"{uncovered.size} neighbour(s) not covered by the senders it heard "
                                      f"({self.name(*self.heard[v])})")
        else:
            self.decide(v, "SUPPRESS", f"all {int(self.adj[v].sum())} neighbours already covered by "
                                       f"{self.name(*self.heard[v])}")
