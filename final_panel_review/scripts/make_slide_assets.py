"""Slide-sized charts, tables and crops for the panel presentation, read only from the experiment outputs
(results/urban/processed/*.csv, results/urban/sensitivity/onoff_*/) and the genuine dashboard captures.
The report's files are not touched: everything written here starts with sl_ or slide_.

    python final_panel_review/scripts/make_slide_assets.py

Writes figures/sl_*.pdf|png, figures/dashboard/sl_*.png, generated/tab_slide_headline.tex,
generated/slide_verdict_grid.tex.
"""
import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "final_panel_review"
FIG, GEN = OUT / "figures", OUT / "generated"
PROC, SENS = ROOT / "results" / "urban" / "processed", ROOT / "results" / "urban" / "sensitivity"
RUNS, D0 = 30, 200
SCHEMES = ["flooding", "flooding_rad", "slotted1p", "slotted1p_rad", "proposed"]
LABEL = {"flooding": "Blind flooding", "flooding_rad": "Flooding + random delay", "slotted1p": "Slotted 1-p",
         "slotted1p_rad": "Slotted 1-p + random delay", "proposed": "Proposed"}
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
    m, c = num(r[key]), num(r.get(key + "_ci95"))
    return (None if m is None else m * scale), (None if c is None else c * scale)


def signed(m, dec):
    return ("+" if m >= 0 else "$-$") + f"{abs(m):.{dec}f}"


# ------------------------------------------------------------------ 200-vehicle table: best mean of each column in bold
COLS = [("transmissions", 1, 1.0, min), ("collision_losses", 0, 1.0, min), ("reachability", 1, 100, max),
        ("t90_ms", 1, 1.0, min), ("suppression_ratio", 1, 100, max), ("rsu_delay_ms", 1, 1.0, min)]
best = {k: pick(round(val(D0, p, k, s)[0], dec) for p in SCHEMES) for k, dec, s, pick in COLS}
rows = []
ROWCOLOR = {"slotted1p_rad": "\\rowcolor{rowBase}", "proposed": "\\rowcolor{rowProp}"}
NAME = {**LABEL, "slotted1p_rad": "\\textbf{Slotted 1-p + random delay}",
        "proposed": "\\textbf{Proposed}"}
for p in SCHEMES:
    cells = [ROWCOLOR.get(p, "") + NAME[p]]
    for k, dec, s, _ in COLS:
        m, c = val(D0, p, k, s)
        txt = f"{m:.{dec}f}"
        txt = f"\\textbf{{{txt}}}" if round(m, dec) == best[k] else txt
        cells.append(txt + f"{{\\scriptsize\\,$\\pm${c:.{dec}f}}}")
    rows.append(" & ".join(cells) + " \\\\")
(GEN / "tab_slide_headline.tex").write_text(
    "\\renewcommand{\\arraystretch}{1.32}\n\\begin{tabular}{lrrrrrr}\n\\toprule\n"
    "\\textbf{Scheme} & \\textbf{Frames} & \\textbf{Rx lost} & \\textbf{Reach (\\%)} & \\textbf{$t_{90}$ (ms)} & "
    "\\textbf{Suppr. (\\%)} & \\textbf{RSU reg. (ms)} \\\\\n"
    "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n", encoding="utf-8")

# ------------------------------------------------------------------ verdict grid: proposed minus slotted 1-p + random delay
METRICS = [("transmissions", "Frames", 1, 1.0, True), ("collision_losses", "Receptions lost", 0, 1.0, True),
           ("reachability", "Reach (pp)", 1, 100, False), ("t90_ms", "$t_{90}$ (ms)", 1, 1.0, True),
           ("rsu_delay_ms", "RSU reg. (ms)", 1, 1.0, True)]
FILL = {"better": "vBetter", "similar": "vSimilar", "worse": "vWorse"}
W, H, X0 = 2.6, 0.7, 1.25
tz = ["\\begin{tikzpicture}[x=1cm,y=1cm]"]
for j, (_, title, *_r) in enumerate(METRICS):
    tz.append(f"\\node[font=\\footnotesize\\bfseries,align=center,text width={W - 0.1}cm] at ({X0 + j * W + W / 2:.3f},0.3) {{{title}}};")
tz.append("\\node[font=\\footnotesize\\bfseries] at (0.55,0.3) {Vehicles};")
for i, d in enumerate(DENS):
    y = -i * H
    tz.append(f"\\node[font=\\small\\bfseries] at (0.55,{y - H / 2:.3f}) {{{d}}};")
    r = paired[(d, "slotted1p_rad")]
    for j, (k, _, dec, s, lower) in enumerate(METRICS):
        m, c, n = num(r[k]) * s, num(r[k + "_ci95"]) * s, int(float(r[k + "_n"]))
        good, bad = (m + c < 0, m - c > 0) if lower else (m - c > 0, m + c < 0)
        v = "better" if good else "worse" if bad else "similar"
        x = X0 + j * W
        note = f"{signed(m, dec)}$\\pm${c:.{dec}f}" + (f" (n={n})" if n < RUNS else "")
        tz.append(f"\\fill[{FILL[v]}] ({x + 0.03:.3f},{y - 0.03:.3f}) rectangle ({x + W - 0.03:.3f},{y - H + 0.03:.3f});")
        tz.append(f"\\node[align=center,inner sep=0pt,font=\\footnotesize] at ({x + W / 2:.3f},{y - H / 2:.3f}) "
                  f"{{\\textbf{{{v}}}\\\\[-1pt]{{\\scriptsize {note}}}}};")
tz.append("\\end{tikzpicture}")
(GEN / "slide_verdict_grid.tex").write_text("\n".join(tz) + "\n", encoding="utf-8")

# ------------------------------------------------------------------ charts at slide size (text width of a 16:9 frame = 14 cm)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 9.5, "axes.titleweight": "bold",
                     "axes.titlelocation": "left", "axes.labelsize": 9, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
                     "legend.fontsize": 8.5, "axes.spines.top": False, "axes.spines.right": False})


def save(fig, name):
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


STYLE = {"flooding": dict(color="#8c8c8c", lw=1.1, ls="--", ms=3.4), "flooding_rad": dict(color="#b8b8b8", lw=1.1, ls=":", ms=3.4),
         "slotted1p": dict(color="#9cc3e6", lw=1.1, ls="-", ms=3.4), "slotted1p_rad": dict(color="#1f5fa0", lw=2.1, ls="-", ms=4.5),
         "proposed": dict(color="#A4123F", lw=2.5, ls="-", ms=4.8)}


def panel(ax, key, title, ylabel, scale=1.0, log=False):
    for i, p in enumerate(SCHEMES):           # densities as evenly spaced categories, so all six labels stay readable
        xs = [k + (i - 2) * 0.05 for k in range(len(DENS))]
        ms = [val(d, p, key, scale)[0] for d in DENS]
        cs = [val(d, p, key, scale)[1] or 0 for d in DENS]
        st = STYLE[p]
        ax.errorbar(xs, ms, yerr=cs, label=LABEL[p] + (" (strongest baseline)" if p == "slotted1p_rad" else ""),
                    color=st["color"], ls=st["ls"], lw=st["lw"], marker=MARK[p], ms=st["ms"], capsize=2,
                    elinewidth=1.0, zorder=4 if p == "proposed" else 3 if p == "slotted1p_rad" else 2)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Vehicles in the scenario")
    ax.set_xticks(range(len(DENS)))
    ax.set_xticklabels([str(d) for d in DENS])
    if log:
        log_ticks(ax)
    ax.grid(alpha=0.3)


def two_panels(name, left, right):
    # drawn at the size it is shown (full slide width), so the fonts on the slide are the sizes set above;
    # the legend is drawn on the slide in one line
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(5.55, 2.2))
    panel(a1, *left)
    panel(a2, *right)
    fig.subplots_adjust(left=0.1, right=0.99, top=0.9, bottom=0.21, wspace=0.24)
    save(fig, name)


# one panel for the combined results slide: frames per alert as traffic grows, lines labelled directly
fig, ax = plt.subplots(figsize=(2.75, 1.1))
for i, p in enumerate(SCHEMES):
    st = STYLE[p]
    ms = [val(d, p, "transmissions")[0] for d in DENS]
    cs = [val(d, p, "transmissions")[1] or 0 for d in DENS]
    ax.errorbar(range(len(DENS)), ms, yerr=cs, color=st["color"], ls=st["ls"], lw=st["lw"] * 0.85, marker=MARK[p],
                ms=st["ms"] * 0.75, capsize=1.5, elinewidth=0.8, zorder=4 if p == "proposed" else 3)
log_ticks(ax)
ax.set_ylim(12, 700)
log_ticks(ax)
ax.set_xticks(range(len(DENS)))
ax.set_xticklabels([str(d) for d in DENS], fontsize=7)
ax.tick_params(axis="y", labelsize=7)
ax.set_xlabel("vehicles in the scenario", fontsize=7.2, labelpad=1)
ax.set_ylabel("frames (log)", fontsize=7.2, labelpad=1)
ax.grid(alpha=0.3)
ax.text(-0.1, 420, "flooding (with or without delay)", fontsize=6.6, color="#6b6b6b")
ax.text(2.55, 46, "slotted 1-p", fontsize=6.6, color="#5b8fc4")
ax.text(0.75, 13.4, "proposed $\\approx$ strongest baseline", fontsize=6.6, color="#A4123F", fontweight="bold")
fig.subplots_adjust(left=0.17, right=0.98, top=0.97, bottom=0.27)
save(fig, "sl_frames_density")

# ------------------------------------------------------------------ simple 200-vehicle results table for the slides
RES = [("transmissions", 1, 1.0, min), ("collision_losses", 0, 1.0, min), ("reachability", 1, 100, max),
       ("t90_ms", 1, 1.0, min)]
best_r = {k: pick(round(val(D0, p, k, s)[0], dec) for p in SCHEMES) for k, dec, s, pick in RES}
rows = []
for p in SCHEMES:
    pre = {"slotted1p_rad": "\\rowcolor{rowBase}", "proposed": "\\rowcolor{rowProp}"}.get(p, "")
    name = LABEL[p]
    cells = [pre + (f"\\textbf{{{name}}}" if p in ("slotted1p_rad", "proposed") else name)]
    for k, dec, s, _ in RES:
        m, c = val(D0, p, k, s)
        t = f"{m:.{dec}f}"
        cells.append((f"\\textbf{{{t}}}" if round(m, dec) == best_r[k] else t)
                     + f"{{\\scriptsize\\color{{inkGray}}\\,$\\pm${c:.{dec}f}}}")
    rows.append(" & ".join(cells) + " \\\\")
(GEN / "tab_slide_results.tex").write_text(
    "\\renewcommand{\\arraystretch}{1.0}\n\\setlength{\\tabcolsep}{3.5pt}\n\\begin{tabular}{@{}lrrrr@{}}\n\\toprule\n"
    "\\textbf{Approach} & \\textbf{Frames sent} & \\textbf{Lost receptions} & "
    "\\textbf{Measured reach (\\%)} &\\textbf{Delay $t_{90}$ (ms)} \\\\\n\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n",
    encoding="utf-8")

ABL = [("proposed", "Full method", "reference"),
       ("no_coverage", "No coverage test", "behaves like flooding"),
       ("no_cluster_forwarding", "No cluster-head priority", "more relays, about 5 ms faster"),
       ("no_clustering", "No DBSCAN clustering", "more relays, about 5 ms faster"),
       ("no_rad", "No random delay", "same-slot vehicles all relay"),
       ("no_slots", "No distance slots", "far vehicles no longer go first"),
       ("no_reputation", "No reputation gate", "forgeries pass (26 of 30)"),
       ("no_security", "No voting + BLS", "any vehicle can raise an alert")]
FMAX = max(val(D0, p, "transmissions")[0] for p, _, _ in ABL)
BAR_X, BAR_W, RH, T90_X, NOTE_X, RIGHT = 4.3, 2.55, 0.5, 8.75, 9.0, 13.95
tz = ["\\begin{tikzpicture}[x=1cm,y=1cm]",
      "\\node[font=\\footnotesize\\bfseries,anchor=west] at (0,0.3) {Removed component};",
      f"\\node[font=\\footnotesize\\bfseries,anchor=west] at ({BAR_X},0.3) {{Frames per alert}};",
      f"\\node[font=\\footnotesize\\bfseries,anchor=east] at ({T90_X},0.3) {{$t_{{90}}$ (ms)}};",
      f"\\node[font=\\footnotesize\\bfseries,anchor=west] at ({NOTE_X},0.3) {{What it shows}};"]
for i, (p, name, note) in enumerate(ABL):
    y = -i * RH - RH / 2
    fr, tn = val(D0, p, "transmissions")[0], val(D0, p, "t90_ms")[0]
    col = "amritaMaroon" if p == "proposed" else "inkGray!55"
    if i % 2 == 0:
        tz.append(f"\\fill[black!4] (-0.1,{y + RH / 2:.3f}) rectangle ({RIGHT},{y - RH / 2:.3f});")
    weight = "\\bfseries" if p == "proposed" else ""
    tz.append(f"\\node[font=\\small{weight},anchor=west] at (0,{y:.3f}) {{{name}}};")
    tz.append(f"\\fill[{col}] ({BAR_X},{y - 0.14:.3f}) rectangle ({BAR_X + BAR_W * fr / FMAX:.3f},{y + 0.14:.3f});")
    tz.append(f"\\node[font=\\small,anchor=west] at ({BAR_X + 0.05 + BAR_W * fr / FMAX:.3f},{y:.3f}) {{{fr:.1f}}};")
    tz.append(f"\\node[font=\\small,anchor=east] at ({T90_X},{y:.3f}) {{{tn:.1f}}};")
    tz.append(f"\\node[font=\\footnotesize,anchor=west,text=inkGray] at ({NOTE_X},{y:.3f}) {{{note}}};")
tz.append("\\end{tikzpicture}")
(GEN / "slide_ablation_table.tex").write_text("\n".join(tz) + "\n", encoding="utf-8")
(GEN / "slide_numbers.tex").write_text(
    "% Generated by scripts/make_slide_assets.py; numbers used only by the presentation\n"
    f"\\newcommand{{\\NReachProp}}{{{val(D0, 'proposed', 'reachability', 100)[0]:.1f}}}\n", encoding="utf-8")


def forgery(path):
    out = {}
    for r in read(path):
        t = out.setdefault((int(r["density"]), r["variant"]), {"runs": 0, "rsu": 0})
        t["runs"] += 1
        t["rsu"] += int(float(r["rsu_registered"]) > 0)
    return out


FORG = forgery(PROC / "forgery_runs.csv")
ONOFF = {c: forgery(SENS / f"onoff_{c}" / "processed" / "forgery_runs.csv") for c in ("0", "0.5", "0.9")}
fig, (a1, a2) = plt.subplots(1, 2, figsize=(2.5, 1.95), sharey=True, gridspec_kw={"width_ratios": [1, 1]})
v1 = [FORG[(D0, v)]["rsu"] for v in ("no_voting", "voting_only", "voting_reputation")]
v2 = [ONOFF[c][(D0, "voting_reputation")]["rsu"] for c in ("0", "0.5", "0.9")]
a1.bar(range(3), v1, color=["#4d4d4d", "#1f5fa0", "#A4123F"], width=0.62)
a2.bar(range(3), v2, color="#A4123F", width=0.62)
a1.set_xticks(range(3))
a1.set_xticklabels(["none", "no\ntrust", "full"], fontsize=7.5)
a2.set_xticks(range(3))
a2.set_xticklabels(["0", "50", "90"], fontsize=7.5)
a1.set_xlabel("protection", fontsize=8)
a2.set_xlabel("% time honest", fontsize=8)
a1.set_title("Persistent", fontsize=8.6)
a2.set_title("On-off", fontsize=8.6)
a1.set_ylabel("recorded\n(of 30 runs)", fontsize=8)
for ax, vs in ((a1, v1), (a2, v2)):
    for i, v in enumerate(vs):
        ax.text(i, v + 0.8, str(v), ha="center", fontsize=8.2, fontweight="bold")
    ax.set_ylim(0, RUNS + 5)
    ax.set_xlim(-0.6, 2.6)
    ax.tick_params(axis="y", labelsize=8)
    ax.grid(axis="y", alpha=0.3)
fig.subplots_adjust(left=0.24, right=0.98, top=0.9, bottom=0.3, wspace=0.12)
save(fig, "sl_forgery")

# ------------------------------------------------------------------ dashboard crops for full-width slides (crops only)
DASH = FIG / "dashboard"
crops = {"sl_dash_live.png": ("dash_live_d200_r25_status.png", (55, 255, 1765, 990)),
         "sl_dash_comparison.png": ("dash_d200_r02_comparison_table.png", (55, 335, 1765, 1120)),
         "sl_sumo_legend.png": ("dash_live_d200_r25_capture.png", (1090, 236, 1385, 580)),
         "sl_live_sumo.png": ("dash_live_d200_r25_capture.png", (400, 0, 1400, 800))}
src_path = FIG / "FIGURE_SOURCES.json"
sources = json.loads(src_path.read_text(encoding="utf-8"))
for name, (src, box) in crops.items():
    Image.open(DASH / src).convert("RGB").crop(box).save(DASH / name)
    sources[f"dashboard/{name}"] = {"source": f"figures/dashboard/{src}, crop {box} (crop of a genuine capture, "
                                              "made by make_slide_assets.py)"}
# zoomed crops around the incident (v164) of two walkthrough captures, where the committee rings are small
ZOOM = (670, 380, 900, 610)
for name, src in (("sl_zoom_votes.png", "sumo_05_votes.png"), ("sl_zoom_certificate.png", "sumo_06_certificate.png")):
    Image.open(FIG / "sumo" / src).convert("RGB").crop(ZOOM).save(FIG / name)
    sources[name] = {"source": f"figures/sumo/{src}, crop {ZOOM} around the incident (crop of a genuine capture, "
                               "made by make_slide_assets.py)"}
src_path.write_text(json.dumps(sources, indent=1), encoding="utf-8")
print("done")
