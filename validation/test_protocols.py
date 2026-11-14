"""Decision rules do what their papers say."""
import pytest
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


# ---------------------------------------------------------------- regression tests for the 2026-11-03 audit fixes
import math

import corroboration
import metrics
from channel import slots_to_ms, ms_to_slots
from config import BLS_VERIFY_MS, HOP_LIMIT
from protocols import Flooding
from scenario import create_alert


def _secured(cls, xy, rsu_nodes=(), **kw):
    """Source 0 with five reputable neighbours (a committee) and whatever else xy holds."""
    xy = np.array(xy, float)
    dist, adj = geometry(xy)
    n = len(xy)
    is_rsu = np.isin(np.arange(n), rsu_nodes)
    names = [f"n{i}" for i in range(n)]
    alert = create_alert(7, "n0", xy[0], 60.0)
    sec = corroboration.plan(alert, 0, dist, adj, n - len(rsu_nodes), np.full(n, 0.9), np.zeros(n, bool))
    extra = (np.zeros(n, int),) if cls is Proposed else ()
    p = cls(dist, adj, np.zeros(n, bool), *extra, is_rsu, sec, **kw)
    p.names = names
    log = simulate(p, adj, 0, np.random.default_rng(3))
    return p, log, dist, adj, names, alert


COMMITTEE = [(0, 0), (20, 0), (0, 20), (-20, 0), (0, -20), (15, 15)]


@pytest.mark.parametrize("cls,kw", [(Flooding, {}), (Flooding, {"rad": True}), (Slotted1P, {}),
                                    (Slotted1P, {"rad": True}), (Proposed, {})])
def test_relays_transmit_only_after_accepting_the_verified_copy(cls, kw):
    """Audit RAD-2: flooding used to relay at the decode slot, before its own 4.3 ms certificate check."""
    p, log, *_ = _secured(cls, COMMITTEE + [(250, 0), (500, 0), (750, 0)], **kw)
    assert p.has.all()
    for tx in log:
        if tx["kind"] == "ALERT" and tx["sender"] != 0:
            assert tx["start"] >= p.first_rx[tx["sender"]], (cls.__name__, kw, tx)


def test_suppression_ratio_ignores_hop_limited_vehicles():
    """Audit MET-4: blind flooding never suppresses, even when the chain is longer than the hop limit."""
    xy = np.array([(250 * i, 0) for i in range(HOP_LIMIT + 3)], float)
    dist, adj = geometry(xy)
    n = len(xy)
    p = Flooding(dist, adj, np.zeros(n, bool))
    p.names = [f"n{i}" for i in range(n)]
    log = simulate(p, adj, 0, np.random.default_rng(0))
    m, _, _ = metrics.run_metrics(adj, 0, np.zeros(n, bool), p, log, n, p.names, create_alert(1, "n0", xy[0], 60.0))
    assert p.rec[HOP_LIMIT]["decision"] == "EXPIRED" and m["suppression_ratio"] == 0.0


def test_rsu_arrival_and_registration_are_reported_separately():
    """Audit MET-8: registration = first decode + one BLS verification."""
    p, log, dist, adj, names, alert = _secured(Proposed, COMMITTEE + [(250, 0)], rsu_nodes=[6])
    m, event, _ = metrics.run_metrics(adj, 0, np.zeros(len(names), bool), p, log, 6, names, alert)
    assert event and math.isclose(m["rsu_delay_ms"] - m["rsu_arrival_ms"], slots_to_ms(ms_to_slots(BLS_VERIFY_MS)), abs_tol=1e-9)
    assert m["rsu_tx_before"] == sum(tx["end"] <= ms_to_slots(m["rsu_arrival_ms"]) for tx in log)


def test_single_sample_has_no_confidence_interval():
    mean, std, ci, n = metrics.summarize([5.0, float("nan")])
    assert mean == 5.0 and n == 1 and math.isnan(std) and math.isnan(ci)


def test_disconnected_cluster_is_outside_the_reach_denominator_and_rsu_metrics_are_undefined():
    """Two groups 1 km apart, an RSU beside the far group: nobody there can be reached, and that is not a scheme failure."""
    xy = np.array([(0, 0), (200, 0), (1200, 0), (1400, 0), (1500, 0)], float)
    dist, adj = geometry(xy)
    is_rsu = np.arange(5) == 4
    p = Proposed(dist, adj, np.zeros(5, bool), np.zeros(5, int), is_rsu)
    p.names = ["v0", "v1", "v2", "v3", "RSU-1"]
    log = simulate(p, adj, 0, np.random.default_rng(0))
    m, event, _ = metrics.run_metrics(adj, 0, np.zeros(5, bool), p, log, 4, p.names, create_alert(1, "v0", xy[0], 60.0))
    assert not p.has[2] and not p.has[3] and m["reachable"] == 2 and m["reachability"] == 1.0
    assert event is None and math.isnan(m["rsu_received"])        # RSU not reachable from the source's component


def test_failed_cluster_head_does_not_suppress_its_neighbours():
    """The tier-0 relay is a black hole: it never transmits, so nobody counts it as coverage, and a tier-1
    vehicle forwards later instead (CH failure costs latency, not delivery)."""
    xy = np.array([(0, 0), (250, 0), (240, 15), (480, 0)], float)
    dist, adj = geometry(xy)
    malicious = np.array([False, True, False, False])
    p = Proposed(dist, adj, malicious, np.array([0, 0, 1, 1]))
    log = simulate(p, adj, 0, np.random.default_rng(0))
    assert p.rec[1]["decision"] == "DROP" and p.rec[2]["decision"] == "FORWARD" and p.has[3]
    assert [tx["sender"] for tx in log] == [0, 2]


def test_report_collection_counts_each_endorser_once():
    """A vote frame heard twice from the same endorser must not count twice toward the quorum."""
    from channel import Channel
    p, *_ = _secured(Proposed, COMMITTEE)
    q = Proposed(p.dist, p.adj, p.malicious, np.zeros(len(p.adj), int), None, p.sec)
    q.bind(Channel(q.adj, np.random.default_rng(0)))
    q.originate(0)
    for _ in range(3):
        q.on_receive(0, 1, 100, {"kind": "VOTE"})
    assert q.votes == [1] and q.release_at is None


def test_every_decision_is_recorded_with_its_lifecycle_times():
    """decoded -> verified (4.3 ms) -> decision, for every vehicle that saw a certified copy."""
    import experiment
    p, log, dist, adj, names, alert = _secured(Proposed, COMMITTEE + [(250, 0), (500, 0)])
    rec = experiment.protocol_record({"ids": names, "trust": np.full(len(names), 0.9)}, names, dist, adj, p, log, None)
    for v in rec["vehicles"]:
        if v["decision"] == "SOURCE":
            continue
        assert v["verified"] is True and v["decision"] in ("FORWARD", "SUPPRESS")
        assert math.isclose(v["rx_ms"] - v["decoded_ms"], slots_to_ms(ms_to_slots(BLS_VERIFY_MS)), abs_tol=1e-3)
        assert v["reason"]
