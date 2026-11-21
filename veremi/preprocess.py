"""VeReMi NextGen InTAS_highway_2 -> message-level feature tables in three separate tracks.

    python -I veremi/preprocess.py --data-dir <dataset dir> --out <dataset dir>/processed/v2 \
        --schema veremi/feature_schema.json --manifest DATASET_MANIFEST_InTAS_highway_2.json \
        --tracks-manifest DATASET_TRACKS_MANIFEST.json

Tracks (approved 18 Nov 2026, see VEREMI_GENERATOR_LABEL_INVESTIGATION.md):
  primary/              14 attack archives: training, model selection and testing
  eval_only/            suddenConstantSpeed: separate evaluation only (defective official labels); also carries a
                        diagnostic label from the documented rule, never to be used for training or selection
  unlabelled_baseline/  the attack-free baseline archive, without any label array
One file per (archive, official split); splits are never mixed.

Row = one received message (receiver-level observation). y = the message's own official `attacker` field, unchanged.
Nothing is deleted: `is_first_reception` marks one canonical row per transmission, and
`dup_of_earlier_primary_archive` marks a reception already present, with identical content and label, in an earlier
primary archive of the same split (key: receiver, sender_id, messageID, sendTime). The ground-truth files are used
only to verify each archive's documented label rule (and for the diagnostic label), never for features.
Exit code 1 if any check fails; the summary then says FAILED.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import NAMES, ReceiverStreams, feature_schema, parse_vec  # noqa: E402

SCENARIO = "InTAS_highway_2"
SPLITS = ("Train", "Validation", "Test")
GT_FILES = {"Train": "InTAS_highway_2_Train_groundTruth.json", "Validation": "InTAS_highway_2_Validation_groundTruth.json",
            "Test": "InTAS_highway_2_Test_ground_truth.json"}
PROFILES = {"NORMAL": 0, "CAUTIOUS": 1, "AGGRESSIVE": 2}
SIDE_FIELDS = ("pos", "spd", "acl", "hed")
DIAG = "y_diag_documented_rule"

# Label semantics per archive, read from Generator/attackGenerator/attackGenerator.py (commit acda994) and verified
# against the data. track: primary | eval_only. rule: the documented labelling rule checked for every reception.
# cross_receiver: what may legitimately differ between receptions of one transmission (generator state shared across
# receiver files). tolerance: share of modified receptions allowed to miss the documented rule (known generator defect).
_GEN = "Generator/attackGenerator/attackGenerator.py"
POLICY = {
    "constantPositionOffset": {"rule": "always", "code": f"{_GEN}:191-195"},
    "randomPositionOffset": {"rule": "always", "code": f"{_GEN}:205-225"},
    "positionMirroring": {"rule": "always", "code": f"{_GEN}:228-235"},
    "constantSpeedOffset": {"rule": "always", "code": f"{_GEN}:238-241"},
    "randomSpeedOffset": {"rule": "always", "code": f"{_GEN}:244-263"},
    "timeDelayAttack": {"rule": "always", "code": f"{_GEN}:198-202"},
    "dataReplay": {"rule": "always", "code": f"{_GEN}:464-534"},
    "dosAttack": {"rule": "dos", "code": f"{_GEN}:377-397"},
    "trafficCongestionSybil": {"rule": "sybil", "code": f"{_GEN}:400-461"},
    "feignedBraking": {"rule": "feignedBraking", "code": f"{_GEN}:360-366",
                       "semantics": "1 only if original acceleration > 0.25 m/s^2; smaller manipulations labelled 0 by design"},
    "accelerationMultiplication": {"rule": "accelerationMultiplication", "code": f"{_GEN}:369-374",
                                   "semantics": "1 only if |original acceleration| > 0.5 m/s^2; smaller manipulations labelled 0 by design"},
    "zeroSpeedReport": {"rule": "moving", "code": f"{_GEN}:266-276", "tolerance": 0.001, "cross_receiver": "labels",
                        "report_separately": True,
                        "caveat": "label uses a global sender_lookup shared across receiver files: a few receptions miss the "
                                  "documented 'moved > 1 m since last message' rule and labels can differ between receivers"},
    "reversedHeading": {"rule": "moving", "code": f"{_GEN}:347-357", "tolerance": 0.001, "cross_receiver": "labels",
                        "report_separately": True,
                        "caveat": "same global sender_lookup defect as zeroSpeedReport"},
    "suddenStop": {"rule": "suddenStop", "code": f"{_GEN}:279-324", "cross_receiver": "labels+content",
                   "report_separately": True,
                   "caveat": "stop state is global per sender and set in receiver-file processing order: one broadcast can be "
                             "stopped at one receiver and normal at another; each reception's label follows its own content"},
    "suddenConstantSpeed": {"rule": "suddenConstantSpeed", "code": f"{_GEN}:327-344", "cross_receiver": "labels+content",
                            "track": "eval_only", "report_separately": True,
                            "caveat": "official label uses a one-sided test (actual - frozen > 1, line 332) where the "
                                      "documentation specifies |actual - frozen| > 1; freeze state set in processing order"},
}
PRIMARY = sorted(a for a, p in POLICY.items() if p.get("track", "primary") == "primary")
EVAL_ONLY = sorted(a for a, p in POLICY.items() if p.get("track") == "eval_only")


def peak_rss_mb():
    """Peak resident memory of this process (Windows: PeakWorkingSetSize; elsewhere ru_maxrss)."""
    if os.name == "nt":
        class PMC(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + \
                       [(n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                                        "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                                        "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = ctypes.c_void_p              # 64-bit pseudo-handle, not a 32-bit int
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_ulong]
        c = PMC(cb=ctypes.sizeof(PMC))
        if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return float("nan")
        return c.PeakWorkingSetSize / 2 ** 20
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def parse_record(m, labelled):
    """Strictly typed view of one received CAM; raises ValueError(reason) instead of guessing.
    The baseline archive stores every value as a string, so values are converted, never assumed numeric."""
    def num(v, what):
        if isinstance(v, bool):
            raise ValueError(f"non-numeric {what}")
        try:
            x = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"non-numeric {what}") from None
        if not math.isfinite(x):
            raise ValueError(f"non-finite {what}")
        return x

    def integer(v, what):
        if isinstance(v, bool) or not isinstance(v, (int, str)):
            raise ValueError(f"non-integer {what}")
        try:
            return int(v)
        except ValueError:
            raise ValueError(f"non-integer {what}") from None

    for k in ("rcvTime", "sendTime", "sender_id", "sender_alias", "messageID", "sender", "receiver"):
        if k not in m:
            raise ValueError(f"missing {k}")
    r = {"rcv": integer(m["rcvTime"], "rcvTime"), "snd": integer(m["sendTime"], "sendTime"),
         "alias": integer(m["sender_alias"], "sender_alias"), "msg": integer(m["messageID"], "messageID")}
    sid = m["sender_id"]
    if not (isinstance(sid, str) and sid.startswith("veh_") and sid[4:].isdigit()):
        raise ValueError("unparseable sender_id")
    r["sid"] = int(sid[4:])
    for side in ("sender", "receiver"):
        d = m[side]
        if not isinstance(d, dict):
            raise ValueError(f"{side} is not an object")
        for k in SIDE_FIELDS:
            if k not in d:
                raise ValueError(f"missing {side}.{k}")
        try:
            r[f"{side}_pos"] = parse_vec(d["pos"])
        except (ValueError, TypeError, AttributeError):
            raise ValueError(f"malformed {side}.pos") from None
        for k in ("spd", "acl", "hed"):
            r[f"{side}_{k}"] = num(d[k], f"{side}.{k}")
    edge = m["sender"].get("distance_to_road_edge")
    r["road_edge"] = num(edge, "sender.distance_to_road_edge") if edge is not None else math.nan
    r["profile"] = PROFILES.get(m["sender"].get("driversProfile"), -1)
    if labelled:
        a = m.get("attacker")
        if isinstance(a, bool) or a not in (0, 1):
            raise ValueError("attacker label missing or not 0/1")
        r["y"] = a
    return r


def load_ground_truth(path):
    """(sender_id, messageID) -> (pos, spd, acl, hed, sendTime, previous position of the same sender or None).
    Train/Validation nest the values under 'sender'; Test is flat. The previous position is the sender's
    chronologically preceding transmission (used only by the documented 'moved > 1 m' rule)."""
    out = {}
    for g in json.loads(path.read_bytes()):
        s = g["sender"] if isinstance(g.get("sender"), dict) else g
        key = (int(g["sender_id"][4:]), int(g["messageID"]))
        if key in out:
            raise ValueError(f"{path.name}: duplicate ground-truth key {key}")
        out[key] = [parse_vec(s["pos"]), float(s["spd"]), float(s["acl"]), float(s["hed"]), int(g["sendTime"]), None]
    by_sender = defaultdict(list)
    for key, v in out.items():
        by_sender[key[0]].append((v[4], key))
    for msgs in by_sender.values():
        msgs.sort()
        for (_, k0), (_, k1) in zip(msgs, msgs[1:]):
            out[k1][5] = out[k0][0]
    return {k: tuple(v) for k, v in out.items()}


def same_as_ground_truth(r, g):
    (gx, gy), spd, acl, hed, snd = g[:5]
    close = lambda a, b: math.isclose(a, b, rel_tol=0.0, abs_tol=1e-9)
    return (close(r["sender_pos"][0], gx) and close(r["sender_pos"][1], gy) and close(r["sender_spd"], spd)
            and close(r["sender_acl"], acl) and close(r["sender_hed"], hed) and r["snd"] == snd)


def documented_label(rule, r, g):
    """The label the documented rule assigns to this reception, or None when the rule cannot decide it
    (only: an unmodified dosAttack message, whose label depends on the unknown attacker set).
    Raises ValueError for a reception the rule says cannot exist (e.g. an unknown message in a content attack)."""
    if g is None:
        if rule in ("dos", "sybil"):
            return 1                                     # injected copy / phantom
        raise ValueError("message absent from ground truth")
    modified = not same_as_ground_truth(r, g)
    (gx, gy), spd, acl, _, _, prev = g
    if not modified:
        if rule == "dos":
            return None                                  # attacker originals are labelled 1, honest messages 0
        return 0
    if rule in ("always", "dos"):
        return 1
    if rule == "sybil":
        raise ValueError("ground-truth message modified in a Sybil archive")
    if rule == "feignedBraking":
        return int(acl > 0.25)
    if rule == "accelerationMultiplication":
        return int(abs(acl) > 0.5)
    if rule == "moving":                                 # zeroSpeedReport, reversedHeading
        return int(spd > 1 and (prev is None or math.dist(prev, (gx, gy)) > 1.0))
    if rule == "suddenStop":
        if math.dist(r["sender_pos"], (gx, gy)) <= 1e-9:      # the stop message itself: own position, speed zeroed
            return int(spd > 1 and acl >= 0)
        return int(spd > 1 or math.dist(r["sender_pos"], (gx, gy)) >= 20)   # frozen copy of the stop message
    if rule == "suddenConstantSpeed":
        return int(spd - r["sender_spd"] > 1)          # the generator's code (one-sided), which the official label follows
    raise ValueError(f"unknown rule {rule}")


def diagnostic_label(r, g):
    """suddenConstantSpeed only: the DOCUMENTED rule |actual - frozen| > 1 m/s. A reception is frozen exactly when its
    reported speed differs from the ground-truth (actual) speed; the frozen value is the reported speed."""
    if g is None:
        raise ValueError("message absent from ground truth")
    return int(not same_as_ground_truth(r, g) and abs(g[1] - r["sender_spd"]) > 1)


def process_split(folder, labelled, gt=None, rule=None, seen_obs=None, diag=False):
    """All receiver files of one split -> arrays + stats. Each receiver's history starts empty (splits never mix).
    rule: verify every reception against that documented label rule (needs gt). seen_obs: dict shared by the primary
    archives of this split, to flag receptions already present (same key, content and label) in an earlier archive."""
    rows, meta, rejected, examples = [], defaultdict(list), Counter(), {}
    tx_seen, tx_receivers, dup, checks, check_examples = {}, defaultdict(set), Counter(), Counter(), {}
    for fp in sorted(folder.rglob("*.json")):
        receiver = int(fp.stem[4:]) if fp.stem.startswith("veh_") and fp.stem[4:].isdigit() else -1
        if receiver < 0:
            rejected["unparseable receiver file name"] += 1
            examples.setdefault("unparseable receiver file name", fp.name)
            continue
        parsed = []
        for i, m in enumerate(json.loads(fp.read_bytes())):
            try:
                parsed.append(parse_record(m, labelled))
            except ValueError as e:
                rejected[str(e)] += 1
                examples.setdefault(str(e), f"{fp.name}[{i}]")
        parsed.sort(key=lambda r: r["rcv"])                      # stable: file order kept for equal rcvTime
        streams = ReceiverStreams()
        for r in parsed:
            rows.append(streams.row(r["alias"], r["rcv"], r["snd"], r["sender_pos"], r["sender_spd"], r["sender_acl"],
                                    r["sender_hed"], r["receiver_pos"], r["receiver_spd"], r["receiver_hed"]))
            for k, v in (("receiver", receiver), ("sender_id", r["sid"]), ("sender_alias", r["alias"]),
                         ("messageID", r["msg"]), ("sendTime", r["snd"]), ("rcvTime", r["rcv"]),
                         ("road_edge_dist", r["road_edge"]), ("drivers_profile", r["profile"])):
                meta[k].append(v)
            key = (r["sid"], r["msg"], r["snd"])
            content = (r["sender_pos"], r["sender_spd"], r["sender_acl"], r["sender_hed"])
            if labelled:
                meta["y"].append(r["y"])
            if key in tx_seen:
                dup["receptions_of_already_seen_tx"] += 1
                if labelled and tx_seen[key][0] != r["y"]:
                    dup["label_differs_between_receptions"] += 1
                if tx_seen[key][1] != content:
                    dup["content_differs_between_receptions"] += 1
                if receiver in tx_receivers[key]:
                    dup["same_tx_twice_at_one_receiver"] += 1
            else:
                tx_seen[key] = (r.get("y"), content)
            tx_receivers[key].add(receiver)
            if seen_obs is not None:
                obs = (receiver,) + key
                meta["dup"].append(seen_obs.get(obs) == (content, r["y"]))
                seen_obs.setdefault(obs, (content, r["y"]))
            g = gt.get((r["sid"], r["msg"])) if gt is not None else None
            if rule is not None:
                try:
                    want = documented_label(rule, r, g)
                    modified = g is None or not same_as_ground_truth(r, g)
                    checks["modified"] += modified
                    if want is None:
                        checks["not_decidable"] += 1
                    elif want == r["y"]:
                        checks["match"] += 1
                    else:
                        checks["mismatch"] += 1
                        checks[f"mismatch_official{r['y']}_rule{want}"] += 1
                        check_examples.setdefault("mismatch", f"{fp.name} sender veh_{r['sid']} msg {r['msg']}: "
                                                              f"label {r['y']}, documented rule {want}")
                except ValueError as e:
                    checks["impossible"] += 1
                    check_examples.setdefault("impossible", f"{fp.name} sender veh_{r['sid']} msg {r['msg']}: {e}")
            if diag:
                meta[DIAG].append(diagnostic_label(r, g))
    n = len(rows)
    arr = {"X": np.asarray(rows, dtype=np.float32).reshape(n, len(NAMES))}
    types = {"receiver": np.int32, "sender_id": np.int32, "sender_alias": np.int64, "messageID": np.int64,
             "sendTime": np.int64, "rcvTime": np.int64, "road_edge_dist": np.float32, "drivers_profile": np.int8,
             "y": np.int8, "dup": bool, DIAG: np.int8}
    for k, dtype in types.items():
        if k in meta or k in ("receiver", "sender_id", "sender_alias", "messageID", "sendTime", "rcvTime",
                              "road_edge_dist", "drivers_profile"):
            arr["dup_of_earlier_primary_archive" if k == "dup" else k] = np.asarray(meta.get(k, []), dtype=dtype)
    first = np.zeros(n, bool)                                  # canonical row = earliest reception of each transmission
    if n:
        order = np.lexsort((arr["rcvTime"], arr["sendTime"], arr["messageID"], arr["sender_id"]))
        k = np.stack([arr["sender_id"][order], arr["messageID"][order], arr["sendTime"][order]], 1)
        first[order[np.r_[True, np.any(k[1:] != k[:-1], axis=1)]]] = True
    arr["is_first_reception"] = first
    per_tx = Counter(len(v) for v in tx_receivers.values())
    stats = {"rows": n, "rejected": dict(rejected), "rejected_examples": examples,
             "transmitted_messages": len(tx_seen), "receptions_per_tx": {str(k): v for k, v in sorted(per_tx.items())},
             "tx_received_by_more_than_one_receiver": sum(v for k, v in per_tx.items() if k > 1),
             "canonical_rows": int(first.sum()), "duplicates": dict(dup)}
    if labelled:
        y = arr["y"]
        stats.update(label_0=int((y == 0).sum()), label_1=int((y == 1).sum()),
                     canonical_label_0=int(((y == 0) & first).sum()), canonical_label_1=int(((y == 1) & first).sum()))
    if rule is not None:
        stats.update(rule_check=dict(checks), rule_check_examples=check_examples)
    if "dup" in meta:
        stats["dup_of_earlier_primary_archive"] = int(np.sum(meta["dup"]))
    if diag:
        d = arr[DIAG]
        stats.update(diag_label_1=int(d.sum()), diag_vs_official={f"official{a}_diag{b}": int(((y == a) & (d == b)).sum())
                                                                  for a in (0, 1) for b in (0, 1)})
    return arr, stats, set(tx_seen)


def policy_problems(attack, splits):
    """Violations of the archive's documented label semantics; anything listed here makes the run FAILED.
    splits = {split: stats}. Rule mismatches are judged over the whole archive, as measured in the investigation
    (VEREMI_GENERATOR_LABEL_INVESTIGATION.md sections 3.1-3.2); everything else per split."""
    p, out = POLICY[attack], []
    total = Counter()
    for split, st in splits.items():
        c = st.get("rule_check", {})
        total.update(c)
        if c.get("impossible"):
            out.append(f"{split}: {c['impossible']} receptions impossible under the documented rule "
                       f"({st['rule_check_examples']['impossible']})")
        may = p.get("cross_receiver", "")
        for k, word in (("label_differs_between_receptions", "labels"), ("content_differs_between_receptions", "content")):
            if st["duplicates"].get(k) and word not in may:
                out.append(f"{split}: {st['duplicates'][k]} receptions: {k.replace('_', ' ')}")
        if st["duplicates"].get("same_tx_twice_at_one_receiver"):
            out.append(f"{split}: {st['duplicates']['same_tx_twice_at_one_receiver']} receptions: same transmission "
                       f"twice at one receiver")
    allowed = math.floor(p.get("tolerance", 0.0) * total["modified"])
    if total["mismatch"] > allowed:
        out.append(f"{total['mismatch']} receptions miss the documented label rule (allowed {allowed} of "
                   f"{total['modified']} modified)")
    if p.get("tolerance") and total["mismatch_official1_rule0"]:     # the known defect only produces official 0 / rule 1
        out.append(f"{total['mismatch_official1_rule0']} mismatches in the direction the known defect cannot explain")
    return out


def load(out_dir, split, attacks=None, track="primary"):
    """Concatenate the labelled tables of one split and one track ('primary' by default; 'eval_only' must be asked for
    explicitly; the unlabelled baseline is never returned). Adds no column: provenance is the stored `attack` array."""
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}")
    if track not in ("primary", "eval_only"):
        raise ValueError("track must be 'primary' or 'eval_only'; the unlabelled baseline is not loadable as labelled data")
    parts = []
    for p in sorted((Path(out_dir) / track).glob(f"*__{split}.npz")):
        attack = p.name.split("__")[0]
        if attacks is None or attack in attacks:
            with np.load(p) as z:
                parts.append({k: z[k] for k in z.files})
    if not parts:
        raise FileNotFoundError(f"no processed {track} {split} tables in {out_dir}")
    per_row = [k for k in parts[0] if k != "feature_names" and parts[0][k].ndim > 0]   # skip 0-d track/split markers
    return {k: np.concatenate([p[k] for p in parts]) for k in per_row} | \
        {"feature_names": parts[0]["feature_names"], "track": track, "split": split}


def md5_of(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--schema", required=True, type=Path, help="where to write the feature schema JSON")
    ap.add_argument("--manifest", required=True, type=Path, help="acquisition manifest (class counts before processing)")
    ap.add_argument("--tracks-manifest", required=True, type=Path, help="where to write the primary/eval-only track manifest")
    ap.add_argument("--overwrite", action="store_true", help="replace existing processed tables")
    a = ap.parse_args()
    t_start = time.time()
    extracted = a.data_dir / "extracted"
    if a.out.exists() and any(a.out.rglob("*.npz")) and not a.overwrite:
        sys.exit(f"STOP: {a.out} already holds processed tables; pass --overwrite to replace them")
    for track in ("primary", "eval_only", "unlabelled_baseline"):
        (a.out / track).mkdir(parents=True, exist_ok=True)
    schema = feature_schema()
    a.schema.write_text(json.dumps(schema, indent=1) + "\n", encoding="utf-8")
    before = json.loads(a.manifest.read_text(encoding="utf-8"))["inspection"]
    gts = {s: load_ground_truth(a.data_dir / "archives" / GT_FILES[s]) for s in SPLITS}

    found = sorted(p.name[len(SCENARIO) + 1:] for p in extracted.iterdir()
                   if p.is_dir() and p.name.startswith(SCENARIO + "_"))
    failures = [f"archive without a label policy: {x}" for x in found if x not in POLICY]
    failures += [f"approved archive missing: {x}" for x in POLICY if x not in found]
    order = [None] + PRIMARY + EVAL_ONLY                         # None = baseline; primary first so dup flags are stable
    summary = {}
    tx_by_split = {s: set() for s in SPLITS}
    msg_by_split = {s: set() for s in SPLITS}
    seen_obs = {s: {} for s in SPLITS}
    for attack in order:
        label = attack or "baseline (no attack)"
        name = SCENARIO + (f"_{attack}" if attack else "")
        track = "unlabelled_baseline" if attack is None else POLICY[attack].get("track", "primary")
        summary[label] = {"track": track, **({k: v for k, v in POLICY[attack].items() if k != "track"} if attack else {})}
        for split in SPLITS:
            t0 = time.time()
            arr, st, keys = process_split(
                extracted / name / split, labelled=attack is not None, gt=gts[split] if attack else None,
                rule=POLICY[attack]["rule"] if attack else None,
                seen_obs=seen_obs[split] if track == "primary" else None, diag=track == "eval_only")
            st["seconds"] = round(time.time() - t0, 1)
            ref = before[label][split]
            st["before"] = {"records": ref["records"], "label_0": ref.get("label_0", 0), "label_1": ref.get("label_1", 0)}
            if st["rows"] + sum(st["rejected"].values()) != ref["records"]:
                failures.append(f"{label}/{split}: {st['rows']} rows + rejected != {ref['records']} records in the manifest")
            if st["rejected"]:
                failures.append(f"{label}/{split}: rejected records {st['rejected']}")
            if attack and (st["label_0"], st["label_1"]) != (ref["label_0"], ref["label_1"]):
                failures.append(f"{label}/{split}: class counts changed during processing")
            tx_by_split[split] |= keys
            msg_by_split[split] |= {k[:2] for k in keys}
            arr["attack"] = np.full(st["rows"], attack or "baseline")
            path = a.out / track / f"{attack or 'baseline'}__{split}.npz"
            np.savez_compressed(path, feature_names=np.array(NAMES), track=np.array(track), split=np.array(split), **arr)
            st.update(file=path.relative_to(a.out).as_posix(), md5=md5_of(path))
            summary[label][split] = st
            chk = st.get("rule_check", {})
            print(f"{track:<20}{label:<28}{split:<11}{st['rows']:>8,} rows  {st.get('label_1', '-'):>7} attack  "
                  f"rule {chk.get('match', '-')}/{chk.get('mismatch', '-')}  {st['seconds']:>5}s")
        if attack:
            problems = policy_problems(attack, {s: summary[label][s] for s in SPLITS})
            summary[label]["policy_problems"] = problems
            failures += [f"{label}: {p}" for p in problems]
    overlap = {f"{x}&{y}": {"tx": len(tx_by_split[x] & tx_by_split[y]), "message": len(msg_by_split[x] & msg_by_split[y])}
               for i, x in enumerate(SPLITS) for y in SPLITS[i + 1:]}
    failures += [f"messages shared between splits {k}: {v}" for k, v in overlap.items() if v["tx"] or v["message"]]
    out = {"scenario": SCENARIO, "feature_names": NAMES, "schema_file": a.schema.as_posix(), "schema_md5": md5_of(a.schema),
           "tracks": {"primary": PRIMARY, "eval_only": EVAL_ONLY, "unlabelled_baseline": ["baseline"]},
           "tx_key": "(sender_id, messageID, sendTime)", "dup_key": "(receiver, sender_id, messageID, sendTime) + identical content and label",
           "cross_split_overlap": overlap, "archives": summary, "failures": failures,
           "status": "OK" if not failures else "FAILED", "seconds": round(time.time() - t_start, 1),
           "peak_rss_mb": round(peak_rss_mb(), 1)}
    (a.out / "preprocess_summary.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    a.tracks_manifest.write_text(json.dumps(tracks_manifest(out, a.out, a.tracks_manifest), indent=1) + "\n", encoding="utf-8")
    print(f"status {out['status']}  {out['seconds']} s  peak {out['peak_rss_mb']} MB")
    for f in failures:
        print("  FAILURE:", f)
    sys.exit(1 if failures else 0)


def tracks_manifest(summary, out_dir, manifest_path):
    """Compact, machine-readable description of what each track contains (written next to the repo's reports)."""
    arch = lambda x: summary["archives"][x if x != "baseline" else "baseline (no attack)"]

    def files(attacks):
        res = {}
        for attack in attacks:
            s = arch(attack)
            res[attack] = {sp: {k: s[sp][k] for k in ("file", "md5", "rows", "label_0", "label_1", "canonical_rows",
                                                      "dup_of_earlier_primary_archive", "diag_label_1") if k in s[sp]}
                           for sp in SPLITS}
            res[attack].update({k: s[k] for k in ("rule", "code", "semantics", "caveat", "report_separately") if k in s})
        return res
    total = lambda attacks, k: {sp: sum(arch(x)[sp].get(k, 0) for x in attacks) for sp in SPLITS}
    return {
        "dataset": "VeReMi NextGen (Zenodo 10.5281/zenodo.19665762, CC-BY 4.0), subset InTAS_highway_2; simulated data",
        "status": summary["status"],
        "processed_dir": os.path.relpath(Path(out_dir).resolve(), Path(manifest_path).resolve().parent).replace("\\", "/"),
        "schema": {"file": summary["schema_file"], "md5": summary["schema_md5"], "features": summary["feature_names"]},
        "label_policy": "y = official per-reception `attacker` field, unchanged; no record relabelled or removed",
        "split_policy": "official Train / Validation / Test kept separate; one file per archive and split",
        "duplicates": {"tx_key": summary["tx_key"], "dup_flag": "dup_of_earlier_primary_archive",
                       "dup_key": summary["dup_key"], "flagged_per_split": total(PRIMARY, "dup_of_earlier_primary_archive"),
                       "use": "per-attack evaluation keeps every row; pooled training/evaluation may drop flagged rows"},
        "cross_split_overlap": summary["cross_split_overlap"],
        "tracks": {
            "primary": {"purpose": "training, model selection and testing", "archives": PRIMARY,
                        "rows": total(PRIMARY, "rows"), "label_0": total(PRIMARY, "label_0"),
                        "label_1": total(PRIMARY, "label_1"), "files": files(PRIMARY)},
            "eval_only": {"purpose": "separate evaluation only; never used for training or model selection",
                          "archives": EVAL_ONLY, "rows": total(EVAL_ONLY, "rows"), "label_0": total(EVAL_ONLY, "label_0"),
                          "label_1": total(EVAL_ONLY, "label_1"),
                          "diagnostic_label": {"column": DIAG, "rule": "|actual speed - frozen speed| > 1 m/s "
                                               "(Documentation/Post-Processing/Attack Generator/README.md lines 101-103)",
                                               "derivation": "frozen = reported speed when it differs from the ground-truth "
                                                             "speed of the same message; actual = ground-truth speed; "
                                                             "0 for unmodified receptions",
                                               "use": "diagnostic evaluation only; derived from ground truth"},
                          "files": files(EVAL_ONLY)},
            "unlabelled_baseline": {"purpose": "attack-free reference traffic; no labels", "rows": total(["baseline"], "rows"),
                                    "files": files(["baseline"])},
        },
    }


if __name__ == "__main__":
    main()
