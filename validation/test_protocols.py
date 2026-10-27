"""Decision rules do what their papers say."""
import numpy as np

from channel import geometry, simulate
from clustering import beta_trust, elect_roles
from config import COMM_RANGE_M, N_SLOTS
from protocols import Proposed, Slotted1P, distance_slot


def test_distance_slot_farthest_first():
    assert distance_slot(COMM_RANGE_M) == 0
    assert distance_slot(0.95 * COMM_RANGE_M) == 0
    assert distance_slot(0.5 * COMM_RANGE_M) == N_SLOTS - 3
    assert distance_slot(1.0) == N_SLOTS - 1


def test_slotted_1p_suppresses_on_duplicate():
    xy = np.array([(0, 0), (280, 0), (100, 0)], float)       # far vehicle 1 gets slot 0, near vehicle 2 slot 3
    dist, adj = geometry(xy)
    p = Slotted1P(dist, adj, np.zeros(3, bool))
    simulate(p, adj, 0, np.random.default_rng(0))
    assert p.rec[1]["decision"] == "FORWARD"
    assert p.rec[2]["decision"] == "SUPPRESS"


def test_proposed_forwards_only_for_uncovered_neighbours():
    xy = np.array([(0, 0), (150, 0), (160, 5), (400, 0)], float)
    dist, adj = geometry(xy)
    p = Proposed(dist, adj, np.zeros(4, bool), np.zeros(4, int))
    simulate(p, adj, 0, np.random.default_rng(0))
    assert p.has.all()
    forwarders = [v for v in (1, 2) if p.rec[v]["decision"] == "FORWARD"]
    assert len(forwarders) == 1                               # one of the two relays covers vehicle 3
    other = ({1, 2} - set(forwarders)).pop()
    assert p.rec[other]["decision"] == "SUPPRESS" and p.rec[other]["uncovered"] == 0


def test_misbehaving_vehicle_never_relays():
    xy = np.array([(0, 0), (250, 0), (500, 0)], float)
    dist, adj = geometry(xy)
    p = Proposed(dist, adj, np.array([False, True, False]), np.zeros(3, int))
    log = simulate(p, adj, 0, np.random.default_rng(0))
    assert p.rec[1]["decision"] == "DROP" and not p.has[2] and len(log) == 1


def test_trust_gates_cluster_heads():
    assert beta_trust(0, 0) == 0.5 and beta_trust(9, 1) > 0.8 and beta_trust(0, 8) < 0.2
    xy = np.array([(0, 0), (20, 0), (40, 0), (60, 0)], float)  # one DBSCAN cluster
    _, adj = geometry(xy)
    trust = np.array([0.9, 0.1, 0.9, 0.9])
    role, tier, _ = elect_roles(xy, np.zeros(4), adj, trust)
    assert role[1] != "CH" and (role == "CH").sum() == 1 and tier[1] == 1
    role_nt, _, _ = elect_roles(xy, np.zeros(4), adj, trust, use_trust=False)
    assert (role_nt == "CH").sum() == 1
