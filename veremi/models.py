"""Block C: first ML detector for malicious CAMs (VeReMi NextGen InTAS_highway_2, approved primary track only).

    python -I veremi/models.py select --processed <dataset>/processed/v2 --out <dataset>/processed/v2/models/block_c
    python -I veremi/models.py test   --processed <dataset>/processed/v2 --out <dataset>/processed/v2/models/block_c

select  fits every candidate on Train only, compares and tunes on Validation only, and freezes the final model and its
        threshold in selection.json. It never loads the Test split.
test    evaluates the frozen choice on Test once (it refuses to run a second time) and, separately, on the
        eval-only suddenConstantSpeed track. Nothing it computes feeds back into a decision.

Inputs are only the 24 receiver-observable features (X); attack, archive, identities, labels, the diagnostic label and
the provenance flags are never model inputs. Pooled training and pooled evaluation drop the rows flagged
dup_of_earlier_primary_archive that are honest (every flagged row in this dataset is honest); per-attack evaluation
keeps every row of its archive. The official label y is never changed.
"""
import argparse
import hashlib
import json
import math
import os
import pickle
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import NAMES  # noqa: E402
from preprocess import DIAG, load, peak_rss_mb  # noqa: E402

SEED = 20261118
MAX_VAL_FPR = 0.01            # operating constraint on genuine messages, chosen before seeing any result
CAVEAT_ATTACKS = ("reversedHeading", "zeroSpeedReport", "suddenStop")
Q_GRID = (0.99, 0.995, 0.999, 0.9995, 0.9999)
GRID = {
    "decision_tree": [{"max_depth": d, "min_samples_leaf": leaf, "class_weight": cw}
                      for d in (8, 16, None) for leaf in (1, 20) for cw in (None, "balanced")],
    "random_forest": [{"n_estimators": 100, "max_features": "sqrt", "max_depth": d, "min_samples_leaf": leaf,
                       "class_weight": cw} for d in (None, 20) for leaf in (1, 5) for cw in (None, "balanced_subsample")],
    "hist_gradient_boosting": [{"max_iter": 300, "learning_rate": lr, "max_leaf_nodes": m, "class_weight": cw,
                                "early_stopping": False} for lr in (0.1, 0.05) for m in (31, 63) for cw in (None, "balanced")],
}
SELECTION_CRITERION = (f"highest pooled-Validation F1 at the threshold chosen on Validation with FPR <= {MAX_VAL_FPR}; "
                       "ties: higher pooled-Validation PR-AUC, then smaller serialized model")
# Plausibility checks of the rule baseline (VeReMi-style): one threshold per check, fitted on genuine Train rows.
RULES = [("spd", "upper", None), ("acl", "upper", "abs"), ("speed_residual", "upper", None),
         ("acl_residual", "upper", None), ("pos_pred_error_m", "upper", None), ("bearing_residual_deg", "upper", None),
         ("yaw_rate_dps", "upper", None), ("rate_1s", "upper", None), ("dist_tx_rx_m", "upper", None),
         ("dt_send_s", "lower", None)]


def pooled_mask(d):
    """Rows used for pooled training/evaluation: everything except repeated honest messages."""
    return ~(d["dup_of_earlier_primary_archive"] & (d["y"] == 0))


def features_only(d):
    """The model input: exactly the 24 approved features, in schema order."""
    if list(d["feature_names"]) != NAMES or d["X"].shape[1] != len(NAMES):
        raise ValueError("feature columns do not match the approved schema")
    return d["X"]


class RuleBaseline:
    """Flags a message when any plausibility check exceeds the q-quantile (or falls below the (1-q)-quantile) of that
    check on genuine Train messages. score = largest standardized exceedance; flagged iff score > 0. NaN = not checked."""

    def __init__(self, q):
        self.q, self.rules = q, []

    def fit(self, X, y):
        genuine = X[y == 0]
        self.rules = []
        for name, side, transform in RULES:
            v = genuine[:, NAMES.index(name)].astype(np.float64)
            v = np.abs(v) if transform == "abs" else v
            v = v[~np.isnan(v)]
            t = float(np.quantile(v, self.q if side == "upper" else 1 - self.q))
            iqr = float(np.subtract(*np.quantile(v, [0.75, 0.25])))
            self.rules.append({"feature": name, "side": side, "transform": transform, "threshold": t,
                               "scale": iqr if iqr > 0 else max(abs(t), 1.0)})
        return self

    def score(self, X):
        s = np.full(len(X), -1e9)
        for r in self.rules:
            v = X[:, NAMES.index(r["feature"])].astype(np.float64)
            v = np.abs(v) if r["transform"] == "abs" else v
            z = (v - r["threshold"]) / r["scale"] if r["side"] == "upper" else (r["threshold"] - v) / r["scale"]
            s = np.fmax(s, np.where(np.isnan(z), -1e9, z))
        return s

    THRESHOLD = float(np.nextafter(0.0, 1.0))                   # score >= this  <=>  some check exceeded


def choose_threshold(y, score, max_fpr):
    """Threshold with the highest F1 among those with FPR <= max_fpr (ties: the higher threshold).
    If no threshold meets the constraint, the one with the lowest FPR. Predict attack iff score >= threshold."""
    y, s = np.asarray(y).astype(bool), np.asarray(score, dtype=np.float64)
    order = np.argsort(-s, kind="stable")
    s_sorted, y_sorted = s[order], y[order]
    last = np.r_[s_sorted[1:] != s_sorted[:-1], True]           # last row of each distinct score value
    tp, fp, thr = np.cumsum(y_sorted)[last], np.cumsum(~y_sorted)[last], s_sorted[last]
    pos, neg = int(y.sum()), int((~y).sum())
    fpr = fp / max(neg, 1)
    f1 = 2 * tp / np.maximum(2 * tp + fp + (pos - tp), 1)
    ok = fpr <= max_fpr
    i = int(np.flatnonzero(ok)[np.argmax(f1[ok])]) if ok.any() else int(np.argmin(fpr))
    return float(thr[i]), {"feasible": bool(ok.any()), "fpr": float(fpr[i]), "f1": float(f1[i])}


def metrics(y, score, threshold):
    y, score = np.asarray(y).astype(bool), np.asarray(score, dtype=np.float64)
    pred = score >= threshold
    tp, fp = int((pred & y).sum()), int((pred & ~y).sum())
    fn, tn = int((~pred & y).sum()), int((~pred & ~y).sum())
    div = lambda a, b: a / b if b else math.nan
    both = 0 < y.sum() < len(y)
    return {"n": int(len(y)), "attack": int(y.sum()), "genuine": int((~y).sum()), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": div(tp, tp + fp), "recall": div(tp, tp + fn), "f1": div(2 * tp, 2 * tp + fp + fn),
            "fpr": div(fp, fp + tn), "pr_auc": float(average_precision_score(y, score)) if both else math.nan,
            "roc_auc": float(roc_auc_score(y, score)) if both else math.nan}


def per_attack(d, score, threshold):
    return {a: metrics(d["y"][d["attack"] == a], score[d["attack"] == a], threshold) for a in sorted(set(d["attack"]))}


def make(family, params):
    if family == "decision_tree":
        return DecisionTreeClassifier(random_state=SEED, **params)
    if family == "random_forest":
        return RandomForestClassifier(random_state=SEED, n_jobs=-1, **params)
    if family == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(random_state=SEED, **params)
    raise ValueError(family)


class _Count:
    def __init__(self):
        self.n = 0

    def write(self, b):
        self.n += memoryview(b).nbytes          # protocol 5 also passes PickleBuffer objects


def serialized_bytes(model):
    c = _Count()
    pickle.dump(model, c, protocol=pickle.HIGHEST_PROTOCOL)
    return c.n


def single_message_latency_ms(predict, X, n=300):
    times = []
    for i in range(n):
        t = time.perf_counter()
        predict(X[i:i + 1])
        times.append(time.perf_counter() - t)
    return {"median": 1e3 * float(np.median(times)), "p95": 1e3 * float(np.percentile(times, 95))}


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def clean(x):
    """JSON-safe copy: NaN -> None, numpy scalars -> Python."""
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if math.isnan(float(x)) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def check_processed(processed):
    summary = json.loads((Path(processed) / "preprocess_summary.json").read_text(encoding="utf-8"))
    if summary.get("status") != "OK" or summary.get("feature_names") != NAMES:
        raise SystemExit("STOP: processed tables are not verified (status != OK) or the feature schema differs")
    return md5(Path(processed) / "preprocess_summary.json")


def select(processed, out, grid=GRID, q_grid=Q_GRID):
    """Train-only fitting and Validation-only selection. Never loads Test."""
    t_start = time.time()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    data_md5 = check_processed(processed)
    tr, va = load(processed, "Train"), load(processed, "Validation")
    mtr, mva = pooled_mask(tr), pooled_mask(va)
    Xtr, ytr = features_only(tr)[mtr], tr["y"][mtr]
    Xva, yva = features_only(va)[mva], va["y"][mva]
    rows = lambda d, m: {"rows": int(len(d["y"])), "pooled_rows": int(m.sum()), "dropped_repeated_honest": int((~m).sum()),
                         "flagged_attack_rows_kept": int((d["dup_of_earlier_primary_archive"] & (d["y"] == 1)).sum()),
                         "pooled_genuine": int((d["y"][m] == 0).sum()), "pooled_attack": int((d["y"][m] == 1).sum())}

    baseline_runs = []
    for q in q_grid:
        rb = RuleBaseline(q).fit(Xtr, ytr)
        baseline_runs.append({"q": q, "validation": metrics(yva, rb.score(Xva), RuleBaseline.THRESHOLD)})
    feasible = [r for r in baseline_runs if r["validation"]["fpr"] <= MAX_VAL_FPR]
    best_q = (max(feasible, key=lambda r: (r["validation"]["f1"], r["q"])) if feasible
              else min(baseline_runs, key=lambda r: r["validation"]["fpr"]))["q"]
    baseline = RuleBaseline(best_q).fit(Xtr, ytr)

    key = lambda c: (c["threshold_info"]["feasible"], c["validation"]["f1"], c["validation"]["pr_auc"], -c["serialized_bytes"])
    candidates, final, model = [], None, None                   # only the best model so far is kept in memory
    for family, settings in grid.items():
        for params in settings:
            m = make(family, params)
            t0 = time.time()
            m.fit(Xtr, ytr)
            fit_s = time.time() - t0
            t0 = time.perf_counter()
            p = m.predict_proba(Xva)[:, 1]
            batch_us = 1e6 * (time.perf_counter() - t0) / len(Xva)
            thr, info = choose_threshold(yva, p, MAX_VAL_FPR)
            entry = {"family": family, "params": params, "fit_seconds": round(fit_s, 2),
                     "batch_latency_us_per_msg": batch_us, "serialized_bytes": serialized_bytes(m),
                     "threshold": thr, "threshold_info": info, "validation": metrics(yva, p, thr)}
            candidates.append(entry)
            if final is None or key(entry) > key(final):
                final, model = entry, m
            del m, p
            print(f"  {family:<24}{json.dumps(params):<120} F1 {entry['validation']['f1']:.4f} "
                  f"FPR {entry['validation']['fpr']:.4f} PR-AUC {entry['validation']['pr_auc']:.4f} fit {fit_s:.1f}s",
                  flush=True)
    if hasattr(model, "n_jobs"):
        model.n_jobs = 1                                        # single-threaded inference, as on one vehicle
    import joblib
    joblib.dump(model, out / "final_model.joblib", compress=3)
    (out / "rule_baseline.json").write_text(json.dumps(clean({"q": best_q, "rules": baseline.rules,
                                                               "flag_if": "score > 0"}), indent=1), encoding="utf-8")
    p_va_full = model.predict_proba(features_only(va))[:, 1]
    s_va_full = baseline.score(features_only(va))
    latency = single_message_latency_ms(model.predict_proba, Xva)
    rb_latency = single_message_latency_ms(baseline.score, Xva)
    selection = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "frozen": True,
        "data": {"processed_summary_md5": data_md5, "track": "primary", "splits_used": ["Train", "Validation"]},
        "environment": {"python": platform.python_version(), "sklearn": sklearn.__version__, "numpy": np.__version__,
                        "platform": platform.platform(), "code_md5": md5(__file__)},
        "seed": SEED, "max_validation_fpr": MAX_VAL_FPR, "selection_criterion": SELECTION_CRITERION,
        "features": NAMES, "pooled_rule": "drop rows flagged dup_of_earlier_primary_archive with y == 0",
        "train": rows(tr, mtr), "validation": rows(va, mva), "grid": grid, "rule_q_grid": list(q_grid),
        "rule_baseline": {"q": best_q, "file": "rule_baseline.json", "grid_results": baseline_runs,
                          "validation_pooled": metrics(yva, baseline.score(Xva), RuleBaseline.THRESHOLD),
                          "validation_per_attack": per_attack(va, s_va_full, RuleBaseline.THRESHOLD),
                          "single_message_latency_ms": rb_latency},
        "candidates": candidates,
        "final": {"family": final["family"], "params": final["params"], "threshold": final["threshold"],
                  "threshold_info": final["threshold_info"], "file": "final_model.joblib",
                  "md5": md5(out / "final_model.joblib"), "file_bytes": (out / "final_model.joblib").stat().st_size,
                  "serialized_bytes": final["serialized_bytes"], "fit_seconds": final["fit_seconds"],
                  "batch_latency_us_per_msg": final["batch_latency_us_per_msg"], "single_message_latency_ms": latency,
                  "validation_pooled": final["validation"],
                  "validation_per_attack": per_attack(va, p_va_full, final["threshold"])},
        "seconds": round(time.time() - t_start, 1), "peak_rss_mb": round(peak_rss_mb(), 1),
    }
    (out / "selection.json").write_text(json.dumps(clean(selection), indent=1), encoding="utf-8")
    (out / "MODEL_COMPARISON_REPORT.md").write_text(comparison_report(clean(selection)), encoding="utf-8")
    print(f"final: {final['family']} {final['params']} threshold {final['threshold']:.4f}; "
          f"{selection['seconds']} s, peak {selection['peak_rss_mb']} MB")
    return selection


def evaluate_test(processed, out, force=False):
    """Evaluates the frozen selection on Test, once."""
    out = Path(out)
    sel = json.loads((out / "selection.json").read_text(encoding="utf-8"))
    if not sel.get("frozen"):
        raise SystemExit("STOP: no frozen selection")
    if (out / "test_results.json").exists() and not force:
        raise SystemExit("STOP: Test was already evaluated (test_results.json exists); it is evaluated once")
    if check_processed(processed) != sel["data"]["processed_summary_md5"]:
        raise SystemExit("STOP: processed data changed since the selection was frozen")
    if md5(out / "final_model.joblib") != sel["final"]["md5"]:
        raise SystemExit("STOP: final_model.joblib differs from the frozen selection")
    import joblib
    model = joblib.load(out / "final_model.joblib")
    rb_spec = json.loads((out / "rule_baseline.json").read_text(encoding="utf-8"))
    baseline = RuleBaseline(rb_spec["q"])
    baseline.rules = rb_spec["rules"]
    thr = sel["final"]["threshold"]
    te = load(processed, "Test")
    m = pooled_mask(te)
    X = features_only(te)
    p, s = model.predict_proba(X)[:, 1], baseline.score(X)
    ev = load(processed, "Test", track="eval_only")
    Xe = features_only(ev)
    pe, se = model.predict_proba(Xe)[:, 1], baseline.score(Xe)
    res = {
        "evaluated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "forced_rerun": bool(force),
        "selection_md5": md5(out / "selection.json"), "final": {"family": sel["final"]["family"], "threshold": thr},
        "test_rows": {"rows": int(len(te["y"])), "pooled_rows": int(m.sum()), "dropped_repeated_honest": int((~m).sum()),
                      "flagged_attack_rows_kept": int((te["dup_of_earlier_primary_archive"] & (te["y"] == 1)).sum())},
        "final_model": {"pooled": metrics(te["y"][m], p[m], thr), "per_attack": per_attack(te, p, thr)},
        "rule_baseline": {"pooled": metrics(te["y"][m], s[m], RuleBaseline.THRESHOLD),
                          "per_attack": per_attack(te, s, RuleBaseline.THRESHOLD)},
        "eval_only_suddenConstantSpeed": {
            "rows": int(len(ev["y"])),
            "final_model": {"official_label": metrics(ev["y"], pe, thr), "diagnostic_label": metrics(ev[DIAG], pe, thr)},
            "rule_baseline": {"official_label": metrics(ev["y"], se, RuleBaseline.THRESHOLD),
                              "diagnostic_label": metrics(ev[DIAG], se, RuleBaseline.THRESHOLD)}},
    }
    (out / "test_results.json").write_text(json.dumps(clean(res), indent=1), encoding="utf-8")
    (out / "TEST_EVALUATION_REPORT.md").write_text(test_report(sel, clean(res)), encoding="utf-8")
    print(f"Test pooled: {json.dumps(clean(res['final_model']['pooled']))}")
    return res


# ------------------------------------------------------------------ reports (generated: no number is typed by hand)
def _f(x, nd=4):
    return "—" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else f"{x:,}")


def _metric_rows(table, keys=None):
    lines = ["| Set | n | Attack | Precision | Recall | F1 | FPR | PR-AUC | TP | FP | FN | TN |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, m in table.items():
        if keys and name not in keys:
            continue
        lines.append(f"| {name} | {_f(m['n'])} | {_f(m['attack'])} | {_f(m['precision'])} | {_f(m['recall'])} | "
                     f"{_f(m['f1'])} | {_f(m['fpr'])} | {_f(m['pr_auc'])} | {_f(m['tp'])} | {_f(m['fp'])} | "
                     f"{_f(m['fn'])} | {_f(m['tn'])} |")
    return "\n".join(lines)


def comparison_report(sel):
    fin, rb = sel["final"], sel["rule_baseline"]
    best = {}
    for c in sel["candidates"]:
        if c["family"] not in best or (c["validation"]["f1"], c["validation"]["pr_auc"]) > \
                (best[c["family"]]["validation"]["f1"], best[c["family"]]["validation"]["pr_auc"]):
            best[c["family"]] = c
    lines = [
        "# Model comparison (Validation only): VeReMi NextGen InTAS_highway_2, primary track",
        "",
        f"Generated by `veremi/models.py select` on {sel['created_utc']}. Fitted on Train only; compared, tuned and "
        f"thresholded on Validation only. The Test split was not loaded. Seed {sel['seed']}; scikit-learn "
        f"{sel['environment']['sklearn']}, Python {sel['environment']['python']}.",
        "",
        "## Data",
        "",
        f"- Features: the 24 approved receiver-observable features only ({', '.join(sel['features'])}).",
        f"- Pooled rule: {sel['pooled_rule']}. Every flagged row is honest "
        f"({sel['train']['flagged_attack_rows_kept']} flagged attack rows in Train, {sel['validation']['flagged_attack_rows_kept']} in Validation).",
        f"- Train: {_f(sel['train']['rows'])} rows; pooled {_f(sel['train']['pooled_rows'])} "
        f"({_f(sel['train']['pooled_genuine'])} genuine, {_f(sel['train']['pooled_attack'])} attack; "
        f"{_f(sel['train']['dropped_repeated_honest'])} repeated honest rows not used).",
        f"- Validation: {_f(sel['validation']['rows'])} rows; pooled {_f(sel['validation']['pooled_rows'])} "
        f"({_f(sel['validation']['pooled_genuine'])} genuine, {_f(sel['validation']['pooled_attack'])} attack). "
        "Per-attack tables use every row of the archive.",
        "",
        "## Selection rule (fixed before the run)",
        "",
        f"{sel['selection_criterion']}. Each model's threshold is chosen on Validation: the highest F1 with FPR ≤ "
        f"{sel['max_validation_fpr']}. Class imbalance: the pooled data is close to balanced after duplicate removal; "
        "class weighting is a grid option, and the FPR-constrained threshold sets the operating point.",
        "",
        "## Candidates (pooled Validation)",
        "",
        "| Family | Parameters | Fit (s) | PR-AUC | Threshold | Precision | Recall | F1 | FPR | Serialized (MB) | Batch latency (µs/msg) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in sel["candidates"]:
        v = c["validation"]
        params = ", ".join(f"{k}={v2}" for k, v2 in c["params"].items())
        lines.append(f"| {c['family']} | {params} | {c['fit_seconds']:.1f} | {_f(v['pr_auc'])} | {c['threshold']:.4f} | "
                     f"{_f(v['precision'])} | {_f(v['recall'])} | {_f(v['f1'])} | {_f(v['fpr'])} | "
                     f"{c['serialized_bytes'] / 1e6:.1f} | {c['batch_latency_us_per_msg']:.2f} |")
    lines += ["", "## Best per family and rule baseline (pooled Validation)", ""]
    table = {f"{fam} (best)": c["validation"] for fam, c in best.items()} | {f"rule baseline (q={rb['q']})": rb["validation_pooled"]}
    lines += [_metric_rows(table), "", "Rule-baseline quantile grid (pooled Validation):", "",
              "| q | Precision | Recall | F1 | FPR |", "|---|---|---|---|---|"]
    lines += [f"| {r['q']} | {_f(r['validation']['precision'])} | {_f(r['validation']['recall'])} | "
              f"{_f(r['validation']['f1'])} | {_f(r['validation']['fpr'])} |" for r in rb["grid_results"]]
    lines += ["", "## Final selection", "",
              f"- **{fin['family']}** with {', '.join(f'{k}={v}' for k, v in fin['params'].items())}.",
              f"- Threshold {fin['threshold']:.6f}: Validation FPR {fin['threshold_info']['fpr']:.4f}, "
              f"F1 {fin['threshold_info']['f1']:.4f}; constraint met: {fin['threshold_info']['feasible']}.",
              f"- Artifact `final_model.joblib`: {fin['file_bytes'] / 1e6:.1f} MB compressed "
              f"({fin['serialized_bytes'] / 1e6:.1f} MB serialized), MD5 `{fin['md5']}`.",
              f"- Fit time {fin['fit_seconds']:.1f} s. Batch latency {fin['batch_latency_us_per_msg']:.2f} µs per message.",
              f"- Single-message latency (single thread): median {fin['single_message_latency_ms']['median']:.2f} ms, "
              f"p95 {fin['single_message_latency_ms']['p95']:.2f} ms.",
              f"- Rule baseline single-message latency: median {rb['single_message_latency_ms']['median']:.3f} ms.",
              f"- Whole run: {sel['seconds']} s, peak resident memory {sel['peak_rss_mb']} MB.",
              "", "## Per-attack Validation results (every row of each archive)", "",
              "### Final model", "", _metric_rows(fin["validation_per_attack"]), "",
              "### Rule baseline", "", _metric_rows(rb["validation_per_attack"]), "",
              "## Attacks with known label caveats (report separately)", "",
              "reversedHeading and zeroSpeedReport: 14 and 13 receptions miss the documented label rule (generator "
              "`sender_lookup` defect). suddenStop: one broadcast can be stopped at one receiver and normal at another. "
              "Their per-attack numbers carry these caveats:", "",
              _metric_rows(fin["validation_per_attack"], keys=CAVEAT_ATTACKS), "",
              "suddenConstantSpeed is not part of any number above; it is evaluated separately at Test time only.", ""]
    return "\n".join(lines)


def test_report(sel, res):
    fm, rb, ev = res["final_model"], res["rule_baseline"], res["eval_only_suddenConstantSpeed"]
    fin = sel["final"]
    lines = [
        "# Test evaluation: VeReMi NextGen InTAS_highway_2",
        "",
        f"Evaluated once on {res['evaluated_utc']} with the selection frozen on {sel['created_utc']} "
        f"(selection.json MD5 `{res['selection_md5']}`). No decision was changed after Test was loaded."
        + (" **This was a forced re-run.**" if res["forced_rerun"] else ""),
        "",
        f"- Final model: **{fin['family']}**, threshold {fin['threshold']:.6f}, chosen on Validation (FPR ≤ {sel['max_validation_fpr']}).",
        f"- Test: {_f(res['test_rows']['rows'])} primary rows; pooled {_f(res['test_rows']['pooled_rows'])} after dropping "
        f"{_f(res['test_rows']['dropped_repeated_honest'])} repeated honest rows ({res['test_rows']['flagged_attack_rows_kept']} flagged attack rows kept).",
        "- Data scope: simulated, low-density highway scenario (VeReMi NextGen InTAS_highway_2). No real-world validation.",
        "",
        "## Pooled Test (primary track)",
        "",
        _metric_rows({"final model": fm["pooled"], f"rule baseline (q={sel['rule_baseline']['q']})": rb["pooled"]}),
        "",
        "## Per-attack Test, final model (every row of each archive)",
        "",
        _metric_rows(fm["per_attack"]),
        "",
        "## Per-attack Test, rule baseline",
        "",
        _metric_rows(rb["per_attack"]),
        "",
        "## Attacks with known label caveats (final model)",
        "",
        _metric_rows(fm["per_attack"], keys=CAVEAT_ATTACKS),
        "",
        "## Separate track: suddenConstantSpeed (eval-only; never used for training or selection)",
        "",
        f"{_f(ev['rows'])} Test rows. The official label follows the generator's one-sided rule; the diagnostic label "
        "follows the documented rule and is derived from ground truth, so it is for diagnosis only.",
        "",
        _metric_rows({"final model, official label": ev["final_model"]["official_label"],
                      "final model, diagnostic label": ev["final_model"]["diagnostic_label"],
                      "rule baseline, official label": ev["rule_baseline"]["official_label"],
                      "rule baseline, diagnostic label": ev["rule_baseline"]["diagnostic_label"]}),
        "",
        "## Limits of these results",
        "",
        "- The labels mark *significant* CAM-content manipulation as defined by the VeReMi NextGen generator. They do not "
        "validate the detection of relay dropping or of forged accident alerts in this project's own simulator.",
        "- Known label defects: reversedHeading (14) and zeroSpeedReport (13) receptions miss the documented rule; "
        "suddenStop broadcasts can differ between receivers; suddenConstantSpeed labels are one-sided, hence the separate track.",
        "- Pooled numbers count each repeated honest message once; per-attack numbers count every row of the archive, "
        "so the honest rows in different per-attack tables overlap.",
        "- One simulated, low-density highway scenario: no claim about urban or high-density traffic, real vehicles, "
        "pseudonym changes (none occur in this subset) or real radio conditions.",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["select", "test"])
    ap.add_argument("--processed", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--force", action="store_true", help="test: allow a second Test evaluation (recorded as forced)")
    a = ap.parse_args()
    if a.command == "select":
        select(a.processed, a.out)
    else:
        evaluate_test(a.processed, a.out, force=a.force)


if __name__ == "__main__":
    main()
