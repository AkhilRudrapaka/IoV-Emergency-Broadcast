"""G3a burst-detector calibration analysis behind results/hardening/G3A_CALIBRATION_REPORT.md (read-only).

    python -X utf8 results/hardening/analysis/g3a_calibration.py      (run from the project root)

Held-out runs 30-59, 10 % attackers, gate 0.70. k = 0 reference (no detector) on the same seeds exists only for
per-second 0.9 and phased 0.9/30 s: Block F C_calibration at gate 0.70 (results/adversarial, never modified).
Means: mean ± 95 % Student-t half-width over runs (metrics.summarize), n = runs; paired: exact sign test."""
import collections, csv, glob, gzip, json, os, sys
import numpy as np
sys.path.insert(0, os.getcwd())
import adversarial
from channel import geometry
from clustering import elect_roles
from metrics import summarize
from scipy.stats import binomtest

H, F = os.path.join("results", "hardening"), os.path.join("results", "adversarial")
GATE, KS, D = 0.70, adversarial.BURST_KS, (100, 200, 300)
L = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))
att = lambda r: (f"phased {float(r['ONOFF_DUTY']):g}/{float(r['ONOFF_PERIOD_S']):g} s" if float(r["ONOFF_PERIOD_S"]) > 0
                 else f"per-second {float(r['MALICIOUS_COOPERATION']):g}")
TYPES = [att({"ONOFF_PERIOD_S": a.get("ONOFF_PERIOD_S", 0), "ONOFF_DUTY": a.get("ONOFF_DUTY", 0.9),
              "MALICIOUS_COOPERATION": a.get("MALICIOUS_COOPERATION", 0)}) for a in adversarial.BURST_ATTACKERS]
REF = {"per-second 0.9": "coop0.9_ratio0.1_gate0.7_cc1", "phased 0.9/30 s": "period30_duty0.9_ratio0.1_gate0.7_cc1"}


def mci(v, s=100, d=1):
    v = [x for x in v if x == x]
    m, _, ci, n = summarize(v)
    return f"{m * s:.{d}f} ± {(ci if ci == ci else 0) * s:.{d}f} (n={n})" if n else "–"


def sign(pairs):
    gain, loss = sum(b and not a for a, b in pairs), sum(a and not b for a, b in pairs)
    return f"+{gain} / -{loss} of {len(pairs)}" + (f" (p = {binomtest(loss, gain + loss).pvalue:.2g})" if gain + loss else "")


first, settings = adversarial.g_sweeps()["G3a"]
T, G, FG = (L(os.path.join(H, f"G3a_{x}_runs.csv")) for x in ("trust", "genuine", "forgery"))
rt = [r for r in L(os.path.join(F, "C_calibration_trust_runs.csv")) if float(r["TRUST_CH_THRESHOLD"]) == GATE]
rg = [r for r in L(os.path.join(F, "C_calibration_genuine_runs.csv")) if float(r["TRUST_CH_THRESHOLD"]) == GATE]
rf = [r for r in L(os.path.join(F, "C_calibration_forgery_runs.csv")) if float(r["TRUST_CH_THRESHOLD"]) == GATE]
kk = lambda r: int(float(r["TRUST_BURST_K"]))

print("## A. Completion")
want = {f"d{d}_r{r:02d}" for d in D for r in range(first, first + 30)}
for s in settings:
    folder = os.path.join(H, "G3a", adversarial.name(s))
    got = {os.path.basename(p)[:-8] for p in glob.glob(os.path.join(folder, "raw", "d*_r*.json.gz")) if "__" not in p}
    rows = len(L(os.path.join(folder, "processed", "runs.csv")))
    print(f"{adversarial.name(s)}: raw {len(got)}/90, missing {sorted(want - got)}, extra {sorted(got - want)}, runs.csv rows {rows}")
print(f"trust rows {len(T)}, genuine rows {len(G)}, forgery rows {len(FG)}")

print("\n## B. Beta trust and run lengths across k (same seed), and against k = 0 (C_calibration, gate 0.70)")
raw = {}                                              # (type, k, run_id) -> vehicles
for s in settings:
    a, k = att({**{"ONOFF_PERIOD_S": 0, "ONOFF_DUTY": 0.9, "MALICIOUS_COOPERATION": 0}, **s}), s["TRUST_BURST_K"]
    for p in glob.glob(os.path.join(H, "G3a", adversarial.name(s), "raw", "d*_r*.json.gz")):
        if "__" not in p:
            raw[(a, k, os.path.basename(p)[:-8])] = json.load(gzip.open(p))["scenario"]["vehicles"]
ref_raw = {(a, os.path.basename(p)[:-8]): json.load(gzip.open(p))["scenario"]["vehicles"]
           for a, n in REF.items() for p in glob.glob(os.path.join(F, "C_calibration", n, "raw", "d*_r*.json.gz"))
           if "__" not in p}
same_trust = same_run = nested = consistent = total = 0
for a in TYPES:
    for rid in sorted(want):
        vs = [raw[(a, k, rid)] for k in KS]
        total += 1
        same_trust += all([v["trust"] for v in x] == [v["trust"] for v in vs[0]] for x in vs)
        same_run += all([v["burst_max_run"] for v in x] == [v["burst_max_run"] for v in vs[0]] for x in vs)
        consistent += all(v["burst_flagged"] == (v["burst_max_run"] >= k) for k, x in zip(KS, vs) for v in x)
        nested += all(not v2["burst_flagged"] or v1["burst_flagged"] for x, y in zip(vs, vs[1:]) for v1, v2 in zip(x, y))
print(f"(type, run) groups: {total}; Beta trust identical across k: {same_trust}; longest run identical across k: "
      f"{same_run}; flag == (longest run >= k): {consistent}; flags nested (k+1 flagged => k flagged): {nested}")
for a in REF:
    ok = sum([(v["id"], v["trust"]) for v in raw[(a, 3, rid)]] == [(v["id"], v["trust"]) for v in ref_raw[(a, rid)]]
             for rid in want)
    print(f"{a}: per-vehicle Beta trust identical to the k = 0 run on the same seed: {ok} of {len(want)} runs")

print("\n## C. Honest false alarm (% of honest vehicles flagged per run)")
print("k | attacker | " + " | ".join(f"{d}: mean ± CI (n) / max run / runs > 1 %" for d in D))
worst = {}
for k in KS:
    for a in TYPES:
        cells = []
        for d in D:
            v = [float(r["honest_flagged"]) for r in T if kk(r) == k and att(r) == a and int(r["density"]) == d]
            worst[k] = max(worst.get(k, 0), float(np.mean(v)))
            cells.append(f"{mci(v, 100, 2)} / {100 * max(v):.2f} / {sum(x > 0.01 for x in v)}")
        print(f"{k} | {a} | " + " | ".join(cells))
chosen = next((k for k in KS if worst[k] <= 0.01), None)
print("worst mean over settings and densities:", {k: round(100 * w, 3) for k, w in worst.items()}, "% -> chosen k:", chosen)
choice = os.path.join(H, "G3a_calibration_choice.json")
print("G3a_calibration_choice.json:", json.load(open(choice)) if os.path.exists(choice) else "missing")

print("\n## D. Attacker detection (pooled over densities, n = 90 runs; per-run shares of the attackers)")
for a in TYPES:
    b = [float(r["attackers_below_gate"]) for r in T if att(r) == a and kk(r) == 3]
    print(f"{a}: Beta below gate (no detector) {mci(b)} %")
    for k in KS:
        rs = [r for r in T if kk(r) == k and att(r) == a]
        per_d = ", ".join(mci([float(r["attackers_flagged"]) for r in rs if int(r["density"]) == d]) for d in D)
        print(f"  k={k}: flagged {mci([float(r['attackers_flagged']) for r in rs])} % [per density {per_d}]; "
              f"flagged with Beta >= gate (newly ineligible) {mci([float(r['attackers_flag_only']) for r in rs])} %; "
              f"ineligible total {mci([float(r['attackers_ineligible']) for r in rs])} %")

print("\n## E. Beta trust of flagged vehicles: recorded Beta (unchanged) -> decision trust min(Beta, 0.5)")
for a in TYPES:
    for k in KS:
        out = []
        for who in (True, False):
            fl = [v for rid in want for v in raw[(a, k, rid)] if v["burst_flagged"] and v["malicious"] == who]
            if fl:
                beta = [v["trust"] for v in fl]
                out.append(f"{'attackers' if who else 'honest'} {len(fl)} flagged, Beta mean {np.mean(beta):.3f} "
                           f"[{min(beta):.2f}, {max(beta):.2f}] -> decision mean {np.mean(np.minimum(beta, 0.5)):.3f}; "
                           f"Beta >= gate (eligibility removed): {sum(x >= GATE for x in beta)}")
            else:
                out.append(f"{'attackers' if who else 'honest'} 0 flagged")
        print(f"{a}, k={k}: " + "; ".join(out))


def roles(vehicles, trust):
    xy = np.array([(v["x"], v["y"]) for v in vehicles])
    return elect_roles(xy, np.array([v["speed"] for v in vehicles]), geometry(xy)[1], np.asarray(trust, float))[0]


print("\n## F. Cluster-head selection: recorded roles vs the same election on Beta trust (no detector)")
check = mism = 0
for a in REF:                                           # the recomputation must reproduce recorded k = 0 roles
    for rid in want:
        vs = ref_raw[(a, rid)]
        check += 1
        mism += list(roles(vs, [v["trust"] for v in vs])) != [v["role"] for v in vs]
print(f"recomputed Beta-trust roles == recorded roles of the k = 0 runs: {check - mism} of {check}")
for a in TYPES:
    for k in KS:
        rows, rec_ok = collections.defaultdict(list), 0
        for rid in want:
            vs = raw[(a, k, rid)]
            beta = [v["trust"] for v in vs]
            dec = [min(v["trust"], 0.5) if v["burst_flagged"] else v["trust"] for v in vs]
            r0, r1 = roles(vs, beta), roles(vs, dec)
            rec_ok += list(r1) == [v["role"] for v in vs]
            mal = np.array([v["malicious"] for v in vs])
            rows["attacker CH, no detector"].append((r0[mal] == "CH").sum())
            rows["attacker CH, detector"].append((r1[mal] == "CH").sum())
            rows["honest CH removed"].append(((r0 == "CH") & (r1 != "CH") & ~mal).sum())
            rows["honest CH added"].append(((r0 != "CH") & (r1 == "CH") & ~mal).sum())
            rows["CH total, no detector"].append((r0 == "CH").sum())
            rows["CH total, detector"].append((r1 == "CH").sum())
        print(f"{a}, k={k}: recorded roles reproduced {rec_ok}/90; " +
              "; ".join(f"{n} {mci(v, 1, 2)}" for n, v in rows.items()))

print("\n## G. Committee, genuine alert and forgery outcomes (per run; n = 90 pooled, 30 per density)")
for a in TYPES:
    refs = [("k=0 (C_cal 0.70)", rt, rg, rf, None)] if a in REF else []
    for label, tr, gn, fg, k in refs + [(f"k={k}", T, G, FG, k) for k in KS]:
        sel = lambda rs: [r for r in rs if att(r) == a and (k is None or kk(r) == k)]
        t_, f_ = sel(tr), [r for r in sel(fg) if r["variant"] == "voting_reputation"]
        fc = [r for r in sel(fg) if r["variant"] == "voting_reputation_committee"]
        p = [r for r in sel(gn) if r["scheme"] == "proposed"]
        ch = [float(r["rsu_relay_received"]) for r in sel(gn) if r["scheme"] == "ch_route" and r["rsu_relay_received"] not in ("", "nan")]
        print(f"{a}, {label}: attackers on committee {mci([float(r['attackers_in_committee']) for r in t_], 1, 2)}; "
              f"genuine accepted {mci([float(r['genuine_accepted']) for r in t_])} % "
              f"[{', '.join(mci([float(r['genuine_accepted']) for r in t_ if int(r['density']) == d]) for d in D)}]; "
              f"proposed delivery (accepted) {mci([float(r['honest_delivery']) for r in p if r['accepted'] == '1.0'])} %; "
              f"CH relay {mci(ch)} %; forged accepted default {mci([float(r['accepted']) for r in f_])} %, "
              f"committee level {mci([float(r['accepted']) for r in fc])} %")

print("\n## H. Paired by seed against k = 0 (C_calibration gate 0.70): gains / losses")
for a in REF:
    r_t = {r["run_id"]: r for r in rt if att(r) == a}
    r_g = {r["run_id"]: r for r in rg if att(r) == a and r["scheme"] == "proposed"}
    r_c = {r["run_id"]: r for r in rg if att(r) == a and r["scheme"] == "ch_route"}
    r_f = {r["run_id"]: r for r in rf if att(r) == a and r["variant"] == "voting_reputation"}
    for k in KS:
        t_ = {r["run_id"]: r for r in T if att(r) == a and kk(r) == k}
        g_ = {r["run_id"]: r for r in G if att(r) == a and kk(r) == k and r["scheme"] == "proposed"}
        c_ = {r["run_id"]: r for r in G if att(r) == a and kk(r) == k and r["scheme"] == "ch_route"}
        f_ = {r["run_id"]: r for r in FG if att(r) == a and kk(r) == k and r["variant"] == "voting_reputation"}
        both = [i for i in r_g if r_g[i]["accepted"] == "1.0" and g_[i]["accepted"] == "1.0"]
        lower = sum(float(g_[i]["honest_delivery"]) < float(r_g[i]["honest_delivery"]) for i in both)
        relay = [(float(r_c[i]["rsu_relay_received"]) == 1, float(c_[i]["rsu_relay_received"]) == 1) for i in r_c
                 if r_c[i]["rsu_relay_received"] not in ("", "nan") and c_[i]["rsu_relay_received"] not in ("", "nan")]
        print(f"{a}, k={k}: genuine accepted {sign([(r_t[i]['genuine_accepted'] == '1.0', t_[i]['genuine_accepted'] == '1.0') for i in r_t])}; "
              f"proposed delivery lower on {lower} of {len(both)} both-accepted seeds; CH relay {sign(relay)}; "
              f"forged accepted (default) {sign([(r_f[i]['accepted'] == '1.0', f_[i]['accepted'] == '1.0') for i in r_f])}")

print("\n## I. Count-based gates on the same held-out seeds (C_calibration, no detector): honest vs attackers below gate")
allr = L(os.path.join(F, "C_calibration_trust_runs.csv"))
for a in REF:
    for g in sorted({float(r["TRUST_CH_THRESHOLD"]) for r in allr}):
        rs = [r for r in allr if att(r) == a and float(r["TRUST_CH_THRESHOLD"]) == g]
        print(f"{a}, gate {g}: honest below gate {mci([float(r['honest_below_gate']) for r in rs], 100, 2)} %; "
              f"attackers below gate {mci([float(r['attackers_below_gate']) for r in rs])} %")
