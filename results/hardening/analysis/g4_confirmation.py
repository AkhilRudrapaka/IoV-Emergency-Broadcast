"""G4 combined confirmation behind results/hardening/G4_CONFIRMATION_REPORT.md (read-only; no simulation).

    python -X utf8 results/hardening/analysis/g4_confirmation.py      (run from the project root)

Arms on the same seeds (runs 0-29, densities 100/200/300), 5/3 committee, gate 0.70:
  F   Block F: no enforcement, no detector          results/adversarial/{B,C}   (MAX_COLLUDERS 5 rows)
  E   G1: enforcement only                          results/hardening/G1        (MAX_COLLUDERS 5 rows)
  D   G3b: detector k = 4 only                      results/hardening/G3b       (19 of the 25 cells)
  C   G4: enforcement + k = 4                       results/hardening/G4
Cell = attacker share x model (per-second cooperation c, or phased duty/period). Means: mean ± 95 % Student-t
half-width (metrics.summarize); paired: gains/losses per seed with an exact sign test."""
import collections, csv, glob, gzip, json, os, sys
sys.path.insert(0, os.getcwd())
import adversarial
from metrics import summarize
from scipy.stats import binomtest

H, F = os.path.join("results", "hardening"), os.path.join("results", "adversarial")
D3 = ("100", "200", "300")
L = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))
f_ = lambda r, k: float(r[k])
cellk = lambda r: (f"{f_(r, 'MALICIOUS_RATIO'):g}", f"phased {f_(r, 'ONOFF_DUTY'):g}/{f_(r, 'ONOFF_PERIOD_S'):g} s"
                   if f_(r, "ONOFF_PERIOD_S") > 0 else f"per-second {f_(r, 'MALICIOUS_COOPERATION'):g}")
SRC = {"F": [(F, "B"), (F, "C")], "E": [(H, "G1")], "D": [(H, "G3b")], "C": [(H, "G4")]}
ARMS = "FEDC"
data = {}
for arm, places in SRC.items():
    for kind in ("trust", "forgery", "genuine"):
        rows = [r for d, sw in places for r in L(os.path.join(d, f"{sw}_{kind}_runs.csv"))
                if int(float(r["MAX_COLLUDERS"])) == 5]
        data[(arm, kind)] = rows
ix = lambda arm, kind, keep=lambda r: True: {(cellk(r), r["run_id"]): r for r in data[(arm, kind)] if keep(r)}
T = {a: ix(a, "trust") for a in ARMS}
FV = {(a, v): ix(a, "forgery", lambda r, v=v: r["variant"] == v) for a in ARMS
      for v in ("voting_reputation", "voting_only", "voting_reputation_committee")}
GP = {a: ix(a, "genuine", lambda r: r["scheme"] == "proposed") for a in ARMS}
GC = {a: ix(a, "genuine", lambda r: r["scheme"] == "ch_route") for a in ARMS}
keys = sorted(T["C"])
cells = sorted({k[0] for k in keys}, key=lambda c: (c[1].startswith("phased"), c[1], c[0]))
inel = lambda a, r, who: f_(r, f"{who}_ineligible") if a in "DC" else f_(r, f"{who}_below_gate")
num = lambda x: None if x in ("", "nan") else float(x)


def mci(v, s=100, d=1):
    v = [x for x in v if x is not None and x == x]
    m, _, ci, n = summarize(v)
    return f"{m * s:.{d}f} ± {(ci if ci == ci else 0) * s:.{d}f}" if n else "–"


def sign(pairs):
    gain, loss = sum(b and not a for a, b in pairs), sum(a and not b for a, b in pairs)
    return f"+{gain}/-{loss}" + (f" (p={binomtest(loss, gain + loss).pvalue:.2g})" if gain + loss else "")


print("## A. Completion and identity")
first, settings = adversarial.g_sweeps(4, (5, 3))["G4"]
for s in settings:
    got = [p for p in glob.glob(os.path.join(H, "G4", adversarial.name(s), "raw", "d*_r*.json.gz")) if "__" not in p]
    if len(got) != 90:
        print(f"G4 {adversarial.name(s)}: {len(got)} raw records")
print(f"G4: {len(settings)} unique settings, {len(T['C'])} trust rows, {len({k[0] for k in keys})} cells")
for a in "FED":
    print(f"{a}: pairs available with G4 {sum(k in T[a] for k in keys)} of {len(keys)}")
same_trust = total = 0
roles = collections.defaultdict(list)
b_names = {adversarial.name(x) for x in adversarial.sweeps()["B"][1]}
for (c, rid), row in T["C"].items():
    s, f_row = row["setting"], T["F"][(c, rid)]
    sw = "B" if f_row["setting"] in b_names else "C"
    vf = json.load(gzip.open(os.path.join(F, sw, f_row["setting"], "raw", f"{rid}.json.gz")))["scenario"]["vehicles"]
    vc = json.load(gzip.open(os.path.join(H, "G4", s, "raw", f"{rid}.json.gz")))["scenario"]["vehicles"]
    total += 1
    same_trust += [(v["id"], v["trust"]) for v in vf] == [(v["id"], v["trust"]) for v in vc]
    roles[(c, "attacker CH F")].append(sum(v["malicious"] and v["role"] == "CH" for v in vf))
    roles[(c, "attacker CH C")].append(sum(v["malicious"] and v["role"] == "CH" for v in vc))
    roles[(c, "honest CH removed")].append(sum(not v["malicious"] and u["role"] == "CH" and v["role"] != "CH"
                                               for u, v in zip(vf, vc)))
    roles[(c, "honest CH added")].append(sum(not v["malicious"] and u["role"] != "CH" and v["role"] == "CH"
                                             for u, v in zip(vf, vc)))
print(f"per-vehicle Beta trust identical in Block F and G4 on the same seed: {same_trust} of {total} runs")
d_c = [k for k in keys if k in T["D"]]
print(f"G4 vs G3b (same detector, enforcement added): genuine accepted identical "
      f"{sum(T['C'][k]['genuine_accepted'] == T['D'][k]['genuine_accepted'] for k in d_c)} of {len(d_c)}; "
      f"honest ineligible identical {sum(T['C'][k]['honest_ineligible'] == T['D'][k]['honest_ineligible'] for k in d_c)}; "
      f"attackers on committee identical "
      f"{sum(T['C'][k]['attackers_in_committee'] == T['D'][k]['attackers_in_committee'] for k in d_c)}")
e_f = [k for k in keys if k in T["E"]]
print(f"G4 genuine accepted vs G1: identical in {sum(T['C'][k]['genuine_accepted'] == T['E'][k]['genuine_accepted'] for k in e_f)} of {len(e_f)}")

print("\n## B. Forged alert accepted (% of runs, n = 90 per cell): default level F / E / D / C; voting-only F / C")
print("   paired: C vs F, C vs E (detector given enforcement), C vs D (enforcement given detector)")
tot = collections.Counter()
for c in cells:
    ks = [k for k in keys if k[0] == c]
    acc = lambda a, v="voting_reputation": [FV[(a, v)][k]["accepted"] == "1.0" for k in ks if k in FV[(a, v)]]
    for a in ARMS:
        tot[(a, "n")] += len(acc(a))
        tot[(a, "acc")] += sum(acc(a))
    d_part = mci([float(x) for x in acc("D")]) if acc("D") else "–"
    pr = lambda a, b: sign([(FV[(a, 'voting_reputation')][k]["accepted"] == "1.0",
                             FV[(b, 'voting_reputation')][k]["accepted"] == "1.0") for k in ks
                            if k in FV[(a, 'voting_reputation')] and k in FV[(b, 'voting_reputation')]])
    print(f"{c[1]} ({c[0]}): {mci([float(x) for x in acc('F')])} / {mci([float(x) for x in acc('E')])} / {d_part} / "
          f"{mci([float(x) for x in acc('C')])} | voting-only {mci([float(x) for x in acc('F', 'voting_only')])} / "
          f"{mci([float(x) for x in acc('C', 'voting_only')])} || C vs F {pr('F', 'C')}, C vs E {pr('E', 'C')}"
          + (f", C vs D {pr('D', 'C')}" if any(k in FV[('D', 'voting_reputation')] for k in ks) else ""))
print("totals (default level, accepted / runs): " + ", ".join(f"{a} {tot[(a, 'acc')]}/{tot[(a, 'n')]}" for a in ARMS))
on19 = [k for k in keys if k in FV[("D", "voting_reputation")]]
print("on the 19 cells with all four arms: " + ", ".join(
    f"{a} {sum(FV[(a, 'voting_reputation')][k]['accepted'] == '1.0' for k in on19)}/{len(on19)}" for a in ARMS))

print("\n## C. Detection and honest exclusion (% per run, n = 90 per cell): attackers ineligible F / D / C; honest "
      "ineligible F / C (max run)")
for c in cells:
    ks = [k for k in keys if k[0] == c]
    dv = [inel("D", T["D"][k], "attackers") for k in ks if k in T["D"]]
    print(f"{c[1]} ({c[0]}): {mci([inel('F', T['F'][k], 'attackers') for k in ks])} / {mci(dv) if dv else '–'} / "
          f"{mci([inel('C', T['C'][k], 'attackers') for k in ks])} ; flagged C {mci([f_(T['C'][k], 'attackers_flagged') for k in ks])} ; "
          f"honest {mci([inel('F', T['F'][k], 'honest') for k in ks], 100, 2)} / "
          f"{mci([inel('C', T['C'][k], 'honest') for k in ks], 100, 2)} (max {100 * max(inel('C', T['C'][k], 'honest') for k in ks):.2f})")
print("honest exclusion per run under G4, all 25 cells: mean ± CI / max / runs > 1 % / runs > 2 %")
for d in D3:
    v = [inel("C", T["C"][k], "honest") for k in keys if k[1].startswith(f"d{d}_")]
    print(f"  {d} vehicles (n={len(v)}): {mci(v, 100, 2)} / {100 * max(v):.2f} / {sum(x > 0.01 for x in v)} / "
          f"{sum(x > 0.02 for x in v)}")

print("\n## D. Genuine alert, CH route, cost (n = 90 per cell): genuine accepted F / E / C; proposed delivery C; "
      "CH relay F / C; vote frames and quorum ms G1 (genuine runs byte-identical to Block F) / C")
for c in cells:
    ks = [k for k in keys if k[0] == c]
    ga = lambda a: [f_(T[a][k], "genuine_accepted") for k in ks]
    ch = lambda a: [num(GC[a][k]["rsu_relay_received"]) for k in ks]
    gp = lambda a, m: [num(GP[a][k][m]) for k in ks if m != "quorum_ms" or GP[a][k]["accepted"] == "1.0"]
    print(f"{c[1]} ({c[0]}): {mci(ga('F'))} / {mci(ga('E'))} / {mci(ga('C'))} ; "
          f"{mci([num(GP['C'][k]['honest_delivery']) for k in ks if GP['C'][k]['accepted'] == '1.0'])} ; "
          f"{mci(ch('F'))} / {mci(ch('C'))} ; {mci(gp('E', 'vote_tx'), 1, 2)} / {mci(gp('C', 'vote_tx'), 1, 2)} ; "
          f"{mci(gp('E', 'quorum_ms'), 1, 2)} / {mci(gp('C', 'quorum_ms'), 1, 2)} || genuine C vs F "
          f"{sign([(T['F'][k]['genuine_accepted'] == '1.0', T['C'][k]['genuine_accepted'] == '1.0') for k in ks])}; "
          f"delivery lower {sum(num(GP['C'][k]['honest_delivery']) < num(GP['F'][k]['honest_delivery']) for k in ks if GP['C'][k]['accepted'] == GP['F'][k]['accepted'] == '1.0')}; "
          f"CH relay {sign([(ch('F')[i] == 1, ch('C')[i] == 1) for i in range(len(ks)) if ch('F')[i] is not None and ch('C')[i] is not None])}")
allg = lambda a: [(T["F"][k]["genuine_accepted"] == "1.0", T[a][k]["genuine_accepted"] == "1.0") for k in keys]
print("genuine accepted, all 25 cells, paired vs F: E " + sign(allg("E")) + ", C " + sign(allg("C")))
low = sum(num(GP["C"][k]["honest_delivery"]) < num(GP["F"][k]["honest_delivery"]) for k in keys
          if GP["C"][k]["accepted"] == GP["F"][k]["accepted"] == "1.0")
relay = [(num(GC["F"][k]["rsu_relay_received"]) == 1, num(GC["C"][k]["rsu_relay_received"]) == 1) for k in keys
         if num(GC["F"][k]["rsu_relay_received"]) is not None and num(GC["C"][k]["rsu_relay_received"]) is not None]
print(f"proposed delivery lower than F on {low} both-accepted seeds; CH relay vs F {sign(relay)}")

print("\n## E. Committee and cluster heads (per run, n = 90 per cell): attackers on committee F / C; attacker CHs F / C; "
      "honest CHs removed / added")
for c in cells:
    ks = [k for k in keys if k[0] == c]
    print(f"{c[1]} ({c[0]}): {mci([f_(T['F'][k], 'attackers_in_committee') for k in ks], 1, 2)} / "
          f"{mci([f_(T['C'][k], 'attackers_in_committee') for k in ks], 1, 2)} ; "
          f"{mci(roles[(c, 'attacker CH F')], 1, 2)} / {mci(roles[(c, 'attacker CH C')], 1, 2)} ; "
          f"{mci(roles[(c, 'honest CH removed')], 1, 2)} / {mci(roles[(c, 'honest CH added')], 1, 2)}")
