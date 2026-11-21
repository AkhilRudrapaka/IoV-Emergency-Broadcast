"""Block D: the Block C detector as a shadow-mode trust signal (ml_trust.py) never changes an existing decision."""
import gzip
import hashlib
import json
import math
from pathlib import Path

import joblib
import numpy as np
import pytest
from sklearn.tree import DecisionTreeClassifier

import config
import corroboration
import experiment
import ml_trust
import scenario
from clustering import beta_trust
from veremi.features import NAMES

ROOT = Path(__file__).resolve().parent.parent
REAL_MODEL = (ROOT / config.ML_MODEL_DIR).resolve()


def _tiny_model_dir(tmp_path, features=NAMES, md5=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, (200, len(NAMES)))
    y = (X[:, NAMES.index("pos_pred_error_m")] > 1).astype(int)
    joblib.dump(DecisionTreeClassifier(max_depth=3, random_state=0).fit(X, y), tmp_path / "final_model.joblib")
    real = hashlib.md5((tmp_path / "final_model.joblib").read_bytes()).hexdigest()
    (tmp_path / "selection.json").write_text(json.dumps({"frozen": True, "features": list(features), "final": {
        "family": "decision_tree", "file": "final_model.joblib", "md5": md5 or real, "threshold": 0.5}}))
    return tmp_path


def _row(**override):
    row = dict.fromkeys(NAMES, 0.0)
    row.update(override)
    return [row[n] for n in NAMES]


def test_missing_or_tampered_artifacts_leave_the_detector_unavailable_and_never_flag(tmp_path):
    for det in (ml_trust.Detector(tmp_path / "nowhere"),
                ml_trust.Detector(_tiny_model_dir(tmp_path / "a", md5="0" * 32)),
                ml_trust.Detector(_tiny_model_dir(tmp_path / "b", features=list(reversed(NAMES))))):
        assert det.status == "unavailable" and det.reason
        res = det.score(np.array([_row(pos_pred_error_m=50.0)]))
        assert res["status"].tolist() == ["model_unavailable"] and not res["flag"].any() and math.isnan(res["score"][0])


def test_feature_width_type_and_missing_values_are_validated(tmp_path):
    det = ml_trust.Detector(_tiny_model_dir(tmp_path))
    assert det.status == "ready" and det.version.startswith("decision_tree:")
    assert det.score(np.zeros((2, 23)))["status"].tolist() == ["invalid_features"] * 2          # wrong width
    rows = np.array([_row(), _row(spd=math.nan), _row(dt_send_s=math.nan), _row(acl=math.inf)])
    assert det.score(rows)["status"].tolist() == ["ok", "invalid_features", "ok", "invalid_features"]
    res = det.score(np.array([_row(pos_pred_error_m=50.0), _row()]))                             # schema order is used
    assert res["flag"].tolist() == [True, False] and res["score"][0] > res["score"][1]


def test_inference_errors_are_reported_and_never_treated_as_malicious(tmp_path, monkeypatch):
    det = ml_trust.Detector(_tiny_model_dir(tmp_path))
    monkeypatch.setattr(det._model, "predict_proba", lambda X: (_ for _ in ()).throw(RuntimeError("boom")))
    res = det.score(np.array([_row(pos_pred_error_m=50.0)]))
    assert res["status"].tolist() == ["inference_error"] and not res["flag"].any()


@pytest.mark.skipif(not (REAL_MODEL / "selection.json").exists(), reason="Block C artifact not present")
def test_the_exact_block_c_artifact_loads_read_only():
    sel = json.loads((REAL_MODEL / "selection.json").read_text(encoding="utf-8"))
    before = hashlib.md5((REAL_MODEL / "final_model.joblib").read_bytes()).hexdigest()
    det = ml_trust.Detector(REAL_MODEL)
    res = det.score(np.array([_row(spd=20.0, has_prev=1.0, n_prev=5.0, rate_1s=1.0, dt_send_s=1.0, dpos_m=20.0,
                                   implied_speed=20.0, delay_ms=1.44)]))
    assert det.status == "ready" and det.threshold == sel["final"]["threshold"] and res["status"].tolist() == ["ok"]
    assert hashlib.md5((REAL_MODEL / "final_model.joblib").read_bytes()).hexdigest() == before == sel["final"]["md5"]


def test_ml_flags_lower_the_what_if_trust_gradually_and_boundedly():
    assert ml_trust.whatif_trust(66, 8, 0) == beta_trust(66, 8)                     # no flag: the existing Beta trust
    one = ml_trust.whatif_trust(66, 8, 1)
    assert beta_trust(66, 8) - one < 0.003                                          # one suspicious CAM barely matters
    series = [ml_trust.whatif_trust(66, 8, k) for k in range(0, 60, 5)]
    assert all(a > b for a, b in zip(series, series[1:9])) and series[-1] == series[-2] == ml_trust.whatif_trust(66, 8, 40)
    assert ml_trust.whatif_trust(66, 8, 10_000) >= config.TRUST_CH_THRESHOLD        # cap: ML alone cannot drop it below the gate


def test_each_transmitted_cam_is_one_observation_however_many_vehicles_receive_it():
    class Counting:
        status, reason, version, threshold = "ready", None, "stub", 0.5

        def score(self, X):
            return {"score": np.full(len(X), 0.9), "flag": np.ones(len(X), bool), "status": np.full(len(X), "ok", dtype=object)}

    obs = ml_trust.CamObserver(Counting())
    ids = ["v0", "v1", "v2", "v3"]
    for t in range(4):
        xy = np.array([[0, 10.0 * t], [5, 10.0 * t], [10, 10.0 * t], [5000, 0]])   # v3 is out of everybody's range
        d = np.hypot(xy[:, 0, None] - xy[None, :, 0], xy[:, 1, None] - xy[None, :, 1])
        obs.observe(float(t), ids, xy, np.full(4, 10.0), np.zeros(4), (d <= config.COMM_RANGE_M).sum(1) > 1, d)
    res = obs.result(ids, {}, {})
    assert [e["cams"] for e in res["evidence"]] == [4, 4, 4, 0]          # v0..v2 each heard by 2 vehicles: still 4 CAMs
    assert res["trust_whatif"][3] == beta_trust(0, 0)


def test_signature_checks_never_consult_ml():
    alert = scenario.create_alert(1, "v1", (0.0, 0.0), 100)
    cert = corroboration.certificate(alert, "v1", ["v2", "v3", "v4"])
    trust, whatif = {v: 0.9 for v in ("v2", "v3", "v4")}, {v: ml_trust.whatif_trust(66, 8, 40) for v in ("v2", "v3", "v4")}
    assert corroboration.accept(alert, cert, trust.get)[0] and corroboration.accept(alert, cert, whatif.get)[0]
    forged = dict(cert, aggregate=corroboration.certificate(alert, "v1", ["v2", "v3", "v5"])["aggregate"])
    assert not corroboration.accept(alert, forged, trust.get)[0] and not corroboration.accept(alert, forged, whatif.get)[0]
    for module in ("corroboration.py", "protocols.py", "rsu.py", "channel.py", "clustering.py", "infrastructure.py"):
        assert "ml_trust" not in (ROOT / module).read_text(encoding="utf-8")


def test_enforcement_is_refused_and_unknown_modes_are_rejected(monkeypatch):
    monkeypatch.setattr(scenario, "ML_TRUST_MODE", "enforce")
    with pytest.raises(NotImplementedError):
        scenario.build(50, 1)
    with pytest.raises(ValueError):
        ml_trust.checked_mode("aggressive")
    assert config.ML_TRUST_MODE == "off"                                   # the shipped default


def _run(monkeypatch, tmp_path, mode):
    out = tmp_path / mode
    monkeypatch.setattr(scenario, "ML_TRUST_MODE", mode)
    monkeypatch.setattr(experiment, "RAW", str(out))
    monkeypatch.setattr(config, "RESULTS_DIR", str(out))
    rows, forged = experiment.run_one(50, 3)
    with gzip.open(out / "d50_r03.json.gz", "rt") as f:
        raw = json.load(f)
    return json.dumps(rows, sort_keys=True), json.dumps(forged, sort_keys=True), raw


def test_shadow_mode_changes_no_decision_and_off_mode_writes_nothing_new(tmp_path, monkeypatch):
    rows_off, forged_off, raw_off = _run(monkeypatch, tmp_path, "off")
    rows_sh, forged_sh, raw_sh = _run(monkeypatch, tmp_path, "shadow")
    assert "ml_shadow" not in raw_off and raw_sh["ml_shadow"]["decisions_changed"] is False
    assert rows_off == rows_sh and forged_off == forged_sh                  # every metric of every scheme, and the forgery test
    for key in ("scenario", "protocols", "forgery"):                         # trust, roles, votes, certificates, RSU outcomes
        assert json.dumps(raw_off[key], sort_keys=True) == json.dumps(raw_sh[key], sort_keys=True)
    assert raw_off["infrastructure"]["route"] == raw_sh["infrastructure"]["route"]
    genuine = raw_sh["protocols"]["proposed"]["corroboration"]
    assert genuine["accepted"] == raw_off["protocols"]["proposed"]["corroboration"]["accepted"]   # alert not suppressed
    log = raw_sh["ml_shadow"]
    assert log["cams"]["cams"] == log["cams"]["scored"] + log["cams"]["invalid"] + log["cams"]["errors"]
    assert len(log["vehicles"]) == len(raw_sh["scenario"]["vehicles"])
