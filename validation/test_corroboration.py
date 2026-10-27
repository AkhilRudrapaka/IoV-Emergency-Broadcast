"""Voting, BLS signatures and the reputation gate (real BLS12-381 via py_ecc)."""
import numpy as np

import corroboration
import rsu
from channel import geometry, simulate
from config import QUORUM
from protocols import Proposed
from scenario import create_alert

ALERT = create_alert(1, "n0", (100.0, 100.0), 60.0)
NAMES = [f"n{i}" for i in range(9)]


def test_bls_certificate_verifies_and_detects_tampering():
    cert = corroboration.certificate(ALERT, "n0", ["n1", "n2", "n3"])
    assert len(bytes.fromhex(cert["aggregate"])) == 96                    # four signatures, one 96-byte aggregate
    assert corroboration.accept(ALERT, cert, lambda v: 0.9)[0]
    moved = {**ALERT, "incident_position": [500.0, 500.0]}                # same signatures, different claim
    assert not corroboration.accept(moved, cert, lambda v: 0.9)[0]
    swapped = {**cert, "signers": ["n0", "n1", "n2", "n4"]}               # n4 never signed
    assert not corroboration.accept(ALERT, swapped, lambda v: 0.9)[0]


def test_quorum_counts_only_reputable_distinct_endorsers():
    cert = corroboration.certificate(ALERT, "n0", ["n1", "n2", "n3"])
    low = {"n1": 0.9, "n2": 0.9, "n3": 0.1}.get                          # one endorser is not reputable
    ok, reason = corroboration.accept(ALERT, cert, low)
    assert not ok and "2 reputable" in reason
    assert corroboration.accept(ALERT, cert, low, use_reputation=False)[0]  # the gate is what rejects it
    assert not corroboration.accept(ALERT, corroboration.certificate(ALERT, "n0", ["n1", "n2"]), lambda v: 0.9)[0]
    twice = corroboration.certificate(ALERT, "n0", ["n1", "n1", "n2"])    # voting twice adds nothing
    assert not corroboration.accept(ALERT, twice, lambda v: 0.9)[0]
    assert corroboration.accept(ALERT, None, lambda v: 0.9) == (False, "no certificate")


def _network(malicious, reputation, genuine, use_reputation=True, with_rsu=False):
    """Source n0 with neighbours n1..n6 around it, and n7 two hops away (plus an RSU near n7)."""
    xy = [(100, 100), (120, 100), (100, 125), (75, 100), (100, 70), (140, 130), (60, 60), (380, 100)]
    xy += [(600, 100)] if with_rsu else []
    dist, adj = geometry(np.array(xy, float))
    n, nv = len(xy), 8
    mal = np.isin(np.arange(n), malicious)
    rep = np.array([reputation.get(i, 0.9) for i in range(nv)])
    sec = corroboration.plan(ALERT, 0, dist, adj, nv, rep, mal, genuine, use_reputation)
    p = Proposed(dist, adj, mal, np.zeros(n, int), np.arange(n) >= nv, sec)
    p.names = NAMES[:n]
    log = simulate(p, adj, 0, np.random.default_rng(0))
    return p, log, sec


def test_genuine_alert_is_voted_certified_and_spreads():
    p, log, sec = _network(malicious=[], reputation={}, genuine=True)
    kinds = [tx["kind"] for tx in log]
    assert kinds[0] == "PROPOSAL" and kinds.count("VOTE") == 5 and kinds.index("ALERT") > kinds.index("VOTE")
    assert len(p.votes) == QUORUM and p.cert_ok and p.has[7]             # released on the third vote; far vehicle accepts
    assert p.cert["signers"] == ["n0"] + [NAMES[v] for v in sec["voters"][:QUORUM]]
    assert p.first_rx[7] > p.rec[0]["released"]                           # nothing is accepted before the certificate


def test_misbehaving_members_abstain_and_too_few_votes_means_no_alert():
    p, log, _ = _network(malicious=[1, 2, 3, 4], reputation={1: 0.9, 2: 0.9, 3: 0.9, 4: 0.9}, genuine=True)
    assert p.cert is None and not p.has[7]                                # only 1 of 5 voted: no quorum, no dissemination
    assert all(tx["kind"] != "ALERT" for tx in log)


def test_forged_alert_is_rejected_only_with_the_reputation_gate():
    colluders, low = [1, 2, 3], {1: 0.05, 2: 0.05, 3: 0.05}
    gated, log, _ = _network(colluders, low, genuine=False, with_rsu=True)
    assert gated.cert is not None and not gated.cert_ok                   # a valid BLS certificate, signed by untrusted vehicles
    assert not gated.has[4] and gated.rec[4]["decision"] == "REJECT" and not gated.has[7]
    assert [tx["kind"] for tx in log].count("ALERT") == 1                 # the forger's own frame; nobody forwards it
    ungated, _, _ = _network(colluders, low, genuine=False, use_reputation=False, with_rsu=True)
    assert ungated.cert_ok and ungated.has[4] and ungated.has[7]          # without the gate the lie spreads

    for proto, registered in ((gated, False), (ungated, True)):           # the RSU applies the same check
        rx = [{"rsu": "RSU", "sender": "n7", "delay_ms": 30.0, "hop": 2, "transmissions_before": 9, "vehicles_reached": 5}]
        event, rejected = rsu.register(ALERT, rx, (proto.cert_ok, proto.cert_reason))
        assert (event is not None) == registered and bool(rejected) != registered


def test_ablation_switches():
    xy = np.array([(0, 0), (150, 0), (160, 5), (400, 0)], float)
    dist, adj = geometry(xy)
    always = Proposed(dist, adj, np.zeros(4, bool), np.zeros(4, int), coverage=False)
    log = simulate(always, adj, 0, np.random.default_rng(0))
    assert len(log) == 4 and all(always.rec[v]["decision"] == "FORWARD" for v in (1, 2, 3))   # no coverage test: all forward
    flat = Proposed(dist, adj, np.zeros(4, bool), np.zeros(4, int), slots=False)
    simulate(flat, adj, 0, np.random.default_rng(0))
    assert all(flat.rec[v]["slot"] == 0 for v in (1, 2))                  # no distance slots
