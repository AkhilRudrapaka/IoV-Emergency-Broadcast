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
    assert p.rsu_rx == [(2, 1, p.first_rx[2], p.first_rx[2], 2)]   # no corroboration: decoded = registered


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


def test_every_rsu_copy_has_a_recorded_outcome_and_distinct_reports_are_not_merged():
    """Duplicates and rejections are recorded per copy; register() handles ONE report, so two reports with different
    event IDs are two events here (reports of one crash are merged by register_reports, tested below)."""
    a = create_alert(1, "v7", (100, 100), 60.0)
    b = create_alert(1, "v9", (102, 101), 60.0)                  # another vehicle reporting the same crash
    copies = [_rx("RSU-1", 1.0), _rx("RSU-2", 2.0)]
    event, _ = rsu.register(a, copies)
    assert [c["status"] for c in sorted(copies, key=lambda c: c["delay_ms"])] == ["REGISTERED", "DUPLICATE"]
    other, _ = rsu.register(b, [_rx("RSU-1", 1.5)])
    assert event["event_id"] != other["event_id"]
    stale = [_rx("RSU-1", 1.0)]
    replay = {**a, "created_s": a["created_s"] - 700}                                     # a 700 s old alert
    assert rsu.register(replay, [_rx("RSU-1", 1.0)])[0] is not None    # judged by its own claim it looks fresh...
    assert rsu.register(replay, stale, clock_s=a["created_s"])[0] is None   # ...by the RSU's clock it is expired
    assert stale[0]["status"].startswith("REJECTED") and "600 s" in stale[0]["status"]


# ---------------------------------------------------------------- several reports of one crash (register_reports)
def _report(source, xy, t, seq=1, copies=(("RSU-1", 1.0),), check=None):
    """One report: the alert a vehicle created, the copies the RSUs decoded, its certificate check, the RSU clock."""
    return create_alert(1, source, xy, t, seq), [_rx(r, d) for r, d in copies], check, t


def test_reports_of_one_crash_from_several_vehicles_make_one_incident(tmp_path):
    import infrastructure
    reports = [_report("v7", (100, 100), 60.0), _report("v9", (104, 102), 60.5, copies=(("RSU-1", 2.0), ("RSU-2", 3.0))),
               _report("v11", (97, 99), 61.0, copies=(("RSU-2", 1.5),))]
    incidents, rejected = rsu.register_reports(reports)
    assert rejected == [] and len(incidents) == 1
    incident = incidents[0]
    assert incident["event_id"] == "EVT-1-v7-1" and incident["delay_ms"] == 1.0 and incident["duplicate_copies"] == 0
    assert [(r["event_id"], r["status"]) for r in incident["reports"]] == \
        [("EVT-1-v7-1", "REGISTERED"), ("EVT-1-v9-1", "MERGED"), ("EVT-1-v11-1", "MERGED")]   # every valid report kept
    assert incident["reporting_vehicles"] == ["v11", "v7", "v9"]
    statuses = [c["status"] for _, copies, _, _ in reports for c in copies]
    assert statuses.count("REGISTERED") == 1                                      # registered once, never twice
    assert statuses.count("MERGED: same incident as EVT-1-v7-1") == 2 and statuses.count("DUPLICATE") == 1
    for i in incidents:                                                          # one dispatch row per incident
        infrastructure.persist("t", i, [], tmp_path)
    import sqlite3
    with sqlite3.connect(tmp_path / "infrastructure" / "backhaul.sqlite3") as db:
        assert db.execute("SELECT COUNT(*) FROM dispatch").fetchone()[0] == 1
    # the report the RSUs registered first is the incident, whatever order the reports are handed over in
    late, early = _report("v7", (100, 100), 60.0, copies=(("RSU-1", 9.0),)), _report("v9", (101, 100), 60.0)
    assert rsu.register_reports([late, early])[0][0]["event_id"] == "EVT-1-v9-1"


def test_a_vehicle_reporting_the_same_crash_again_contributes_once():
    incidents, _ = rsu.register_reports([_report("v7", (100, 100), 60.0), _report("v7", (100, 100), 61.0, seq=2)])
    assert len(incidents) == 1 and incidents[0]["reporting_vehicles"] == ["v7"]               # one contribution
    assert [r["event_id"] for r in incidents[0]["reports"]] == ["EVT-1-v7-1", "EVT-1-v7-2"]    # both reports kept
    # the identical report handed over twice is ONE report: its extra copy is a duplicate, not a second report
    incidents, _ = rsu.register_reports([_report("v7", (100, 100), 60.0),
                                         _report("v7", (100, 100), 60.0, copies=(("RSU-2", 2.0),))])
    assert len(incidents[0]["reports"]) == 1 and incidents[0]["duplicate_copies"] == 1
    assert incidents[0]["rsus_that_received"] == ["RSU-1", "RSU-2"]
    # an event ID already registered never becomes a second report or a second vehicle, whatever its content
    # claims (here no certificate is checked, as in the no-voting ablation)
    genuine = _report("v7", (100, 100), 60.0)
    altered = ({**genuine[0], "source_vehicle": "v99", "incident_position": [400.0, 300.0]}, [_rx("RSU-2", 2.0)], None, 60.0)
    incidents, _ = rsu.register_reports([genuine, altered])
    assert len(incidents) == 1 and incidents[0]["reporting_vehicles"] == ["v7"] and len(incidents[0]["reports"]) == 1
    assert altered[1][0]["status"] == "DUPLICATE" and incidents[0]["duplicate_copies"] == 1


def test_close_but_separate_crashes_stay_separate():
    a = _report("v7", (100, 100), 60.0)
    near = _report("v9", (100 + rsu.MERGE_RADIUS_M + 5, 100), 60.0)               # 15 m away, same second
    later = _report("v11", (100, 100), 60.0 + rsu.MERGE_WINDOW_S + 1)              # same place, 3 s later
    incidents, _ = rsu.register_reports([a, near, later])
    assert len(incidents) == 3 and all(len(i["reports"]) == 1 for i in incidents)
    # the bounds are inclusive: 10.0 m and 2.0 s merge, 10.01 m or 2.01 s do not
    for xy, t, merged in (((110, 100), 60.0, True), ((110.01, 100), 60.0, False),
                          ((100, 100), 62.0, True), ((100, 100), 62.01, False)):
        incidents, _ = rsu.register_reports([_report("v7", (100, 100), 60.0), _report("v9", xy, t)])
        assert len(incidents) == (1 if merged else 2), (xy, t)
    # pairwise, so no chaining: the middle report reaches the RSU first; the outer reports are 16 m apart and can
    # never share an incident, whichever of them joins the middle one
    incidents, _ = rsu.register_reports([_report("v7", (100, 100), 60.0, copies=(("RSU-1", 2.0),)),
                                         _report("v9", (108, 100), 60.0, copies=(("RSU-1", 1.0),)),
                                         _report("v11", (116, 100), 60.0, copies=(("RSU-1", 3.0),))])
    assert [[r["source_vehicle"] for r in i["reports"]] for i in incidents] == [["v9", "v7"], ["v11"]]


def test_a_rejected_report_stays_rejected_after_a_merge_attempt():
    """Real certificates and the unchanged acceptance rule: the second report of the same crash is signed correctly
    but has only one reputable endorser, so it is rejected and is not merged (no pooling of endorsements)."""
    from corroboration import accept, certificate
    reputation = {"v1": 0.9, "v2": 0.9, "v3": 0.9, "v4": 0.9, "v5": 0.2, "v6": 0.1}.get
    good, weak = create_alert(1, "v7", (100, 100), 60.0), create_alert(1, "v9", (101, 100), 60.2)
    good_check = accept(good, certificate(good, "v7", ["v1", "v2", "v3"]), reputation)
    weak_check = accept(weak, certificate(weak, "v9", ["v4", "v5", "v6"]), reputation)
    assert good_check[0] and not weak_check[0]
    weak_copies = [_rx("RSU-1", 0.5)]                                             # it even arrives first
    incidents, rejected = rsu.register_reports([(good, [_rx("RSU-1", 1.0)], good_check, 60.0),
                                                (weak, weak_copies, weak_check, 60.2)])
    assert len(incidents) == 1 and incidents[0]["reporting_vehicles"] == ["v7"] and len(incidents[0]["reports"]) == 1
    assert len(rejected) == 1 and weak_copies[0]["status"] == f"REJECTED: not corroborated: {weak_check[1]}"


def test_a_single_report_is_registered_exactly_as_before():
    alert = create_alert(1, "v7", (100, 100), 60.0)
    copies = [_rx("RSU-2", 3.0), _rx("RSU-1", 1.0), _rx("RSU-1", 4.0)]
    before = [dict(c) for c in copies]
    event, rejected = rsu.register(alert, before)
    incidents, rejected_now = rsu.register_reports([(alert, copies, None, None)])
    assert rejected == rejected_now == [] and len(incidents) == 1
    assert {k: v for k, v in incidents[0].items() if k not in ("reports", "reporting_vehicles")} == event
    assert [c["status"] for c in copies] == [c["status"] for c in before]
    assert rsu.register_reports([]) == ([], [])
