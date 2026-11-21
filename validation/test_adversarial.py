"""Block F: relay dropping, forged alerts, phased on-off attackers, collusion, and the opt-in committee level.
Every default is the earlier behaviour (the tracked results are checked by the existing tests); real BLS12-381."""
import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

import adversarial
import config
import corroboration
import experiment
import scenario
from channel import geometry, simulate
from protocols import Proposed
from scenario import build, create_alert, seed_for

ROOT = Path(__file__).resolve().parent.parent
ALERT = create_alert(1, "n0", (0.0, 0.0), 60.0)
NAMES = [f"n{i}" for i in range(9)]
HONEST_NEAR, FAR_ATTACKERS = ["n1", "n2", "n3", "n4", "n5"], ["n6", "n7", "n8"]


def _net(genuine, require_committee=False, malicious=(6, 7, 8)):
    """Source n0; n1-n5 honest, 20-40 m away (they are the committee); n6-n8 misbehaving, 120-160 m away; all reputable."""
    xy = [(0, 0)] + [(20 + 5 * i, 0) for i in range(5)] + [(0, 120 + 20 * i) for i in range(3)]
    dist, adj = geometry(np.array(xy, float))
    mal = np.isin(np.arange(9), malicious)
    sec = corroboration.plan(ALERT, 0, dist, adj, 9, np.full(9, 0.9), mal, genuine, require_committee=require_committee)
    p = Proposed(dist, adj, mal, np.zeros(9, int), None, sec)
    p.names = NAMES
    simulate(p, adj, 0, np.random.default_rng(0))
    return p, sec


def _block_f(monkeypatch):
    """These tests characterise Block F, i.e. the rule before committee enforcement became the default (Block G)."""
    import infrastructure
    for module in (config, corroboration, infrastructure):
        monkeypatch.setattr(module, "ENFORCE_COMMITTEE", 0)


def test_defaults_are_the_earlier_behaviour_and_draw_nothing():
    assert (config.MALICIOUS_DROP_PROB, config.MAX_COLLUDERS, config.ONOFF_PERIOD_S, config.COMMITTEE_CHECK) == (1.0, 5, 0.0, 0)
    assert list(config.FORGERY) == ["voting_reputation", "voting_only", "no_voting"]
    mal = np.array([True, False, True])
    assert experiment.droppers({"seed": 1}, mal) is mal                    # returned as is: no random number drawn


def test_drop_probability_decides_who_drops_the_alert(monkeypatch):
    mal = np.ones(20000, bool)
    monkeypatch.setattr(config, "MALICIOUS_DROP_PROB", 0.5)
    half = experiment.droppers({"seed": 7}, mal)
    assert 0.48 < half.mean() < 0.52 and np.array_equal(half, experiment.droppers({"seed": 7}, mal))   # same seed, same draw
    assert not np.array_equal(half, experiment.droppers({"seed": 8}, mal))
    assert not experiment.droppers({"seed": 7}, np.zeros(5, bool)).any()   # an honest vehicle never drops
    monkeypatch.setattr(config, "MALICIOUS_DROP_PROB", 0.0)
    p, _ = _net(genuine=True, malicious=(6, 7, 8))
    p2 = Proposed(p.dist, p.adj, p.malicious, np.zeros(9, int))
    p2.names, p2.drops = NAMES, experiment.droppers({"seed": 1}, p.malicious)
    simulate(p2, p.adj, 0, np.random.default_rng(0))
    assert p2.has[6:].all() and not any(r.get("decision") == "DROP" for r in p2.rec.values())


def _run(monkeypatch, tmp_path, d, r, **knobs):
    for mod, key, value in knobs.get("patch", []):
        monkeypatch.setattr(mod, key, value)
    monkeypatch.setattr(experiment, "RAW", str(tmp_path))
    monkeypatch.setattr(config, "RESULTS_DIR", str(tmp_path))
    rows, forged = experiment.run_one(d, r, archive=False)
    with gzip.open(tmp_path / f"d{d}_r{r:02d}.json.gz", "rt") as fh:
        return rows, forged, json.load(fh)


def test_the_same_droppers_act_in_every_scheme_and_the_forgery_test(tmp_path, monkeypatch):
    _, _, raw = _run(monkeypatch, tmp_path, 50, 3, patch=[(config, "MALICIOUS_DROP_PROB", 0.5)])
    vs = raw["scenario"]["vehicles"]
    mal = np.concatenate([[v["malicious"] for v in vs], np.zeros(len(config.RSU_POSITIONS), bool)])
    drops = experiment.droppers({"seed": seed_for(50, 3)}, mal)
    expected = {vs[i]["id"] for i in np.flatnonzero(drops[:len(vs)])}
    assert expected and expected != {v["id"] for v in vs if v["malicious"]}  # some attackers drop, some relay
    records = list(raw["protocols"].values()) + list(raw["forgery"]["variants"].values())
    for rec in records:
        for v in rec["vehicles"]:
            if v["decision"] == "DROP":
                assert v["id"] in expected
            elif v["id"] in expected and v["rx_ms"] is not None and v["decision"] != "SOURCE":   # a forger originates
                raise AssertionError(f"{v['id']} should have dropped")


def test_the_committee_level_counts_only_committee_endorsers_and_keeps_genuine_alerts(monkeypatch):
    _block_f(monkeypatch)
    outside = corroboration.certificate(ALERT, "n0", FAR_ATTACKERS)
    inside = corroboration.certificate(ALERT, "n0", HONEST_NEAR[:3])
    rep = lambda v: 0.9
    assert corroboration.accept(ALERT, outside, rep)[0]                      # the known gap: any 3 reputable signers
    assert corroboration.accept(ALERT, outside, rep, committee=HONEST_NEAR) == (
        False, "only 0 reputable committee endorser(s), 3 needed")
    assert corroboration.accept(ALERT, inside, rep)[0] and corroboration.accept(ALERT, inside, rep, committee=HONEST_NEAR)[0]
    forged, sec = _net(genuine=False)                                        # default level: the colluders' lie spreads
    assert [NAMES[v] for v in sec["committee"]] == HONEST_NEAR and forged.cert_ok and forged.has[1:6].all()
    gated, _ = _net(genuine=False, require_committee=True)
    assert gated.cert is not None and not gated.cert_ok and not gated.has[1:6].any()
    assert "committee" in gated.cert_reason
    genuine, _ = _net(genuine=True, require_committee=True)
    assert genuine.cert_ok and genuine.has.all()                             # genuine votes come from the committee


def test_the_colluder_limit(monkeypatch):
    _block_f(monkeypatch)
    monkeypatch.setattr(corroboration, "MAX_COLLUDERS", 2)
    p, sec = _net(genuine=False)
    assert len(sec["voters"]) == 2 and p.cert is None and not p.has[1:].any()   # 2 endorsers: no quorum, no alert
    monkeypatch.setattr(corroboration, "MAX_COLLUDERS", 3)
    p, sec = _net(genuine=False)
    assert len(sec["voters"]) == 3 and p.cert_ok


def test_the_opt_in_level_leaves_the_three_default_levels_unchanged(tmp_path, monkeypatch):
    _block_f(monkeypatch)
    onoff = [(scenario, "MALICIOUS_COOPERATION", 0.9)]
    _, forged_a, a = _run(monkeypatch, tmp_path / "a", 200, 2, patch=onoff)
    levels = {**config.FORGERY, "voting_reputation_committee": "committee"}
    _, forged_b, b = _run(monkeypatch, tmp_path / "b", 200, 2, patch=onoff + [(config, "FORGERY", levels)])
    for variant in ("voting_reputation", "voting_only", "no_voting"):
        assert json.dumps(a["forgery"]["variants"][variant], sort_keys=True) == \
            json.dumps(b["forgery"]["variants"][variant], sort_keys=True)
    assert forged_b[:3] == forged_a and [r["variant"] for r in forged_b][3] == "voting_reputation_committee"
    assert b["forgery"]["variants"]["voting_reputation"]["corroboration"]["accepted"]           # the on-off forgery
    c = b["forgery"]["variants"]["voting_reputation_committee"]["corroboration"]
    assert not c["accepted"] and "committee" in c["reason"] and forged_b[3]["accepted_share"] == 0.0
    assert json.dumps(a["protocols"], sort_keys=True) == json.dumps(b["protocols"], sort_keys=True)


def test_phased_on_off_changes_only_the_attackers_cooperation(monkeypatch):
    base = build(50, 3)
    honest, att = ~base["malicious"], base["malicious"]
    monkeypatch.setattr(scenario, "ONOFF_PERIOD_S", 10.0)
    means = {}
    for duty in (0.0, 0.5, 1.0):
        monkeypatch.setattr(scenario, "ONOFF_DUTY", duty)
        sc = build(50, 3)
        assert np.array_equal(sc["trust"][honest], base["trust"][honest])   # the watchdog's random stream is untouched
        means[duty] = sc["trust"][att].mean()
        if duty == 0.0:
            assert np.array_equal(sc["trust"], base["trust"])               # never cooperating = the persistent black hole
    assert np.array_equal(build(50, 3)["trust"], sc["trust"])                # same seed, same phases
    assert means[0.0] < 0.5 and 0.35 < means[0.5] < 0.55 and means[1.0] >= config.TRUST_CH_THRESHOLD


def test_calibration_picks_the_smallest_safe_gate(tmp_path):
    rows = [{"TRUST_CH_THRESHOLD": g, "variant": "voting_reputation", "accepted": a} for g, a in
            ((0.7, 0.8), (0.75, 0.1), (0.8, 0.0), (0.84, 0.0), (0.86, 0.0), (0.88, 0.0), (0.9, 0.0))]
    trust = [{"TRUST_CH_THRESHOLD": g, "genuine_accepted": a} for g, a in
             ((0.7, 1.0), (0.75, 1.0), (0.8, 0.97), (0.84, 1.0), (0.86, 1.0), (0.88, 0.9), (0.9, 0.9))]
    adversarial._write(tmp_path / "C_calibration_forgery_summary.csv", rows)
    adversarial._write(tmp_path / "C_calibration_trust_summary.csv", trust)
    assert adversarial.calibrate(str(tmp_path)) == 0.84                     # 0.80 loses genuine alerts
    assert json.loads((tmp_path / "C_calibration_choice.json").read_text())["chosen_gate"] == 0.84


def test_the_sweep_runner_writes_only_its_folder_and_collects_every_run(tmp_path):
    tracked = ROOT / "results/urban/processed/summary.csv"
    before = hashlib.md5(tracked.read_bytes()).hexdigest()
    setting = {"MALICIOUS_DROP_PROB": 0.5, "COMMITTEE_CHECK": 1}
    folder = tmp_path / "T" / adversarial.name(setting)
    assert adversarial.run_setting(str(folder), setting, [50], 2, 0) is True
    assert adversarial.run_setting(str(folder), setting, [50], 2, 0) is False                 # finished: skipped
    paths = adversarial.summarise("T", [setting], str(tmp_path))
    assert hashlib.md5(tracked.read_bytes()).hexdigest() == before
    read = lambda kind: list(csv.DictReader(open(tmp_path / f"T_{kind}_runs.csv", encoding="utf-8")))
    genuine, trust, forgery = read("genuine"), read("trust"), read("forgery")
    assert len(genuine) == 2 * len(adversarial.SCHEMES) and len(trust) == 2 and len(paths) == 6
    assert all(float(r["MALICIOUS_DROP_PROB"]) == 0.5 and float(r["MALICIOUS_RATIO"]) == config.MALICIOUS_RATIO for r in genuine)
    assert all(0 <= float(r["trust_auc"]) <= 1 for r in trust)
    assert {r["variant"] for r in forgery} <= {*config.FORGERY, "voting_reputation_committee"}
    assert "voting_reputation_committee" in {r["variant"] for r in forgery}
    for r in forgery:                                                        # the opt-in level never accepts more
        if r["variant"] == "voting_reputation_committee":
            same = next(x for x in forgery if x["run_id"] == r["run_id"] and x["variant"] == "voting_reputation")
            assert float(r["accepted"]) <= float(same["accepted"])
