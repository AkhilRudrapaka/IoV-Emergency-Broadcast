"""End-to-end: one alert per simulation, reproducible seeds, sane metrics, all outputs written."""
import glob
import json
import os
import subprocess
import sys

import numpy as np
import pytest
from py_ecc.bls import G2ProofOfPossession as bls

import config
import corroboration
import experiment
from metrics import METRICS
from scenario import build, NET_FILE, SUMO_BIN


def test_same_seed_same_scenario():
    a, b = build(50, 3), build(50, 3)
    assert a["ids"] == b["ids"] and a["source_id"] == b["source_id"]
    assert a["incident_time_s"] == b["incident_time_s"]
    assert np.array_equal(a["xy"], b["xy"]) and np.array_equal(a["trust"], b["trust"])


def test_incident_is_randomised_between_runs():
    incidents = {(s["incident_time_s"], s["source_id"]) for s in (build(50, r) for r in range(4))}
    assert len(incidents) == 4


def test_exactly_one_incident_and_valid_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(experiment, "RAW", str(tmp_path))
    monkeypatch.setattr(config, "RESULTS_DIR", str(tmp_path))     # the backhaul sqlite too: never touch tracked results
    rows, forged = experiment.run_one(100, 1)
    raw = experiment.load_raw(rows[0]["run_id"])
    scenario, alert = raw["scenario"], raw["scenario"]["alert"]
    assert [r["protocol"] for r in rows] == config.PROTOCOLS
    for name, p in raw["protocols"].items():
        sources = [v for v in p["vehicles"] if v["decision"] == "SOURCE"]
        assert len(sources) == 1 and sources[0]["id"] == scenario["source_id"], name
        assert p["transmissions"][0]["sender"] == scenario["source_id"]
    assert len({r["incident_vehicle"] for r in rows}) == 1        # every scheme saw the same incident
    for r in rows:
        assert 0 <= r["reachability"] <= 1 and 0 <= r["suppression_ratio"] <= 1
        assert r["transmissions"] >= 1 and 0 <= r["cbr_100ms"] <= 1
        # Coverage time is undefined when this scheme never reaches 90%.
        if r["reachability"] >= 0.9:
            assert np.isfinite(r["t90_ms"]) and r["t90_ms"] >= 0
        else:
            assert np.isnan(r["t90_ms"])
    again, forged_again = experiment.run_one(100, 1, save=False)
    assert json.dumps([rows, forged]) == json.dumps([again, forged_again])   # bit-identical rerun

    # every vehicle belongs to a DBSCAN cluster or is isolated, and each cluster has a representative
    labels = {v["id"]: v["dbscan"] for v in scenario["vehicles"]}
    assert len(labels) == rows[0]["vehicles"] and all(isinstance(c, int) for c in labels.values())
    for c in set(labels.values()) - {-1}:
        members = [v for v in scenario["vehicles"] if v["dbscan"] == c]
        assert len(members) >= config.DBSCAN_MIN_PTS
        assert any(v["role"] == "CH" for v in members) or all(v["trust"] < config.TRUST_CH_THRESHOLD for v in members)

    # corroboration: a real BLS certificate from a quorum of reputable committee members
    assert alert["source_vehicle"] == scenario["source_id"] and len(scenario["rsus"]) == 2
    trust = {v["id"]: v["trust"] for v in scenario["vehicles"]}
    c = raw["protocols"]["proposed"]["corroboration"]
    signers = c["certificate"]["signers"]
    assert c["accepted"] and signers[0] == alert["source_vehicle"] and len(signers) == config.QUORUM + 1
    assert set(signers[1:]) <= set(c["committee"]) and all(trust[v] >= config.TRUST_CH_THRESHOLD for v in signers[1:])
    assert bls.FastAggregateVerify([corroboration.public_key(v) for v in signers], corroboration.digest(alert),
                                   bytes.fromhex(c["certificate"]["aggregate"]))
    assert raw["protocols"]["no_security"]["corroboration"] is None
    released = raw["protocols"]["proposed"]["metrics"]["quorum_ms"]
    assert all(v["rx_ms"] > released for v in raw["protocols"]["proposed"]["vehicles"] if v["from"])

    for name, p in raw["protocols"].items():
        event = p["rsu_event"]
        if event:                                                 # one registered event, never one per RSU copy
            assert event["event_id"] == alert["event_id"] and event["status"] == "REGISTERED"
            assert event["delay_ms"] == min(r["delay_ms"] for r in p["rsu_receptions"])
            assert event["duplicate_copies"] == len(p["rsu_receptions"]) - 1
        assert all(v["hop"] <= alert["hop_limit"] for v in p["vehicles"])

    # forged-alert test on the same traffic: one forged alert per simulation, rejected by the full system
    by = {r["variant"]: r for r in forged}
    assert set(by) == set(config.FORGERY) and raw["forgery"]["forger"] != scenario["source_id"]
    assert by["voting_reputation"]["accepted_share"] == 0 and by["voting_reputation"]["rsu_registered"] == 0
    assert by["no_voting"]["accepted_share"] == 1


def test_sumo_gui_replay_matches_the_recorded_snapshot(tmp_path):
    """sumo-gui replays a run through TraCI; it must show the positions the experiment used."""
    traci = pytest.importorskip("traci")
    sc = build(50, 2, workdir=str(tmp_path), history_s=3)
    assert [h["t"] for h in sc["history"]] == [sc["incident_time_s"] - 2, sc["incident_time_s"] - 1, sc["incident_time_s"]]
    traci.start([SUMO_BIN, "-n", NET_FILE, "-r", str(tmp_path / "routes.rou.xml"),
                 "--step-length", "1", "--seed", str(sc["seed"]), "--no-step-log", "true", "--no-warnings", "true"])
    try:
        traci.simulationStep(sc["incident_time_s"] + 1)       # FCD timestep t == TraCI clock t+1
        live = {v: traci.vehicle.getPosition(v) for v in traci.vehicle.getIDList()}
    finally:
        traci.close()
    assert set(live) == set(sc["ids"])
    assert np.allclose([live[v] for v in sc["ids"]], sc["xy"], atol=0.01)


def test_full_pipeline_writes_every_output(tmp_path):
    env = {**os.environ, "EXP_RESULTS_DIR": str(tmp_path)}
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    completed = subprocess.run([sys.executable, "run.py", "experiment", "--densities", "50", "--runs", "3"],
                   cwd=root, env=env, capture_output=True)
    assert completed.returncode == 0, completed.stderr.decode(errors='replace')
    for pattern in ("raw/*.json.gz", "processed/runs.csv", "processed/summary.csv", "processed/forgery_runs.csv",
                    "processed/forgery_summary.csv", "figures/comparison.png", "figures/ablation.png",
                    "figures/forgery.png", "figures/clusters_*.png",
                    "figures/incident_map_*.png", "figures/timeline_*.png", "figures/decisions_*.png",
                    "figures/rsu.png", "figures/topology.png", "figures/propagation_*.gif",
                    "summaries/RESULTS.md", "summaries/experiment_config.json", "summaries/explain_*.md",
                    "dashboard.html"):
        assert glob.glob(str(tmp_path / pattern)), pattern
    header = open(tmp_path / "processed" / "runs.csv").readline().strip().split(",")
    assert set(METRICS) <= set(header)


def test_default_watchdog_stream_is_unchanged_and_on_off_attackers_gain_trust(monkeypatch):
    """Audit SCE-2: a persistent black hole can never exceed trust 0.5; an on-off attacker can pass the 0.7 gate.
    The new knob defaults to 0 and then draws nothing, so the recorded demo run's trust is reproduced exactly."""
    import scenario
    sc = build(200, 2)
    recorded = {v["id"]: v["trust"] for v in experiment.load_raw("d200_r02")["scenario"]["vehicles"]}
    assert [round(float(t), 3) for t in sc["trust"]] == [recorded[v] for v in sc["ids"]]
    assert sc["trust"][sc["malicious"]].max() <= 0.5
    monkeypatch.setattr(scenario, "MALICIOUS_COOPERATION", 0.9)
    onoff = build(200, 2)
    assert onoff["trust"][onoff["malicious"]].max() >= config.TRUST_CH_THRESHOLD
    assert np.array_equal(onoff["xy"], sc["xy"])                  # mobility is untouched


def test_a_route_head_without_local_quorum_records_why():
    """d200_r12 (pair P005): route head v95 collects only 2 of the 3 local votes. It never decides, and its record
    must say why instead of an empty reason (the decision itself stays UNDECIDED, so no metric changes)."""
    sc = build(200, 12)
    net = experiment.network(sc)
    schemes, _ = experiment.arms(sc, net, sc["alert"], sc["source"])
    make, roles = schemes["ch_route"]
    rng = np.random.default_rng([sc["seed"], config.PROTOCOLS.index("ch_route")])
    _, record = experiment.run_arm(make, roles, sc, net, sc["alert"], sc["source"], rng)
    failed = [row for row in record["cluster_consensus"] if not row["accepted"]]
    assert [row["cluster_head"] for row in failed] == ["v95"]
    head = next(v for v in record["vehicles"] if v["id"] == "v95")
    assert head["decision"] == "UNDECIDED" and "local quorum failed (insufficient distinct votes received)" in head["reason"]
    assert not [v["id"] for v in record["vehicles"] if v["decision"] == "UNDECIDED" and not v["reason"]]


def test_results_md_names_n_where_fewer_runs_had_a_value():
    """A RESULTS.md cell says how many runs it comes from when not every run defined the value; the tracked RESULTS.md
    is exactly what the code writes from the tracked processed CSVs (only its 'Generated <date>' line is not compared)."""
    import figures
    import report
    row = {"t90_ms": 36.3, "t90_ms_ci95": 3.4, "t90_ms_n": 23, "runs": 30}
    assert report._fmt(row, "t90_ms") == "36.3 ± 3.4 (n=23)"
    assert report._fmt(row, "t90_ms", show_n=False) == "36.3 ± 3.4"           # a table with its own n column
    assert report._fmt({**row, "t90_ms_n": 30}, "t90_ms") == "36.3 ± 3.4"      # every run: no note
    proc = os.path.join(config.RESULTS_DIR, "processed")
    text = report.results_md(figures._read(os.path.join(proc, "summary.csv")), figures._read(os.path.join(proc, "forgery_summary.csv")),
                             experiment.paired(figures._read(os.path.join(proc, "runs.csv"))))
    with open(os.path.join(config.RESULTS_DIR, "summaries", "RESULTS.md"), encoding="utf-8") as f:
        tracked = f.read()
    body = lambda t: [line for line in t.splitlines() if not line.startswith("Generated ")]
    assert body(text) == body(tracked), "RESULTS.md differs from what the code writes from the processed CSVs"


def test_the_suite_reads_the_tracked_results():
    # validation/conftest.py drops EXP_RESULTS_DIR: the reference data is results/urban even when the variable is set
    assert "EXP_RESULTS_DIR" not in os.environ and config.RESULTS_DIR == "results/urban"
