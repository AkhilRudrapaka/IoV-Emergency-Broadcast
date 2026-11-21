"""
Block F: adversarial evaluation sweeps. Each setting is one `python run.py experiment` in its own folder
results/adversarial/<sweep>/<setting>/ with EXP_ overrides (scalars only), so the tracked results/urban are never
touched; summarise() reads the folders back into per-run CSVs and aggregated CSVs (mean, 95% CI over runs).

  A              relay dropping: MALICIOUS_RATIO x MALICIOUS_DROP_PROB x MALICIOUS_COOPERATION
  B              forged alerts: MALICIOUS_RATIO x MALICIOUS_COOPERATION x MAX_COLLUDERS (committee level on)
  C_calibration  held-out seeds 30-59: TRUST_CH_THRESHOLD for an i.i.d. (p = 0.9) and a phased (duty 0.9, 30 s) attacker
  C              phased on-off: MALICIOUS_RATIO x ONOFF_DUTY x ONOFF_PERIOD_S (committee level on)
  C_gate         seeds 0-29 at the gate calibrate() chose, same two attackers as C_calibration
  D              collusion has no sweep of its own: colluder endorsement (B) and vote withholding (B, C) are read
                 from the same runs
Block G sweeps (BLOCK_G_SECURITY_HARDENING_PLAN.md, section 8) write to results/hardening/:
  G1   the B and C settings with ENFORCE_COMMITTEE=1
  G2   committee size/quorum 5/3, 7/4, 9/5 and the 7/3 contrast (MAX_COLLUDERS = size), committee enforced
  G3a  TRUST_BURST_K 3-6 on held-out runs 30-59 (calibrate_burst picks k); G3b  the chosen k on the C and B(0.9) settings
  G4   the configuration select_committee and calibrate_burst chose, on the B and C settings
The selection rules are fixed in PREREGISTERED (written to results/hardening before any Block G sweep runs).
Trust here is the existing Beta watchdog reputation. The VeReMi ML detector is not used anywhere in this module.
"""
import csv
import glob
import gzip
import itertools
import json
import os
import subprocess
import sys

import numpy as np
from scipy import stats

import config
from metrics import summarize

OUT = os.path.join("results", "adversarial")
HARDENING = os.path.join("results", "hardening")
DENSITIES = [100, 200, 300]
SCHEMES = ["flooding", "slotted1p", "proposed", "no_reputation", "no_cluster_forwarding", "ch_route"]
GATES = [0.70, 0.75, 0.80, 0.84, 0.86, 0.88, 0.90]
ALIAS = {"MALICIOUS_RATIO": "ratio", "MALICIOUS_DROP_PROB": "pdrop", "MALICIOUS_COOPERATION": "coop",
         "MAX_COLLUDERS": "colluders", "ONOFF_PERIOD_S": "period", "ONOFF_DUTY": "duty", "TRUST_CH_THRESHOLD": "gate",
         "COMMITTEE_CHECK": "cc", "COMMITTEE_SIZE": "m", "QUORUM": "q", "ENFORCE_COMMITTEE": "enf",
         "TRUST_BURST_K": "k"}
COMMITTEES = [(5, 3), (7, 4), (9, 5), (7, 3)]          # G2; (7, 3) is the lower-quorum contrast
COMMITTEE_CANDIDATES = [(5, 3), (7, 4), (9, 5)]          # selectable (plan 4.1: majority quorum); 7/3 is never
ADOPTION_RULE = ("plan section 8 criterion 2 (genuine acceptance and delivery not lower than Block F on any seed) applied "
                 "to every genuine path of the proposed design: the proposed broadcast (G2_admissible criterion 2) and "
                 "the CH route (honest delivery and relayed RSU reception, strict, on seeds where both accepted the "
                 "genuine alert). Stated in G2_RESULTS_REPORT.md section 7 before this correction.")
BURST_KS = [3, 4, 5, 6]                                 # G3a candidates
G3B_COMPARISON_GATE = 0.75                              # count gate compared with the detector in G3b (G3a report)
BURST_ATTACKERS = [{"MALICIOUS_COOPERATION": 0.9}, {"ONOFF_PERIOD_S": 30.0, "ONOFF_DUTY": 0.8},
                   {"ONOFF_PERIOD_S": 30.0, "ONOFF_DUTY": 0.9}, {"ONOFF_PERIOD_S": 30.0, "ONOFF_DUTY": 0.95},
                   {"ONOFF_PERIOD_S": 10.0, "ONOFF_DUTY": 0.9}]
PREREGISTERED = {
    "written": "before any Block G sweep was run",
    "G3a_rule": "k = the smallest of 3, 4, 5, 6 for which, in every G3a setting (5 attackers) and at every density, the "
                "mean over runs of the share of honest vehicles flagged by the burst detector is <= 0.01. No such k: "
                "G3 is negative, G3b is not run and G4 has no detector.",
    "G2_admissible": "criterion 1: in every G2 cell with a Block F reference (per-second 0.9 at 10/20/30 %; phased 0.9/30 s "
                     "at 10/20 %), the default-level forgery acceptance rate is <= Block F's default-level rate at every "
                     "density. Criterion 2: no seed where Block F accepted the genuine alert and G2 did not, unless G2 had "
                     ">= m - q + 1 attackers on the committee (the withholding rule; reported); and no seed where both "
                     "accepted and the proposed scheme's honest delivery is lower than in Block F (strict). Cells without "
                     "a Block F reference (phased 0.9/30 s at 30 %) are reported but not used in either criterion.",
    "G2_selection": "among admissible configurations (5/3 included): highest pooled genuine acceptance over all G2 runs; "
                    "then lowest pooled default-level forgery acceptance; then the smallest committee.",
    "G4": "the selected committee + ENFORCE_COMMITTEE=1 + the G3a k (if any) on the 18 B and 16 C settings, with "
          "MAX_COLLUDERS = max(setting value, committee size). If the selection is 5/3 without a detector, G4 equals G1 "
          "and is not run again.",
    "adoption": "plan section 8: no weakening, genuine availability (paired), honest false alarm <= 1 %, everything "
                "reported, no default changed.",
}
ONOFF_ATTACKERS = [{"MALICIOUS_COOPERATION": 0.9}, {"ONOFF_PERIOD_S": 30.0, "ONOFF_DUTY": 0.9}]


def product(**axes):
    return [dict(zip(axes, values)) for values in itertools.product(*axes.values())]


def sweeps(gate=None):
    """name -> (first run index, list of settings). C_gate needs the gate chosen by calibrate()."""
    out = {
        "A": (0, product(MALICIOUS_RATIO=[0.1, 0.2, 0.3], MALICIOUS_DROP_PROB=[0.25, 0.5, 1.0],
                         MALICIOUS_COOPERATION=[0.0, 0.9])),
        "B": (0, [dict(s, COMMITTEE_CHECK=1) for s in product(MALICIOUS_RATIO=[0.1, 0.2, 0.3],
                                                              MALICIOUS_COOPERATION=[0.0, 0.5, 0.9], MAX_COLLUDERS=[3, 5])]),
        "C_calibration": (30, [dict(a, MALICIOUS_RATIO=0.1, TRUST_CH_THRESHOLD=g, COMMITTEE_CHECK=1)
                               for a in ONOFF_ATTACKERS for g in GATES]),
        "C": (0, [dict(s, COMMITTEE_CHECK=1) for s in product(MALICIOUS_RATIO=[0.1, 0.2], ONOFF_DUTY=[0.5, 0.8, 0.9, 0.95],
                                                              ONOFF_PERIOD_S=[10.0, 30.0])]),
    }
    if gate is not None:
        out["C_gate"] = (0, [dict(a, MALICIOUS_RATIO=0.1, TRUST_CH_THRESHOLD=gate, COMMITTEE_CHECK=1)
                             for a in ONOFF_ATTACKERS])
    return out


def g_sweeps(burst_k=None, committee=None):
    """Block G sweeps (results/hardening). G3b needs the calibrated k, G4 the selected committee."""
    bc = sweeps()["B"][1] + sweeps()["C"][1]
    out = {"G1": (0, [dict(s, ENFORCE_COMMITTEE=1) for s in bc]),
           "G2": (0, [dict(a, MALICIOUS_RATIO=r, COMMITTEE_SIZE=m, QUORUM=q, MAX_COLLUDERS=m, ENFORCE_COMMITTEE=1,
                           COMMITTEE_CHECK=1) for m, q in COMMITTEES for r in (0.1, 0.2, 0.3) for a in ONOFF_ATTACKERS]),
           "G3a": (30, [dict(a, MALICIOUS_RATIO=0.1, TRUST_BURST_K=k, COMMITTEE_CHECK=1)
                        for k in BURST_KS for a in BURST_ATTACKERS])}
    if burst_k:
        g3b = sweeps()["C"][1] + [dict(MALICIOUS_RATIO=r, MALICIOUS_COOPERATION=0.9, MAX_COLLUDERS=5, COMMITTEE_CHECK=1)
                                  for r in (0.1, 0.2, 0.3)]
        out["G3b"] = (0, [dict(s, TRUST_BURST_K=burst_k) for s in g3b])
        # approved comparison arm: the same settings with a count gate instead of the detector (no TRUST_BURST_K)
        out["G3b_gate"] = (0, [dict(s, TRUST_CH_THRESHOLD=G3B_COMPARISON_GATE) for s in g3b])
    if committee:
        m, q = committee
        extra = dict(COMMITTEE_SIZE=m, QUORUM=q, ENFORCE_COMMITTEE=1, **({"TRUST_BURST_K": burst_k} if burst_k else {}))
        g4 = [dict(s, **extra, MAX_COLLUDERS=max(s.get("MAX_COLLUDERS", 5), m)) for s in bc]
        # max() maps the 3-colluder B settings onto the m-colluder ones (same folder name): keep each setting once,
        # else the sweep skips the copy as finished and summarise() collects that folder twice
        out["G4"] = (0, list({name(s): s for s in g4}.values()))
    return out


def name(setting):
    return "_".join(f"{ALIAS[k]}{v:g}" for k, v in setting.items())


def run_setting(folder, setting, densities, runs, first):
    """One `run.py experiment` with this setting's overrides; skipped when the folder already holds a finished run."""
    if os.path.exists(os.path.join(folder, "summaries", "experiment_config.json")):
        return False
    env = {**os.environ, **{f"EXP_{k}": str(v) for k, v in setting.items()}, "EXP_RESULTS_DIR": folder}
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.py"), "experiment",
                    "--densities", *map(str, densities), "--runs", str(runs), "--first-run", str(first), "--no-report"],
                   env=env, check=True, stdout=subprocess.DEVNULL)
    return True


def _csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def auc_low_trust(trust, malicious):
    """P(an attacker's trust < an honest vehicle's trust), ties counted half: how well low trust singles out attackers."""
    trust, malicious = np.asarray(trust, float), np.asarray(malicious, bool)
    if malicious.all() or not malicious.any():
        return float("nan")
    ranks = stats.rankdata(-trust)                              # rank 1 = highest trust
    n1, n0 = malicious.sum(), (~malicious).sum()
    return float((ranks[malicious].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def collect(folder, setting):
    """Per-run rows of one finished setting: genuine dissemination per scheme, trust and roles, forged-alert levels."""
    params = json.load(open(os.path.join(folder, "summaries", "experiment_config.json"), encoding="utf-8"))["parameters"]
    gate, quorum, size = params["TRUST_CH_THRESHOLD"], params["QUORUM"], params["COMMITTEE_SIZE"]
    base = {"setting": name(setting), **{k: params.get(k, 0) for k in ALIAS}}   # every parameter as actually used
    # eligibility = Beta trust at or above the gate and not burst-flagged (Block G); the Beta trust itself is unchanged
    elig = lambda v: v["trust"] >= gate and not v.get("burst_flagged", False)
    runs = {(r["run_id"], r["protocol"]): r for r in _csv(os.path.join(folder, "processed", "runs.csv"))}
    forged_path = os.path.join(folder, "processed", "forgery_runs.csv")
    forged = {(r["run_id"], r["variant"]): r for r in _csv(forged_path)} if os.path.exists(forged_path) else {}
    genuine, trust, forgery = [], [], []
    for path in sorted(glob.glob(os.path.join(folder, "raw", "d*_r*.json.gz"))):
        if "__" in os.path.basename(path):
            continue                                            # interactive archive copies, not matrix runs
        with gzip.open(path, "rt") as fh:
            raw = json.load(fh)
        sc = raw["scenario"]
        mal = {v["id"]: v["malicious"] for v in sc["vehicles"]}
        by_id = {v["id"]: v for v in sc["vehicles"]}
        key = {"run_id": sc["run_id"], "density": sc["density"], "run": sc["run"], "seed": sc["seed"]}
        for scheme in SCHEMES:
            m, rec = runs[(sc["run_id"], scheme)], raw["protocols"][scheme]
            reach = float(m["honest_reachable"])
            genuine.append({**base, **key, "scheme": scheme,
                            "honest_delivery": float(m["honest_reached"]) / reach if reach else float("nan"),
                            **{k: float(m[k]) for k in ("accepted", "quorum_ms", "t90_ms", "reachability",
                                                        "rsu_relay_received", "transmissions", "vote_tx")},
                            "dropped": sum(v["decision"] == "DROP" for v in rec["vehicles"])})
        t = [v["trust"] for v in sc["vehicles"]]
        m_ = [v["malicious"] for v in sc["vehicles"]]
        att, hon = [x for x, b in zip(t, m_) if b], [x for x, b in zip(t, m_) if not b]
        heads = [v for v in sc["vehicles"] if v["role"] == "CH"]
        route = [v for v in raw["infrastructure"]["route"].get("vehicle_ids", [])[1:] if v in mal]
        cor = raw["protocols"]["proposed"]["corroboration"] or {}
        signers = (cor.get("certificate") or {}).get("signers", [])[1:]
        burst = "burst_flagged" in sc["vehicles"][0]
        share = lambda vs, f: float(np.mean([f(v) for v in vs])) if vs and burst else float("nan")
        att_v, hon_v = [v for v in sc["vehicles"] if v["malicious"]], [v for v in sc["vehicles"] if not v["malicious"]]
        trust.append({**base, **key, "attackers": len(att), "trust_auc": auc_low_trust(t, m_),
                      "attackers_below_gate": float(np.mean([x < gate for x in att])) if att else float("nan"),
                      "honest_below_gate": float(np.mean([x < gate for x in hon])) if hon else float("nan"),
                      "attacker_share_of_heads": float(np.mean([v["malicious"] for v in heads])) if heads else float("nan"),
                      "attackers_on_ch_route": sum(mal[v] for v in route),
                      "attackers_in_committee": sum(mal[v] for v in cor.get("committee", [])),
                      "genuine_votes": len(cor.get("votes_counted", [])),
                      "genuine_accepted": float(bool(cor.get("accepted"))),
                      "genuine_passes_committee_check": float(bool(cor.get("accepted")) and sum(
                          s in cor["committee"] and elig(by_id[s]) for s in signers) >= quorum),
                      "committee_size": len(cor.get("committee", [])),
                      "committee_full": float(len(cor.get("committee", [])) >= size),
                      "committee_below_quorum": float(len(cor.get("committee", [])) < quorum),
                      "attackers_ineligible": float(np.mean([not elig(v) for v in att_v])) if att_v else float("nan"),
                      "honest_ineligible": float(np.mean([not elig(v) for v in hon_v])) if hon_v else float("nan"),
                      "attackers_flagged": share(att_v, lambda v: v["burst_flagged"]),
                      "honest_flagged": share(hon_v, lambda v: v["burst_flagged"]),
                      "attackers_flag_only": share(att_v, lambda v: v["burst_flagged"] and v["trust"] >= gate),
                      "honest_flag_only": share(hon_v, lambda v: v["burst_flagged"] and v["trust"] >= gate)})
        for variant, rec in ((raw.get("forgery") or {}).get("variants") or {}).items():
            c, f = rec["corroboration"] or {}, forged[(sc["run_id"], variant)]
            endorsers = (c.get("certificate") or {}).get("signers", [])[1:]
            reputable = [s for s in endorsers if elig(by_id[s])]
            forgery.append({**base, **key, "variant": variant, "forger": f["forger"], "colluders": int(f["colluders"]),
                            **{k: float(f[k]) for k in ("certificate_formed", "accepted_share", "rsu_registered",
                                                        "transmissions")},
                            "accepted": float(bool(c.get("accepted"))), "endorsers": len(endorsers),
                            "reputable_endorsers": len(reputable),
                            "reputable_endorsers_in_committee": sum(s in c.get("committee", []) for s in reputable),
                            "attackers_in_committee": sum(mal[v] for v in c.get("committee", []))})
    return genuine, trust, forgery


def aggregate(rows, by, metrics):
    """Mean, std, 95% CI half-width and n over runs (metrics.summarize, as for the published results) per group."""
    out = []
    for group in sorted({tuple(r[k] for k in by) for r in rows}, key=str):
        sel = [r for r in rows if tuple(r[k] for k in by) == group]
        row = {**dict(zip(by, group)), "runs": len(sel)}
        for k in metrics:
            mean, std, ci, n = summarize([r[k] for r in sel])
            row.update({k: mean, f"{k}_std": std, f"{k}_ci95": ci, f"{k}_n": n})
        out.append(row)
    return out


def _write(path, rows):
    if not rows:
        return None
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


def summarise(sweep, settings, out_dir=OUT):
    """Per-run and aggregated CSVs of one sweep: <sweep>_{genuine,trust,forgery}_runs.csv and _summary.csv."""
    genuine, trust, forgery = [], [], []
    for s in settings:
        folder = os.path.join(out_dir, sweep, name(s))
        if os.path.exists(os.path.join(folder, "summaries", "experiment_config.json")):
            g, t, f = collect(folder, s)
            genuine, trust, forgery = genuine + g, trust + t, forgery + f
    keys = ["setting", *ALIAS, "density"]
    paths = [_write(os.path.join(out_dir, f"{sweep}_{kind}_runs.csv"), rows)
             for kind, rows in (("genuine", genuine), ("trust", trust), ("forgery", forgery))]
    paths += [_write(os.path.join(out_dir, f"{sweep}_genuine_summary.csv"), aggregate(genuine, keys + ["scheme"], [
                  "honest_delivery", "accepted", "quorum_ms", "t90_ms", "rsu_relay_received", "transmissions", "dropped",
                  "vote_tx"])),
              _write(os.path.join(out_dir, f"{sweep}_trust_summary.csv"), aggregate(trust, keys, [
                  "trust_auc", "attackers_below_gate", "honest_below_gate", "attacker_share_of_heads",
                  "attackers_on_ch_route", "attackers_in_committee", "genuine_accepted", "genuine_passes_committee_check",
                  "committee_size", "committee_full", "committee_below_quorum", "attackers_ineligible",
                  "honest_ineligible", "attackers_flagged", "honest_flagged", "attackers_flag_only",
                  "honest_flag_only"])),
              _write(os.path.join(out_dir, f"{sweep}_forgery_summary.csv"), aggregate(forgery, keys + ["variant"], [
                  "certificate_formed", "accepted", "accepted_share", "rsu_registered", "reputable_endorsers",
                  "reputable_endorsers_in_committee"]))]
    return [p for p in paths if p]


def calibrate(out_dir=OUT):
    """Smallest gate whose held-out runs (C_calibration) accept no forged alert at the full default level for both
    attackers at every density, while the genuine alert is accepted at least as often as at the 0.70 gate."""
    forged = _csv(os.path.join(out_dir, "C_calibration_forgery_summary.csv"))
    trust = _csv(os.path.join(out_dir, "C_calibration_trust_summary.csv"))
    genuine = lambda g: [float(r["genuine_accepted"]) for r in trust if float(r["TRUST_CH_THRESHOLD"]) == g]
    chosen = None
    for g in GATES:
        accepted = [float(r["accepted"]) for r in forged if float(r["TRUST_CH_THRESHOLD"]) == g
                    and r["variant"] == "voting_reputation"]
        if accepted and max(accepted) == 0 and min(genuine(g)) >= min(genuine(GATES[0])):
            chosen = g
            break
    record = {"chosen_gate": chosen, "candidates": GATES, "seeds": "runs 30-59 (held out)",
              "rule": "smallest gate with no forged alert accepted at the default full level (both attackers, every "
                      "density) and a genuine acceptance rate no lower than at the 0.70 gate"}
    with open(os.path.join(out_dir, "C_calibration_choice.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
    return chosen


def calibrate_burst(out_dir=HARDENING):
    """PREREGISTERED["G3a_rule"]: smallest k whose honest burst-flag share (mean over runs) is <= 1 % in every G3a
    setting at every density. Writes G3a_calibration_choice.json; returns k or None."""
    trust = _csv(os.path.join(out_dir, "G3a_trust_summary.csv"))
    worst = {k: max(float(r["honest_flagged"]) for r in trust if int(float(r["TRUST_BURST_K"])) == k) for k in BURST_KS}
    chosen = next((k for k in BURST_KS if worst[k] <= 0.01), None)
    record = {"chosen_k": chosen, "candidates": BURST_KS, "worst_mean_honest_flagged": worst,
              "rule": PREREGISTERED["G3a_rule"], "seeds": "runs 30-59 (held out)"}
    with open(os.path.join(out_dir, "G3a_calibration_choice.json"), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
    return chosen


def _cell(r):
    """A G2/Block F cell: attacker share and attacker model (per-second cooperation, phase period and duty)."""
    return (round(float(r["MALICIOUS_RATIO"]), 3), round(float(r["MALICIOUS_COOPERATION"]), 3),
            round(float(r["ONOFF_PERIOD_S"]), 3), round(float(r["ONOFF_DUTY"]), 3))


def select_committee(out_dir=HARDENING, reference=OUT, out_name="G2_selection_corrected.json"):
    """PREREGISTERED["G2_admissible"] and ["G2_selection"] applied to the G2 runs against the Block F runs (B and C,
    MAX_COLLUDERS 5), over the approved candidates only (COMMITTEE_CANDIDATES; 7/3 is reported as a contrast and is
    never selectable). "selection_rule_choice" is the registered rule exactly. "chosen" additionally requires plan
    section 8 criterion 2 on the CH route (ADOPTION_RULE); None when no candidate qualifies. Writes out_name (the
    historical G2_selection.json is never written); returns (m, q) or None."""
    g_tr, g_fg, g_gn = (_csv(os.path.join(out_dir, f"G2_{k}_runs.csv")) for k in ("trust", "forgery", "genuine"))
    ref_tr = [r for s in ("B", "C") for r in _csv(os.path.join(reference, f"{s}_trust_runs.csv"))
              if int(float(r["MAX_COLLUDERS"])) == 5]
    ref_fg = [r for s in ("B", "C") for r in _csv(os.path.join(reference, f"{s}_forgery_runs.csv"))
              if int(float(r["MAX_COLLUDERS"])) == 5 and r["variant"] == "voting_reputation"]
    ref_all = [r for s in ("B", "C") for r in _csv(os.path.join(reference, f"{s}_genuine_runs.csv"))
               if int(float(r["MAX_COLLUDERS"])) == 5]
    ref_gn = [r for r in ref_all if r["scheme"] == "proposed"]
    ref_ch = {(_cell(r), r["run_id"]): r for r in ref_all if r["scheme"] == "ch_route" and float(r["accepted"]) == 1}
    ref_cells = {_cell(r) for r in ref_tr}
    num = lambda x: float(x) if x not in ("", "nan") else None
    rows = {}
    for m, q in COMMITTEES:
        mine = lambda rs: [r for r in rs if int(float(r["COMMITTEE_SIZE"])) == m and int(float(r["QUORUM"])) == q]
        tr, fg = mine(g_tr), [r for r in mine(g_fg) if r["variant"] == "voting_reputation"]
        gn = [r for r in mine(g_gn) if r["scheme"] == "proposed"]
        c1 = []
        for cell in sorted({_cell(r) for r in tr} & ref_cells):
            for d in sorted({r["density"] for r in tr}):
                rate = lambda rs: sum(float(r["accepted"]) for r in rs if _cell(r) == cell and r["density"] == d) / max(
                    1, sum(1 for r in rs if _cell(r) == cell and r["density"] == d))
                if rate(fg) > rate(ref_fg):
                    c1.append({"cell": cell, "density": d, "g2": rate(fg), "block_f": rate(ref_fg)})
        ref_acc = {(_cell(r), r["run_id"]): float(r["genuine_accepted"]) for r in ref_tr}
        ref_del = {(_cell(r), r["run_id"]): float(r["honest_delivery"]) for r in ref_gn if float(r["accepted"]) == 1}
        withheld, c2 = [], []
        for r in tr:
            key = (_cell(r), r["run_id"])
            if key in ref_acc and ref_acc[key] == 1 and float(r["genuine_accepted"]) == 0:
                (withheld if float(r["attackers_in_committee"]) >= m - q + 1 else c2).append(
                    {"cell": key[0], "run_id": key[1], "attackers_in_committee": float(r["attackers_in_committee"]),
                     "committee_size": float(r["committee_size"])})
        for r in gn:
            key = (_cell(r), r["run_id"])
            if key in ref_del and float(r["accepted"]) == 1 and float(r["honest_delivery"]) < ref_del[key]:
                c2.append({"cell": key[0], "run_id": key[1], "delivery": float(r["honest_delivery"]),
                           "block_f_delivery": ref_del[key]})
        ch = []                                           # ADOPTION_RULE: the CH route, seeds where both accepted
        for r in mine(g_gn):
            key = (_cell(r), r["run_id"])
            if r["scheme"] != "ch_route" or key not in ref_ch or float(r["accepted"]) != 1:
                continue
            for k in ("honest_delivery", "rsu_relay_received"):
                new, old = num(r[k]), num(ref_ch[key][k])
                if new is not None and old is not None and new < old:
                    ch.append({"cell": key[0], "run_id": key[1], "metric": k, "g2": new, "block_f": old})
        candidate, admissible = (m, q) in COMMITTEE_CANDIDATES, not c1 and not c2
        rows[f"{m}/{q}"] = {"m": m, "q": q, "candidate": candidate, "admissible": admissible,
                            "adoptable": candidate and admissible and not ch, "criterion1_violations": c1,
                            "criterion2_violations": c2, "withholding_explained_regressions": withheld,
                            "ch_route_violations": ch,
                            "pooled_genuine_accepted": sum(float(r["genuine_accepted"]) for r in tr) / len(tr),
                            "pooled_default_forgery_accepted": sum(float(r["accepted"]) for r in fg) / len(fg)}
    rank = lambda vs: max(vs, key=lambda v: (v["pooled_genuine_accepted"], -v["pooled_default_forgery_accepted"],
                                             -v["m"]), default=None)
    pick = lambda v: [v["m"], v["q"]] if v else None
    best = rank([v for v in rows.values() if v["candidate"] and v["adoptable"]])
    record = {"chosen": pick(best),
              "selection_rule_choice": pick(rank([v for v in rows.values() if v["candidate"] and v["admissible"]])),
              "eligible_candidates": [f"{m}/{q}" for m, q in COMMITTEE_CANDIDATES],
              "contrast_only": [f"{m}/{q}" for m, q in COMMITTEES if (m, q) not in COMMITTEE_CANDIDATES],
              "candidates": rows, "admissible_rule": PREREGISTERED["G2_admissible"],
              "selection_rule": PREREGISTERED["G2_selection"], "adoption_rule": ADOPTION_RULE,
              "correction": "G2_selection.json (kept as the historical record) chose 7/3 because the coded candidate "
                            "list included the 7/3 contrast arm, and it had no way to select nothing."}
    with open(os.path.join(out_dir, out_name), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1)
    return (best["m"], best["q"]) if best else None


def _choices(out_dir):
    read = lambda f, k: json.load(open(os.path.join(out_dir, f), encoding="utf-8"))[k]         if os.path.exists(os.path.join(out_dir, f)) else None
    committee = read("G2_selection_corrected.json", "chosen")
    return read("G3a_calibration_choice.json", "chosen_k"), tuple(committee) if committee else None


def main(sweep, densities=DENSITIES, runs=30, out_dir=None, summarise_only=False):
    gate = None
    out_dir = out_dir or (HARDENING if sweep.startswith("G") else OUT)
    if sweep.startswith("G"):
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "PREREGISTERED_RULES.json")
        if not os.path.exists(path):                         # written once, before the first Block G sweep
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(PREREGISTERED, fh, indent=1)
        k, committee = _choices(out_dir)
        if sweep in ("G3b", "G3b_gate") and not k:
            return "G3a chose no k (or has not run): G3b is not run"
        if sweep == "G4" and not committee:
            return "G2 has not selected a committee: G4 is not run"
        if sweep == "G4" and tuple(committee) == (5, 3) and not k:
            return "selection is 5/3 without a detector: G4 equals G1 and is not run again (PREREGISTERED['G4'])"
        table = g_sweeps(k, committee)
    else:
        if sweep == "C_gate":
            with open(os.path.join(out_dir, "C_calibration_choice.json"), encoding="utf-8") as fh:
                gate = json.load(fh)["chosen_gate"]
            if gate is None:
                return "C_calibration chose no gate: nothing to evaluate"
        table = sweeps(gate)
    first, settings = table[sweep]
    done = 0
    if not summarise_only:
        for i, s in enumerate(settings, 1):
            done += run_setting(os.path.join(out_dir, sweep, name(s)), s, densities, runs, first)
            print(f"  [{i}/{len(settings)}] {sweep} {name(s)}", flush=True)
    paths = summarise(sweep, settings, out_dir)
    msg = f"{sweep}: {len(settings)} settings ({done} run now), runs {first}..{first + runs - 1}, densities {densities}"
    if sweep == "C_calibration" and paths:
        msg += f"; chosen gate: {calibrate(out_dir)}"
    if sweep == "G3a" and paths:
        msg += f"; chosen k: {calibrate_burst(out_dir)}"
    if sweep == "G2" and paths:
        msg += f"; selected committee: {select_committee(out_dir)}"
    return msg + "\n" + "\n".join(paths)
