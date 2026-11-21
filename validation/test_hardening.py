"""Block G: ENFORCE_COMMITTEE (receiver-rebuilt committee at every certificate check; default on since the Block G
final decision, 0 = Block F) and TRUST_BURST_K (burst detector that removes eligibility but keeps the Beta trust;
default off, k = 4 opt-in). Real BLS12-381."""
import gzip
import json

import numpy as np

import config
import corroboration
import experiment
import incident_response as ir
import infrastructure
import scenario
from channel import geometry, simulate
from protocols import Proposed
from scenario import build, create_alert

ALERT = create_alert(1, "n0", (0.0, 0.0), 60.0)
NAMES = [f"n{i}" for i in range(9)]
HONEST_NEAR, FAR_ATTACKERS = ["n1", "n2", "n3", "n4", "n5"], ["n6", "n7", "n8"]


def _net(genuine, use_reputation=True):
    """Source n0; n1-n5 honest, 20-40 m away (the committee); n6-n8 misbehaving, 120-160 m away; all reputable."""
    xy = [(0, 0)] + [(20 + 5 * i, 0) for i in range(5)] + [(0, 120 + 20 * i) for i in range(3)]
    dist, adj = geometry(np.array(xy, float))
    mal = np.isin(np.arange(9), (6, 7, 8))
    sec = corroboration.plan(ALERT, 0, dist, adj, 9, np.full(9, 0.9), mal, genuine, use_reputation)
    p = Proposed(dist, adj, mal, np.zeros(9, int), None, sec)
    p.names = NAMES
    simulate(p, adj, 0, np.random.default_rng(0))
    return p, sec


def _enforce(monkeypatch, on=1):
    for module in (config, corroboration, infrastructure):
        monkeypatch.setattr(module, "ENFORCE_COMMITTEE", on)


def test_final_defaults_enforce_the_committee_at_5_of_3_without_the_burst_detector():
    assert (config.ENFORCE_COMMITTEE, config.COMMITTEE_SIZE, config.QUORUM, config.TRUST_BURST_K) == (1, 5, 3, 0)
    assert corroboration.ENFORCE_COMMITTEE == infrastructure.ENFORCE_COMMITTEE == 1    # module copies agree
    assert (corroboration.COMMITTEE_SIZE, corroboration.QUORUM) == (5, 3)
    assert not hasattr(config, "CH_ROUTE_QUORUM") and config.ML_TRUST_MODE == "off"   # no local quorum; ML shadow only
    forged, sec = _net(genuine=False)                                       # reputable outsiders sign a forged alert
    assert sec["require_committee"] is True and not forged.cert_ok and "committee" in forged.cert_reason
    genuine, _ = _net(genuine=True)
    assert genuine.cert_ok and genuine.has.all()                            # the genuine alert is not suppressed


def test_enforcement_can_be_switched_off_to_reproduce_block_f(monkeypatch):
    _enforce(monkeypatch, 0)
    forged, sec = _net(genuine=False)
    assert sec["require_committee"] is False and forged.cert_ok            # the Block F gap, as before


def test_every_check_site_rejects_outsider_signers_by_default():
    outsiders = corroboration.certificate(ALERT, "n0", FAR_ATTACKERS)
    record = {"corroboration": {"accepted": True, "use_reputation": True, "committee": HONEST_NEAR,
                                "certificate": outsiders},
              "vehicles": [{"id": v, "rx_ms": 1.0, "verified": True} for v in NAMES]}
    ids, check = ir.accepted_by(record, ALERT, {v: 0.9 for v in NAMES})    # incident re-verification
    assert ids == [] and "committee" in check["reason"]
    accepted, rejected = infrastructure.batch_authenticate([(ALERT, outsiders, HONEST_NEAR)], {v: 0.9 for v in NAMES})
    assert accepted == [] and "committee" in rejected[0]["reason"]          # RSU batch authentication
    forged, _ = _net(genuine=False)                                         # release / every receiver (protocols)
    assert not forged.cert_ok and not forged.has[1:].any()


def test_the_k4_opt_in_and_the_g4_settings_are_preserved():
    import adversarial
    first, g4 = adversarial.g_sweeps(4, (5, 3))["G4"]
    names = [adversarial.name(s) for s in g4]
    assert first == 0 and len(names) == len(set(names)) == 25              # 18 B + 16 C, colluders-3 B folded into 5
    assert all(s["TRUST_BURST_K"] == 4 and s["ENFORCE_COMMITTEE"] == 1 and (s["COMMITTEE_SIZE"], s["QUORUM"]) == (5, 3)
               and s["MAX_COLLUDERS"] == 5 for s in g4)
    assert all(s["TRUST_BURST_K"] == 4 for s in adversarial.g_sweeps(4)["G3b"][1])


def test_enforced_committee_rejects_outsider_signers_at_every_voting_level(monkeypatch):
    _enforce(monkeypatch)
    for use_reputation in (True, False):                                    # voting + reputation, and voting only
        forged, sec = _net(genuine=False, use_reputation=use_reputation)
        assert sec["require_committee"] is True and forged.cert is not None and not forged.cert_ok
        assert "committee" in forged.cert_reason and not forged.has[1:6].any()
        genuine, _ = _net(genuine=True, use_reputation=use_reputation)
        assert genuine.cert_ok and genuine.has.all()                        # genuine votes come from the committee


def test_a_committee_listed_in_a_certificate_is_never_used():
    cert = dict(corroboration.certificate(ALERT, "n0", FAR_ATTACKERS), committee=FAR_ATTACKERS)   # a forger's claim
    rep = lambda v: 0.9
    assert not corroboration.accept(ALERT, cert, rep, committee=HONEST_NEAR)[0]   # the rebuilt committee decides
    accepted, rejected = infrastructure.batch_authenticate([(ALERT, cert, HONEST_NEAR)], {v: 0.9 for v in NAMES})
    assert accepted == [] and "committee" in rejected[0]["reason"]
    accepted, _ = infrastructure.batch_authenticate([(ALERT, cert)], {v: 0.9 for v in NAMES})   # no committee given:
    assert accepted == [ALERT]                                                                # the Block F rule
    inside = corroboration.certificate(ALERT, "n0", HONEST_NEAR[:3])
    assert infrastructure.batch_authenticate([(ALERT, inside, HONEST_NEAR)], {v: 0.9 for v in NAMES})[0] == [ALERT]


def test_incident_reverification_follows_enforcement(monkeypatch):
    record = {"corroboration": {"accepted": True, "use_reputation": True, "committee": HONEST_NEAR,
                                "certificate": corroboration.certificate(ALERT, "n0", FAR_ATTACKERS)},
              "vehicles": [{"id": v, "rx_ms": 1.0, "verified": True} for v in NAMES]}
    trust = {v: 0.9 for v in NAMES}
    _enforce(monkeypatch, 0)
    assert len(ir.accepted_by(record, ALERT, trust)[0]) == 8                # enforcement off: Block F behaviour
    _enforce(monkeypatch)
    ids, check = ir.accepted_by(record, ALERT, trust)
    assert ids == [] and not check["reverified"] and "committee" in check["reason"]


def _run(monkeypatch, tmp_path, d, r, patch=()):
    for module, key, value in patch:
        monkeypatch.setattr(module, key, value)
    monkeypatch.setattr(experiment, "RAW", str(tmp_path))
    monkeypatch.setattr(config, "RESULTS_DIR", str(tmp_path))
    rows, forged = experiment.run_one(d, r, archive=False)
    with gzip.open(tmp_path / f"d{d}_r{r:02d}.json.gz", "rt") as fh:
        return rows, forged, json.load(fh)


def test_genuine_runs_are_identical_with_enforcement(tmp_path, monkeypatch):
    _enforce(monkeypatch, 0)
    rows_off, _, off = _run(monkeypatch, tmp_path / "off", 50, 3)
    _enforce(monkeypatch)
    rows_on, _, on = _run(monkeypatch, tmp_path / "on", 50, 3)
    assert json.dumps(rows_off, sort_keys=True) == json.dumps(rows_on, sort_keys=True)          # every scheme's metrics
    for key in ("scenario", "protocols"):                                   # incl. CH-route cluster rounds
        assert json.dumps(off[key], sort_keys=True) == json.dumps(on[key], sort_keys=True)
    assert off["infrastructure"]["batch_authentication"] == on["infrastructure"]["batch_authentication"]
    assert on["protocols"]["ch_route"]["cluster_consensus"] and all(
        c["accepted"] == d["accepted"] for c, d in zip(off["protocols"]["ch_route"]["cluster_consensus"],
                                                       on["protocols"]["ch_route"]["cluster_consensus"]))


def test_enforced_default_level_decides_like_the_block_f_committee_level(tmp_path, monkeypatch):
    levels = {**config.FORGERY, "voting_reputation_committee": "committee"}
    _enforce(monkeypatch)
    _, forged, raw = _run(monkeypatch, tmp_path, 200, 2, patch=[(scenario, "MALICIOUS_COOPERATION", 0.9),
                                                                 (config, "FORGERY", levels)])
    v = {k: x["corroboration"] for k, x in raw["forgery"]["variants"].items() if x["corroboration"]}
    assert v["voting_reputation"]["accepted"] == v["voting_reputation_committee"]["accepted"] is False   # was True
    assert "committee" in v["voting_reputation"]["reason"] and not v["voting_only"]["accepted"]
    assert [r["accepted_share"] for r in forged][:2] == [0.0, 0.0]


# ------------------------------------------------------------------ TRUST_BURST_K (G3)
def test_the_burst_detector_is_off_by_default_and_never_changes_the_beta_trust(monkeypatch):
    base = build(50, 3)
    assert "burst_flagged" not in base and scenario.decision_trust(base) is base["trust"]
    monkeypatch.setattr(scenario, "TRUST_BURST_K", 3)
    on = build(50, 3)
    assert np.array_equal(on["trust"], base["trust"])                       # Beta trust identical; nothing drawn
    assert np.array_equal(on["burst_flagged"], on["burst_max_run"] >= 3)
    again = build(50, 3)
    assert np.array_equal(again["burst_max_run"], on["burst_max_run"])      # deterministic
    dec, flagged = scenario.decision_trust(on), on["burst_flagged"]
    assert np.array_equal(dec[flagged], np.minimum(on["trust"][flagged], 0.5))   # capped at the prior (plan 4.3)
    assert (dec[flagged] < config.TRUST_CH_THRESHOLD).all()
    assert np.array_equal(dec[~flagged], on["trust"][~flagged])


def _bursts(monkeypatch, period, k):
    """Watchdog misses off, 10 % phased attackers with duty 0.9: every failure is an attacker's off-window second, so the
    failure runs are exactly (1 - duty) * period seconds long (1 s for a 10 s period, 3 s for a 30 s period)."""
    for key, value in (("WATCHDOG_MISS_PROB", 0.0), ("ONOFF_PERIOD_S", period), ("ONOFF_DUTY", 0.9),
                       ("TRUST_BURST_K", k)):
        monkeypatch.setattr(scenario, key, value)
    return build(50, 3)


def test_isolated_failures_never_form_a_burst(monkeypatch):
    sc = _bursts(monkeypatch, 10.0, 2)                  # one failed second, then nine good ones, per cycle
    att = sc["malicious"]
    assert (sc["burst_max_run"][att] == 1).all() and (sc["burst_max_run"][~att] == 0).all()
    assert not sc["burst_flagged"].any()


def test_exactly_k_consecutive_failures_raise_the_flag(monkeypatch):
    sc = _bursts(monkeypatch, 30.0, 3)                  # three failed seconds in a row, per cycle
    att = sc["malicious"]
    assert (sc["burst_max_run"][att] == 3).all() and (sc["burst_max_run"][~att] == 0).all()
    assert np.array_equal(sc["burst_flagged"], att)     # k = 3 consecutive failures: flagged
    assert not _bursts(monkeypatch, 30.0, 4)["burst_flagged"].any()          # k = 4: never reached


def test_long_off_periods_produce_long_failure_runs_and_honest_misses_do_not(monkeypatch):
    for key, value in (("TRUST_BURST_K", 4), ("ONOFF_PERIOD_S", 30.0), ("ONOFF_DUTY", 0.8)):
        monkeypatch.setattr(scenario, key, value)                           # off windows of about 6 s
    sc = build(50, 3)
    att, hon = sc["burst_max_run"][sc["malicious"]], sc["burst_max_run"][~sc["malicious"]]
    assert att.min() >= 4 and sc["burst_flagged"][sc["malicious"]].all()
    assert np.median(hon) <= 2 and att.min() > np.median(hon)


def test_flagged_vehicles_lose_eligibility_while_records_keep_their_beta_trust(tmp_path, monkeypatch):
    _, _, off = _run(monkeypatch, tmp_path / "off", 50, 3, patch=[(scenario, "ONOFF_PERIOD_S", 30.0),
                                                                  (scenario, "ONOFF_DUTY", 0.8)])
    _, _, on = _run(monkeypatch, tmp_path / "on", 50, 3, patch=[(scenario, "TRUST_BURST_K", 4)])
    v_off, v_on = off["scenario"]["vehicles"], on["scenario"]["vehicles"]
    assert [v["trust"] for v in v_off] == [v["trust"] for v in v_on]           # Beta trust kept in the record
    assert "burst_flagged" not in v_off[0] and "burst_flagged" in v_on[0]
    flagged = {v["id"] for v in v_on if v["burst_flagged"]}
    assert flagged and not any(v["role"] == "CH" for v in v_on if v["id"] in flagged)
    committee = on["protocols"]["proposed"]["corroboration"]["committee"]
    assert not flagged & set(committee)                                       # never on a committee
    eligible_before = {v["id"] for v in v_off if v["trust"] >= config.TRUST_CH_THRESHOLD}
    assert flagged & eligible_before                                          # some lost eligibility only by the flag


# ------------------------------------------------------------------ committee size / quorum (G2) and the sweep rules
def test_withholding_rule_for_a_seven_seat_committee_with_quorum_four(monkeypatch):
    import protocols
    monkeypatch.setattr(corroboration, "COMMITTEE_SIZE", 7)
    for module in (corroboration, protocols):
        monkeypatch.setattr(module, "QUORUM", 4)
    xy = np.array([(0, 0)] + [(15 + 10 * i, 0) for i in range(9)], float)   # n1..n9 by distance
    dist, adj = geometry(xy)
    for silent, released in (((1, 2, 3, 4), False), ((1, 2, 3), True)):    # m - q + 1 = 4 silent attackers block
        mal = np.isin(np.arange(10), silent)
        sec = corroboration.plan(ALERT, 0, dist, adj, 10, np.full(10, 0.9), mal, True)
        p = Proposed(dist, adj, mal, np.zeros(10, int), None, sec)
        p.names = [f"n{i}" for i in range(10)]
        simulate(p, adj, 0, np.random.default_rng(0))
        assert len(sec["committee"]) == 7 and (p.cert is not None) == released
        if released:
            assert len(p.cert["signers"]) == 1 + 4 and p.cert_ok


def test_burst_calibration_and_committee_selection_follow_the_preregistered_rules(tmp_path):
    import adversarial
    trust = [{"TRUST_BURST_K": k, "honest_flagged": f} for k, f in ((3, 0.08), (3, 0.002), (4, 0.012), (4, 0.0),
                                                                     (5, 0.004), (5, 0.001), (6, 0.0), (6, 0.0))]
    adversarial._write(tmp_path / "G3a_trust_summary.csv", trust)
    assert adversarial.calibrate_burst(str(tmp_path)) == 5                  # 4 fails one setting (1.2 % > 1 %)
    ref = tmp_path / "ref"
    ref.mkdir()
    cell = dict(MALICIOUS_RATIO=0.2, MALICIOUS_COOPERATION=0.9, ONOFF_PERIOD_S=0.0, ONOFF_DUTY=0.9, MAX_COLLUDERS=5,
                density=200)
    for sweep in ("B", "C"):
        adversarial._write(ref / f"{sweep}_trust_runs.csv",
                           [dict(cell, run_id=f"r{i}", genuine_accepted=a) for i, a in enumerate((1, 1))])
        adversarial._write(ref / f"{sweep}_forgery_runs.csv", [dict(cell, run_id="r0", variant="voting_reputation",
                                                                    accepted=1), dict(cell, run_id="r1",
                                                                    variant="voting_reputation", accepted=1)])
        adversarial._write(ref / f"{sweep}_genuine_runs.csv", [dict(cell, run_id=f"r{i}", scheme="proposed",
                                                                    accepted=1, honest_delivery=1.0) for i in (0, 1)])
    tr, fg, gn = [], [], []
    for m, q in adversarial.COMMITTEES:
        acc = {(5, 3): (1, 1), (7, 4): (1, 1), (9, 5): (1, 0), (7, 3): (1, 1)}[(m, q)]   # 9/5 loses r1 ...
        att = {(9, 5): 2}.get((m, q), 0)                                                  # ... not by withholding
        g = dict(cell, COMMITTEE_SIZE=m, QUORUM=q)
        tr += [dict(g, run_id=f"r{i}", genuine_accepted=a, attackers_in_committee=att, committee_size=m)
               for i, a in enumerate(acc)]
        fg += [dict(g, run_id=f"r{i}", variant="voting_reputation", accepted=int((m, q) == (7, 3))) for i in (0, 1)]
        gn += [dict(g, run_id=f"r{i}", scheme="proposed", accepted=a, honest_delivery=1.0) for i, a in enumerate(acc)]
    for kind, rows in (("trust", tr), ("forgery", fg), ("genuine", gn)):
        adversarial._write(tmp_path / f"G2_{kind}_runs.csv", rows)
    assert adversarial.select_committee(str(tmp_path), str(ref)) == (5, 3)   # ties: fewer forgeries, then smaller
    sel = json.loads((tmp_path / "G2_selection_corrected.json").read_text())["candidates"]
    assert not sel["9/5"]["admissible"] and sel["7/3"]["admissible"] and sel["7/4"]["admissible"]
    assert not sel["7/3"]["candidate"] and not (tmp_path / "G2_selection.json").exists()   # history never written


# ------------------------------------------------------------------ corrected committee selection (G4.1)
def _g2(tmp_path, ref_genuine, genuine, forged, ref_forged=1, ch_lost=()):
    """Two seeds of one G2 cell and its Block F reference. genuine / forged: (m, q) -> per-seed accepted (default 1).
    ch_lost: configurations whose CH route loses the relayed RSU copy on r0 that Block F delivered."""
    import adversarial
    cell = dict(MALICIOUS_RATIO=0.2, MALICIOUS_COOPERATION=0.9, ONOFF_PERIOD_S=0.0, ONOFF_DUTY=0.9, MAX_COLLUDERS=5,
                density=200)
    ref = tmp_path / "ref"
    ref.mkdir(exist_ok=True)
    gen = lambda g, acc, relay: ([dict(g, run_id=f"r{i}", scheme="proposed", accepted=a, honest_delivery=1.0,
                                       rsu_relay_received=1) for i, a in enumerate(acc)] +
                                 [dict(g, run_id=f"r{i}", scheme="ch_route", accepted=a, honest_delivery=1.0,
                                       rsu_relay_received=relay if i == 0 else 1) for i, a in enumerate(acc)])
    for sweep in ("B", "C"):
        adversarial._write(ref / f"{sweep}_trust_runs.csv",
                           [dict(cell, run_id=f"r{i}", genuine_accepted=a) for i, a in enumerate(ref_genuine)])
        adversarial._write(ref / f"{sweep}_forgery_runs.csv", [dict(cell, run_id=f"r{i}", variant="voting_reputation",
                                                                    accepted=ref_forged) for i in (0, 1)])
        adversarial._write(ref / f"{sweep}_genuine_runs.csv", gen(cell, ref_genuine, 1))
    tr, fg, gn = [], [], []
    for m, q in adversarial.COMMITTEES:
        g, acc = dict(cell, COMMITTEE_SIZE=m, QUORUM=q), genuine.get((m, q), (1, 1))
        tr += [dict(g, run_id=f"r{i}", genuine_accepted=a, attackers_in_committee=0, committee_size=m)
               for i, a in enumerate(acc)]
        fg += [dict(g, run_id=f"r{i}", variant="voting_reputation", accepted=forged.get((m, q), 0)) for i in (0, 1)]
        gn += gen(g, acc, 0 if (m, q) in ch_lost else 1)
    for kind, rows in (("trust", tr), ("forgery", fg), ("genuine", gn)):
        adversarial._write(tmp_path / f"G2_{kind}_runs.csv", rows)
    chosen = adversarial.select_committee(str(tmp_path), str(ref))
    return chosen, json.loads((tmp_path / "G2_selection_corrected.json").read_text())


def test_the_seven_three_contrast_can_never_be_selected(tmp_path):
    # 7/3 alone has no forgery: by the registered ranking it would win, but it is a contrast arm, not a candidate
    chosen, rec = _g2(tmp_path, (1, 1), {}, {(5, 3): 1, (7, 4): 1, (9, 5): 1, (7, 3): 0})
    assert rec["candidates"]["7/3"]["admissible"] and not rec["candidates"]["7/3"]["candidate"]
    assert chosen == (5, 3) and rec["chosen"] == rec["selection_rule_choice"] == [5, 3]    # tie -> smallest
    assert rec["eligible_candidates"] == ["5/3", "7/4", "9/5"] and rec["contrast_only"] == ["7/3"]


def test_the_registered_rule_ranks_admissible_candidates_by_genuine_acceptance(tmp_path):
    # Block F lost the genuine alert on r1; 9/5 recovers it, so it has the highest pooled genuine acceptance
    chosen, rec = _g2(tmp_path, (1, 0), {(5, 3): (1, 0), (7, 4): (1, 0), (9, 5): (1, 1), (7, 3): (1, 1)}, {})
    assert chosen == (9, 5) and rec["selection_rule_choice"] == [9, 5]


def test_ch_route_losses_block_adoption_but_not_the_registered_rule(tmp_path):
    chosen, rec = _g2(tmp_path, (1, 0), {(5, 3): (1, 0), (7, 4): (1, 0), (9, 5): (1, 1), (7, 3): (1, 1)}, {},
                      ch_lost={(9, 5), (7, 4)})
    assert rec["selection_rule_choice"] == [9, 5]                            # registered rule: proposed scheme only
    assert rec["candidates"]["9/5"]["ch_route_violations"] and not rec["candidates"]["9/5"]["adoptable"]
    assert chosen == (5, 3) and rec["chosen"] == [5, 3]


def test_no_committee_is_selected_when_no_candidate_qualifies(tmp_path):
    import adversarial
    chosen, rec = _g2(tmp_path, (1, 1), {}, {(5, 3): 1, (7, 4): 1, (9, 5): 1, (7, 3): 1}, ref_forged=0)
    assert chosen is None and rec["chosen"] is None and rec["selection_rule_choice"] is None
    assert all(v["criterion1_violations"] for v in rec["candidates"].values())
    assert adversarial._choices(str(tmp_path))[1] is None
    assert "not run" in adversarial.main("G4", out_dir=str(tmp_path))


def test_block_g_sweeps_only_write_to_their_own_folder(tmp_path, monkeypatch):
    import adversarial
    monkeypatch.setattr(adversarial, "HARDENING", str(tmp_path / "hardening"))
    assert "not run" in adversarial.main("G3b") and "not run" in adversarial.main("G4")
    assert json.loads((tmp_path / "hardening" / "PREREGISTERED_RULES.json").read_text()) == adversarial.PREREGISTERED
    assert sorted(p.name for p in (tmp_path / "hardening").iterdir()) == ["PREREGISTERED_RULES.json"]
