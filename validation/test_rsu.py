"""RSU endpoint, event registry, hop limit, and the emergency packet."""
import numpy as np

import rsu
from channel import geometry, simulate
from config import HOP_LIMIT
from protocols import Flooding, Proposed
from scenario import create_alert


def _run(cls, xy, rsu_nodes, *extra):
    xy = np.array(xy, float)
    dist, adj = geometry(xy)
    is_rsu = np.isin(np.arange(len(xy)), rsu_nodes)
    p = cls(dist, adj, np.zeros(len(xy), bool), *extra, is_rsu)
    log = simulate(p, adj, 0, np.random.default_rng(0))
    return p, log


def test_rsu_receives_through_a_relay_and_never_transmits():
    p, log = _run(Flooding, [(0, 0), (250, 0), (500, 0)], [2])
    assert p.has[2] and p.hop[2] == 2                       # source -> relay -> RSU
    assert [tx["sender"] for tx in log] == [0, 1]           # the RSU is an endpoint, not a relay
    assert p.rsu_rx == [(2, 1, p.first_rx[2], 2)]


def test_uncovered_rsu_makes_a_vehicle_forward():
    """Both relays' vehicle neighbours are covered by the source; only the RSU is not."""
    with_rsu, log = _run(Proposed, [(0, 0), (250, 0), (255, 5), (500, 0)], [3], np.zeros(4, int))
    assert with_rsu.has[3] and len(log) == 2                # exactly one relay forwards, for the RSU
    without, log = _run(Proposed, [(0, 0), (250, 0), (255, 5)], [], np.zeros(3, int))
    assert len(log) == 1                                    # no RSU: nobody needs to forward


def test_hop_limit_stops_relaying():
    chain = [(250 * i, 0) for i in range(HOP_LIMIT + 3)]
    p, log = _run(Flooding, chain, [])
    assert p.has[HOP_LIMIT] and p.rec[HOP_LIMIT]["decision"] == "EXPIRED"
    assert not p.has[HOP_LIMIT + 1] and len(log) == HOP_LIMIT


def test_alert_packet_fields():
    a = create_alert(30000, "v7", (123.456, 78.9), 88.0)
    assert set(rsu.REQUIRED) <= set(a)
    assert a["event_id"] == "EVT-30000-v7-1" and a["message_type"] == "ACCIDENT" and a["hop_limit"] == HOP_LIMIT


def _rx(name, delay, hop=1):
    return {"rsu": name, "sender": "v1", "delay_ms": delay, "hop": hop, "transmissions_before": 1, "vehicles_reached": 5}


def test_same_event_at_two_rsus_is_registered_once():
    alert = create_alert(1, "v7", (100, 100), 60.0)
    event, rejected = rsu.register(alert, [_rx("RSU-2", 3.0), _rx("RSU-1", 1.0), _rx("RSU-1", 4.0)])
    assert rejected == [] and event["receiving_rsu"] == "RSU-1" and event["delay_ms"] == 1.0
    assert event["duplicate_copies"] == 2 and event["rsus_that_received"] == ["RSU-1", "RSU-2"]
    assert rsu.register(alert, []) == (None, [])


def test_implausible_alerts_are_rejected():
    good = create_alert(1, "v7", (100, 100), 60.0)
    assert rsu.validate(good, 1, 60.001) == []
    assert rsu.validate({**good, "incident_position": [5000, 5000]}, 1, 60.001)
    assert rsu.validate(good, HOP_LIMIT + 1, 60.001)
    assert rsu.validate({**good, "message_type": "PARTY"}, 1, 60.001)
    assert rsu.validate(good, 1, 59.0)                      # received before it was created
    assert rsu.validate({"event_id": "x"}, 1, 60.0)
    event, rejected = rsu.register({**good, "incident_position": [5000, 5000]}, [_rx("RSU-1", 1.0)])
    assert event is None and len(rejected) == 1
