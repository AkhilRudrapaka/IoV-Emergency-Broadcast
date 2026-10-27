"""
IEEE 802.11p broadcast channel, simulated slot by slot (13 us).

Why a channel model at all: without contention and collisions a broadcast
storm has no cost except a transmission count. With it, redundant rebroadcasts
visibly cost delay (carrier-sense deferral) and reliability (collisions).

Model (all deliberate simplifications, see PROJECT_GUIDE.md "Limitations"):
  * unit disk: a frame is decodable, sensed, and interfering within COMM_RANGE_M
  * CSMA/CA broadcast: AIFS then a random backoff in [0, CW_MIN], frozen while
    the medium is busy; no ACK, no retransmission, CW never grows (broadcast)
  * collision = another transmission overlapping in time from a node within
    range of the receiver (includes hidden terminals); half-duplex; no capture
  * no fading, no background (beacon) traffic, propagation delay ignored (1 us)
"""
import math
import numpy as np

from config import COMM_RANGE_M, SLOT_US, SIFS_US, AIFSN, CW_MIN, PAYLOAD_BYTES, MAC_OVERHEAD_BYTES

AIFS_SLOTS = math.ceil((SIFS_US + AIFSN * SLOT_US) / SLOT_US)   # 58 us -> 5 slots


def frame_slots(payload_bytes):
    """Airtime of a frame at 6 Mbit/s: 40 us preamble + 8 us per 48 data bits, in 13 us slots."""
    air_us = 40 + math.ceil((16 + 6 + 8 * (payload_bytes + MAC_OVERHEAD_BYTES)) / 48) * 8
    return math.ceil(air_us / SLOT_US)


FRAME_SLOTS = frame_slots(PAYLOAD_BYTES)                         # the bare 300 B alert: 496 us -> 39 slots


def slots_to_ms(slots):
    return slots * SLOT_US / 1000.0


def ms_to_slots(ms):
    return round(ms * 1000.0 / SLOT_US)


def geometry(xy, comm_range=COMM_RANGE_M):
    """Pairwise distances and the in-range adjacency matrix (no self loops)."""
    dist = np.hypot(xy[:, 0, None] - xy[None, :, 0], xy[:, 1, None] - xy[None, :, 1])
    adj = dist <= comm_range
    np.fill_diagonal(adj, False)
    return dist, adj


class Channel:
    def __init__(self, adj, rng):
        n = len(adj)
        self.adj = adj
        self.rng = rng
        self.pending = np.zeros(n, bool)   # frame queued at the MAC
        self.aifs = np.zeros(n, int)
        self.backoff = np.zeros(n, int)
        self.frame = {}                    # node -> (kind, airtime in slots) of its queued frame
        self.active = []                   # [sender, start, end] still on air
        self.log = []                      # every transmission: dict(sender, kind, start, end, new, dup, lost)

    def enqueue(self, node, kind="ALERT", slots=FRAME_SLOTS):
        self.pending[node] = True
        self.frame[node] = (kind, slots)
        self.aifs[node] = AIFS_SLOTS
        self.backoff[node] = self.rng.integers(0, CW_MIN + 1)

    def contend(self, t):
        """One slot of CSMA/CA for every queued node. Nodes that finish backoff in
        the same slot cannot hear each other yet -- that is how collisions arise."""
        idx = np.flatnonzero(self.pending)
        if idx.size == 0:
            return
        on_air = [a[0] for a in self.active]
        busy = self.adj[np.ix_(idx, on_air)].any(1) if on_air else np.zeros(idx.size, bool)

        self.aifs[idx[busy]] = AIFS_SLOTS                       # medium busy: restart AIFS, backoff frozen
        idle = idx[~busy]
        a, b = self.aifs[idle], self.backoff[idle]              # one action per idle slot, from the same snapshot
        self.aifs[idle[a > 0]] -= 1
        self.backoff[idle[(a == 0) & (b > 0)]] -= 1
        for s in idle[(a == 0) & (b == 0)]:
            self.pending[s] = False
            kind, slots = self.frame[int(s)]
            tx = {"sender": int(s), "kind": kind, "start": t, "end": t + slots, "new": 0, "dup": 0, "other": 0, "lost": 0}
            self.active.append([int(s), t, t + slots, tx])
            self.log.append(tx)

    def finish(self, t):
        """Frames ending at slot t: returns [(sender, receivers_ok)] and retires them."""
        done = [a for a in self.active if a[2] == t]
        self.active = [a for a in self.active if a[2] > t]
        out = []
        for s, start, end, tx in done:
            cand = np.flatnonzero(self.adj[s])
            others = [o["sender"] for o in self.log
                      if o["sender"] != s and o["start"] < end and o["end"] > start]
            if others:
                bad = np.isin(cand, others) | self.adj[np.ix_(cand, others)].any(1)   # half-duplex | interference
            else:
                bad = np.zeros(cand.size, bool)
            tx["lost"] = int(bad.sum())
            out.append((s, cand[~bad], tx))
        return out

    def next_end(self):
        return min((a[2] for a in self.active), default=None)


def simulate(protocol, adj, source, rng, max_ms=2000):
    """Runs one dissemination to completion. The protocol object supplies the
    forwarding decisions; the channel decides what is actually received."""
    ch = Channel(adj, rng)
    protocol.bind(ch)
    protocol.originate(source)
    t, limit = 0, ms_to_slots(max_ms)
    while t <= limit:
        for s, receivers, tx in ch.finish(t):
            for r in receivers:
                # "new" / "dup" for an accepted alert copy; anything else (proposal, vote, rejected copy) is "other"
                tx[protocol.on_receive(int(r), s, t, tx) or "other"] += 1
        protocol.fire_timers(t)
        ch.contend(t)
        if ch.pending.any():
            t += 1
            continue
        # nothing contending: jump straight to the next frame end or timer
        nxt = [x for x in (ch.next_end(), protocol.next_timer()) if x is not None]
        if not nxt:
            break
        t = int(max(t + 1, min(nxt)))
    return ch.log
