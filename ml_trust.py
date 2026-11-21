"""Block D: the frozen Block C CAM-misbehaviour detector as an additional, bounded trust signal, in SHADOW mode.

This simulator transmits no CAMs (channel.py: no beacon traffic); trust comes from the per-second watchdog abstraction
in scenario.build. In shadow mode, that same loop also forms, every second, the CAM each observed vehicle would
broadcast from its SUMO state (as received by its nearest neighbour), scores it once per transmission with the frozen
Block C model, and counts the flags as separate ML evidence. Nothing that decides anything is changed: trust, roles,
votes, certificates, BLS checks, forwarding and RSU handling stay exactly as without ML. Only a what-if trust and the
decisions it would have produced are recorded.

Modes (config.ML_TRUST_MODE): "off" (default, nothing runs) | "shadow" | "enforce" (reserved and refused: the
simulator has no CAM-falsifying attacker, so ML evidence here can only be false positives).

What the detector can and cannot say: it was trained on VeReMi NextGen CAM-content manipulation (position, speed,
heading, acceleration, timing, replay, Sybil, DoS). It says nothing about relay dropping or forged accident alerts.
"""
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

import config
import corroboration
from clustering import elect_roles
from veremi.features import FEATURES, NAMES, ReceiverStreams

MODES = ("off", "shadow", "enforce")
NEVER_MISSING = [i for i, f in enumerate(FEATURES) if f[4].startswith("never")]   # schema: these may not be NaN


def checked_mode(mode):
    if mode not in MODES:
        raise ValueError(f"ML_TRUST_MODE must be one of {MODES}, not {mode!r}")
    if mode == "enforce":
        raise NotImplementedError("ML_TRUST_MODE='enforce' is reserved: this simulator has no CAM-falsifying attacker, so ML "
                                  "evidence can only be false positives here. Use 'shadow' (see BLOCK_D_INTEGRATION_REPORT.md)")
    return mode


def _md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


class Detector:
    """Read-only adapter for the frozen Block C model: verifies the artifact against selection.json (frozen flag, MD5,
    feature list) before loading it, and never fits or writes anything. Failures leave it 'unavailable'."""

    def __init__(self, model_dir):
        self.status, self.reason, self.version, self.threshold, self._model = "unavailable", None, None, None, None
        try:
            model_dir = Path(model_dir)
            sel = json.loads((model_dir / "selection.json").read_text(encoding="utf-8"))
            if not sel.get("frozen"):
                raise ValueError("selection is not frozen")
            if sel.get("features") != NAMES:
                raise ValueError("the model's feature list differs from the approved schema")
            path = model_dir / sel["final"]["file"]
            if _md5(path) != sel["final"]["md5"]:
                raise ValueError("model artifact does not match the frozen selection (MD5)")
            import joblib
            self._model = joblib.load(path)                 # only after the integrity check
            self.threshold = float(sel["final"]["threshold"])
            self.version = f"{sel['final']['family']}:{sel['final']['md5'][:12]}"
            self.status = "ready"
        except (OSError, ValueError, KeyError, TypeError) as e:
            self.reason = f"{type(e).__name__}: {e}"

    def score(self, X):
        """X: (n, 24) features in schema order. Returns per-row score (NaN if not scored), flag (score >= frozen
        threshold; False whenever not scored), status ('ok' | 'invalid_features' | 'model_unavailable' |
        'inference_error') and the model version. A failure is never reported as malicious."""
        X = np.asarray(X, dtype=np.float64)
        n = len(X) if X.ndim == 2 else 0
        score, flag = np.full(n, math.nan), np.zeros(n, bool)
        status = np.full(n, "ok" if self.status == "ready" else "model_unavailable", dtype=object)
        if X.ndim != 2 or X.shape[1] != len(NAMES):
            return {"score": score, "flag": flag, "status": np.full(n, "invalid_features", dtype=object),
                    "model_version": self.version}
        valid = ~np.isinf(X).any(axis=1) & ~np.isnan(X[:, NEVER_MISSING]).any(axis=1)
        status[~valid] = "invalid_features"
        if self.status == "ready" and valid.any():
            try:
                p = self._model.predict_proba(X[valid].astype(np.float32))[:, 1]
                score[valid], flag[valid] = p, p >= self.threshold
            except Exception:                                # noqa: BLE001 - any model failure is reported, not raised
                status[valid] = "inference_error"
        return {"score": score, "flag": flag, "status": status, "model_version": self.version}


@lru_cache(maxsize=4)
def detector(model_dir=None):
    model_dir = Path(model_dir or config.ML_MODEL_DIR)
    if not model_dir.is_absolute():
        model_dir = Path(config.__file__).resolve().parent / model_dir
    return Detector(model_dir)


def whatif_trust(successes, failures, flags, weight=None, cap=None):
    """The existing Beta trust (s+1)/(s+f+2) with ML flags as extra, bounded failure evidence:
    (s+1)/(s+f+2+weight*min(flags, cap)). A clean CAM adds nothing: it says nothing about relaying behaviour."""
    weight = config.ML_EVIDENCE_WEIGHT if weight is None else weight
    cap = config.ML_EVIDENCE_CAP if cap is None else cap
    return (successes + 1.0) / (successes + failures + 2.0 + weight * min(flags, cap))


class CamObserver:
    """Shadow CAM layer for scenario.build. Each second, every vehicle the watchdog observes (it has a neighbour)
    broadcasts one CAM built from its SUMO state; it is scored ONCE, as received by its nearest neighbour, so repeated
    receptions of one transmission never count as independent evidence. History features use the sender's previous
    CAMs (a receiver that hears every CAM of that sender). Content is noise-free and honest by construction."""

    def __init__(self, det, delay_ms=None):
        self.det = det
        self.delay_ns = int(round((config.ML_CAM_DELAY_MS if delay_ms is None else delay_ms) * 1e6))
        self.streams, self.prev_speed, self.ev = ReceiverStreams(), {}, {}

    def observe(self, t, ids, xy, speed, angle, seen, dist):
        rows, who = [], []
        snd = int(round(t * 1e9))
        for i, vid in enumerate(ids):
            acl = float(speed[i] - self.prev_speed.get(vid, speed[i]))   # 1-s step; 0 in a vehicle's first second
            self.prev_speed[vid] = speed[i]
            if not seen[i]:
                continue
            d = dist[i].copy()
            d[i] = np.inf
            j = int(np.argmin(d))                                         # the canonical receiver of this CAM
            rows.append(self.streams.row(vid, snd + self.delay_ns, snd, (float(xy[i, 0]), float(xy[i, 1])), float(speed[i]),
                                         acl, float(angle[i]), (float(xy[j, 0]), float(xy[j, 1])), float(speed[j]),
                                         float(angle[j])))
            who.append(vid)
        if not rows:
            return
        res = self.det.score(np.array(rows))
        for vid, s, f, st in zip(who, res["score"], res["flag"], res["status"]):
            e = self.ev.setdefault(vid, {"cams": 0, "scored": 0, "flagged": 0, "invalid": 0, "errors": 0, "max_score": None})
            e["cams"] += 1
            if st == "ok":
                e["scored"] += 1
                e["flagged"] += int(f)
                e["max_score"] = float(s) if e["max_score"] is None else max(e["max_score"], float(s))
            elif st == "invalid_features":
                e["invalid"] += 1
            else:
                e["errors"] += 1

    def result(self, ids, ok, bad):
        empty = {"cams": 0, "scored": 0, "flagged": 0, "invalid": 0, "errors": 0, "max_score": None}
        ev = [self.ev.get(v, empty) for v in ids]
        return {"mode": "shadow", "model_status": self.det.status, "model_reason": self.det.reason,
                "model_version": self.det.version, "threshold": self.det.threshold,
                "weight": config.ML_EVIDENCE_WEIGHT, "cap": config.ML_EVIDENCE_CAP, "cam_delay_ms": config.ML_CAM_DELAY_MS,
                "evidence": ev,
                "trust_whatif": np.array([whatif_trust(ok.get(v, 0), bad.get(v, 0), e["flagged"]) for v, e in zip(ids, ev)])}


def observer_for(mode):
    """scenario.build's entry point: None when ML is off; a shadow observer otherwise ('enforce' is refused)."""
    return None if checked_mode(mode) == "off" else CamObserver(detector())


def shadow_record(sc, net, roles):
    """The shadow log of one run (experiment.run_one). It reports what the ML-enhanced trust WOULD have changed;
    nothing reads it back. Ground-truth labels appear only in these counts, never in a decision."""
    nv, names, is_rsu, malicious, dist, adj = net
    sh, trust = sc["ml_shadow"], sc["trust"]
    whatif, gate, mal = sh["trust_whatif"], config.TRUST_CH_THRESHOLD, sc["malicious"]
    flip = (trust >= gate) != (whatif >= gate)
    roles_whatif = elect_roles(sc["xy"], sc["speed"], adj[:nv, :nv], whatif)[0]
    actual = corroboration.committee(sc["source"], dist, adj, nv, trust)
    would = corroboration.committee(sc["source"], dist, adj, nv, whatif)
    honest = lambda c: sum(1 for v in c if not mal[v])
    ev = sh["evidence"]
    total = lambda k: int(sum(e[k] for e in ev))
    return {
        "mode": "shadow", "decisions_changed": False, "model_status": sh["model_status"], "model_reason": sh["model_reason"],
        "model_version": sh["model_version"], "threshold": sh["threshold"], "weight": sh["weight"], "cap": sh["cap"],
        "cam_delay_ms": sh["cam_delay_ms"],
        "cams": {k: total(k) for k in ("cams", "scored", "flagged", "invalid", "errors")},
        "flagged_by_vehicle_type": {"honest": int(sum(e["flagged"] for e, m in zip(ev, mal) if not m)),
                                    "misbehaving": int(sum(e["flagged"] for e, m in zip(ev, mal) if m))},
        "would_change": {
            "trusted_status": {"honest": int((flip & ~mal).sum()), "misbehaving": int((flip & mal).sum())},
            "cluster_heads": int(((roles == "CH") != (roles_whatif == "CH")).sum()),
            "genuine_alert_committee": {"actual": [names[v] for v in actual], "would_be": [names[v] for v in would],
                                        "honest_voters_actual": honest(actual), "honest_voters_would_be": honest(would),
                                        "quorum_would_hold": honest(would) >= config.QUORUM}},
        "vehicles": [{"id": v, "trust": round(float(t), 4), "trust_whatif": round(float(w), 4), **e}
                     for v, t, w, e in zip(sc["ids"], trust, whatif, ev)],
    }
