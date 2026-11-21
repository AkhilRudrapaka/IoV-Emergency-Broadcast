"""Receiver-side features for VeReMi NextGen CAMs: one row per received message, computed only from what the receiving
vehicle has at that moment (the message, its own state, and earlier messages it received from the same pseudonym).

The single source of truth for the feature schema is FEATURES below; `feature_schema()` turns it into the JSON schema.
Nothing here reads the ground-truth files or the `attacker` label.
"""
import math
from collections import deque

WINDOW = 5            # messages in the per-pseudonym history window (current message included)
RATE_WINDOW_S = 1.0   # window for the message-rate feature
MIN_DISPLACEMENT_M = 1.0   # below this the direction of travel is undefined

# name, source fields, calculation, logical type, availability, missing-value rule
_HIST = "NaN when the receiver has no earlier message from this pseudonym (has_prev = 0)"
FEATURES = [
    ("spd", "sender.spd", "reported speed", "float m/s", "never missing"),
    ("acl", "sender.acl", "reported acceleration", "float m/s^2", "never missing"),
    ("dist_tx_rx_m", "sender.pos, receiver.pos", "2-D distance between reported sender position and receiver's own position",
     "float m", "never missing"),
    ("abs_rel_speed", "sender.spd, receiver.spd", "|reported speed - receiver's own speed|", "float m/s", "never missing"),
    ("heading_diff_rx_deg", "sender.hed, receiver.hed", "absolute angular difference of the two headings", "float deg [0,180]",
     "never missing"),
    ("delay_ms", "rcvTime, sendTime", "rcvTime - sendTime", "float ms", "never missing"),
    ("has_prev", "stream", "1 if the receiver got an earlier message from this pseudonym, else 0", "binary", "never missing"),
    ("n_prev", "stream", "number of earlier messages from this pseudonym at this receiver", "count", "never missing"),
    ("rate_1s", "stream, rcvTime", f"earlier messages from this pseudonym received within the last {RATE_WINDOW_S:g} s", "count",
     "never missing (0 without history)"),
    ("dt_send_s", "sendTime", "sendTime - previous sendTime of this pseudonym (negative = out of order)", "float s", _HIST),
    ("dt_rcv_s", "rcvTime", "rcvTime - previous rcvTime of this pseudonym", "float s", _HIST),
    ("dpos_m", "sender.pos", "2-D distance to the previous reported position", "float m", _HIST),
    ("implied_speed", "sender.pos, sendTime", "dpos_m / dt_send_s", "float m/s", _HIST + "; also NaN when dt_send_s <= 0"),
    ("speed_residual", "sender.pos, sender.spd, sendTime", "|implied_speed - mean(spd, previous spd)|", "float m/s",
     _HIST + "; also NaN when dt_send_s <= 0"),
    ("dspd", "sender.spd", "spd - previous spd", "float m/s", _HIST),
    ("implied_acl", "sender.spd, sendTime", "dspd / dt_send_s", "float m/s^2", _HIST + "; also NaN when dt_send_s <= 0"),
    ("acl_residual", "sender.spd, sender.acl, sendTime", "|implied_acl - mean(acl, previous acl)|", "float m/s^2",
     _HIST + "; also NaN when dt_send_s <= 0"),
    ("dhed_deg", "sender.hed", "absolute angular change of heading since the previous message", "float deg [0,180]", _HIST),
    ("yaw_rate_dps", "sender.hed, sendTime", "dhed_deg / dt_send_s", "float deg/s", _HIST + "; also NaN when dt_send_s <= 0"),
    ("bearing_residual_deg", "sender.pos, sender.hed",
     "angle between direction of travel (north = 0, clockwise) and reported heading", "float deg [0,180]",
     _HIST + f"; also NaN when dpos_m < {MIN_DISPLACEMENT_M:g} m"),
    ("pos_pred_error_m", "sender.pos, sender.spd, sender.hed, sendTime",
     "distance between reported position and dead-reckoned position (previous position + previous spd * dt along previous heading)",
     "float m", _HIST),
    ("speed_residual_mean5", "stream", f"mean speed_residual over the last {WINDOW} messages of this pseudonym (current included)",
     "float m/s", "NaN when none of them has a speed_residual"),
    ("pos_pred_error_max5", "stream", f"max pos_pred_error_m over the last {WINDOW} messages (current included)", "float m",
     "NaN when none of them has a pos_pred_error_m"),
    ("dt_send_min5", "stream", f"min dt_send_s over the last {WINDOW} messages (current included)", "float s",
     "NaN when none of them has a dt_send_s"),
]
NAMES = [f[0] for f in FEATURES]
HISTORY = ["dt_send_s", "dt_rcv_s", "dpos_m", "implied_speed", "speed_residual", "dspd", "implied_acl", "acl_residual",
           "dhed_deg", "yaw_rate_dps", "bearing_residual_deg", "pos_pred_error_m"]   # NaN without an earlier message

# Fields that exist in the data but must never be model inputs.
EXCLUDED = {
    "attacker": "the target label",
    "ground-truth files": "ground truth only; used for mapping verification, never for features",
    "sender_id": "true vehicle identity; a receiver only sees the pseudonym",
    "receiver id (file name)": "identity",
    "sender_alias": "pseudonym; used only to group a receiver's history, never as a value",
    "messageID": "dataset bookkeeping identifier, not CAM content; correlated with time",
    "rcvTime, sendTime (absolute)": "absolute time identifies the split and the scenario period; only differences are used",
    "sender.pos, receiver.pos (absolute)": "absolute location identifies the area (Test is a different area); only distances are used",
    "sender.hed, receiver.hed (absolute)": "road orientation proxy for location; only angular differences are used",
    "sender.distance_to_road_edge": "not part of the transmitted message: added after the attacks by "
                                    "Generator/enrichMsgsWithFutherInfo/enrichMsgs.py:158-163 from the REPORTED sender position "
                                    "and the SUMO road map. Computable only by a receiver with the same lane-level map, so it "
                                    "is kept as metadata (road_edge_dist) for an explicitly labelled map-based variant",
    "*_noise fields": "realised sensor error, not a transmitted confidence: the generator recovers the true position as "
                      "reported - pos_noise (Generator/attackGenerator/attackGenerator.py:179-188); a real receiver cannot "
                      "know it. Also unmodified by the attacks checked, so any signal would be a sender-selection artefact",
    "driversProfile": "simulation metadata a receiver cannot observe; attack share differs by profile (selection shortcut)",
    "receiver.acl, receiver.*_noise": "receiver-own values not needed by any feature",
}


def parse_vec(s):
    """'x,y,z' string (or list) -> (x, y) floats; ValueError if malformed or not finite."""
    parts = s.split(",") if isinstance(s, str) else list(s)
    if len(parts) != 3:
        raise ValueError(f"expected 3 components, got {len(parts)}")
    x, y, z = (float(p) for p in parts)
    if not all(map(math.isfinite, (x, y, z))):
        raise ValueError("non-finite component")
    return x, y


def angdiff(a, b):
    """Absolute angular difference in degrees, in [0, 180]."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def bearing(dx, dy):
    """Direction of travel, north = 0 deg, clockwise (the dataset's heading convention, checked on genuine streams)."""
    return math.degrees(math.atan2(dx, dy)) % 360.0


def _nan_agg(fn, xs):
    xs = [x for x in xs if not math.isnan(x)]
    return fn(xs) if xs else math.nan


class ReceiverStreams:
    """Causal feature state of ONE receiver: per pseudonym, the last WINDOW messages and recent receive times.
    Feed messages in receive order; row(m) uses only m and messages fed before it."""

    def __init__(self):
        self.hist, self.times, self.count = {}, {}, {}

    def row(self, alias, rcv, snd, pos, spd, acl, hed, rx_pos, rx_spd, rx_hed):
        nan = math.nan
        h = self.hist.setdefault(alias, deque(maxlen=WINDOW))
        times = self.times.setdefault(alias, deque())
        while times and times[0] <= rcv - RATE_WINDOW_S * 1e9:
            times.popleft()
        n_prev = self.count.get(alias, 0)
        f = {"spd": spd, "acl": acl, "dist_tx_rx_m": math.dist(pos, rx_pos), "abs_rel_speed": abs(spd - rx_spd),
             "heading_diff_rx_deg": angdiff(hed, rx_hed), "delay_ms": (rcv - snd) / 1e6, "has_prev": float(bool(h)),
             "n_prev": float(n_prev), "rate_1s": float(len(times))}
        for k in HISTORY:
            f[k] = nan
        if h:
            p = h[-1]
            dt = (snd - p["snd"]) / 1e9
            dx, dy = pos[0] - p["pos"][0], pos[1] - p["pos"][1]
            dpos = math.hypot(dx, dy)
            f.update(dt_send_s=dt, dt_rcv_s=(rcv - p["rcv"]) / 1e9, dpos_m=dpos, dspd=spd - p["spd"],
                     dhed_deg=angdiff(hed, p["hed"]))
            if dt > 0:
                f["implied_speed"] = dpos / dt
                f["speed_residual"] = abs(f["implied_speed"] - (spd + p["spd"]) / 2)
                f["implied_acl"] = f["dspd"] / dt
                f["acl_residual"] = abs(f["implied_acl"] - (acl + p["acl"]) / 2)
                f["yaw_rate_dps"] = f["dhed_deg"] / dt
            if dpos >= MIN_DISPLACEMENT_M:
                f["bearing_residual_deg"] = angdiff(bearing(dx, dy), hed)
            r, step = math.radians(p["hed"]), p["spd"] * dt
            f["pos_pred_error_m"] = math.dist(pos, (p["pos"][0] + step * math.sin(r), p["pos"][1] + step * math.cos(r)))
        cur = {"rcv": rcv, "snd": snd, "pos": pos, "spd": spd, "acl": acl, "hed": hed,
               "speed_residual": f["speed_residual"], "pos_pred_error_m": f["pos_pred_error_m"], "dt_send_s": f["dt_send_s"]}
        window = list(h) + [cur]
        f["speed_residual_mean5"] = _nan_agg(lambda xs: sum(xs) / len(xs), [w["speed_residual"] for w in window])
        f["pos_pred_error_max5"] = _nan_agg(max, [w["pos_pred_error_m"] for w in window])
        f["dt_send_min5"] = _nan_agg(min, [w["dt_send_s"] for w in window])
        h.append(cur)
        times.append(rcv)
        self.count[alias] = n_prev + 1
        return [f[k] for k in NAMES]


def feature_schema():
    return {"version": 2, "row": "one received message (receiver-level observation)", "window": WINDOW,
            "notes": ["timeDelayAttack shifts sendTime AND rcvTime by the same delay (attackGenerator.py:199-200), so "
                      "delay_ms carries no signal for that attack by construction",
                      "features never read the ground-truth files or the attacker label; the eval-only diagnostic label "
                      "is stored outside X"],
            "rate_window_s": RATE_WINDOW_S, "heading_convention": "degrees, north = 0, clockwise",
            "fitted_transforms": "none: every feature is a deterministic function of the message and the receiver's earlier "
                                 "messages; any scaler added later must be fitted on Train only",
            "features": [{"index": i, "name": n, "source": s, "calculation": c, "type": t, "available_at_inference": True,
                          "missing": m} for i, (n, s, c, t, m) in enumerate(FEATURES)],
            "excluded": EXCLUDED}
