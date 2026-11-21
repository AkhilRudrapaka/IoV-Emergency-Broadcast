"""G2 paired analysis behind results/hardening/G2_RESULTS_REPORT.md (read-only; no simulation).

    python -X utf8 results/hardening/analysis/g2_paired.py      (run from the project root)

Pairs are (attacker cell, run_id), i.e. the same seed. Block F reference: B and C runs with MAX_COLLUDERS 5,
per-second 0.9 (10/20/30 %) and phased 0.9/30 s (10/20 %). Proportions: Clopper-Pearson 95 %; per-density means:
Student t (metrics.summarize); paired gains/losses: exact two-sided sign test (scipy binomtest)."""
import collections, csv, gzip, json, os, sys
sys.path.insert(0, os.getcwd())
from metrics import summarize
from scipy.stats import beta, binomtest

H, F = os.path.join("results", "hardening"), os.path.join("results", "adversarial")
C = ("5/3", "7/4", "9/5", "7/3")
L = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))
cfg = lambda r: f"{int(float(r['COMMITTEE_SIZE']))}/{int(float(r['QUORUM']))}"
cell = lambda r: (r["MALICIOUS_RATIO"], "phased 0.9/30 s" if float(r["ONOFF_PERIOD_S"]) > 0 else "per-second 0.9")
num = lambda x: float(x) if x not in ("", "nan") else None
ref_ok = lambda r: int(float(r["MAX_COLLUDERS"])) == 5 and (
    float(r["ONOFF_PERIOD_S"]) == 0 and float(r["MALICIOUS_COOPERATION"]) == 0.9
    or float(r["ONOFF_PERIOD_S"]) == 30 and float(r["ONOFF_DUTY"]) == 0.9)
T, FG, G = (L(os.path.join(H, f"G2_{k}_runs.csv")) for k in ("trust", "forgery", "genuine"))
t = {(cfg(r), cell(r), r["run_id"]): r for r in T}
f = {(cfg(r), cell(r), r["run_id"]): r for r in FG if r["variant"] == "voting_reputation"}
g = {(cfg(r), cell(r), r["run_id"], r["scheme"]): r for r in G}
bt = {(cell(r), r["run_id"]): r for s in "BC" for r in L(os.path.join(F, f"{s}_trust_runs.csv")) if ref_ok(r)}
bf = {(cell(r), r["run_id"]): r for s in "BC" for r in L(os.path.join(F, f"{s}_forgery_runs.csv"))
      if ref_ok(r) and r["variant"] == "voting_reputation"}
bg = {(cell(r), r["run_id"], r["scheme"]): r for s in "BC" for r in L(os.path.join(F, f"{s}_genuine_runs.csv"))
      if ref_ok(r)}
keys = sorted({(c_, r) for (_, c_, r) in t})


def cp(k, n):
    lo = beta.ppf(0.025, k, n - k + 1) if k else 0.0
    hi = beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    return f"{k}/{n} = {100 * k / n:.1f} % [{100 * lo:.1f}, {100 * hi:.1f}]"


def mci(v, s=100, d=1):
    m, _, ci, n = summarize(v)
    return f"{m * s:.{d}f} ± {ci * s:.{d}f}"


def paired(a, b):
    """a, b: dicts pair -> bool; returns gains (b true, a false), losses, n, sign-test p."""
    common = [k for k in a if k in b]
    gain = sum(b[k] and not a[k] for k in common)
    loss = sum(a[k] and not b[k] for k in common)
    p = binomtest(loss, gain + loss).pvalue if gain + loss else 1.0
    return f"+{gain} / -{loss} of {len(common)} (p = {p:.2g})"


acc = lambda c: {(ce, r): t[(c, ce, r)]["genuine_accepted"] == "1.0" for ce, r in keys}
forged = lambda c: {(ce, r): f[(c, ce, r)]["accepted"] == "1.0" for ce, r in keys}
relay = lambda c: {(ce, r): num(g[(c, ce, r, "ch_route")]["rsu_relay_received"]) == 1 for ce, r in keys
                   if num(g[(c, ce, r, "ch_route")]["rsu_relay_received"]) is not None}
ref_acc = {k: r["genuine_accepted"] == "1.0" for k, r in bt.items()}
ref_forged = {k: r["accepted"] == "1.0" for k, r in bf.items()}
ref_relay = {(ce, r): num(x["rsu_relay_received"]) == 1 for (ce, r, s), x in bg.items()
             if s == "ch_route" and num(x["rsu_relay_received"]) is not None}

print("## Pooled over all 6 cells (540 runs per configuration)")
for c in C:
    m, q = map(int, c.split("/"))
    rows = [t[(c, *k)] for k in keys]
    fails = [r for r in rows if r["genuine_accepted"] != "1.0"]
    vo = [r for r in FG if cfg(r) == c and r["variant"] == "voting_only"]
    rl = relay(c)
    print(f"{c}: genuine {cp(sum(acc(c).values()), len(rows))}; failures {len(fails)}, with >= m-q+1 = {m - q + 1} "
          f"attackers on the committee {sum(float(r['attackers_in_committee']) >= m - q + 1 for r in fails)}; "
          f"forged default {cp(sum(forged(c).values()), len(rows))}; forged voting_only "
          f"{cp(sum(r['accepted'] == '1.0' for r in vo), len(vo))}; CH relay {cp(sum(rl.values()), len(rl))}")

print("\n## Per density (6 cells, 180 runs each; mean ± 95 % t half-width)")
for c in C:
    for d in ("100", "200", "300"):
        ks = [k for k in keys if k[1].startswith(f"d{d}_")]
        gn = [g[(c, *k, "proposed")] for k in ks]
        rl = [num(g[(c, *k, "ch_route")]["rsu_relay_received"]) for k in ks]
        rl = [x for x in rl if x is not None]
        print(f"{c} d{d}: genuine {mci([float(t[(c, *k)]['genuine_accepted']) for k in ks])} %; forged default "
              f"{mci([float(f[(c, *k)]['accepted']) for k in ks])} %; attackers on committee "
              f"{mci([float(t[(c, *k)]['attackers_in_committee']) for k in ks], 1, 2)}; CH relay {mci(rl)} % (n={len(rl)}); "
              f"vote frames {mci([float(r['vote_tx']) for r in gn], 1)}; quorum ms "
              f"{mci([float(r['quorum_ms']) for r in gn if r['accepted'] == '1.0'], 1, 2)}; committee full "
              f"{mci([float(t[(c, *k)]['committee_full']) for k in ks])} %; below quorum "
              f"{mci([float(t[(c, *k)]['committee_below_quorum']) for k in ks])} %")

print("\n## Paired by seed: gains / losses (sign test)")
for c in C[1:]:
    print(f"{c} vs 5/3 (= G1 on the 5 shared cells; 540 pairs): genuine {paired(acc('5/3'), acc(c))}; "
          f"forged accepted {paired(forged('5/3'), forged(c))}; CH relay {paired(relay('5/3'), relay(c))}")
for c in C:
    print(f"{c} vs Block F default level (450 pairs): genuine {paired(ref_acc, acc(c))}; "
          f"forged accepted {paired(ref_forged, forged(c))}; CH relay {paired(ref_relay, relay(c))}")

print("\n## Proposed and CH-route delivery vs Block F, seeds where both accepted the genuine alert")
for c in C:
    for s in ("proposed", "ch_route"):
        pairs = [(bg[(ce, r, s)], g[(c, ce, r, s)]) for ce, r in keys if (ce, r, s) in bg
                 and bg[(ce, r, s)]["accepted"] == "1.0" and g[(c, ce, r, s)]["accepted"] == "1.0"]
        lo = sum(float(b["honest_delivery"]) < float(a["honest_delivery"]) for a, b in pairs)
        hi = sum(float(b["honest_delivery"]) > float(a["honest_delivery"]) for a, b in pairs)
        print(f"{c} {s}: n = {len(pairs)}, delivery lower {lo}, higher {hi}")

print("\n## CH-route relay lost vs 5/3: endorsements collected by the first route head short of q")
for c in ("7/4", "9/5"):
    q, hist = int(c.split("/")[1]), collections.Counter()
    for ce, r in keys:
        a, b = g[("5/3", ce, r, "ch_route")], g[(c, ce, r, "ch_route")]
        if num(a["rsu_relay_received"]) == 1 and num(b["rsu_relay_received"]) == 0:
            tx = json.load(gzip.open(os.path.join(H, "G2", b["setting"], "raw", f"{r}.json.gz")))["protocols"]["ch_route"]["transmissions"]
            votes = collections.Counter(x["kind"].split(":")[1] for x in tx if x["kind"].startswith("CVOTE:"))
            got = [1 + votes[x["kind"].split(":")[1]] for x in tx if x["kind"].startswith("CPROPOSAL:")]
            hist[next((e for e in got if e < q), "none short (genuine alert not accepted)")] += 1
    print(f"{c}: {dict(hist)}")
