"""Incident response on live SUMO (incident_response.py): staged stop -> detection from telemetry -> verified alert ->
rerouting of the vehicles that accepted it; a rejected forged alert changes no route."""
import gzip
import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import config
import incident_response as ir
from scenario import build

ROOT = Path(__file__).resolve().parent.parent
TRACKED = ROOT / "results/urban/raw/d200_r02.json.gz"


@pytest.fixture(scope="module")
def showcase(tmp_path_factory):
    before = hashlib.md5(TRACKED.read_bytes()).hexdigest()
    rec = ir.run(config.DEMO_DENSITY, config.DEMO_RUN, out_dir=str(tmp_path_factory.mktemp("incident")))
    assert hashlib.md5(TRACKED.read_bytes()).hexdigest() == before          # the tracked record is only read
    return rec


def test_the_stop_is_detected_from_live_telemetry_and_releases_the_recorded_alert(showcase):
    g = showcase["genuine"]
    d, stop = g["detection"], g["staged_stop"]
    assert d["vehicle"] == stop["vehicle"] == g["event_id"].split("-")[2]
    assert d["t_s"] == stop["t_s"] + 1 and d["speed_drop_mps"] == pytest.approx(stop["speed_before_mps"], abs=1e-3)
    assert d["speed_drop_mps"] > d["threshold_mps2"] and d["edge"] == d["lane"].rsplit("_", 1)[0]
    assert g["released"] and g["position_offset_m"] < 0.05 and g["snapshot_drift_m"] < 0.05
    # the published d200_r02 record predates committee enforcement (default since Block G): the genuine dissemination
    # is identical, only the forged-alert test differs (the voting-only forgery is now rejected)
    with gzip.open(showcase["dissemination_record"]["path"], "rt") as fh:
        live = json.load(fh)
    with gzip.open(TRACKED, "rt") as fh:
        saved = json.load(fh)
    same = lambda k: json.dumps(live[k], sort_keys=True) == json.dumps(saved[k], sort_keys=True)
    assert same("scenario") and same("protocols") and live["infrastructure"]["route"] == saved["infrastructure"]["route"]
    assert saved["forgery"]["variants"]["voting_only"]["corroboration"]["accepted"] is True       # Block F gap
    assert live["forgery"]["variants"]["voting_only"]["corroboration"]["accepted"] is False       # closed
    assert all(showcase["acceptance"][k] for k in ("detected_from_telemetry", "no_other_detection"))


def test_with_enforcement_off_the_published_record_is_reproduced_exactly(tmp_path, monkeypatch):
    import corroboration, demo, infrastructure
    for module in (config, corroboration, infrastructure):
        monkeypatch.setattr(module, "ENFORCE_COMMITTEE", 0)
    raw = ir.dissemination(config.DEMO_DENSITY, config.DEMO_RUN, str(tmp_path))
    with gzip.open(TRACKED, "rt") as fh:
        assert demo.record_fingerprint(raw) == demo.record_fingerprint(json.load(fh))


def _fake(speeds, edge="E1", route=("A", "E1", "B"), after=None):
    """Minimal TraCI stand-in: one step per call to .step(); speeds[v] is the list of per-step speeds."""
    clock = {"t": 1.0, "i": 0}                       # the state of time 0 is read once the clock reads 1
    routes = {v: list(route) for v in speeds}
    veh = SimpleNamespace(
        getIDList=lambda: list(speeds), getSpeed=lambda v: speeds[v][clock["i"]], getTypeID=lambda v: "car",
        getPosition=lambda v: (0.0, 0.0), getRoadID=lambda v: "A", getLaneID=lambda v: "A_0",
        getLanePosition=lambda v: 10.0, getRoute=lambda v: tuple(routes[v]), getRouteIndex=lambda v: 0,
        setAdaptedTraveltime=lambda v, e, t: None,
        rerouteTraveltime=lambda v, cur=True: routes.__setitem__(v, list(after or route)))
    tc = SimpleNamespace(simulation=SimpleNamespace(getTime=lambda: clock["t"]), vehicle=veh,
                         vehicletype=SimpleNamespace(getEmergencyDecel=lambda t: 9.0),
                         lane=SimpleNamespace(getLength=lambda lane: 100.0))

    def step():
        clock["t"] += 1.0
        clock["i"] += 1
    tc.step, tc.routes = step, routes
    return tc


def test_only_an_impact_like_stop_triggers_the_detector_not_hard_braking_or_a_slow_stop():
    tc = _fake({"crash": [0, 12.0, 0.0, 0.0], "brake": [0, 13.0, 4.0, 0.0], "slow": [0, 8.9, 0.0, 0.0],
                "jam": [0, 12.0, 1.0, 0.0]})
    det = ir.StopDetector(tc)
    found = det.update()
    for _ in range(3):
        tc.step()
        found += det.update()
    # not: 9 m/s^2 emergency braking ("brake"), a stop from 8.9 m/s ("slow"), an 11 m/s drop not to standstill ("jam")
    assert [(d["vehicle"], d["t_s"]) for d in found] == [("crash", 2.0)]
    alert = {"source_vehicle": "crash", "created_s": 1.0}
    assert ir.bind(found, alert) is found[0]
    assert ir.bind(found, dict(alert, source_vehicle="brake")) is None       # a detection binds only to its own alert
    assert ir.bind(found, dict(alert, created_s=0.0)) is None                # ... and only within one step of it


def _record(accepted, verified=True):
    return {"corroboration": {"accepted": accepted, "certificate": {"signers": []}, "use_reputation": True,
                              "committee": []},
            "vehicles": [{"id": "src", "rx_ms": 0.0, "verified": True}, {"id": "a", "rx_ms": 3.0, "verified": verified},
                         {"id": "b", "rx_ms": None, "verified": False}]}


def test_only_vehicles_that_accepted_the_certificate_are_rerouted(monkeypatch):
    calls = []
    monkeypatch.setattr(ir.corroboration, "accept",       # *committee: the enforced committee (default since Block G)
                        lambda alert, cert, rep, use, *committee: (calls.append(1) or True, "ok"))
    alert = {"source_vehicle": "src"}
    assert ir.accepted_by(_record(True), alert, {})[0] == ["a"]               # "b" never received it; source excluded
    assert ir.accepted_by(_record(True, verified=False), alert, {})[0] == []   # its own certificate check failed
    assert ir.accepted_by(_record(False), alert, {})[0] == []                  # rejected certificate: nobody
    assert ir.accepted_by({"corroboration": None, "vehicles": _record(True)["vehicles"]}, alert, {})[0] == []  # no voting
    monkeypatch.setattr(ir.corroboration, "accept", lambda *a: (False, "BLS aggregate signature invalid"))
    assert ir.accepted_by(_record(True), alert, {}) == ([], {"recorded": True, "reverified": False,
                                                              "reason": "BLS aggregate signature invalid"})
    tc = _fake({"a": [5.0], "b": [5.0]}, route=("A", "E1", "B"), after=("A", "C", "B"))
    res = ir.respond(tc, alert, _record(False), "E1", 50.0, {})
    assert {r["outcome"] for r in res["vehicles"]} == {"not_informed"} and tc.routes["a"] == ["A", "E1", "B"]


def test_a_vehicle_without_an_alternative_is_reported_not_dropped():
    tc = _fake({"a": [5.0]}, route=("A", "E1", "B"), after=("A", "E1", "B"))
    assert ir.reroute(tc, "a", "E1") == ("no_alternative", "SUMO's reroute from its position still uses the incident edge", "B")
    assert ir.reroute(_fake({"a": [5.0]}, route=("A", "E1")), "a", "E1")[:2] == ("no_alternative",
                                                                                  "its destination is the incident edge")
    assert ir.reroute(_fake({"a": [5.0]}, after=("A", "C", "D")), "a", "E1")[0] == "destination_changed"
    assert ir.reroute(_fake({"a": [5.0]}, after=("A", "C", "B")), "a", "E1") == ("rerouted", "", "B")


def test_rerouted_vehicles_keep_their_destination_and_never_enter_the_incident_edge(showcase):
    g, a = showcase["genuine"], showcase["acceptance"]
    rer = [r for r in g["vehicles"] if r["outcome"] == "rerouted"]
    assert len(rer) >= 40 and g["followup"]["steps"] == config.INCIDENT_FOLLOWUP_S
    for r in rer:
        assert r["accepted_alert"] and r["entries_onto_incident_edge"] == 0
        assert r["arrived_in_window"] or (r["destination_kept"] and r["route_avoids_edge_at_end"])
    assert a["only_accepting_vehicles_rerouted"] and a["destinations_kept"] and a["rerouted_never_enter_incident_edge"]
    listed = [r for r in g["vehicles"] if r["outcome"] == "no_alternative"]
    assert listed and a["no_alternative_listed"] == [r["id"] for r in listed] and all(r["reason"] and r["lane"] for r in listed)
    assert sum(r["outcome"] in ("rerouted", "no_alternative", "unavoidable", "not_informed") for r in g["vehicles"]) \
        == len(g["vehicles"])                                                  # every crossing vehicle has an outcome


def test_the_stopped_vehicle_stays_put_for_the_whole_window(showcase):
    stop = showcase["genuine"]["followup"]["stopped_vehicle"]
    assert stop["id"] == showcase["genuine"]["staged_stop"]["vehicle"]
    assert stop["max_speed_mps"] == 0 and stop["max_displacement_m"] == 0 and stop["lane_kept"]


def test_a_rejected_forged_alert_changes_no_route(showcase):
    f = showcase["forged"]
    assert f["certificate"]["recorded"] is False and f["certificate"]["reverified"] is False
    assert f["alert_accepted_by"] == 0 and f["routes_changed"] == 0 and f["detections"] == []
    assert {r["outcome"] for r in f["vehicles"]} == {"not_informed"}
    # Block F accepted this forgery at the voting-only level (reported, never applied); committee enforcement, the
    # default since Block G, rejects it there too
    assert f["counterfactual_not_applied"]["voting_only"]["certificate_accepted"] is False
    assert showcase["acceptance"]["forged_alert_zero_reroutes"]


def test_an_undetected_stop_releases_no_alert_and_reroutes_nobody(tmp_path):
    rec = ir.run(50, 4, out_dir=str(tmp_path), followup_s=10)             # v19 stops from 8.88 m/s: below the trigger
    g = rec["genuine"]
    assert g["staged_stop"]["speed_before_mps"] < 9.5 and g["detection"] is None and not g["released"]
    assert g["vehicles"] == [] and g["detections"] == [] and not rec["acceptance"]["detected_from_telemetry"]
    assert json.loads((tmp_path / "d50_r04.json").read_text())["acceptance"] == rec["acceptance"]


def test_the_same_seed_gives_the_same_incident_record(tmp_path):
    a = ir.run(50, 3, out_dir=str(tmp_path / "a"), followup_s=30)
    b = ir.run(50, 3, out_dir=str(tmp_path / "b"), followup_s=30)
    for rec in (a, b):
        rec["genuine"].pop("sumo_log"), rec["forged"].pop("sumo_log")           # the only per-folder values
    strip = lambda rec: json.dumps({k: rec[k] for k in ("genuine", "forged", "acceptance")}, sort_keys=True)
    assert strip(a) == strip(b) and a["dissemination_record"]["fingerprint"] == b["dissemination_record"]["fingerprint"]
    assert a["parameters"]["ML_TRUST_MODE"] == config.ML_TRUST_MODE == "off"


def test_live_sumo_must_match_the_recorded_snapshot(tmp_path):
    ir.run(50, 3, out_dir=str(tmp_path), followup_s=0)
    with gzip.open(tmp_path / "raw" / "d50_r03.json.gz", "rt") as fh:
        raw = json.load(fh)
    raw["scenario"]["vehicles"][0]["x"] += 1.0                               # a record that is not this traffic
    with tempfile.TemporaryDirectory() as tmp:
        sc = build(50, 3, workdir=tmp)
        with pytest.raises(RuntimeError, match="differs from the recorded snapshot"):
            ir.session(raw, str(Path(tmp) / "routes.rou.xml"), dict(zip(sc["ids"], sc["trust"])),
                       str(tmp_path / "x.log"), 0)
