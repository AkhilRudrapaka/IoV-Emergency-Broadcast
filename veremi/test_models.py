"""Block C pipeline (veremi/models.py): pooled rows, rule baseline, threshold choice, metrics, and the Train/Validation
-> frozen selection -> single Test evaluation protocol, on a small synthetic processed dataset."""
import json

import numpy as np
import pytest

import veremi.models as M
from veremi.features import NAMES

DIAG = "y_diag_documented_rule"


def test_pooled_rows_drop_only_flagged_honest_messages():
    d = {"y": np.array([0, 0, 1, 1, 0]), "dup_of_earlier_primary_archive": np.array([True, False, True, False, False])}
    assert M.pooled_mask(d).tolist() == [False, True, True, True, True]   # the flagged attack row is kept


def test_rule_baseline_thresholds_come_from_genuine_train_rows_and_nan_is_never_flagged():
    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, (2000, len(NAMES))).astype(np.float32)
    y = np.zeros(2000, int)
    y[:100] = 1
    X[:100, NAMES.index("pos_pred_error_m")] = 1e6                      # attack rows far outside the genuine range
    rb = M.RuleBaseline(0.99).fit(X, y)
    rule = next(r for r in rb.rules if r["feature"] == "pos_pred_error_m")
    assert rule["threshold"] == pytest.approx(np.quantile(X[100:, NAMES.index("pos_pred_error_m")], 0.99))
    s = rb.score(X)
    assert (s[:100] > 0).all() and (s[100:] > 0).mean() < 0.15
    nan_row = np.full((1, len(NAMES)), np.nan, dtype=np.float32)
    assert rb.score(nan_row)[0] < M.RuleBaseline.THRESHOLD and np.isfinite(rb.score(nan_row)[0])


def test_threshold_choice_respects_the_fpr_constraint_and_maximizes_f1():
    y = np.array([1, 1, 1, 0, 1, 0, 0, 0, 0, 0])
    s = np.array([.9, .8, .7, .65, .6, .5, .4, .3, .2, .1])
    thr, info = M.choose_threshold(y, s, max_fpr=0.0)
    assert thr == .7 and info == {"feasible": True, "fpr": 0.0, "f1": pytest.approx(6 / 7)}
    thr, info = M.choose_threshold(y, s, max_fpr=0.2)                   # one false positive allowed
    assert thr == .6 and info["fpr"] == pytest.approx(1 / 6) and info["f1"] == pytest.approx(8 / 9)
    thr, info = M.choose_threshold(np.array([0, 1]), np.array([.9, .1]), max_fpr=0.0)   # constraint unreachable
    assert not info["feasible"] and thr == .9 and info["fpr"] == 1.0                    # -> lowest-FPR threshold


def test_metrics_confusion_counts_and_rates():
    m = M.metrics(np.array([1, 1, 0, 0, 0]), np.array([.9, .2, .8, .1, .1]), 0.5)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 1, 1, 2)
    assert m["precision"] == .5 and m["recall"] == .5 and m["fpr"] == pytest.approx(1 / 3)


def test_only_the_24_schema_features_are_model_inputs():
    d = {"X": np.zeros((3, len(NAMES)), np.float32), "feature_names": np.array(NAMES), "attack": np.array(["a"] * 3)}
    assert M.features_only(d).shape == (3, 24)
    with pytest.raises(ValueError):
        M.features_only({"X": np.zeros((3, 25), np.float32), "feature_names": np.array(NAMES + ["attack"])})


def _write_synthetic(root, rng):
    """Two primary archives and the eval-only archive, three splits, separable attack rows."""
    for track, attacks in (("primary", ["constantPositionOffset", "suddenStop"]), ("eval_only", ["suddenConstantSpeed"])):
        (root / track).mkdir(parents=True)
        for attack in attacks:
            for split in ("Train", "Validation", "Test"):
                n = 400
                X = rng.normal(0, 1, (n, len(NAMES))).astype(np.float32)
                y = (rng.random(n) < 0.3).astype(np.int8)
                X[y == 1, NAMES.index("pos_pred_error_m")] += 6
                arrays = {"X": X, "y": y, "attack": np.full(n, attack),
                          "dup_of_earlier_primary_archive": (rng.random(n) < 0.2) & (y == 0)}
                if track == "eval_only":
                    arrays[DIAG] = y.copy()
                np.savez_compressed(root / track / f"{attack}__{split}.npz", feature_names=np.array(NAMES),
                                    track=np.array(track), split=np.array(split), **arrays)
    (root / "preprocess_summary.json").write_text(json.dumps({"status": "OK", "feature_names": NAMES}))


def test_selection_never_loads_test_and_test_is_evaluated_once(tmp_path, monkeypatch):
    processed, out = tmp_path / "processed", tmp_path / "processed" / "models" / "block_c"
    _write_synthetic(processed, np.random.default_rng(1))
    calls, real_load = [], M.load
    monkeypatch.setattr(M, "load", lambda p, split, **kw: calls.append(split) or real_load(p, split, **kw))
    grid = {"decision_tree": [{"max_depth": 4}], "random_forest": [{"n_estimators": 5, "max_depth": 4}],
            "hist_gradient_boosting": [{"max_iter": 10}]}
    sel = M.select(processed, out, grid=grid, q_grid=(0.99,))
    assert "Test" not in calls and sorted(set(calls)) == ["Train", "Validation"]
    assert sel["frozen"] and (out / "final_model.joblib").exists() and (out / "MODEL_COMPARISON_REPORT.md").exists()
    assert {c["family"] for c in sel["candidates"]} == set(grid) and sel["final"]["validation_pooled"]["f1"] > 0.8
    assert set(sel["final"]["validation_per_attack"]) == {"constantPositionOffset", "suddenStop"}   # never the eval track
    res = M.evaluate_test(processed, out)
    assert "Test" in calls and res["final_model"]["pooled"]["n"] == res["test_rows"]["pooled_rows"]
    assert set(res["eval_only_suddenConstantSpeed"]["final_model"]) == {"official_label", "diagnostic_label"}
    with pytest.raises(SystemExit, match="once"):
        M.evaluate_test(processed, out)
    (processed / "preprocess_summary.json").write_text(json.dumps({"status": "OK", "feature_names": NAMES, "x": 1}))
    with pytest.raises(SystemExit, match="changed"):
        M.evaluate_test(processed, out, force=True)
