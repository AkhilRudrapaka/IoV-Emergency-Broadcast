"""Charts, LaTeX tables and shared numbers for the panel report and presentation, read only from the project's own
experiment outputs (results/urban/processed/*.csv and results/urban/sensitivity/*/processed/*.csv). Nothing is typed in.

    python final_panel_review/scripts/make_figures_and_tables.py

Writes final_panel_review/figures/chart_*.pdf|png, final_panel_review/generated/tab_*.tex and
final_panel_review/generated/numbers.tex (one macro per number quoted in the text of both documents).
"""
import csv
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "final_panel_review"
FIG, GEN = OUT / "figures", OUT / "generated"
FIG.mkdir(parents=True, exist_ok=True)
GEN.mkdir(parents=True, exist_ok=True)
PROC = ROOT / "results" / "urban" / "processed"
SENS = ROOT / "results" / "urban" / "sensitivity"
RUNS = 30

LABEL = {"flooding": "Blind flooding", "flooding_rad": "Flooding + random delay", "slotted1p": "Slotted 1-persistence",
         "slotted1p_rad": "Slotted 1-p + random delay", "proposed": "Proposed (full)", "ch_route": "CH-to-CH route stage",
         "no_rad": "without random delay", "no_slots": "without distance slots", "no_coverage": "without coverage test",
         "no_clustering": "without clustering", "no_cluster_forwarding": "without cluster-based forwarding",
         "no_reputation": "without reputation gate", "no_security": "without voting + BLS"}
SCHEMES = ["flooding", "flooding_rad", "slotted1p", "slotted1p_rad", "proposed"]
ABLATIONS = ["no_rad", "no_slots", "no_coverage", "no_clustering", "no_cluster_forwarding", "no_reputation", "no_security"]
COLOR = {"flooding": "#4d4d4d", "flooding_rad": "#a0a0a0", "slotted1p": "#7fb3e0", "slotted1p_rad": "#1f5fa0",
         "proposed": "#A4123F"}
MARK = {"flooding": "s", "flooding_rad": "D", "slotted1p": "^", "slotted1p_rad": "v", "proposed": "o"}


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


summary = {(int(r["density"]), r["protocol"]): r for r in read(PROC / "summary.csv")}
paired = {(int(r["density"]), r["baseline"]): r for r in read(PROC / "paired.csv")}
DENS = sorted({d for d, _ in summary})


def val(d, p, key, scale=1.0):
    r = summary[(d, p)]
    m, c, n = num(r[key]), num(r.get(key + "_ci95")), num(r.get(key + "_n"))
    return (None if m is None else m * scale, None if c is None else c * scale, None if n is None else int(n))


def cell(m, c, n, dec, runs=RUNS):
    if m is None:
        return "--"
    s = f"{m:.{dec}f}" + (f" $\\pm$ {c:.{dec}f}" if c is not None else "")
    return s + (f" (n={n})" if n is not None and n < runs else "")


def signed(m, dec):
    """+1.3 or $-$1.3 (a real minus sign in LaTeX)."""
    return ("+" if m >= 0 else "$-$") + f"{abs(m):.{dec}f}"


def pm(m, c, n, dec):
    """Signed paired difference."""
    if m is None:
        return "--"
    s = signed(m, dec) + (f" $\\pm$ {c:.{dec}f}" if c is not None else "")
    return s + (f" (n={n})" if n is not None and n < RUNS else "")


def write(name, text):
    (GEN / name).write_text(text, encoding="utf-8")
    print("wrote", GEN / name)


def tabular(cols, head, rows, size="\\footnotesize"):
    body = "\n".join(" & ".join(r) + " \\\\" for r in rows)
    return (f"{size}\n\\renewcommand{{\\arraystretch}}{{1.2}}\n\\begin{{tabular}}{{{cols}}}\n\\toprule\n" + " & ".join(head)
            + " \\\\\n\\midrule\n" + body + "\n\\bottomrule\n\\end{tabular}\n")


# ------------------------------------------------------------------ tables
D0 = 200
# report table: the best mean of each column in bold (rounded as printed), not the whole proposed row
HEAD_COLS = [("transmissions", 1, 1.0, min), ("collision_losses", 0, 1.0, min), ("reachability", 1, 100, max),
             ("t90_ms", 1, 1.0, min), ("suppression_ratio", 1, 100, max), ("rsu_delay_ms", 1, 1.0, min)]
best = {k: pick(round(val(D0, p, k, s)[0], dec) for p in SCHEMES) for k, dec, s, pick in HEAD_COLS}
rows = []
for p in SCHEMES:
    row = [LABEL[p]]
    for k, dec, s, _ in HEAD_COLS:
        m, c, n = val(D0, p, k, s)
        txt = cell(m, c, n, dec)
        row.append(f"\\textbf{{{txt}}}" if round(m, dec) == best[k] else txt)
    rows.append(row)
write("tab_headline_200.tex", tabular("lrrrrrr", ["Scheme", "Frames on air", "Receptions lost", "Reach (\\%)",
                                                  "$t_{90}$ (ms)", "Suppression (\\%)", "RSU registration (ms)"], rows))


def verdict(m, c, lower_is_better=True):
    """Paired difference (proposed minus baseline) judged by its 95 % CI: clearly better, clearly worse, or similar."""
    if m is None or c is None:
        return "--"
    lo, hi = m - c, m + c
    good, bad = (hi < 0, lo > 0) if lower_is_better else (lo > 0, hi < 0)
    return "better" if good else "worse" if bad else "similar"


VERDICT_COLS = [("transmissions", 1, 1.0, True), ("collision_losses", 0, 1.0, True), ("reachability", 1, 100, False),
                ("t90_ms", 1, 1.0, True), ("rsu_delay_ms", 1, 1.0, True)]


def verdict_cell(r, k, dec, s, lower):
    m, c, n = num(r[k]), num(r[k + "_ci95"]), int(float(r[k + "_n"]))
    m, c = (None if m is None else m * s), (None if c is None else c * s)
    v = verdict(m, c, lower)
    word = {"better": "\\textbf{better}", "worse": "\\textit{worse}", "similar": "similar"}.get(v, v)
    return f"{word}\\newline {{\\scriptsize {pm(m, c, n, dec)}}}"


rows = [[LABEL[b_]] + [verdict_cell(paired[(D0, b_)], k, dec, s, lo) for k, dec, s, lo in VERDICT_COLS]
        for b_ in ["flooding", "flooding_rad", "slotted1p", "slotted1p_rad"]]
write("tab_verdict_200.tex", tabular("p{3.4cm}" + ">{\\raggedleft\\arraybackslash}p{2.15cm}" * 5,
                                     ["Proposed vs", "Frames on air", "Receptions lost", "Reach (pp)", "$t_{90}$ (ms)",
                                      "RSU registration (ms)"], rows))
rows = [[str(d)] + [verdict_cell(paired[(d, "slotted1p_rad")], k, dec, s, lo) for k, dec, s, lo in VERDICT_COLS]
        for d in DENS]
write("tab_verdict_strongest.tex", tabular("r" + ">{\\raggedleft\\arraybackslash}p{2.35cm}" * 5,
                                           ["Vehicles", "Frames on air", "Receptions lost", "Reach (pp)", "$t_{90}$ (ms)",
                                            "RSU registration (ms)"], rows))
# slide version: fewer columns, no CI
rows = []
for p in SCHEMES:
    b = (lambda s: f"\\textbf{{{s}}}") if p == "proposed" else (lambda s: s)
    f = lambda key, dec, s=1.0: f"{val(D0, p, key, s)[0]:.{dec}f}"
    rows.append([b(LABEL[p]), b(f("transmissions", 1)), b(f("collision_losses", 0)), b(f("reachability", 1, 100)),
                 b(f("t90_ms", 1)), b(f("suppression_ratio", 1, 100))])
write("tab_headline_200_slide.tex", tabular("lrrrrr", ["Scheme (200 vehicles)", "Frames", "Rx lost", "Reach \\%",
                                                       "$t_{90}$ ms", "Suppr. \\%"], rows, "\\small"))

for key, name, dec, scale in (("transmissions", "frames", 1, 1.0), ("t90_ms", "t90", 1, 1.0),
                              ("collision_losses", "losses", 0, 1.0)):
    rows = [[str(d)] + [cell(*val(d, p, key, scale), dec) for p in SCHEMES] for d in DENS]
    write(f"tab_density_{name}.tex", tabular("r" + "r" * len(SCHEMES), ["Vehicles"] + [LABEL[p].replace("Slotted 1-persistence", "Slotted 1-p")
                                                                                         for p in SCHEMES], rows, "\\scriptsize"))

rows = []
for b_ in ["flooding", "flooding_rad", "slotted1p", "slotted1p_rad"]:
    r = paired[(D0, b_)]
    g = lambda k, dec, s=1.0: pm(num(r[k]) * s if num(r[k]) is not None else None,
                                  num(r[k + "_ci95"]) * s if num(r[k + "_ci95"]) is not None else None, int(float(r[k + "_n"])), dec)
    rows.append([LABEL[b_], g("transmissions", 1), g("collision_losses", 0), g("reachability", 1, 100), g("t90_ms", 1),
                 g("rsu_delay_ms", 1)])
write("tab_paired_200.tex", tabular("lrrrrr", ["Proposed minus", "$\\Delta$ frames", "$\\Delta$ receptions lost",
                                               "$\\Delta$ reach (pp)", "$\\Delta t_{90}$ (ms)", "$\\Delta$ RSU registration (ms)"], rows))

rows = []
for d in DENS:
    r = paired[(d, "slotted1p_rad")]
    g = lambda k, dec, s=1.0: pm(num(r[k]) * s, num(r[k + "_ci95"]) * s, int(float(r[k + "_n"])), dec)
    rows.append([str(d), g("transmissions", 1), g("collision_losses", 0), g("reachability", 1, 100), g("t90_ms", 1)])
write("tab_paired_strongest.tex", tabular("rrrrr", ["Vehicles", "$\\Delta$ frames", "$\\Delta$ receptions lost",
                                                    "$\\Delta$ reach (pp)", "$\\Delta t_{90}$ (ms)"], rows))

rows = []
for p in ["proposed"] + ABLATIONS:
    b = (lambda s: f"\\textbf{{{s}}}") if p == "proposed" else (lambda s: s)
    rows.append([b(LABEL[p]), b(cell(*val(D0, p, "transmissions"), 1)), b(cell(*val(D0, p, "collision_losses"), 0)),
                 b(cell(*val(D0, p, "reachability", 100), 1)), b(cell(*val(D0, p, "t90_ms"), 1)),
                 b(cell(*val(D0, p, "suppression_ratio", 100), 1))])
write("tab_ablation_200.tex", tabular("lrrrrr", ["Configuration (200 vehicles)", "Frames on air", "Receptions lost",
                                                 "Reach (\\%)", "$t_{90}$ (ms)", "Suppression (\\%)"], rows))

rows = []
for d in DENS:
    fr, n_reg = val(d, "ch_route", "transmissions"), val(d, "ch_route", "rsu_delay_ms")
    rows.append([str(d), cell(*fr, 1), f"{n_reg[2]} of {RUNS}", cell(n_reg[0], n_reg[1], None, 1),
                 cell(*val(d, "proposed", "rsu_delay_ms"), 1)])
write("tab_chroute.tex", tabular("rrrrr", ["Vehicles", "Route frames", "RSU registered (runs)",
                                           "Route: RSU registration (ms)", "Broadcast: RSU registration (ms)"], rows))


def forgery(path):
    out = {}
    for r in read(path):
        k = (int(r["density"]), r["variant"])
        t = out.setdefault(k, {"runs": 0, "cert": 0, "rsu": 0, "share": []})
        t["runs"] += 1
        t["cert"] += int(float(r["certificate_formed"]) > 0)
        t["rsu"] += int(float(r["rsu_registered"]) > 0)
        s = num(r["accepted_share"])
        if s is not None:
            t["share"].append(s)
    return out


FORG = forgery(PROC / "forgery_runs.csv")
ONOFF = {c: forgery(SENS / f"onoff_{c}" / "processed" / "forgery_runs.csv") for c in ("0", "0.5", "0.9")}
VAR = [("no_voting", "No voting (alert accepted as sent)"), ("voting_only", "Voting + BLS, no reputation gate"),
       ("voting_reputation", "Voting + BLS + reputation (full)")]
rows = []
for v, lab in VAR:
    t = FORG[(D0, v)]
    share = 100 * sum(t["share"]) / len(t["share"])
    rows.append([lab, "persistent (default)", f"{t['cert']} of {t['runs']}", f"{share:.1f}", f"{t['rsu']} of {t['runs']}"])
for c, lab in (("0.5", "on-off, well-behaved 50\\,\\%"), ("0.9", "on-off, well-behaved 90\\,\\%")):
    t = ONOFF[c][(D0, "voting_reputation")]
    share = 100 * sum(t["share"]) / len(t["share"])
    rows.append(["Voting + BLS + reputation (full)", lab, f"{t['cert']} of {t['runs']}", f"{share:.1f}", f"{t['rsu']} of {t['runs']}"])
R_ = ">{\\raggedleft\\arraybackslash}p{1.9cm}"
write("tab_forgery_200.tex", tabular(">{\\raggedright\\arraybackslash}p{4.9cm}>{\\raggedright\\arraybackslash}p{3.6cm}" + R_ * 3,
                                     ["Protection", "Attackers", "Certificate formed",
                                      "Honest vehicles accepting (\\%)", "Registered by an RSU"], rows))


def sens(name):
    return {r["protocol"]: r for r in read(SENS / name / "processed" / "summary.csv") if int(r["density"]) == D0}


rows = []
for rng in ("150", "300", "450"):
    s = sens(f"range_{rng}")
    for p in ("flooding", "slotted1p_rad", "proposed"):
        r = s[p]
        g = lambda k, dec, sc=1.0: cell(num(r[k]) * sc if num(r[k]) is not None else None,
                                         num(r[k + "_ci95"]) * sc if num(r[k + "_ci95"]) is not None else None,
                                         int(float(r[k + "_n"])), dec)
        rows.append([f"{rng} m", LABEL[p], g("transmissions", 1), g("reachability", 1, 100), g("t90_ms", 1)])
write("tab_range.tex", tabular("llrrr", ["Radio range", "Scheme", "Frames on air", "Reach (\\%)", "$t_{90}$ (ms)"], rows,
                               "\\scriptsize"))

# ------------------------------------------------------------------ numbers quoted in the text (both documents)
F = lambda d, p, k, dec=1, s=1.0: f"{val(d, p, k, s)[0]:.{dec}f}"
P = lambda d, b_, k, dec=1, s=1.0: signed(num(paired[(d, b_)][k]) * s, dec)
PC = lambda d, b_, k, dec=1, s=1.0: f"{num(paired[(d, b_)][k + '_ci95']) * s:.{dec}f}"
fl, pr = val(D0, "flooding", "transmissions")[0], val(D0, "proposed", "transmissions")[0]
s1 = val(D0, "slotted1p", "transmissions")[0]
macros = {
    "FrFlood": F(D0, "flooding", "transmissions"), "FrFloodRad": F(D0, "flooding_rad", "transmissions"),
    "FrSlot": F(D0, "slotted1p", "transmissions"), "FrSlotRad": F(D0, "slotted1p_rad", "transmissions"),
    "FrProp": F(D0, "proposed", "transmissions"), "FrRoute": F(D0, "ch_route", "transmissions"),
    "FrPropFiveH": F(500, "proposed", "transmissions"), "FrFloodFiveH": F(500, "flooding", "transmissions"),
    "FrSlotRadFiveH": F(500, "slotted1p_rad", "transmissions"), "FrSlotFiveH": F(500, "slotted1p", "transmissions"),
    "FrPropFifty": F(50, "proposed", "transmissions"), "FrFloodFifty": F(50, "flooding", "transmissions"),
    "CutVsFlood": f"{100 * (1 - pr / fl):.0f}", "CutVsSlot": f"{100 * (1 - pr / s1):.0f}",
    "LossFlood": F(D0, "flooding", "collision_losses", 0), "LossSlot": F(D0, "slotted1p", "collision_losses", 0),
    "LossSlotRad": F(D0, "slotted1p_rad", "collision_losses", 0), "LossProp": F(D0, "proposed", "collision_losses", 0),
    "LossPropFiveH": F(500, "proposed", "collision_losses", 0), "LossSlotRadFiveH": F(500, "slotted1p_rad", "collision_losses", 0),
    "TnFlood": F(D0, "flooding", "t90_ms"), "TnSlotRad": F(D0, "slotted1p_rad", "t90_ms"), "TnProp": F(D0, "proposed", "t90_ms"),
    "TnSlot": F(D0, "slotted1p", "t90_ms"),
    "DTnFlood": P(D0, "flooding", "t90_ms"), "DTnFloodCI": PC(D0, "flooding", "t90_ms"),
    "DTnSlotRadFiveH": P(500, "slotted1p_rad", "t90_ms"), "DTnSlotRadFiveHCI": PC(500, "slotted1p_rad", "t90_ms"),
    "DTnSlotRadFifty": P(50, "slotted1p_rad", "t90_ms"), "DTnSlotRadFiftyCI": PC(50, "slotted1p_rad", "t90_ms"),
    "DFrSlotRad": P(D0, "slotted1p_rad", "transmissions"), "DFrSlotRadCI": PC(D0, "slotted1p_rad", "transmissions"),
    "SupProp": F(D0, "proposed", "suppression_ratio", 1, 100), "SupSlotRad": F(D0, "slotted1p_rad", "suppression_ratio", 1, 100),
    "SupSlot": F(D0, "slotted1p", "suppression_ratio", 1, 100),
    "ReachSlotRadFifty": F(50, "slotted1p_rad", "reachability", 1, 100), "ReachSlotFifty": F(50, "slotted1p", "reachability", 1, 100),
    "ReachFloodTwoH": F(D0, "flooding", "reachability", 1, 100),
    "RsuProp": F(D0, "proposed", "rsu_delay_ms"), "RsuFlood": F(D0, "flooding", "rsu_delay_ms"),
    "RsuRoute": F(D0, "ch_route", "rsu_delay_ms"), "RsuRouteRuns": str(val(D0, "ch_route", "rsu_delay_ms")[2]),
    "QuorumMs": F(D0, "proposed", "quorum_ms"),
    "FrNoSec": F(D0, "no_security", "transmissions"), "TnNoSec": F(D0, "no_security", "t90_ms"),
    "SecFrames": f"{val(D0, 'proposed', 'transmissions')[0] - val(D0, 'no_security', 'transmissions')[0]:.1f}",
    "SecTn": f"{val(D0, 'proposed', 't90_ms')[0] - val(D0, 'no_security', 't90_ms')[0]:.1f}",
    "FrNoClu": F(D0, "no_clustering", "transmissions"), "FrNoCluFiveH": F(500, "no_clustering", "transmissions"),
    "FrNoCov": F(D0, "no_coverage", "transmissions"), "FrNoRad": F(D0, "no_rad", "transmissions"),
    "ForgNoVote": f"{FORG[(D0, 'no_voting')]['rsu']}", "ForgVoteOnly": f"{FORG[(D0, 'voting_only')]['rsu']}",
    "ForgFull": f"{FORG[(D0, 'voting_reputation')]['rsu']}", "ForgOnOffHalf": f"{ONOFF['0.5'][(D0, 'voting_reputation')]['rsu']}",
    "ForgOnOffNine": f"{ONOFF['0.9'][(D0, 'voting_reputation')]['rsu']}",
    "ForgCertFull": f"{FORG[(D0, 'voting_reputation')]['cert']}",
    "Runs": str(RUNS), "Scenarios": str(len(DENS) * RUNS), "Densities": str(len(DENS)),
    # added for the results discussion of the report (same CSVs)
    "FrNoSlots": F(D0, "no_slots", "transmissions"), "FrNoCluFwd": F(D0, "no_cluster_forwarding", "transmissions"),
    "FrNoRep": F(D0, "no_reputation", "transmissions"),
    "FrPropPlusRoute": f"{val(D0, 'proposed', 'transmissions')[0] + val(D0, 'ch_route', 'transmissions')[0]:.1f}",
    "DTnFloodRad": P(D0, "flooding_rad", "t90_ms"), "DTnFloodRadCI": PC(D0, "flooding_rad", "t90_ms"),
    "DTnSlot": P(D0, "slotted1p", "t90_ms"), "DTnSlotCI": PC(D0, "slotted1p", "t90_ms"),
    "DTnSlotRad": P(D0, "slotted1p_rad", "t90_ms"), "DTnSlotRadCI": PC(D0, "slotted1p_rad", "t90_ms"),
    "DTnSlotRadThreeH": P(300, "slotted1p_rad", "t90_ms"), "DTnSlotRadThreeHCI": PC(300, "slotted1p_rad", "t90_ms"),
    "DFrSlot": P(D0, "slotted1p", "transmissions"), "DFrSlotCI": PC(D0, "slotted1p", "transmissions"),
    "DFrSlotRadHundred": P(100, "slotted1p_rad", "transmissions"),
    "DFrSlotRadHundredCI": PC(100, "slotted1p_rad", "transmissions"),
    "DLossSlotRad": P(D0, "slotted1p_rad", "collision_losses", 0), "DLossSlotRadCI": PC(D0, "slotted1p_rad", "collision_losses", 0),
    "DLossSlotRadFiveH": P(500, "slotted1p_rad", "collision_losses", 0),
    "DLossSlotRadFiveHCI": PC(500, "slotted1p_rad", "collision_losses", 0),
    "DLossSlotRadHundred": P(100, "slotted1p_rad", "collision_losses", 0),
    "DLossSlotRadHundredCI": PC(100, "slotted1p_rad", "collision_losses", 0),
    "DReachSlotRadFifty": P(50, "slotted1p_rad", "reachability", 1, 100),
    "DReachSlotRadFiftyCI": PC(50, "slotted1p_rad", "reachability", 1, 100),
    "DRsuSlotRad": P(D0, "slotted1p_rad", "rsu_delay_ms"), "DRsuSlotRadCI": PC(D0, "slotted1p_rad", "rsu_delay_ms"),
    "NTnSlotRadFifty": str(int(float(paired[(50, "slotted1p_rad")]["t90_ms_n"]))),
    "TnSlotRadFifty": F(50, "slotted1p_rad", "t90_ms"), "TnPropFifty": F(50, "proposed", "t90_ms"),
    "TnPropFiveH": F(500, "proposed", "t90_ms"), "TnSlotRadFiveH": F(500, "slotted1p_rad", "t90_ms"),
    "RsuSlotRad": F(D0, "slotted1p_rad", "rsu_delay_ms"),
}
lines = ["% Generated by scripts/make_figures_and_tables.py from results/urban/processed and results/urban/sensitivity.",
         "% 200 vehicles unless the name says FiveH (500) or Fifty (50). Do not edit by hand."]
lines += [f"\\newcommand{{\\N{k}}}{{{v}}}" for k, v in macros.items()]
write("numbers.tex", "\n".join(lines) + "\n")

# ------------------------------------------------------------------ charts
plt.rcParams.update({"font.size": 12, "axes.titlesize": 13, "axes.labelsize": 12, "legend.fontsize": 10.5,
                     "font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / f"{name}.pdf")


def density_chart(key, ylabel, name, log=False, scale=1.0):
    fig, ax = plt.subplots(figsize=(7.2, 4.3))
    for i, p in enumerate(SCHEMES):
        xs = [d * (1 + (i - 2) * 0.012) for d in DENS]
        ms = [val(d, p, key, scale)[0] for d in DENS]
        cs = [val(d, p, key, scale)[1] or 0 for d in DENS]
        ax.errorbar(xs, ms, yerr=cs, label=LABEL[p], color=COLOR[p], marker=MARK[p], ms=6, lw=2.2 if p == "proposed" else 1.6,
                    capsize=3)
    ax.set_xlabel("Vehicles in the scenario")
    ax.set_ylabel(ylabel + (" (log scale)" if log else ""))
    if log:
        ax.set_yscale("log")
        lo, hi = ax.get_ylim()
        ticks = [t for t in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000) if lo <= t <= hi]
        ax.set_yticks(ticks)
        ax.set_yticklabels([f"{t:,}" for t in ticks])
        ax.minorticks_off()
    ax.set_xticks(DENS)
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.17), fontsize=10)
    save(fig, name)


density_chart("transmissions", "Frames on air per alert", "chart_frames", log=True)
density_chart("collision_losses", "Receptions lost to collisions", "chart_losses", log=True)
density_chart("t90_ms", "Time until 90 % hold it, t90 (ms)", "chart_t90")

fig, ax = plt.subplots(figsize=(7.2, 4.3))
order = ["proposed"] + ABLATIONS
ms = [val(D0, p, "transmissions")[0] for p in order]
cs = [val(D0, p, "transmissions")[1] for p in order]
ax.barh(range(len(order)), ms, xerr=cs, color=["#A4123F"] + ["#8a9bb0"] * len(ABLATIONS), capsize=3)
ax.set_yticks(range(len(order)))
ax.set_yticklabels(["Proposed (full)"] + [LABEL[p] for p in ABLATIONS])
ax.invert_yaxis()
for i, m in enumerate(ms):
    ax.text(m + max(ms) * 0.01 + (cs[i] or 0), i, f"{m:.1f}", va="center", fontsize=10)
ax.set_xlabel("Frames on air per alert, 200 vehicles (mean, 95 % CI)")
ax.grid(axis="x", alpha=0.3)
save(fig, "chart_ablation")

fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.4, 3.9), gridspec_kw={"width_ratios": [1.15, 1]})
labs = ["No voting", "Voting + BLS,\nno reputation", "Voting + BLS +\nreputation (full)"]
vals = [FORG[(D0, v)]["rsu"] for v, _ in VAR]
a1.bar(range(3), vals, color=["#4d4d4d", "#1f5fa0", "#A4123F"])
for i, v in enumerate(vals):
    a1.text(i, v + 0.6, f"{v} of {RUNS}", ha="center", fontsize=10.5)
a1.set_xticks(range(3))
a1.set_xticklabels(labs, fontsize=10)
a1.set_ylim(0, RUNS + 4)
a1.set_ylabel("Runs in which an RSU\nregistered the forged event")
a1.set_title("(a) Protection level, persistent attackers", fontsize=11.5)
vals = [ONOFF[c][(D0, "voting_reputation")]["rsu"] for c in ("0", "0.5", "0.9")]
a2.bar(range(3), vals, color=["#A4123F"] * 3)
for i, v in enumerate(vals):
    a2.text(i, v + 0.6, f"{v} of {RUNS}", ha="center", fontsize=10.5)
a2.set_xticks(range(3))
a2.set_xticklabels(["never (0)", "50 % of\nthe time", "90 % of\nthe time"], fontsize=10)
a2.set_ylim(0, RUNS + 4)
a2.set_xlabel("Attacker relays correctly while watched")
a2.set_title("(b) Full protection vs on-off attackers", fontsize=11.5)
for a in (a1, a2):
    a.grid(axis="y", alpha=0.3)
fig.tight_layout()
save(fig, "chart_forgery")

# ------------------------------------------------------------------ report charts (drawn at print size: 6.7 in = text width)
# The chart_* files above are sized for the slides and stay unchanged; the report uses these rep_* files.
plt.rcParams.update({"font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8, "xtick.labelsize": 7.5,
                     "ytick.labelsize": 7.5, "legend.fontsize": 7.5, "axes.titleweight": "bold", "axes.titlelocation": "left"})
TW = 6.7
SHORT = {**LABEL, "slotted1p": "Slotted 1-p", "slotted1p_rad": "Slotted 1-p + random delay"}


def rsave(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=300)
    plt.close(fig)
    print("wrote", FIG / f"{name}.pdf")


def log_ticks(ax):
    ax.set_yscale("log")
    lo, hi = ax.get_ylim()
    ticks = [t for t in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000) if lo <= t <= hi]
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{t:,}" for t in ticks])
    ax.minorticks_off()


def density_panel(ax, key, title, ylabel, scale=1.0, log=False):
    for i, p in enumerate(SCHEMES):
        xs = [d + (i - 2) * 4 for d in DENS]
        ms = [val(d, p, key, scale)[0] for d in DENS]
        cs = [val(d, p, key, scale)[1] or 0 for d in DENS]
        ax.errorbar(xs, ms, yerr=cs, label=SHORT[p], color=COLOR[p], marker=MARK[p], ms=3.6,
                    lw=1.7 if p == "proposed" else 1.1, capsize=2, zorder=3 if p == "proposed" else 2)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Vehicles in the scenario")
    ax.set_xticks(DENS)
    ax.set_xticklabels([str(d) for d in DENS])
    if log:
        log_ticks(ax)
    ax.grid(alpha=0.3)


def legend_below(fig, ax):
    h, l = ax.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, handlelength=1.8, columnspacing=1.0)


fig, (a1, a2) = plt.subplots(1, 2, figsize=(TW, 2.75))
density_panel(a1, "transmissions", "(a) Frames on air per alert", "Frames (log scale)", log=True)
density_panel(a2, "collision_losses", "(b) Receptions lost to collisions", "Receptions (log scale)", log=True)
fig.subplots_adjust(left=0.085, right=0.99, top=0.91, bottom=0.27, wspace=0.27)
legend_below(fig, a1)
rsave(fig, "rep_frames_losses")

fig, (a1, a2) = plt.subplots(1, 2, figsize=(TW, 2.75))
density_panel(a1, "reachability", "(a) Reach", "Reach (%)", scale=100)
density_panel(a2, "t90_ms", "(b) Time until 90 % hold the alert, $t_{90}$", "$t_{90}$ (ms)")
fig.subplots_adjust(left=0.085, right=0.99, top=0.91, bottom=0.27, wspace=0.27)
legend_below(fig, a1)
rsave(fig, "rep_reach_t90")

# proposed minus the strongest baseline, per density (paired, mean and 95 % CI)
fig, axes = plt.subplots(1, 3, figsize=(TW, 2.3))
for ax, (k, title, unit) in zip(axes, [("transmissions", "(a) $\\Delta$ frames on air", "frames"),
                                       ("collision_losses", "(b) $\\Delta$ receptions lost", "receptions"),
                                       ("t90_ms", "(c) $\\Delta t_{90}$", "ms")]):
    ms = [num(paired[(d, "slotted1p_rad")][k]) for d in DENS]
    cs = [num(paired[(d, "slotted1p_rad")][k + "_ci95"]) for d in DENS]
    ax.axhline(0, color="#555", lw=0.8, ls="--")
    ax.errorbar(range(len(DENS)), ms, yerr=cs, color="#A4123F", marker="o", ms=3.6, lw=0, elinewidth=1.2, capsize=2.5)
    ax.set_xticks(range(len(DENS)))
    ax.set_xticklabels([str(d) for d in DENS])
    ax.set_xlabel("Vehicles in the scenario")
    ax.set_ylabel(unit)
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.3)
fig.subplots_adjust(left=0.075, right=0.99, top=0.88, bottom=0.2, wspace=0.34)
rsave(fig, "rep_strongest")

fig, (a1, a2) = plt.subplots(1, 2, figsize=(TW, 2.45), sharey=True)
order = ["proposed"] + ABLATIONS
names = ["Proposed (full)"] + [LABEL[p] for p in ABLATIONS]
for ax, (k, title, xlabel) in zip((a1, a2), [("transmissions", "(a) Frames on air per alert", "Frames"),
                                             ("t90_ms", "(b) $t_{90}$", "ms")]):
    ms = [val(D0, p, k)[0] for p in order]
    cs = [val(D0, p, k)[1] or 0 for p in order]
    ax.barh(range(len(order)), ms, xerr=cs, color=["#A4123F"] + ["#8a9bb0"] * len(ABLATIONS), capsize=2,
            error_kw={"elinewidth": 0.8})
    for i, m in enumerate(ms):
        ax.text(m + cs[i] + max(ms) * 0.015, i, f"{m:.1f}", va="center", fontsize=7)
    ax.set_xlim(0, max(m + c for m, c in zip(ms, cs)) * 1.18)
    ax.set_title(title)
    ax.set_xlabel(xlabel + " (mean, 95 % CI, 200 vehicles)")
    ax.grid(axis="x", alpha=0.3)
a1.set_yticks(range(len(order)))
a1.set_yticklabels(names)
a1.invert_yaxis()
fig.subplots_adjust(left=0.3, right=0.99, top=0.9, bottom=0.18, wspace=0.08)
rsave(fig, "rep_ablation")

fig, (a1, a2) = plt.subplots(1, 2, figsize=(TW, 2.45), gridspec_kw={"width_ratios": [1.1, 1]}, sharey=True)
vals = [FORG[(D0, v)]["rsu"] for v, _ in VAR]
a1.bar(range(3), vals, color=["#4d4d4d", "#1f5fa0", "#A4123F"], width=0.6)
a1.set_xticks(range(3))
a1.set_xticklabels(["No voting", "Voting + BLS,\nno reputation", "Voting + BLS +\nreputation (full)"])
a1.set_ylabel("Runs with the forged event\nregistered by an RSU (of 30)")
a1.set_title("(a) Protection level, persistent attackers")
vals2 = [ONOFF[c][(D0, "voting_reputation")]["rsu"] for c in ("0", "0.5", "0.9")]
a2.bar(range(3), vals2, color="#A4123F", width=0.6)
a2.set_xticks(range(3))
a2.set_xticklabels(["never", "50 % of\nthe time", "90 % of\nthe time"])
a2.set_xlabel("Attacker relays correctly while watched", labelpad=2)
a2.set_title("(b) Full protection, on-off attackers")
for ax, vs in ((a1, vals), (a2, vals2)):
    for i, v in enumerate(vs):
        ax.text(i, v + 0.7, f"{v} of {RUNS}", ha="center", fontsize=7.5)
    ax.set_ylim(0, RUNS + 4)
    ax.grid(axis="y", alpha=0.3)
fig.subplots_adjust(left=0.1, right=0.99, top=0.9, bottom=0.25, wspace=0.08)
rsave(fig, "rep_forgery")
print("done")
