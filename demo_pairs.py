"""
Comparison pairs for the faculty demo (python run.py pair ..., python run.py demo --pair ..., or the web dashboard).

A pair is ONE incident scenario replayed twice in SUMO-GUI, one approach per run and never two runs at once: once with
a single baseline, once with the proposed method. The CH-to-CH route is replayed as a stage of the proposed method
(docs/SYSTEM_DESIGN.md §3 lists it as stage 10 of the proposed pipeline; its baselines are blind flooding, flooding +
RAD, slotted 1-persistence and slotted 1-p + RAD). Both runs re-simulate the same seed with the unchanged experiment
engine, so both replay the same run record, in which every scheme ran on the identical snapshot, network, demand,
radio and parameters (experiment.run_one); each run stores the record's fingerprint, and the comparison is shown only
when both fingerprints agree.

Scenarios are the experiment's own seeds at the demo density (scenario ID d200_r07, seed = BASE_SEED + 100*d + r). Each
seed already fixes a different incident on the same road network and traffic model: a random honest vehicle at a random
second (scenario.build). The scenarios are offered in an order shuffled by the pairs folder's selection seed, drawn at
random when the folder's first pair is made and kept in selection.json: each new folder offers its own sequence of
incidents, and every pair records its selection seed and rank, so its choice can be reproduced. A new pair takes the
first unused scenario in that order whose incident lies on the road network and at least MIN_SEPARATION_M from every
incident already used. The choice never looks at any algorithm's result. Only when no such scenario is left is a
location reused, and the pair records it (selection.repeat_of).

Everything is written under results/demo_pairs/ (or $DEMO_PAIRS_DIR): selection.json, and per pair <pair>/pair.json,
<pair>/<approach>_console.log and one results folder per approach, <pair>/<approach>/, holding that run's own
re-simulated record (raw/), live feed, SUMO log, local outbox and live window captures. Tracked results are never
written. (Pairs run before per-approach folders keep one shared record in <pair>/raw/, which is still read.)
"""
import gzip
import json
import math
import os
import random
import re
import secrets
import subprocess
import sys
import threading
import zlib
from datetime import datetime

import config
from scenario import BOUNDS, EDGES, build, seed_for

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.environ.get("DEMO_PAIRS_DIR") or os.path.join(HERE, "results", "demo_pairs"))
DENSITY = config.DEMO_DENSITY                # one traffic model: the demo density's demand
CANDIDATE_RUNS = range(config.RUNS_PER_DENSITY)
MIN_SEPARATION_M = 50.0                      # incidents closer than this count as the same location
BASELINES = [p for p in config.BASELINES if p != "proposed"]
PROPOSED = ["proposed", "ch_route"]
APPROACHES = ("baseline", "proposed")
ACTIVE = "active_run.json"
SELECTION = "selection.json"
PAIR_ID = re.compile(r"P\d{3,}")


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def schemes_for(approach, baseline):
    """The schemes ONE separated run replays."""
    if approach == "baseline":
        if baseline not in BASELINES:
            raise ValueError(f"unknown baseline {baseline!r}; implemented: {', '.join(BASELINES)}")
        return [baseline]
    if approach == "proposed":
        return list(PROPOSED)
    raise ValueError(f"approach must be one of {', '.join(APPROACHES)}")


def algorithm(approach, baseline):
    return config.LABELS[baseline] if approach == "baseline" else f"{config.LABELS['proposed']} with its CH-to-CH route stage"


# ---------------------------------------------------------------- scenarios
def scenario_id(run):
    return f"d{DENSITY}_r{run:02d}"


def incident(run):
    """The incident a scenario fixes, computed by the scenario builder itself (never an invented coordinate)."""
    sc = build(DENSITY, run)
    x, y = sc["incident_xy"]
    return {"vehicle": sc["source_id"], "x": x, "y": y, "lane": sc["incident_lane"],
            "time_s": float(sc["incident_time_s"]), "event_id": sc["alert"]["event_id"]}


def valid(inc):
    """On the road network: inside its bounding box and on one of its lanes (a road lane, or a junction's)."""
    lane = inc.get("lane") or ""
    return (BOUNDS[0] <= inc["x"] <= BOUNDS[2] and BOUNDS[1] <= inc["y"] <= BOUNDS[3]
            and (lane.startswith(":") or lane.rsplit("_", 1)[0] in EDGES))


def order(selection_seed):
    runs = list(CANDIDATE_RUNS)
    random.Random(selection_seed).shuffle(runs)
    return runs


def selection_seed():
    """This pairs folder's selection seed (selection.json). The first pair of a new folder draws it at random; a folder
    whose pairs were made before selection.json existed keeps the seed they recorded."""
    path = os.path.join(ROOT, SELECTION)
    try:
        with open(path, encoding="utf-8") as f:
            return int(json.load(f)["selection_seed"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    recorded = [p["scenario"]["selection"].get("selection_seed") for p in pairs()]
    seed = next((s for s in recorded if isinstance(s, int)), None)
    source = "kept from the folder's earlier pairs" if seed is not None else "drawn at random"
    seed = secrets.randbelow(2 ** 31) if seed is None else seed
    os.makedirs(ROOT, exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump({"selection_seed": seed, "created": now(), "source": source}, f, indent=1)
    os.replace(path + ".tmp", path)
    return seed


def select(used, selection_seed, incident_of=None):
    """(run, incident, repeat_of, rank) for the next pair. used: [(scenario ID, x, y)] of earlier pairs, oldest first.
    Prefers an unused scenario whose incident is >= MIN_SEPARATION_M from every used one; then an unused scenario at a
    nearby location; then the least recently used scenario. A reuse is never silent: repeat_of names what it repeats."""
    incident_of = incident_of or incident                             # resolved at call time
    runs, taken = order(selection_seed), {sid for sid, _, _ in used}
    fresh = [(rank, run) for rank, run in enumerate(runs) if scenario_id(run) not in taken]
    nearby = []
    for rank, run in fresh:
        inc = incident_of(run)
        if not valid(inc):
            continue
        gaps = [(math.hypot(inc["x"] - x, inc["y"] - y), sid) for sid, x, y in used]
        if all(g >= MIN_SEPARATION_M for g, _ in gaps):
            return run, inc, None, rank
        nearby.append((run, inc, min(gaps)[1], rank))
    if nearby:
        return nearby[0]
    last = {sid: i for i, (sid, _, _) in enumerate(used)}            # every scenario used: least recently used one
    for sid in sorted(last, key=last.get):
        run = int(sid.rsplit("_r", 1)[1])
        inc = incident_of(run)
        if valid(inc):
            return run, inc, sid, runs.index(run)
    raise RuntimeError("no scenario has an incident on the road network")


# ---------------------------------------------------------------- pair records
def pair_dir(pair_id):
    if not isinstance(pair_id, str) or not PAIR_ID.fullmatch(pair_id):
        raise ValueError(f"not a pair ID: {pair_id!r}")
    return os.path.join(ROOT, pair_id)


def approach_dir(pair_id, approach):
    """The results folder of one approach's run (its EXP_RESULTS_DIR): nothing in it is shared with the other run."""
    if approach not in APPROACHES:
        raise ValueError(f"approach must be one of {', '.join(APPROACHES)}")
    return os.path.join(pair_dir(pair_id), approach)


def load(pair_id):
    with open(os.path.join(pair_dir(pair_id), "pair.json"), encoding="utf-8") as f:
        return json.load(f)


def save(pair):
    path = os.path.join(pair_dir(pair["pair_id"]), "pair.json")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(pair, f, indent=1)
    os.replace(path + ".tmp", path)


def pairs():
    out = []
    for name in sorted(os.listdir(ROOT)) if os.path.isdir(ROOT) else []:
        if PAIR_ID.fullmatch(name):
            try:
                out.append(load(name))
            except (OSError, ValueError):
                continue                                             # being written, or not a pair: skip it
    return out


def new_pair(baseline="flooding", run=None):
    """A new comparison pair: the next reproducible scenario (or `run`, chosen explicitly) and one baseline."""
    schemes_for("baseline", baseline)                                # validates the baseline
    existing = pairs()
    used = [(p["scenario"]["scenario_id"], p["scenario"]["incident"]["x"], p["scenario"]["incident"]["y"]) for p in existing]
    seed = selection_seed()
    if run is None:
        run, inc, repeat_of, rank = select(used, seed)
        method = (f"order shuffled by this folder's selection seed {seed}; first unused scenario whose incident is on the "
                  f"road network and at least {MIN_SEPARATION_M:.0f} m from every incident used before")
    else:
        if run not in CANDIDATE_RUNS:
            raise ValueError(f"scenario run must be 0..{len(CANDIDATE_RUNS) - 1}")
        inc, rank, method = incident(run), None, "chosen explicitly"
        if not valid(inc):
            raise ValueError("this scenario's incident is not on the road network")
        repeat_of = next((sid for sid, x, y in used if sid == scenario_id(run)
                          or math.hypot(inc["x"] - x, inc["y"] - y) < MIN_SEPARATION_M), None)
    os.makedirs(ROOT, exist_ok=True)
    number = max((int(p["pair_id"][1:]) for p in existing), default=0) + 1
    while True:                                                      # claim the ID atomically
        try:
            os.makedirs(pair_dir(f"P{number:03d}"))
            break
        except FileExistsError:
            number += 1
    pair = {"pair_id": f"P{number:03d}", "created": now(), "baseline": baseline,
            "scenario": {"scenario_id": scenario_id(run), "density": DENSITY, "run": run, "seed": seed_for(DENSITY, run),
                         "network": config.NET_FILE, "incident": inc,
                         "selection": {"method": method, "selection_seed": seed, "rank": rank,
                                       "repeat_of": repeat_of}},
            "runs": {a: {"approach": a, "algorithm": algorithm(a, baseline), "schemes": schemes_for(a, baseline),
                         "status": "not started"} for a in APPROACHES}}
    save(pair)
    return pair


def update_run(pair_id, approach, **fields):
    pair = load(pair_id)
    pair["runs"][approach].update(fields)
    save(pair)
    return pair


def check_record(pair, raw):
    """The re-simulated record must be this pair's scenario: same scenario ID, seed, incident vehicle, time, place."""
    sc, want = raw["scenario"], pair["scenario"]
    got = (sc["run_id"], sc["seed"], sc["source_id"], float(sc["incident_time_s"]), [float(c) for c in sc["incident_xy"]])
    inc = want["incident"]
    expected = (want["scenario_id"], want["seed"], inc["vehicle"], inc["time_s"], [inc["x"], inc["y"]])
    if got != expected:
        raise RuntimeError(f"the re-simulated record is not this pair's scenario: {got} != {expected}")


def record_path(pair, approach):
    """The record this approach's run wrote: <pair>/<approach>/raw/<scenario>.json.gz, or, for a pair run before
    per-approach folders, the record both runs shared in <pair>/raw/."""
    name = pair["scenario"]["scenario_id"] + ".json.gz"
    own = os.path.join(approach_dir(pair["pair_id"], approach), "raw", name)
    shared = os.path.join(pair_dir(pair["pair_id"]), "raw", name)
    return shared if not os.path.exists(own) and os.path.exists(shared) else own


def record(pair, approach):
    """The record of this approach's run, or None -- also while a run in progress is rewriting it (a half-written gzip
    ends early: EOFError / zlib.error)."""
    path = record_path(pair, approach)
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, EOFError, zlib.error):
        return None


def comparison(pair):
    """(raw, None) when the comparison may be shown: both runs finished, each on its own record, and the two records
    have the same fingerprint (same scenario, schemes and results), each still as its run left it. Otherwise
    (None, reason) -- no values are shown from incomplete or inconsistent runs."""
    from demo import record_fingerprint
    runs = pair["runs"]
    waiting = [a for a in APPROACHES if runs[a]["status"] != "finished"]
    if waiting:
        return None, f"available after both runs have finished (waiting for: {', '.join(waiting)})"
    if runs["baseline"].get("fingerprint") != runs["proposed"].get("fingerprint"):
        return None, "the two runs did not replay the same record, so they are not compared"
    raws = {a: record(pair, a) for a in APPROACHES}
    if any(raw is None or record_fingerprint(raw) != runs[a]["fingerprint"] for a, raw in raws.items()):
        return None, "a run's record is missing or changed after the runs, so they are not compared"
    return raws["proposed"], None


METRICS = [   # (record key, label, unit, definition) -- metrics.py; values are copied from the record, never recomputed
    ("received", "Vehicles holding the verified alert", "vehicles",
     "vehicles that accepted the certified alert (the source included), of all vehicles"),
    ("reachability", "Reach", "% of reachable vehicles",
     "vehicles holding the alert / vehicles connected to the source by radio (unit disk, 300 m)"),
    ("t90_ms", "Time until 90 % of reachable vehicles hold it", "ms radio time",
     "from the incident; 'not reached' when 90 % never hold it"),
    ("transmissions", "Frames on air", "frames",
     "every frame sent: proposal, committee votes and alert copies (and a route head's local votes)"),
    ("collision_losses", "Receptions lost to collisions", "receptions", "copies destroyed by overlapping frames"),
    ("rsu_delay_ms", "First RSU registration", "ms radio time",
     "until an RSU registered the event: first valid copy decoded + 4.3 ms verification; 'not registered' if none did"),
    ("rsu_dup_copies", "Duplicate copies at RSUs", "copies", "copies of the registered event decoded later by the RSUs"),
    ("dup_rx", "Duplicate receptions at vehicles", "receptions", "copies decoded by vehicles that already held the alert"),
]


def _text(key, v, m, event):
    if v is None:
        return {"t90_ms": "not reached", "rsu_delay_ms": "not registered"}.get(key, "not available")
    if key == "received":
        return f"{int(v)}/{m['vehicles']}"
    if key == "reachability":
        return f"{100 * v:.1f} %"
    if key == "t90_ms":
        return f"{v:.1f} ms"
    if key == "rsu_delay_ms":
        return f"{event['receiving_rsu']} +{v:.1f} ms"
    return f"{v:.0f}"


def comparison_rows(pair, raw):
    """One row per implemented scheme of the pair's own record: the replayed baseline, the other baselines (same
    record, not replayed), the proposed method and its CH-to-CH route stage. Values are copied from the record."""
    base = pair["baseline"]
    rows = []
    for s in [base] + [b for b in BASELINES if b != base] + PROPOSED:
        role = ("baseline: replayed in this pair" if s == base else "baseline: same record, not replayed" if s in BASELINES
                else "proposed method: replayed" if s == "proposed" else "proposed method: its CH-to-CH route stage, replayed")
        P = raw["protocols"].get(s)
        if P is None:
            rows.append({"scheme": s, "label": config.LABELS[s], "role": role, "available": False,
                         "reason": "this scheme is not in the pair's run record", "cells": []})
            continue
        m, cells = P["metrics"], []
        for key, label, unit, _ in METRICS:
            v = m.get(key)
            v = None if v is None or (isinstance(v, float) and not math.isfinite(v)) else v
            cells.append({"key": key, "label": label, "unit": unit, "value": v, "text": _text(key, v, m, P["rsu_event"])})
        rows.append({"scheme": s, "label": config.LABELS[s], "role": role, "available": True, "cells": cells,
                     "rsu": P["rsu_event"]["receiving_rsu"] if P["rsu_event"] else None})
    return rows


# ---------------------------------------------------------------- one run at a time
def pid_alive(pid):
    """Is process `pid` running? (On Windows os.kill(pid, 0) would TERMINATE it, so the process is only queried.)"""
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)           # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel32.CloseHandle(handle)
        return bool(ok) and code.value == 259                        # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


STARTING_GRACE_S = 60     # a run the dashboard has just launched may take this long to report its process


def reconcile():
    """The active runs, after clearing what is stale: a lock whose process has ended is removed, and a run whose
    process ended without finishing is marked failed. Each active run: {pair_id, approach, pid, source: lock|status}."""
    lock_path = os.path.join(ROOT, ACTIVE)
    try:
        with open(lock_path, encoding="utf-8") as f:
            lock = json.load(f)
    except (OSError, ValueError):
        lock = None
    if lock and not pid_alive(lock.get("pid")):
        try:
            os.remove(lock_path)
        except OSError:
            pass
        lock = None
    active = [{**lock, "source": "lock"}] if lock else []
    for pair in pairs():
        for approach, r in pair["runs"].items():
            if r["status"] not in ("starting", "running"):
                continue
            requested = r.get("requested")
            young = (r["status"] == "starting" and requested is not None and
                     (datetime.now().astimezone() - datetime.fromisoformat(requested)).total_seconds() < STARTING_GRACE_S)
            if pid_alive(r.get("pid")) or young:
                active.append({"pair_id": pair["pair_id"], "approach": approach, "pid": r.get("pid"), "source": "status"})
            else:
                update_run(pair["pair_id"], approach, status="failed", finished=now(),
                           message="the demo process ended without finishing (stale run)")
    return active


def acquire(pair_id, approach):
    """Take the single run lock: refused while any other run is active (its own 'starting' entry is not another)."""
    os.makedirs(ROOT, exist_ok=True)
    others = [a for a in reconcile() if not (a["source"] == "status" and (a["pair_id"], a["approach"]) == (pair_id, approach))]
    if others:
        o = others[0]
        raise RuntimeError(f"another demo run is active: pair {o['pair_id']}, {o['approach']} (process {o['pid']}); "
                           f"wait for it to finish")
    try:
        fd = os.open(os.path.join(ROOT, ACTIVE), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError("another demo run started at the same moment; wait for it to finish") from None
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"pair_id": pair_id, "approach": approach, "pid": os.getpid(), "started": now()}, f)


def release():
    path = os.path.join(ROOT, ACTIVE)
    try:
        with open(path, encoding="utf-8") as f:
            mine = json.load(f).get("pid") == os.getpid()
        if mine:
            os.remove(path)
    except (OSError, ValueError):
        pass


def start(pair_id, approach, pace=None):
    """Start one separated run in its own process (SUMO-GUI opens); every write goes to this approach's own folder,
    its console output to <pair>/<approach>_console.log. Refused while another run is active. Returns the process ID."""
    pair = load(pair_id)
    schemes_for(approach, pair["baseline"])
    active = reconcile()
    if active:
        raise RuntimeError(f"another demo run is active: pair {active[0]['pair_id']}, {active[0]['approach']}; "
                           f"wait for it to finish")
    cmd = [sys.executable, os.path.join(HERE, "run.py"), "demo", "--pair", pair_id, "--approach", approach, "--no-wait"]
    if pace is not None:
        cmd += ["--pace", str(float(pace))]
    folder = pair_dir(pair_id)
    # 'starting' is written BEFORE the process exists, so the run's own first write can never be overwritten
    update_run(pair_id, approach, status="starting", pid=None, requested=now(), started=None, finished=None,
               message=None, fingerprint=None)
    with open(os.path.join(folder, f"{approach}_console.log"), "w", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, cwd=HERE, stdout=log, stderr=subprocess.STDOUT,
                                env={**os.environ, "EXP_RESULTS_DIR": approach_dir(pair_id, approach),
                                     "DEMO_PAIRS_DIR": ROOT})
    pair = load(pair_id)
    if pair["runs"][approach]["status"] == "starting":                # not yet taken over by the run itself
        pair["runs"][approach]["pid"] = proc.pid
        save(pair)
    threading.Thread(target=_reap, args=(pair_id, approach, proc), daemon=True).start()
    return proc.pid


def _reap(pair_id, approach, proc):
    """Record the exit code of a run started here; a run that exits non-zero before finishing is marked failed. Only
    this process's own entry is touched (never a newer run of the same approach)."""
    code = proc.wait()
    pair = load(pair_id)
    r = pair["runs"][approach]
    if r.get("pid") not in (proc.pid, None) and r["status"] in ("starting", "running"):
        return                                                       # a newer run already took over this entry
    r["exit_code"] = code
    if code != 0 and r["status"] in ("starting", "running"):
        r.update(status="failed", finished=now(), message=f"the demo process exited with code {code} "
                                                           f"(see {approach}_console.log in the pair's folder)")
    save(pair)
