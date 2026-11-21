"""
Block E: routing comparison on identical demand. Four headless SUMO sessions per seed, with the same routes, SUMO
seed and options (incident_response.session); only the incident handling differs:

  A  no incident                     B  incident, no rerouting
  C  incident, shortest-path reroute (the earlier method, baseline)    D  incident, route-preserving detour (default)

Every session ends at config.ROUTING_EVAL_END_S; the stopped vehicle never leaves, unfinished vehicles are written
by SUMO's tripinfo (write-unfinished) and reported. Vehicles are paired by ID across sessions. Groups are fixed at the
response instant from the stopped vehicle's actual edge (read-only, identical in B, C and D): 'ahead' = the incident
edge is still in the route, 'upstream' = already on it behind the stop, 'not_crossing' = neither (the noise-floor
group: SUMO's vehicles share random-number streams, so any change elsewhere also changes their trips).
Writes results/incident_routing/ only.
"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from multiprocessing import Pool

import numpy as np
from scipy import stats

import config
import incident_response as ir
from scenario import build

OUT = os.path.join("results", "incident_routing")
SESSIONS = {"A": None, "B": "none", "C": "shortest", "D": "detour"}
GROUPS = ("ahead", "upstream", "not_crossing")


def trips(path):
    """SUMO tripinfo, one entry per vehicle: finished trips and (write-unfinished) the ones still driving at the end."""
    out = {}
    for t in ET.parse(path).getroot().iter("tripinfo"):
        out[t.get("id")] = {"finished": float(t.get("arrival")) >= 0, "depart_s": float(t.get("depart")),
                            "duration_s": float(t.get("duration")), "length_m": float(t.get("routeLength"))}
    return out


def run_seed(args):
    """The four sessions of one seed; returns one row per vehicle and saves the session records."""
    density, run, out_dir, end_s = args
    run_id = f"d{density}_r{run:02d}"
    raw = ir.dissemination(density, run, out_dir)
    for sub in ("logs", "tripinfo", "sessions"):
        os.makedirs(os.path.join(out_dir, sub), exist_ok=True)
    res = {}
    with tempfile.TemporaryDirectory() as tmp:
        sc = build(density, run, workdir=tmp)
        routes, trust = os.path.join(tmp, "routes.rou.xml"), dict(zip(sc["ids"], sc["trust"]))
        follow = int(end_s - sc["incident_time_s"] - 2)           # the last step brings the clock to end_s
        for name, method in SESSIONS.items():
            ti = os.path.join(out_dir, "tripinfo", f"{run_id}_{name}.xml")
            res[name] = ir.session(raw, routes, trust, os.path.join(out_dir, "logs", f"{run_id}_{name}.log"), follow,
                                   method=method, stop=name != "A",
                                   extra=("--tripinfo-output", ti, "--tripinfo-output.write-unfinished", "true"))
            res[name]["trips"] = trips(ti)
    rows = vehicle_rows(raw, res)
    with open(os.path.join(out_dir, "sessions", run_id + ".json"), "w", encoding="utf-8") as fh:
        json.dump({k: {x: y for x, y in v.items() if x != "trips"} for k, v in res.items()}, fh)
    return rows


def vehicle_rows(raw, res):
    sc, B = raw["scenario"], res["B"]
    truth = B["ground_truth"]
    if not all(res[x]["ground_truth"] == truth for x in "CD"):
        raise RuntimeError(f"{sc['run_id']}: B, C and D differ before the response")    # identical demand and state
    detected = B["detection"] is not None
    rec = {x: {r["id"]: r for r in res[x]["vehicles"]} for x in "BCD"}
    ms = {x: res[x].get("compute_ms", {}) for x in "CD"}
    rows = []
    for v in sorted(res["A"]["trips"], key=lambda i: int(i[1:])):
        c, d = rec["C"].get(v, {}), rec["D"].get(v, {})
        row = {"run_id": sc["run_id"], "seed": sc["seed"], "detected": int(detected), "incident_edge": truth["edge"],
               "vehicle": v, "group": "stopped" if v == sc["source_id"] else truth["crossing"].get(v, "not_crossing"),
               "eligible": int(detected and v in rec["D"] and rec["D"][v]["accepted_alert"]
                               and rec["D"][v]["where"] == "ahead"),
               "outcome_C": c.get("outcome", ""), "outcome_D": d.get("outcome", ""), "reason_C": c.get("reason", ""),
               "reason_D": d.get("reason", ""),
               "splices_D": len(d.get("splices", [])), "probes_D": d.get("probes", ""),
               "planned_before_m": d.get("planned_before_m", ""), "planned_after_C_m": c.get("planned_after_m", ""),
               "planned_after_D_m": d.get("planned_after_m", ""), "compute_ms_C": ms["C"].get(v, ""),
               "compute_ms_D": ms["D"].get(v, ""), "odometer_D_m": d.get("odometer_m", "")}
        for x in "BCD":
            row[f"entries_{x}"] = rec[x].get(v, {}).get("entries_onto_incident_edge", "")
        row["depart_s"] = res["A"]["trips"][v]["depart_s"]
        for x in "ABCD":
            t = res[x]["trips"][v]
            row.update({f"finished_{x}": int(t["finished"]), f"duration_{x}_s": t["duration_s"],
                        f"length_{x}_m": t["length_m"]})
        rows.append(row)
    return rows


def _ci(per_seed):
    """Mean over seeds of the per-seed means and its 95% t-interval (seeds are independent; vehicles in one seed are
    not, so the seed is the unit). Returns (mean, low, high, n_seeds)."""
    x = np.array([m for m in per_seed if m is not None and np.isfinite(m)])
    if len(x) == 0:
        return (float("nan"),) * 3 + (0,)
    if len(x) == 1:
        return float(x[0]), float("nan"), float("nan"), 1
    low, high = stats.t.interval(0.95, len(x) - 1, loc=x.mean(), scale=stats.sem(x)) if x.std() > 0 else (x.mean(),) * 2
    return float(x.mean()), float(low), float(high), len(x)


def effects(rows, end_s, a, b):
    """Paired per-vehicle differences b - a (travel time, distance) by seed set and group. 'paired' = finished in both
    sessions. A vehicle finished in a but not in b is censored: its difference is at least (end - depart) - duration_a,
    which gives a lower bound on the mean over every vehicle finished in a."""
    out = []
    for seedset in ("detected", "undetected"):
        sel = [r for r in rows if r["detected"] == (seedset == "detected")]
        for group in GROUPS:
            g = [r for r in sel if r["group"] == group]
            both = [r for r in g if r[f"finished_{a}"] and r[f"finished_{b}"]]
            censored = [r for r in g if r[f"finished_{a}"] and not r[f"finished_{b}"]]
            row = {"seeds": seedset, "n_seeds": len({r["run_id"] for r in sel}), "comparison": f"{b} - {a}",
                   "group": group, "vehicles": len(g), "unfinished_reference": sum(not r[f"finished_{a}"] for r in g),
                   "unfinished_compared": sum(not r[f"finished_{b}"] for r in g), "paired": len(both)}
            for name, col in (("time_s", "duration_{}_s"), ("distance_m", "length_{}_m")):
                d = {r["vehicle"] + r["run_id"]: r[col.format(b)] - r[col.format(a)] for r in both}
                per_seed = [np.mean([d[r["vehicle"] + r["run_id"]] for r in both if r["run_id"] == s])
                            for s in sorted({r["run_id"] for r in both})]
                m, lo, hi, n = _ci(per_seed)
                row.update({f"mean_{name}": m, f"ci95_low_{name}": lo, f"ci95_high_{name}": hi, f"seeds_{name}": n,
                            f"pooled_median_{name}": float(np.median(list(d.values()))) if d else float("nan")})
            low = [r[f"duration_{b}_s"] - r[f"duration_{a}_s"] for r in both] +                   [(end_s - r["depart_s"]) - r[f"duration_{a}_s"] for r in censored]
            row["lower_bound_mean_time_incl_unfinished_s"] = float(np.mean(low)) if low else float("nan")
            out.append(row)
    return out


def rerouting(rows):
    """Per method (C shortest, D detour), detected seeds, eligible 'ahead' vehicles."""
    out = []
    for x, method in (("C", "shortest"), ("D", "detour")):
        e = [r for r in rows if r["detected"] and r["eligible"]]
        ok = [r for r in e if r[f"outcome_{x}"] == "rerouted"]
        extra = [r[f"planned_after_{x}_m"] - r["planned_before_m"] for r in ok]
        ms = [r[f"compute_ms_{x}"] for r in e if r[f"compute_ms_{x}"] != ""]
        reasons = {}
        for r in e:
            if r[f"outcome_{x}"] != "rerouted":
                key = r[f"reason_{x}"]
                reasons[key] = reasons.get(key, 0) + 1
        out.append({"method": method, "eligible_ahead": len(e), "rerouted": len(ok),
                    "success_rate": len(ok) / len(e) if e else float("nan"), "unable": len(e) - len(ok),
                    "entries_after_reroute": sum(int(r[f"entries_{x}"] or 0) for r in ok),
                    "planned_extra_mean_m": float(np.mean(extra)) if extra else "",
                    "planned_extra_median_m": float(np.median(extra)) if extra else "",
                    "planned_extra_min_m": min(extra) if extra else "", "planned_extra_max_m": max(extra) if extra else "",
                    "compute_ms_median": float(np.median(ms)) if ms else "",
                    "compute_ms_p95": float(np.percentile(ms, 95)) if ms else "", "compute_ms_max": max(ms) if ms else "",
                    "unable_reasons": json.dumps(reasons, sort_keys=True)})
    return out


def _write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


def load_rows(path):
    """per_vehicle.csv back as typed rows (numbers parsed, empty cells kept as '')."""
    def cell(v):
        for cast in (int, float):
            try:
                return cast(v)
            except ValueError:
                pass
        return v
    with open(path, newline="", encoding="utf-8") as fh:
        return [{k: cell(v) for k, v in r.items()} for r in csv.DictReader(fh)]


def main(density=config.DEMO_DENSITY, runs=config.RUNS_PER_DENSITY, end_s=config.ROUTING_EVAL_END_S, out_dir=OUT,
         workers=None, simulate=True):
    """simulate=False re-derives every table and figure from an existing per_vehicle.csv without re-running SUMO."""
    os.makedirs(out_dir, exist_ok=True)
    if simulate:
        jobs = [(density, r, out_dir, end_s) for r in range(runs)]
        with Pool(workers or min(len(jobs), os.cpu_count())) as pool:
            _write(os.path.join(out_dir, "per_vehicle.csv"),
                   [row for seed_rows in pool.imap(run_seed, jobs) for row in seed_rows])
    rows = load_rows(os.path.join(out_dir, "per_vehicle.csv"))            # every number below comes from this file
    eff = effects(rows, end_s, "A", "B") + effects(rows, end_s, "A", "C") + effects(rows, end_s, "A", "D") \
        + effects(rows, end_s, "C", "D")
    _write(os.path.join(out_dir, "travel_effects.csv"), eff)
    _write(os.path.join(out_dir, "rerouting.csv"), rerouting(rows))
    completion = []
    for s in sorted({r["run_id"] for r in rows}):
        sr = [r for r in rows if r["run_id"] == s and r["group"] != "stopped"]
        completion.append({"run_id": s, "detected": sr[0]["detected"], "vehicles": len(sr),
                           **{f"unfinished_{x}": sum(not r[f"finished_{x}"] for r in sr) for x in "ABCD"},
                           "C_equals_B": int(all(r["duration_C_s"] == r["duration_B_s"] for r in sr)),
                           "D_equals_B": int(all(r["duration_D_s"] == r["duration_B_s"] for r in sr))})
    _write(os.path.join(out_dir, "completion.csv"), completion)
    rev = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    with open(os.path.join(out_dir, "sessions", rows[0]["run_id"] + ".json"), encoding="utf-8") as fh:
        sumo_version = json.load(fh)["A"]["sumo"]
    with open(os.path.join(out_dir, "experiment_config.json"), "w", encoding="utf-8") as fh:
        json.dump({"command": f"python run.py incident-compare -d {density} --runs {runs} --end {end_s}",
                   "seeds": [f"d{density}_r{r:02d}" for r in range(runs)], "seed_rule": "10000 + 100*density + run",
                   "sumo": sumo_version,
                   "sessions": {"A": "no incident", "B": "incident, no rerouting", "C": "incident, shortest-path reroute",
                                "D": "incident, route-preserving detour"}, "end_s": end_s,
                   "sumo_options": "--step-length 1 --collision.action none --time-to-teleport -1 "
                                   "--tripinfo-output.write-unfinished true",
                   "parameters": {k: getattr(config, k) for k in ("CRASH_DECEL_MARGIN", "CRASH_STOP_SPEED",
                                                                   "BLOCKED_EDGE_TT_S", "TRUST_CH_THRESHOLD", "QUORUM",
                                                                   "COMMITTEE_SIZE", "ML_TRUST_MODE")},
                   "ci_method": "per seed: mean of the per-vehicle paired differences; then mean over seeds with a "
                                "two-sided 95% Student-t interval (df = seeds - 1); the seed is the unit",
                   "git_revision": rev + " (working tree has uncommitted changes)", "python": sys.version.split()[0],
                   "created_utc": datetime.now(timezone.utc).isoformat()}, fh, indent=1)
    draw(out_dir, rows, eff)
    return f"{len(rows)} vehicle rows from {runs} seeds -> {out_dir}"


SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = {"C": "#2a78d6", "D": "#eb6834"}                 # reference palette slots 1-2 (validated: CVD dE 24.7)
LABEL = {"A": "A no incident", "B": "B no rerouting", "C": "C shortest path", "D": "D detour"}


def _axes(ax, title):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=10, color=INK)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8.5)


def draw(out_dir, rows, eff):
    """Three static figures under <out_dir>/figures (every value is in the CSVs next to them)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig_dir = os.path.join(out_dir, "figures")
    os.makedirs(fig_dir, exist_ok=True)
    paths = []
    # 1 unfinished vehicles at the end, per session, detected vs undetected seeds (the stopped vehicle excluded)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), facecolor=SURFACE, sharey=True)
    for ax, det in zip(axes, (1, 0)):
        sel = [r for r in rows if r["detected"] == det and r["group"] != "stopped"]
        n = len({r["run_id"] for r in sel})
        vals = [sum(not r[f"finished_{x}"] for r in sel) for x in "ABCD"]
        ax.bar(range(4), vals, width=0.55, color=SERIES["C"], edgecolor=SURFACE, linewidth=2)
        for i, v in enumerate(vals):
            ax.text(i, v, f"{v}", ha="center", va="bottom", fontsize=9, color=INK)
        ax.set_xticks(range(4), [LABEL[x] for x in "ABCD"], fontsize=8)
        _axes(ax, f"{'Detected' if det else 'Undetected'} incident seeds (n = {n})")
    axes[0].set_ylabel(f"vehicles unfinished at {config.ROUTING_EVAL_END_S} s", color=INK2, fontsize=9)
    fig.tight_layout()
    paths.append(os.path.join(fig_dir, "unfinished.png"))
    fig.savefig(paths[-1], dpi=150)
    plt.close(fig)
    # 2 additional travel time vs A (paired, vehicles finished in both), detected seeds: mean of seed means, 95% CI
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), facecolor=SURFACE)
    for ax, group, title in zip(axes, ("ahead", "not_crossing"), ("Route crossed the incident edge ('ahead')",
                                                                     "Route never crossed it (noise floor)")):
        pts = [next(e for e in eff if e["seeds"] == "detected" and e["group"] == group and e["comparison"] == f"{x} - A")
               for x in "BCD"]
        for i, e in enumerate(pts):
            m, lo, hi = e["mean_time_s"], e["ci95_low_time_s"], e["ci95_high_time_s"]
            hollow = e["unfinished_compared"] > 0.05 * e["vehicles"]    # survivor-biased: many vehicles excluded
            ax.errorbar(i, m, yerr=[[m - lo], [hi - m]], fmt="o", ms=8, color=SERIES["C"], ecolor=SERIES["C"],
                        elinewidth=2, capsize=4, markeredgecolor=SERIES["C"] if hollow else SURFACE, markeredgewidth=2,
                        markerfacecolor=SURFACE if hollow else SERIES["C"])
            ax.text(i + 0.12, m, f"{m:+.0f} s\n[{lo:+.0f}, {hi:+.0f}]\npaired {e['paired']}\nunfinished "
                                 f"{e['unfinished_compared']}", va="center", fontsize=7.5, color=INK2)
        ax.axhline(0, color=INK2, linewidth=0.8)
        ax.set_xticks(range(3), [LABEL[x] for x in "BCD"], fontsize=8)
        ax.set_xlim(-0.4, 2.9)
        _axes(ax, title)
    axes[0].set_ylabel("additional travel time vs A (s)", color=INK2, fontsize=9)
    fig.text(0.01, 0.01, "Detected seeds; mean of per-seed means, 95% t-interval over seeds.\nHollow: more than 5% of "
                         "the group unfinished and excluded, so the paired mean is survivor-biased (lower bounds: "
                         "travel_effects.csv).", fontsize=7.5, color=INK2)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    paths.append(os.path.join(fig_dir, "additional_time.png"))
    fig.savefig(paths[-1], dpi=150)
    plt.close(fig)
    # 3 planned extra distance per rerouted vehicle (route geometry only, no traffic noise): C vs D on one axis
    fig, ax = plt.subplots(figsize=(9, 2.8), facecolor=SURFACE)
    rng = np.random.default_rng(0)                         # jitter for legibility only
    for i, x in enumerate("CD"):
        vals = [r[f"planned_after_{x}_m"] - r["planned_before_m"] for r in rows
                if r["detected"] and r["eligible"] and r[f"outcome_{x}"] == "rerouted"]
        ax.scatter(vals, i + rng.uniform(-0.18, 0.18, len(vals)), s=14, color=SERIES[x], alpha=0.55, linewidths=0,
                   label=f"{LABEL[x]} (n = {len(vals)}, median {np.median(vals):+.0f} m)")
    ax.axvline(0, color=INK2, linewidth=0.8)
    ax.set_yticks([0, 1], [LABEL["C"], LABEL["D"]], fontsize=8.5)
    ax.set_xlabel("planned remaining route length after - before rerouting (m)", color=INK2, fontsize=9)
    _axes(ax, "Planned extra distance per rerouted vehicle (detected seeds)")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    fig.tight_layout()
    paths.append(os.path.join(fig_dir, "planned_extra_distance.png"))
    fig.savefig(paths[-1], dpi=150)
    plt.close(fig)
    return paths
