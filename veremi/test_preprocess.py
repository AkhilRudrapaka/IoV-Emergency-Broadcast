"""Key processing, label-rule and track behaviour of veremi/preprocess.py and veremi/features.py, on small synthetic
files. The last test checks the real processed dataset (approved tracks) and is skipped when it has not been built."""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from veremi.features import NAMES, ReceiverStreams, feature_schema
from veremi.preprocess import (DIAG, EVAL_ONLY, POLICY, PRIMARY, diagnostic_label, documented_label, load,
                               load_ground_truth, parse_record, policy_problems, process_split)

DATA = Path(__file__).resolve().parents[3] / "data/veremi_nextgen/InTAS_highway_2"   # <repo>/../../data, as config.py
ROOT = Path(__file__).resolve().parent.parent
V2 = DATA / "processed" / "v2"


def msg(sid, mid, t_s, x, y, spd=10.0, hed=0.0, acl=0.0, attacker=0, alias=None, rx=(0.0, 0.0), delay_ms=2.0):
    """One received CAM in the dataset's attack-archive schema (times in ns, position as an 'x,y,z' string)."""
    side = lambda px, py, s, h: {"pos": f"{px},{py},0.0", "pos_noise": "0.1,0.1,0.0", "spd": s, "spd_noise": 0.0,
                                 "acl": acl, "acl_noise": 0.0, "hed": h, "hed_noise": 0.0, "driversProfile": "NORMAL"}
    snd = int(t_s * 1e9)
    return {"rcvTime": snd + int(delay_ms * 1e6), "sendTime": snd, "sender_id": f"veh_{sid}",
            "sender_alias": alias if alias is not None else 1000 + sid, "messageID": mid, "attacker": attacker,
            "receiver": side(rx[0], rx[1], 12.0, 0.0), "sender": {**side(x, y, spd, hed), "distance_to_road_edge": 1.0}}


def gt_entry(x, y, spd=10.0, acl=0.0, hed=0.0, t_s=0.0, prev=None):
    return ((float(x), float(y)), spd, acl, hed, int(t_s * 1e9), prev)


def parsed(m):
    return parse_record(m, labelled=True)


def write_split(folder, receivers):
    for rid, msgs in receivers.items():
        p = folder / "inner" / f"veh_{rid}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(msgs))
    return folder


def test_label_is_the_messages_own_attacker_field_unchanged(tmp_path):
    msgs = [msg(7, i, i, 0, 10 * i, attacker=a) for i, a in enumerate([1, 0, 1])] + [msg(8, 9, 0.5, 5, 5)]
    arr, st, _ = process_split(write_split(tmp_path, {1: msgs}), labelled=True)
    assert arr["y"][np.argsort(arr["rcvTime"])].tolist() == [1, 0, 0, 1]
    assert (st["label_0"], st["label_1"]) == (2, 2)


def test_string_typed_baseline_records_parse_and_bad_records_are_rejected_with_a_reason(tmp_path):
    m = msg(3, 1, 0, 1.5, 2.5)
    strings = {k: (str(v) if not isinstance(v, dict) else {kk: str(vv) for kk, vv in v.items()}) for k, v in m.items()}
    del strings["attacker"]
    r = parse_record(strings, labelled=False)
    assert r["sender_pos"] == (1.5, 2.5) and r["sender_spd"] == 10.0 and r["snd"] == 0 and "y" not in r
    bad_pos, no_label, no_field = msg(3, 1, 0, 0, 0), msg(3, 2, 1, 0, 0), msg(3, 3, 2, 0, 0)
    bad_pos["sender"]["pos"] = "1.0,2.0"
    no_label["attacker"] = 2
    del no_field["receiver"]["spd"]
    _, st, _ = process_split(write_split(tmp_path, {1: [bad_pos, no_label, no_field, msg(3, 4, 3, 0, 0)]}), labelled=True)
    assert st["rows"] == 1 and st["rejected"] == {"malformed sender.pos": 1, "attacker label missing or not 0/1": 1,
                                                  "missing receiver.spd": 1}


def test_both_ground_truth_schemas_and_the_previous_position_of_each_sender(tmp_path):
    v1 = {"pos": "1.0,2.0,0.0", "spd": "3.0", "acl": "0.5", "hed": "90.0"}
    v2 = {"pos": "4.0,6.0,0.0", "spd": "3.0", "acl": "0.5", "hed": "90.0"}
    nested = [{"sender_id": "veh_5", "messageID": "12", "sendTime": "2000", "receiver": v2, "sender": v2},
              {"sender_id": "veh_5", "messageID": "11", "sendTime": "1000", "receiver": v1, "sender": v1}]
    flat = [{"sender_id": "veh_5", "messageID": "12", "sendTime": "2000", **v2},
            {"sender_id": "veh_5", "messageID": "11", "sendTime": "1000", **v1}]
    (tmp_path / "n.json").write_text(json.dumps(nested))
    (tmp_path / "f.json").write_text(json.dumps(flat))
    want = {(5, 11): ((1.0, 2.0), 3.0, 0.5, 90.0, 1000, None), (5, 12): ((4.0, 6.0), 3.0, 0.5, 90.0, 2000, (1.0, 2.0))}
    assert load_ground_truth(tmp_path / "n.json") == load_ground_truth(tmp_path / "f.json") == want
    (tmp_path / "d.json").write_text(json.dumps(flat + flat[:1]))
    with pytest.raises(ValueError):
        load_ground_truth(tmp_path / "d.json")


def test_documented_label_rules_of_the_conditional_attacks():
    g = gt_entry(0, 0, spd=10.0, acl=0.2)
    assert documented_label("always", parsed(msg(1, 1, 0, 0, 0, acl=0.2)), g) == 0          # unmodified -> genuine
    assert documented_label("always", parsed(msg(1, 1, 0, 50, 0, acl=0.2)), g) == 1
    assert documented_label("feignedBraking", parsed(msg(1, 1, 0, 0, 0, acl=-0.6)), g) == 0  # acl 0.2 <= 0.25
    assert documented_label("feignedBraking", parsed(msg(1, 1, 0, 0, 0, acl=-0.9)), gt_entry(0, 0, acl=0.3)) == 1
    assert documented_label("accelerationMultiplication", parsed(msg(1, 1, 0, 0, 0, acl=1.2)), gt_entry(0, 0, acl=0.4)) == 0
    moving = gt_entry(0, 10, spd=10.0, prev=(0.0, 0.0))
    assert documented_label("moving", parsed(msg(1, 1, 0, 0, 10, spd=0.0)), moving) == 1
    assert documented_label("moving", parsed(msg(1, 1, 0, 0, 10, spd=0.0)), gt_entry(0, 10, spd=0.5, prev=(0, 0))) == 0
    assert documented_label("moving", parsed(msg(1, 1, 0, 0, 10, spd=0.0)), gt_entry(0, 10, spd=9, prev=(0, 9.5))) == 0
    assert documented_label("dos", parsed(msg(1, 1, 0, 0, 0)), None) == 1                      # injected copy
    assert documented_label("dos", parsed(msg(1, 1, 0, 0, 0)), gt_entry(0, 0)) is None         # identity unknown
    with pytest.raises(ValueError):
        documented_label("always", parsed(msg(1, 1, 0, 0, 0)), None)


def test_sudden_stop_rule_distinguishes_the_stop_message_from_frozen_copies():
    trigger = parsed(msg(1, 1, 0, 0, 0, spd=0.0, acl=0.0))
    assert documented_label("suddenStop", trigger, gt_entry(0, 0, spd=10.0, acl=0.5)) == 1
    assert documented_label("suddenStop", trigger, gt_entry(0, 0, spd=10.0, acl=-1.0)) == 0  # was already braking
    frozen = parsed(msg(1, 2, 1, 0, 0, spd=0.0, acl=0.0))                                    # reports the old position
    assert documented_label("suddenStop", frozen, gt_entry(0, 30, spd=0.5)) == 1             # 30 m away
    assert documented_label("suddenStop", frozen, gt_entry(0, 5, spd=0.5)) == 0              # slow and near the stop


def test_sudden_constant_speed_official_rule_is_one_sided_and_the_diagnostic_label_follows_the_documentation():
    frozen_high = parsed(msg(1, 1, 0, 0, 0, spd=20.0))                     # frozen 20 m/s, actual 10 m/s
    frozen_low = parsed(msg(1, 2, 0, 0, 0, spd=5.0))                       # frozen 5 m/s, actual 10 m/s
    g = gt_entry(0, 0, spd=10.0)
    assert documented_label("suddenConstantSpeed", frozen_high, g) == 0 and diagnostic_label(frozen_high, g) == 1
    assert documented_label("suddenConstantSpeed", frozen_low, g) == 1 and diagnostic_label(frozen_low, g) == 1
    unmodified = parsed(msg(1, 3, 0, 0, 0, spd=10.0))
    assert documented_label("suddenConstantSpeed", unmodified, g) == 0 and diagnostic_label(unmodified, g) == 0


def test_policy_tolerates_only_the_documented_generator_defects(tmp_path):
    good, attacked = msg(1, 1, 0, 0, 0), msg(1, 2, 1, 50, 0, attacker=1)
    gt = {(1, 1): gt_entry(0, 0), (1, 2): gt_entry(0, 10, t_s=1)}
    _, st, _ = process_split(write_split(tmp_path / "a", {1: [good, attacked]}), labelled=True, gt=gt, rule="always")
    assert st["rule_check"] == {"modified": 1, "match": 2} and policy_problems("constantPositionOffset", {"Train": st}) == []
    wrong = msg(1, 2, 1, 50, 0, attacker=0)                                # modified content labelled genuine
    _, st, _ = process_split(write_split(tmp_path / "b", {1: [good, wrong]}), labelled=True, gt=gt, rule="always")
    assert "miss the documented label rule" in policy_problems("constantPositionOffset", {"Train": st})[0]
    split_label = {1: [msg(1, 1, 0, 0, 0)], 2: [msg(1, 1, 0, 0, 0, attacker=1)]}   # one broadcast, two labels
    _, st, _ = process_split(write_split(tmp_path / "c", split_label), labelled=True)
    assert any("label differs" in p for p in policy_problems("constantPositionOffset", {"Train": st}))
    assert not any("label differs" in p for p in policy_problems("zeroSpeedReport", {"Train": st}))
    # zeroSpeedReport tolerates 0.1 % rule misses over the whole archive, and only official 0 where the rule says 1
    ok = {"Train": {"rule_check": {"modified": 1000, "mismatch": 1, "mismatch_official0_rule1": 1}, "duplicates": {}}}
    assert policy_problems("zeroSpeedReport", ok) == []
    wrong_way = {"Train": {"rule_check": {"modified": 1000, "mismatch": 1, "mismatch_official1_rule0": 1}, "duplicates": {}}}
    assert "direction" in policy_problems("zeroSpeedReport", wrong_way)[0]
    too_many = {"Train": {"rule_check": {"modified": 1000, "mismatch": 2, "mismatch_official0_rule1": 2}, "duplicates": {}}}
    assert "allowed 1" in policy_problems("zeroSpeedReport", too_many)[0]


def test_features_are_causal_and_history_is_per_receiver_and_pseudonym():
    feed = lambda s, m: s.row(m["sender_alias"], m["rcvTime"], m["sendTime"], tuple(map(float, m["sender"]["pos"].split(",")[:2])),
                              m["sender"]["spd"], m["sender"]["acl"], m["sender"]["hed"], (0.0, 0.0), 12.0, 0.0)
    stream = [msg(1, i, i, 0, 10 * i) for i in range(6)]
    s1, s2 = ReceiverStreams(), ReceiverStreams()
    base = [feed(s1, m) for m in stream]
    altered = [feed(s2, m) for m in stream[:3] + [msg(1, 99, 3, 500, 500)]]
    assert np.array_equal(np.array(base[:3]), np.array(altered[:3]), equal_nan=True)
    assert feed(ReceiverStreams(), stream[1])[NAMES.index("has_prev")] == 0.0
    s3 = ReceiverStreams()
    feed(s3, stream[0])
    assert feed(s3, msg(2, 50, 1, 0, 10))[NAMES.index("has_prev")] == 0.0


def test_kinematic_consistency_features_on_a_straight_northbound_track():
    s = ReceiverStreams()
    row = lambda m: dict(zip(NAMES, s.row(m["sender_alias"], m["rcvTime"], m["sendTime"],
                                          tuple(map(float, m["sender"]["pos"].split(",")[:2])), m["sender"]["spd"],
                                          m["sender"]["acl"], m["sender"]["hed"], (0.0, 0.0), 12.0, 0.0)))
    first = row(msg(1, 1, 0, 0, 0))
    assert first["has_prev"] == 0 and all(math.isnan(first[k]) for k in ("dt_send_s", "speed_residual", "pos_pred_error_m"))
    ok = row(msg(1, 2, 1, 0, 10))
    assert ok["speed_residual"] == pytest.approx(0) and ok["bearing_residual_deg"] == pytest.approx(0)
    assert ok["pos_pred_error_m"] == pytest.approx(0) and ok["dt_send_s"] == pytest.approx(1)
    jump = row(msg(1, 3, 2, 50, 20))
    assert jump["pos_pred_error_m"] == pytest.approx(50) and jump["bearing_residual_deg"] > 70
    assert row(msg(1, 4, 2.01, 50, 20))["rate_1s"] == 1


def test_one_canonical_row_per_transmission_and_cross_archive_duplicates_are_flagged_not_removed(tmp_path):
    tx = msg(4, 1, 0, 0, 0)
    late = dict(tx, rcvTime=tx["rcvTime"] + 5_000_000)
    flood = msg(4, 1, 0.2, 0, 0, attacker=1)
    seen = {}
    arr, st, _ = process_split(write_split(tmp_path / "a", {1: [tx, flood], 2: [late]}), labelled=True, seen_obs=seen)
    assert st["transmitted_messages"] == 2 and st["canonical_rows"] == 2 and not arr["dup_of_earlier_primary_archive"].any()
    other = msg(4, 1, 0.2, 0, 0, attacker=0)                    # same reception key, different label: not a duplicate
    arr2, st2, _ = process_split(write_split(tmp_path / "b", {1: [tx, other], 2: [late]}), labelled=True, seen_obs=seen)
    flags = dict(zip(zip(arr2["receiver"].tolist(), arr2["sendTime"].tolist()), arr2["dup_of_earlier_primary_archive"]))
    assert st2["rows"] == 3 and st2["dup_of_earlier_primary_archive"] == 2 and not flags[(1, int(0.2e9))]


def test_tracks_hold_the_approved_archives_and_load_separates_them(tmp_path):
    assert len(PRIMARY) == 14 and "suddenConstantSpeed" not in PRIMARY and EVAL_ONLY == ["suddenConstantSpeed"]
    assert {"zeroSpeedReport", "reversedHeading", "suddenStop", "suddenConstantSpeed"} == \
        {a for a, p in POLICY.items() if p.get("report_separately")}
    m = msg(1, 1, 0, 0, 0)
    arr, _, _ = process_split(write_split(tmp_path / "raw", {1: [m]}), labelled=True)
    for track, attack in (("primary", "constantPositionOffset"), ("eval_only", "suddenConstantSpeed")):
        (tmp_path / "out" / track).mkdir(parents=True)
        np.savez_compressed(tmp_path / "out" / track / f"{attack}__Train.npz", feature_names=np.array(NAMES),
                            track=np.array(track), split=np.array("Train"), attack=np.array([attack]), **arr)
    assert set(load(tmp_path / "out", "Train")["attack"]) == {"constantPositionOffset"}
    assert set(load(tmp_path / "out", "Train", track="eval_only")["attack"]) == {"suddenConstantSpeed"}
    with pytest.raises(ValueError):
        load(tmp_path / "out", "Train", track="unlabelled_baseline")


def test_no_label_identity_ground_truth_or_absolute_field_is_a_feature():
    forbidden = ("attacker", "label", "diag", "sender_id", "alias", "messageid", "receiver_id", "rcvtime", "sendtime",
                 "pos_x", "pos_y", "road_edge", "noise", "profile", "ground", "truth")
    assert not [n for n in NAMES if any(f in n.lower() for f in forbidden)]
    schema = feature_schema()
    assert schema["version"] == 2 and [f["name"] for f in schema["features"]] == NAMES
    assert all(f["available_at_inference"] for f in schema["features"]) and "none" in schema["fitted_transforms"]


@pytest.mark.skipif(not (V2 / "preprocess_summary.json").exists(),
                    reason=f"missing dataset: processed v2 data not found at {V2} (<repo>/../../data/veremi_nextgen/"
                           "InTAS_highway_2/processed/v2; build it with veremi/preprocess.py)")
def test_processed_dataset_is_verified_with_the_approved_tracks():
    summary = json.loads((V2 / "preprocess_summary.json").read_text(encoding="utf-8"))
    acquired = json.loads((ROOT / "DATASET_MANIFEST_InTAS_highway_2.json").read_text(encoding="utf-8"))["inspection"]
    tracks = json.loads((ROOT / "DATASET_TRACKS_MANIFEST.json").read_text(encoding="utf-8"))
    assert summary["status"] == tracks["status"] == "OK" and not summary["failures"]
    assert summary["feature_names"] == NAMES and tracks["tracks"]["primary"]["archives"] == PRIMARY
    assert tracks["tracks"]["eval_only"]["archives"] == ["suddenConstantSpeed"]
    assert not any(v["tx"] or v["message"] for v in summary["cross_split_overlap"].values())
    for archive, info in summary["archives"].items():
        for split in ("Train", "Validation", "Test"):
            st, ref = info[split], acquired[archive][split]
            assert st["rows"] == ref["records"] and not st["rejected"]                 # nothing deleted
            if archive != "baseline (no attack)":
                assert (st["label_0"], st["label_1"]) == (ref["label_0"], ref["label_1"])   # labels unchanged
            with np.load(V2 / st["file"]) as z:
                assert z["X"].shape == (st["rows"], len(NAMES)) and str(z["track"]) == info["track"]
                assert ("y" in z.files) == (archive != "baseline (no attack)") and (DIAG in z.files) == (info["track"] == "eval_only")
    test = load(V2, "Test")
    assert set(test["attack"]) == set(PRIMARY) and DIAG not in test
