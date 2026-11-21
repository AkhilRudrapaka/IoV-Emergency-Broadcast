"""G3b evaluation behind results/hardening/G3B_EVALUATION_REPORT.md (read-only; no simulation).

    python -X utf8 results/hardening/analysis/g3b_evaluation.py      (run from the project root)

Three arms on the same 19 settings and seeds (runs 0-29, densities 100/200/300):
  F  Block F, gate 0.70, no detector (results/adversarial B and C; the no-detector baseline)
  D  G3b, gate 0.70, TRUST_BURST_K = 4
  G  G3b_gate, gate 0.75, no detector (count-gate comparison)
Ineligible = Beta below the gate, or (D only) burst-flagged. Means: mean ± 95 % Student-t half-width over runs
(metrics.summarize); paired: gains / losses per seed with an exact sign test."""
import collections, csv, glob, gzip, json, os, sys
sys.path.insert(0, os.getcwd())
import adversarial
from metrics import summarize
from scipy.stats import binomtest

H, F = os.path.join("results", "hardening"), os.path.join("results", "adversarial")
D3 = ("100", "200", "300")
L = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))
typ = lambda r: (f"phased {float(r['ONOFF_DUTY']):g}/{float(r['ONOFF_PERIOD_S']):g} s" if float(r["ONOFF_PERIOD_S"]) > 0
                 else f"per-second {float(r['MALICIOUS_COOPERATION']):g}")
cell = lambda r: (typ(r), f"{float(r['MALICIOUS_RATIO']):g}")
base = lambda s: s.replace("_k4", "").replace("_gate0.75", "")
settings = adversarial.g_sweeps(4)["G3b"][1]
names = {adversarial.name({k: v for k, v in s.items() if k != "TRUST_BURST_K"}) for s in settings}
src = {"F": [(F, sw) for sw in ("B", "C")], "D": [(H, "G3b")], "G": [(H, "G3b_gate")]}
data = {}
for arm, places in src.items():
    for kind in ("trust", "forgery", "genuine"):
        data[(arm, kind)] = [r for d, sw in places for r in L(os.path.join(d, f"{sw}_{kind}_runs.csv"))
                             if base(r["setting"]) in names]
idx = lambda arm, kind, f=lambda r: True, extra=lambda r: (): {(base(r["setting"]), r["run_id"], *extra(r)): r
                                                              for r in data[(arm, kind)] if f(r)}
T = {a: idx(a, "trust") for a in "FDG"}
FD = {a: idx(a, "forgery", lambda r: r["variant"] == "voting_reputation") for a in "FDG"}
FC = {a: idx(a, "forgery", lambda r: r["variant"] == "voting_reputation_committee") for a in "FDG"}
GP = {a: idx(a, "genuine", lambda r: r["scheme"] == "proposed") for a in "FDG"}
GC = {a: idx(a, "genuine", lambda r: r["scheme"] == "ch_route") for a in "FDG"}
inel_a = lambda a, r: float(r["attackers_ineligible"] if a != "F" else r["attackers_below_gate"])
inel_h = lambda a, r: float(r["honest_ineligible"] if a != "F" else r["honest_below_gate"])
keys = sorted(T["F"])
cells = sorted({cell(T["F"][k]) for k in keys}, key=lambda c: (c[0] != "per-second 0.9", c))
ofcell = lambda c: [k for k in keys if cell(T["F"][k]) == c]


def mci(v, s=100, d=1):
    v = [x for x in v if x == x]
    m, _, ci, n = summarize(v)
    return f"{m * s:.{d}f} ± {(ci if ci == ci else 0) * s:.{d}f}" if n else "–"


def sign(pairs):
    gain, loss = sum(b and not a for a, b in pairs), sum(a and not b for a, b in pairs)
    return f"+{gain}/-{loss}" + (f" (p={binomtest(loss, gain + loss).pvalue:.2g})" if gain + loss else "")


print("## A. Completion and identity")
for arm, sw in (("D", "G3b"), ("G", "G3b_gate")):
    for s in adversarial.g_sweeps(4)[sw][1]:
        got = [p for p in glob.glob(os.path.join(H, sw, adversarial.name(s), "raw", "d*_r*.json.gz")) if "__" not in p]
        if len(got) != 90:
            print(f"{sw} {adversarial.name(s)}: {len(got)} raw records")
    print(f"{sw}: {len(adversarial.g_sweeps(4)[sw][1])} settings, trust rows {len(T[arm])}, keys equal to Block F: "
          f"{sorted(T[arm]) == keys}")
same, total, roles = 0, 0, collections.defaultdict(list)
for k in keys:
    s, rid = k
    sw = "B" if "colluders" in s else "C"
    rec = {a: json.load(gzip.open(os.path.join(d, f, raw_name, "raw", f"{rid}.json.gz")))["scenario"]["vehicles"]
           for a, d, f, raw_name in (("F", F, sw, s), ("D", H, "G3b", s + "_k4"), ("G", H, "G3b_gate", s + "_gate0.75"))}
    total += 1
    same += [(v["id"], v["trust"]) for v in rec["F"]] == [(v["id"], v["trust"]) for v in rec["D"]] == \
            [(v["id"], v["trust"]) for v in rec["G"]]
    for a in "DG":
        f_, x = rec["F"], rec[a]
        roles[(cell(T["F"][k]), a, "attacker CH")].append(sum(v["malicious"] and v["role"] == "CH" for v in x))
        roles[(cell(T["F"][k]), a, "honest CH removed")].append(
            sum(not v["malicious"] and u["role"] == "CH" and v["role"] != "CH" for u, v in zip(f_, x)))
        roles[(cell(T["F"][k]), a, "honest CH added")].append(
            sum(not v["malicious"] and u["role"] != "CH" and v["role"] == "CH" for u, v in zip(f_, x)))
    roles[(cell(T["F"][k]), "F", "attacker CH")].append(sum(v["malicious"] and v["role"] == "CH" for v in rec["F"]))
print(f"per-vehicle Beta trust identical in F, D and G on the same seed: {same} of {total} runs")

print("\n## B. Honest exclusion per run (% of honest vehicles ineligible): mean ± CI / max / runs > 1 % / runs > 2 %")
for a, label in (("F", "Block F 0.70"), ("D", "k=4 at 0.70"), ("G", "gate 0.75")):
    for d in D3:
        v = [inel_h(a, T[a][k]) for k in keys if T["F"][k]["density"] == d]
        print(f"{label}, {d} vehicles, all 19 settings (n={len(v)}): {mci(v, 100, 2)} / {100 * max(v):.2f} / "
              f"{sum(x > 0.01 for x in v)} / {sum(x > 0.02 for x in v)}")
print("per attacker cell (pooled n = 90): F | D | G   mean ± CI, max")
for c in cells:
    row = []
    for a in "FDG":
        v = [inel_h(a, T[a][k]) for k in ofcell(c)]
        row.append(f"{mci(v, 100, 2)}, max {100 * max(v):.2f}")
    print(f"{c[0]} {c[1]}: " + " | ".join(row))

print("\n## C. Detection: attackers ineligible per run (%), pooled n = 90 [per density] ; D also: flagged")
for c in cells:
    ks = ofcell(c)
    parts = []
    for a in "FDG":
        per_d = ", ".join(mci([inel_a(a, T[a][k]) for k in ks if T["F"][k]["density"] == d]) for d in D3)
        parts.append(f"{a} {mci([inel_a(a, T[a][k]) for k in ks])} [{per_d}]")
    print(f"{c[0]} {c[1]}: " + " ; ".join(parts) + f" ; D flagged {mci([float(T['D'][k]['attackers_flagged']) for k in ks])}")

print("\n## D. Forged alert accepted (%), default and committee level; paired vs F, and D vs G")
for c in cells:
    ks = ofcell(c)
    acc = lambda M, a: [M[a][k]["accepted"] == "1.0" for k in ks]
    out = [f"{a} {mci([float(x) for x in acc(FD, a)])} / {mci([float(x) for x in acc(FC, a)])}" for a in "FDG"]
    print(f"{c[0]} {c[1]}: " + " | ".join(out) +
          f" || default: D vs F {sign(list(zip(acc(FD, 'F'), acc(FD, 'D'))))}, G vs F {sign(list(zip(acc(FD, 'F'), acc(FD, 'G'))))}, "
          f"D vs G {sign(list(zip(acc(FD, 'G'), acc(FD, 'D'))))}")

print("\n## E. Genuine alert: accepted (%) | proposed delivery, accepted runs (%) | CH relayed RSU (%); paired vs F")
for c in cells:
    ks = ofcell(c)
    out = []
    for a in "FDG":
        ga = [float(T[a][k]["genuine_accepted"]) for k in ks]
        dl = [float(GP[a][k]["honest_delivery"]) for k in ks if GP[a][k]["accepted"] == "1.0"]
        ch = [float(GC[a][k]["rsu_relay_received"]) for k in ks if GC[a][k]["rsu_relay_received"] not in ("", "nan")]
        out.append(f"{a} {mci(ga)} | {mci(dl)} | {mci(ch)} (n={len(ch)})")
    pr = lambda a: sign([(T["F"][k]["genuine_accepted"] == "1.0", T[a][k]["genuine_accepted"] == "1.0") for k in ks])
    low = lambda a: sum(float(GP[a][k]["honest_delivery"]) < float(GP["F"][k]["honest_delivery"]) for k in ks
                        if GP[a][k]["accepted"] == "1.0" and GP["F"][k]["accepted"] == "1.0")
    rel = lambda a: sign([(float(GC["F"][k]["rsu_relay_received"]) == 1, float(GC[a][k]["rsu_relay_received"]) == 1)
                          for k in ks if "" not in (GC["F"][k]["rsu_relay_received"], GC[a][k]["rsu_relay_received"])
                          and "nan" not in (GC["F"][k]["rsu_relay_received"], GC[a][k]["rsu_relay_received"])])
    print(f"{c[0]} {c[1]}: " + " ; ".join(out) + f" || genuine D {pr('D')}, G {pr('G')}; delivery lower D {low('D')}, "
          f"G {low('G')}; CH relay D {rel('D')}, G {rel('G')}")

print("\n## F. Committee and cluster heads (per run, pooled n = 90)")
for c in cells:
    ks = ofcell(c)
    com = " | ".join(f"{a} {mci([float(T[a][k]['attackers_in_committee']) for k in ks], 1, 2)}" for a in "FDG")
    ch = " | ".join(f"{a}: attacker CH {mci(roles[(c, a, 'attacker CH')], 1, 2)}" +
                    ("" if a == "F" else f", honest CH removed {mci(roles[(c, a, 'honest CH removed')], 1, 2)}, "
                                         f"added {mci(roles[(c, a, 'honest CH added')], 1, 2)}") for a in "FDG")
    print(f"{c[0]} {c[1]}: attackers on committee {com} ; {ch}")

print("\n## G. Honest-exclusion distribution per run, by honest population and density (k=4 vs gate 0.75)")
print("The 8 phased types share one honest observation stream per share, so the honest populations are: per-second at")
print("10/20/30 % and phased at 10/20 %. Buckets: 0 | (0,1] | (1,2] | (2,3] | >3 %; then mean ± CI, max (n = 30 runs).")
pops = [("per-second 0.9", r) for r in ("0.1", "0.2", "0.3")] + [("phased 0.9/30 s", r) for r in ("0.1", "0.2")]
for a, label in (("D", "k=4 at 0.70"), ("G", "gate 0.75")):
    for c in pops:
        for d in D3:
            v = [100 * inel_h(a, T[a][k]) for k in ofcell(c) if T["F"][k]["density"] == d]
            b = [sum(x == 0 for x in v), sum(0 < x <= 1 for x in v), sum(1 < x <= 2 for x in v),
                 sum(2 < x <= 3 for x in v), sum(x > 3 for x in v)]
            print(f"{label} | {'phased' if c[0].startswith('phased') else 'per-second'} {c[1]} | {d}: "
                  f"{' / '.join(map(str, b))} | {mci([x / 100 for x in v], 100, 2)}, max {max(v):.2f}")
