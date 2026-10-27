"""
Trust-aware clustering: decides WHICH vehicles the proposed scheme relies on first.

  1. DBSCAN (Chen & Wu 2024: eps 40 m, MinPts 3) splits traffic into dense
     groups and isolated "noise" vehicles. An isolated vehicle is often the only
     link across a sparse gap, so it is treated as a BRIDGE relay.
  2. Inside each dense group, cluster heads are elected greedily: repeatedly
     pick the TRUSTED vehicle whose radio range covers the most still-uncovered
     group members (greedy set cover -> few, central relays), tie-broken by the
     lowest relative speed to its neighbours (Chen 2024 VSM velocity term,
     i.e. the most stable choice).
  3. Trust is a Beta reputation (Josang & Ismail 2002) over watchdog
     observations (Marti et al. 2000): trust = (s + 1) / (s + f + 2).
"""
import numpy as np
from sklearn.cluster import DBSCAN

from config import DBSCAN_EPS_M, DBSCAN_MIN_PTS, TRUST_CH_THRESHOLD


def beta_trust(successes, failures):
    return (successes + 1.0) / (successes + failures + 2.0)


def elect_roles(xy, speed, adj, trust, use_trust=True, cluster=True):
    """Returns (role, tier, labels): role in {CH, BRIDGE, MEMBER}; tier 0 relays
    decide first, tier 1 later (and usually find their neighbourhood covered).
    labels is the DBSCAN cluster ID of every vehicle (-1 = isolated).
    cluster=False skips DBSCAN (ablation): every vehicle is then treated as isolated."""
    n = len(xy)
    labels = (DBSCAN(eps=DBSCAN_EPS_M, min_samples=DBSCAN_MIN_PTS).fit_predict(xy) if cluster and n
              else np.full(n, -1))
    trusted = trust >= TRUST_CH_THRESHOLD if use_trust else np.ones(n, bool)
    role = np.where(labels == -1, "BRIDGE", "MEMBER").astype(object)
    reach = adj | np.eye(n, dtype=bool)

    for c in set(labels) - {-1}:
        members = np.flatnonzero(labels == c)
        uncovered = np.zeros(n, bool)
        uncovered[members] = True
        cands = [m for m in members if trusted[m]]
        while uncovered.any() and cands:
            def key(m):
                nbrs = np.flatnonzero(adj[m] & (labels == c))
                rel_speed = np.abs(speed[nbrs] - speed[m]).mean() if nbrs.size else 0.0
                return (int((reach[m] & uncovered).sum()), -rel_speed)
            best = max(cands, key=key)
            if key(best)[0] == 0:
                break                              # remaining members have no trusted vehicle in range
            role[best] = "CH"
            uncovered &= ~reach[best]
            cands.remove(best)

    tier = np.where(((role == "CH") | (role == "BRIDGE")) & trusted, 0, 1)
    return role, tier, labels
