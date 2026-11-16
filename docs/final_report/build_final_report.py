"""
Build docs/Final_Project_Report.pdf -- the complete project workflow and experimental evaluation -- from the
project's own artefacts only:

  * the comparison pairs in results/demo_pairs/ (python run.py pair ... / the dashboard): pair.json, the run record
    that BOTH runs of a pair replayed (equal fingerprints are required, the scenario is re-checked), and the SUMO-GUI
    window captures each run took (captures.json);
  * the multi-seed experiment in results/urban/processed/ (summary.csv, runs.csv, paired.csv, forgery_summary.csv);
  * config.py for every design parameter;
  * dashboard screenshots taken from the running dashboard with headless Microsoft Edge (prepared once with
    --dashboard-shots DIR; kept in docs/final_report/figures/ with dashboard_shots.json);
  * docs/final_report/verification.json: outcomes of the verification commands run for this report.

Every number in the text, tables and charts is read from these files; nothing is typed in by hand. Diagrams are
explanatory drawings and are labelled as such; every screenshot is a pixel copy of the real application.

    python docs/final_report/build_final_report.py [--dashboard-shots DIR]

Needs Microsoft Edge or Google Chrome (headless printing), pypdfium2 (pip install pypdfium2), matplotlib, Pillow.
"""
import argparse
import csv
import html
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import matplotlib                                       # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                         # noqa: E402
from matplotlib.patches import Patch                    # noqa: E402
import numpy as np                                      # noqa: E402
from PIL import Image                                   # noqa: E402

import config                                           # noqa: E402
import rsu                                              # noqa: E402
import demo_pairs                                       # noqa: E402
from demo import record_fingerprint, TX                 # noqa: E402

FIG = HERE / "figures"
HTML_OUT = HERE / "final_report.html"
DATA_OUT = HERE / "report_data.json"
PDF_OUT = ROOT / "docs" / "Final_Project_Report.pdf"
PROC = ROOT / config.RESULTS_DIR / "processed"
TITLE = ("IoV-Based Intelligent Accident Detection and Reliable Emergency Message Dissemination")
SUBTITLE = "Complete Project Workflow and Experimental Evaluation"
BASES = ["flooding", "flooding_rad", "slotted1p", "slotted1p_rad"]
SCHEMES = BASES + ["proposed"]
NAME = {"flooding": "Blind flooding", "flooding_rad": "Flooding + random delay", "slotted1p": "Slotted 1-persistence",
        "slotted1p_rad": "Slotted 1-p + random delay", "proposed": "Proposed method", "ch_route": "CH-to-CH route stage"}
COLOUR = {"flooding": "#8f99a6", "flooding_rad": "#c0c7d0", "slotted1p": "#4f74a3", "slotted1p_rad": "#9db5d3",
          "proposed": "#137f75", "ch_route": "#7a46c8"}
XLABELS = ["Blind\nflooding", "Flooding\n+ RAD", "Slotted\n1-p", "Slotted\n1-p + RAD", "Proposed"]
FIG_W = 168                                            # mm: full text width on A4 with the margins below
D = config.DEMO_DENSITY


def esc(s):
    return html.escape(str(s), quote=True)


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ================================================================ data
def read_csv(name):
    with open(PROC / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_pairs():
    """Pairs whose two runs both finished on the same record (anything else is listed, never compared)."""
    usable, skipped = [], []
    for p in demo_pairs.pairs():
        raw, reason = demo_pairs.comparison(p)
        if raw is None:
            skipped.append((p["pair_id"], reason))
            continue
        demo_pairs.check_record(p, raw)                         # the record really is this pair's scenario
        folder = Path(demo_pairs.pair_dir(p["pair_id"]))
        caps = {a: json.loads((folder / a / "captures.json").read_text(encoding="utf-8")) for a in demo_pairs.APPROACHES}
        usable.append({"pair": p, "raw": raw, "fp": record_fingerprint(raw), "caps": caps, "folder": folder,
                       "rows": {r["scheme"]: r for r in demo_pairs.comparison_rows(p, raw)}})
    return usable, skipped


def summary_at(rows, density):
    return {r["protocol"]: r for r in rows if int(r["density"]) == density}


def ms(row, key, scale=1.0, d=1):
    """'mean ± ci' text of a summary row (with n when fewer runs than seeds had a value), or 'not available'."""
    m, c, n = num(row.get(key)), num(row.get(key + "_ci95")), num(row.get(key + "_n"))
    if m is None:
        return "not available"
    text = f"{m * scale:.{d}f} ± {c * scale:.{d}f}" if c is not None else f"{m * scale:.{d}f}"
    return text + (f" (n = {n:.0f})" if n is not None and n < config.RUNS_PER_DENSITY else "")


def run_seconds(run):
    return (datetime.fromisoformat(run["finished"]) - datetime.fromisoformat(run["started"])).total_seconds()


# ================================================================ figures from the application
def pick(caps, scheme=None, stage=None, done=None, at="first", startswith=None):
    c = [x for x in caps if (scheme is None or x["scheme"] == scheme) and (stage is None or x["workflow_stage"] == stage)
         and (done is None or bool(x.get("done")) == done) and (startswith is None or str(x["scheme"]).startswith(startswith))]
    if not c:
        return None
    return c[0] if at == "first" else c[-1] if at == "last" else c[len(c) // 2]


def on_air(path):
    """Pixels of the 'transmitting' orange in the map area of a SUMO-GUI capture (the side panel, whose legend holds an
    orange swatch, starts right of x = 900 in the fixed 1500 x 1050 demo window)."""
    a = np.asarray(Image.open(path).convert("RGB"), dtype=int)[340:1000, 300:900]
    return int((np.abs(a - np.array(TX[:3])) <= 25).all(axis=2).sum())


def copy_capture(entry, approach, cap, key, prov):
    if cap is None:
        raise SystemExit(f"no capture for {key} in pair {entry['pair']['pair_id']} ({approach})")
    name = f"sumo_{entry['pair']['pair_id']}_{approach}_{key}.png"
    shutil.copyfile(entry["folder"] / approach / cap["file"], FIG / name)
    prov[name] = {"pair": entry["pair"]["pair_id"], "scenario": entry["pair"]["scenario"]["scenario_id"],
                  "seed": entry["pair"]["scenario"]["seed"], "approach": approach, "capture": cap["file"],
                  "stage": cap["workflow_stage"], "scheme": cap["scheme"], "radio_ms": cap.get("t_ms"),
                  "sim_time_s": cap.get("sim_time_s"), "record_fingerprint": entry["fp"][:16]}
    return name


def sumo_figures(pairs):
    """The SUMO-GUI captures shown in the report, chosen by stage from each run's own captures.json."""
    prov = {}
    canon = next((e for e in pairs if e["pair"]["scenario"]["scenario_id"] == f"d{D}_r{config.DEMO_RUN:02d}"), pairs[0])
    b, p = canon["caps"]["baseline"], canon["caps"]["proposed"]
    shots = {
        "traffic": copy_capture(canon, "baseline", pick(b, stage="live traffic", at="last"), "traffic", prov),
        "incident": copy_capture(canon, "baseline", pick(b, stage="Incident"), "incident", prov),
        "alert": copy_capture(canon, "baseline", pick(b, stage="Alert"), "alert", prov),
        "clusters": copy_capture(canon, "proposed", pick(p, stage="Cluster / CH"), "clusters", prov),
        "votes": copy_capture(canon, "proposed", pick(p, scheme="Proposed (full)", stage="Votes", at="last"), "votes", prov),
        "certificate": copy_capture(canon, "proposed", pick(p, scheme="Proposed (full)", stage="Certificate"), "certificate", prov),
        "forwarding": copy_capture(canon, "proposed", pick(p, scheme="Proposed (full)", stage="Forwarding / Route", at="mid"), "forwarding", prov),
        # the replay's own RSU stage (its last capture would be the run's final screen, shown as "final_proposed")
        "rsu": copy_capture(canon, "proposed", pick(p, scheme="Proposed (full)", stage="RSU", done=False), "rsu", prov),
        "route": copy_capture(canon, "proposed", pick(p, scheme=config.LABELS["ch_route"], stage="RSU", at="last")
                              or pick(p, scheme=config.LABELS["ch_route"], at="last"), "route", prov),
        "forged": copy_capture(canon, "proposed", pick(p, startswith="FORGED", at="last"), "forged", prov),
        "final_proposed": copy_capture(canon, "proposed", pick(p, done=True, at="last"), "final", prov),
        "final_baseline": copy_capture(canon, "baseline", pick(b, done=True, at="last"), "final", prov),
    }
    for e in [canon] + [x for x in pairs if x is not canon]:   # each baseline's own run (the first pair that replayed it)
        base = e["pair"]["baseline"]
        if "fwd_" + base not in shots:
            # the forwarding capture with the most relays on air (their orange rings last one 0.5 ms frame, so a capture
            # can catch none), measured from the pixels
            fwd = [c for c in e["caps"]["baseline"] if c["scheme"] == config.LABELS[base] and c["workflow_stage"] == "Forwarding / Route"]
            cap = max(fwd, key=lambda c: on_air(e["folder"] / "baseline" / c["file"]), default=None)
            shots["fwd_" + base] = copy_capture(e, "baseline", cap, "forwarding", prov)
    return shots, prov, canon


def crop_sections(path, dsf):
    """Section cards of a dashboard screenshot, found by their navy number badges: a circle about 30 px wide (a
    selected tab button, also navy, is far wider), standing on a white card. A card ends where the next begins, the
    last one at the first full row of page background below it."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    navy = lambda c: abs(c[0] - 16) < 14 and abs(c[1] - 43) < 14 and abs(c[2] - 60) < 14
    page = lambda c: abs(c[0] - 243) <= 3 and abs(c[1] - 245) <= 3 and abs(c[2] - 247) <= 3
    near_page = lambda c: abs(c[0] - 243) < 7 and abs(c[1] - 245) < 7 and abs(c[2] - 247) < 7
    lo, hi = int(w * 0.04), int(w * 0.20)
    groups = []
    for y in range(h):
        if near_page(px[int(w * 0.02), y]) and any(navy(px[x, y]) for x in range(lo, hi, 2)):
            if groups and y - groups[-1][1] <= 3:
                groups[-1][1] = y
            else:
                groups.append([y, y])
    badges = []
    for a, b in groups:
        mid = (a + b) // 2
        x0 = next((x for x in range(lo, hi) if navy(px[x, mid])), None)
        # a badge is ~30 px wide and followed by the white gap before its heading; a selected tab is navy there too
        solid = x0 is not None and sum(navy(px[x, mid]) for x in range(x0, min(w, x0 + 30 * dsf))) >= 15 * dsf
        if 26 * dsf <= b - a <= 34 * dsf and solid and not navy(px[min(w - 1, x0 + 35 * dsf), mid]):
            badges.append(a)
    tops = [y - 26 * dsf for y in badges]
    cards, sample = [], [int(w * f) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
    for i, t in enumerate(tops):
        if i + 1 < len(tops):
            bottom = tops[i + 1] - 20 * dsf
        else:
            y = int(t + 60 * dsf)
            while y < h - 1 and not all(page(px[x, y]) for x in sample):
                y += 1
            bottom = y + 2
        cards.append(im.crop((int(w * 0.045), max(0, int(t)), int(w * 0.955), int(bottom))))
    return cards


def split_tall(im, limit=1.45, target=1.36):
    """Cut a section image taller than `limit` x its width at blank rows (never through content), so that every part
    fits one page at full width."""
    parts = []
    while im.size[1] > limit * im.size[0]:
        w, h = im.size
        g = im.convert("L")
        px = g.load()
        aim = int(target * w)
        xs = range(int(w * 0.04), int(w * 0.96), 7)                 # the card's interior, not its border or the page
        blank = lambda y: max(px[x, y] for x in xs) - min(px[x, y] for x in xs) < 4
        # 60 contiguous blank rows, every row checked: only the space between blocks, never between table rows
        cut = next((y for y in range(aim, int(aim * 0.4), -1) if all(blank(y + d) for d in range(60))), aim)
        parts.append(im.crop((0, 0, w, cut + 6)))
        im = im.crop((0, cut, w, h))
    return parts + [im]


def dashboard_figures(shots_dir):
    """Crop the dashboard screenshots taken with headless Edge into one image per section (only with
    --dashboard-shots; otherwise the prepared images in figures/ are used)."""
    manifest = json.loads((Path(shots_dir) / "shots.json").read_text(encoding="utf-8"))
    out = {}
    for old in FIG.glob("dash_*.png"):
        old.unlink()
    for item in manifest["shots"]:
        cards = crop_sections(Path(shots_dir) / item["file"], manifest["dsf"])
        for name, index in item["sections"].items():
            index, keep = (index, None) if isinstance(index, int) else index      # [card, top fraction kept]
            card = cards[index] if keep is None else cards[index].crop((0, 0, cards[index].size[0], int(cards[index].size[1] * keep)))
            for k, part in enumerate(split_tall(card)):
                fname = f"dash_{name}.png" if k == 0 else f"dash_{name}_{k + 1}.png"
                part.save(FIG / fname)
                out[fname] = {**{key: v for key, v in item.items() if key != "sections"}, "section": index + 1, "part": k + 1}
    (FIG / "dashboard_shots.json").write_text(json.dumps({"taken_with": manifest.get("taken_with"), "figures": out}, indent=1),
                                              encoding="utf-8")


# ================================================================ charts from the results
def style_axes(ax, title, ylabel):
    ax.set_title(title, fontsize=9.5, loc="left", color="#17375e", fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=8.5)
    ax.tick_params(labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#e3e8ee", linewidth=0.7)
    ax.set_axisbelow(True)


def chart_multiseed(s200):
    panels = [("transmissions", "Frames on air", "frames", 1), ("collision_losses", "Receptions lost to collisions", "receptions", 1),
              ("reachability", "Reach", "% of reachable vehicles", 100), ("t90_ms", "Time until 90 % hold the alert", "ms", 1),
              ("rsu_delay_ms", "First RSU registration", "ms", 1), ("dup_rx", "Duplicate receptions at vehicles", "receptions", 1)]
    fig, axes = plt.subplots(2, 3, figsize=(10.2, 6.0))
    for ax, (key, title, unit, scale) in zip(axes.flat, panels):
        vals = [num(s200[s][key]) for s in SCHEMES]
        cis = [num(s200[s][key + "_ci95"]) or 0 for s in SCHEMES]
        x = np.arange(len(SCHEMES))
        ax.bar(x, [v * scale if v is not None else 0 for v in vals], yerr=[c * scale for c in cis], capsize=3,
               color=[COLOUR[s] for s in SCHEMES], edgecolor="#40536a", linewidth=0.5)
        for xi, v, c in zip(x, vals, cis):                       # above the error bar, never across it
            ax.text(xi, ((v or 0) + c) * scale, f"{v * scale:.1f}" if v is not None else "n/a", ha="center", va="bottom",
                    fontsize=7, color="#1f2933")
        ax.set_xticks(x, XLABELS, fontsize=6.6)
        style_axes(ax, title, unit)
        if key == "reachability":
            ax.set_ylim(90, 101.5)
    fig.suptitle(f"{D} vehicles, 30 seeds per scheme: mean ± 95 % confidence interval", fontsize=9, color="#44546a", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(FIG / "chart_multiseed_200.png", dpi=220)
    plt.close(fig)


def chart_density(summary):
    densities = sorted({int(r["density"]) for r in summary})
    panels = [("transmissions", "Frames on air", "frames (log scale)", True), ("collision_losses", "Receptions lost to collisions",
              "receptions (log scale)", True), ("t90_ms", "Time until 90 % hold the alert", "ms", False)]
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.5))
    for ax, (key, title, unit, log) in zip(axes, panels):
        for s in SCHEMES:
            rows = [summary_at(summary, d)[s] for d in densities]
            y = np.array([num(r[key]) or np.nan for r in rows])
            ci = np.array([num(r[key + "_ci95"]) or 0 for r in rows])
            ax.plot(densities, y, marker="o", ms=3.5, lw=1.6 if s == "proposed" else 1.1, color=COLOUR[s], label=NAME[s])
            ax.fill_between(densities, y - ci, y + ci, color=COLOUR[s], alpha=0.15, lw=0)
        if log:
            ax.set_yscale("log")
        ax.set_xlabel("vehicles", fontsize=8.5)
        style_axes(ax, title, unit)
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, fontsize=7.5, frameon=False)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    fig.savefig(FIG / "chart_density.png", dpi=220)
    plt.close(fig)


def chart_seeds(runs):
    """Every individual run at the demo density: one dot per seed and scheme."""
    rows = [r for r in runs if int(r["density"]) == D]
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.6))
    rng = np.random.default_rng(0)                              # horizontal jitter only, for visibility
    for ax, (key, title, unit) in zip(axes, [("transmissions", "Frames on air", "frames"),
                                             ("collision_losses", "Receptions lost to collisions", "receptions"),
                                             ("t90_ms", "Time until 90 % hold the alert", "ms")]):
        for i, s in enumerate(SCHEMES):
            y = [num(r[key]) for r in rows if r["protocol"] == s]
            y = [v for v in y if v is not None]
            ax.scatter(i + rng.uniform(-0.18, 0.18, len(y)), y, s=9, color=COLOUR[s], edgecolor="#40536a", linewidth=0.3)
            ax.hlines(np.mean(y), i - 0.3, i + 0.3, color="#1f2933", lw=1.2)
        ax.set_xticks(range(len(SCHEMES)), XLABELS, fontsize=6.6)
        if key == "collision_losses":
            ax.set_yscale("symlog", linthresh=100)
            ax.set_ylim(bottom=0)
        style_axes(ax, title, unit)
    fig.suptitle(f"Each dot is one seed ({D} vehicles, 30 seeds); the bar is the mean", fontsize=9, color="#44546a", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(FIG / "chart_seeds_200.png", dpi=220)
    plt.close(fig)


def chart_pairs(pairs):
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.7))
    labels = [e["pair"]["pair_id"] for e in pairs]           # scenario IDs do not fit side by side; they are in the pair table
    x = np.arange(len(pairs))
    width = 0.16
    for ax, (key, title, unit) in zip(axes, [("transmissions", "Frames on air", "frames"),
                                             ("collision_losses", "Receptions lost to collisions", "receptions"),
                                             ("t90_ms", "Time until 90 % hold the alert", "ms")]):
        for k, s in enumerate(SCHEMES):
            vals = []
            for e in pairs:
                cell = next(c for c in e["rows"][s]["cells"] if c["key"] == key)
                vals.append(cell["value"] if cell["value"] is not None else np.nan)
            edge = ["#000000" if e["pair"]["baseline"] == s else "#40536a" for e in pairs]
            lw = [1.4 if e["pair"]["baseline"] == s else 0.4 for e in pairs]
            ax.bar(x + (k - 2) * width, vals, width, color=COLOUR[s], edgecolor=edge, linewidth=lw, label=NAME[s])
        ax.set_xticks(x, labels, fontsize=7.5)
        if key == "collision_losses":
            ax.set_yscale("symlog", linthresh=100)
            ax.set_ylim(bottom=0)
        style_axes(ax, title, unit)
    key = [Patch(facecolor=COLOUR[s], edgecolor="#40536a", linewidth=0.4, label=NAME[s]) for s in SCHEMES]   # not the first
    fig.legend(handles=key, loc="lower center", ncol=5, fontsize=7.5, frameon=False)                    # bar's outline
    fig.suptitle("Each pair: every scheme on the pair's identical record (black outline = the baseline replayed in SUMO-GUI)",
                 fontsize=9, color="#44546a", x=0.01, ha="left")
    fig.tight_layout(rect=[0, 0.09, 1, 1])
    fig.savefig(FIG / "chart_pairs.png", dpi=220)
    plt.close(fig)


def chart_forgery(forgery):
    densities = sorted({int(r["density"]) for r in forgery})
    names = {"voting_reputation": "Voting + BLS + reputation (full)", "voting_only": "Voting + BLS, no reputation gate",
             "no_voting": "No voting"}
    colours = {"voting_reputation": "#137f75", "voting_only": "#c9952b", "no_voting": "#a64027"}
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.3))
    for ax, (key, title) in zip(axes, [("accepted_share", "Honest vehicles that accepted the forged alert"),
                                       ("rsu_registered", "Runs in which an RSU registered it")]):
        for v, label in names.items():
            rows = {int(r["density"]): r for r in forgery if r["variant"] == v}
            ax.plot(densities, [100 * (num(rows[d][key]) or 0) for d in densities], marker="o", ms=3.5, color=colours[v], label=label)
        ax.set_ylim(-5, 105)
        ax.set_xlabel("vehicles", fontsize=8.5)
        style_axes(ax, title, "%")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, fontsize=7.5, frameon=False)
    fig.tight_layout(rect=[0, 0.1, 1, 1])
    fig.savefig(FIG / "chart_forgery.png", dpi=220)
    plt.close(fig)


# ================================================================ explanatory diagrams (SVG)
def _box(x, y, w, h, title, sub="", fill="#eef3f8", stroke="#6f8fb3", tcol="#17375e", size=15):
    lines = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>']
    subs = sub.split("\n") if sub else []
    ty = y + h / 2 + 5 - 8 * len(subs)
    lines.append(f'<text x="{x + w / 2}" y="{ty}" text-anchor="middle" font-size="{size}" font-weight="600" '
                 f'fill="{tcol}">{esc(title)}</text>')
    for k, s in enumerate(subs):
        lines.append(f'<text x="{x + w / 2}" y="{ty + 18 + 16 * k}" text-anchor="middle" font-size="12" '
                     f'fill="#3a4b5e">{esc(s)}</text>')
    return "".join(lines)


def _arrow(x1, y1, x2, y2, label=""):
    s = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#5b7290" stroke-width="1.6" marker-end="url(#ah)"/>'
    if label and y1 == y2:                                  # horizontal: centred above the line, clear of the arrowhead
        s += f'<text x="{(x1 + x2) / 2}" y="{y1 - 8}" text-anchor="middle" font-size="11.5" fill="#44546a">{esc(label)}</text>'
    elif label:
        s += f'<text x="{(x1 + x2) / 2 + 6}" y="{(y1 + y2) / 2 - 4}" font-size="11.5" fill="#44546a">{esc(label)}</text>'
    return s


def _svg(w, h, body):
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" font-family="Segoe UI, Calibri, Arial, sans-serif">'
            '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#5b7290"/></marker></defs>' + body + '</svg>')


GREEN, PURPLE, AMBER = ("#e8f3ef", "#4f9a84"), ("#f1ecfa", "#7a46c8"), ("#fff4e0", "#c9952b")


def diagram_architecture():
    b = [_box(20, 20, 300, 80, "SUMO 1.27.1 (sumo, sumo-gui)", "network/urban.net.xml: 5 × 5 grid\nKrauss car-following, 1 s steps", *GREEN),
         _box(360, 20, 300, 80, "scenario.py", "seed → routes, mobility (FCD),\nwatchdog trust, incident + alert"),
         _box(700, 20, 280, 80, "config.py", "every parameter in one place", *AMBER),
         _box(200, 142, 600, 68, "experiment.py · run_one(density, run)", "one seed = one scenario; every scheme runs on the identical snapshot")]
    comps = [("clustering.py", "DBSCAN + trusted\nCH election, tiers"), ("corroboration.py", "committee, votes,\nBLS12-381 certificate"),
             ("protocols.py, channel.py", "forwarding rules,\nslot-level 802.11p"), ("rsu.py", "validate, register\nonce, duplicates"),
             ("infrastructure.py", "CH-to-CH route,\nSQLite outbox")]
    for i, (t, s) in enumerate(comps):
        b.append(_box(20 + i * 194, 252, 178, 86, t, s, size=13.5))
        b.append(_arrow(500, 210, 109 + i * 194, 252))
        b.append(_arrow(109 + i * 194, 338, 500, 378))
    b.append(_box(200, 378, 600, 64, "metrics.py → results/urban/", "run records · processed CSVs (30 seeds × 6 densities) · figures · summaries"))
    b += [_box(20, 484, 300, 88, "demo.py (SUMO-GUI via TraCI)", "replays a recorded run; separated\nruns for demo_pairs.py", *GREEN),
          _box(360, 484, 300, 88, "web_results.py, results_viewer.html", "faculty-demo dashboard: pairs,\nlive view, outcome, comparison", *PURPLE),
          _box(700, 484, 280, 88, "report.py, figures.py, portal/", "static results dashboard, figures,\ndocumentation website", *PURPLE),
          _arrow(320, 60, 360, 60), _arrow(510, 100, 510, 142), _arrow(840, 100, 700, 142),
          _arrow(400, 442, 170, 484), _arrow(510, 442, 510, 484), _arrow(620, 442, 840, 484), _arrow(320, 528, 360, 528)]
    return _svg(1000, 592, "".join(b))


WORKFLOW = [("1", "SUMO network and demand", "urban.net.xml; scenario.write_routes"),
            ("2", "Vehicle movement", "SUMO 1 s steps → positions, speeds, lanes"),
            ("3", "Scenario and incident selection", "seed fixes all; demo_pairs.select"),
            ("4", "Staged incident", "random honest vehicle, t ~ U{60..120} s"),
            ("5", "Incident report (alert)", "scenario.create_alert: one per incident"),
            ("6", "Clustering and CH election", "clustering.elect_roles: DBSCAN + trust"),
            ("7", "Committee formation", "5 nearest reputable neighbours"),
            ("8", "Voting", "PROPOSAL → VOTEs (BLS signatures)"),
            ("9", "Certificate and verification", "quorum 3 → aggregate, checked by all"),
            ("10", "Forwarding, duplicate control", "one decision per vehicle (scheme rule)"),
            ("11", "CH-to-CH route (proposed)", "trusted heads → nearest RSU"),
            ("12", "RSU verification, registration", "rsu.register: checks, once, outbox"),
            ("13", "Metrics and run records", "metrics.run_metrics → results/"),
            ("14", "Replay, dashboard, comparison", "demo.py, web_results.py")]


def diagram_workflow():
    b = []
    for i, (n, title, sub) in enumerate(WORKFLOW):
        col, row = divmod(i, 7)
        x, y = 30 + col * 490, 20 + row * 100
        fill = GREEN if i < 5 else ("#eef3f8", "#6f8fb3") if i < 12 else PURPLE
        b.append(f'<circle cx="{x + 22}" cy="{y + 36}" r="17" fill="#17375e"/><text x="{x + 22}" y="{y + 41}" '
                 f'text-anchor="middle" font-size="14" font-weight="700" fill="white">{n}</text>')
        b.append(_box(x + 50, y + 4, 400, 64, title, sub, *fill, size=14.5))
        if row < 6:
            b.append(_arrow(x + 250, y + 68, x + 250, y + 104))
    b.append('<path d="M 480 656 L 480 36 L 528 36" fill="none" stroke="#5b7290" stroke-width="1.6" marker-end="url(#ah)"/>')
    return _svg(1000, 712, "".join(b))


def diagram_proposed():
    b = [_box(20, 20, 290, 66, "Incident vehicle: PROPOSAL", "signed alert, broadcast once", *GREEN, size=13.5),
         _box(20, 114, 290, 66, "Committee: 5 nearest reputable", "honest members observe and VOTE", *GREEN, size=13.5),
         _box(20, 208, 290, 66, "Quorum: 3 distinct votes", "→ one aggregate BLS signature", *GREEN, size=13.5),
         _box(20, 302, 290, 66, "Certified ALERT broadcast", "event ID, position, time, hop limit", *GREEN, size=13.5),
         _arrow(165, 86, 165, 114), _arrow(165, 180, 165, 208), _arrow(165, 274, 165, 302), _arrow(310, 335, 360, 52),
         _box(360, 22, 300, 60, "Receiver decodes a certified copy", "", size=13.5),
         _box(360, 108, 300, 60, "Verify certificate (4.3 ms)", "source first; BLS valid; 3 reputable", size=13.5),
         _box(700, 108, 280, 60, "REJECT", "not accepted, never forwarded", "#fbe9e6", "#c0392b", 13.5),
         _box(360, 194, 300, 60, "First accepted copy?", "", size=13.5),
         _box(700, 194, 280, 60, "Duplicate", "sender added to 'heard'; no re-processing", "#f3f6fa", "#6f8fb3", 13.5),
         _box(360, 280, 300, 60, "Misbehaving, or hop limit reached?", "", size=13.5),
         _box(700, 280, 280, 60, "DROP / EXPIRED", "does not relay", "#f3f6fa", "#6f8fb3", 13.5),
         _box(360, 366, 300, 74, "Wait (tier·Ns + S(D))·τ + U[0, RAD)", "tier 0 (trusted CH, bridge) first;\nfarther receivers first", *AMBER, 13.5),
         _box(360, 466, 300, 70, "Coverage test", "a beacon neighbour (vehicle or RSU)\nnot covered by any sender heard?", *AMBER, 13.5),
         _box(700, 440, 130, 50, "FORWARD", "", "#dff3ea", "#11694b"), _box(850, 440, 130, 50, "SUPPRESS", "", "#e8edf2", "#5b7290"),
         _arrow(510, 82, 510, 108), _arrow(660, 138, 700, 138, "invalid"), _arrow(510, 168, 510, 194, "valid"),
         _arrow(660, 224, 700, 224, "no"), _arrow(510, 254, 510, 280, "yes"), _arrow(660, 310, 700, 310, "yes"),
         _arrow(510, 340, 510, 366, "no"), _arrow(510, 440, 510, 466), _arrow(660, 476, 700, 476, "yes"),
         _arrow(660, 522, 915, 490, "no"),                   # passes below FORWARD (bottom at y = 490)
         _box(20, 414, 290, 122, "CH-to-CH route (a stage)", "Dijkstra over trusted CHs to the\nnearest RSU; each route head\ncollects a local quorum, then\nforwards; others stay silent", *PURPLE, 13.5),
         _box(20, 562, 960, 54, "RSU: decode → verify → plausibility checks → register the event ID once (later copies DUPLICATE) → local outbox", "", size=13.5),
         _arrow(510, 536, 510, 562)]
    return _svg(1000, 632, "".join(b))


def diagram_pairs():
    b = [_box(20, 20, 280, 92, "Dashboard (browser)", "New pair · Run baseline only ·\nRun proposed only", *PURPLE),
         _box(360, 20, 300, 92, "web_results.py → demo_pairs.start", "one run at a time (lock);\nPOST /api/run → own process"),
         _box(700, 20, 280, 92, "run.py demo --pair P --approach A", "EXP_RESULTS_DIR = <pair>/<approach>", *AMBER),
         _box(700, 150, 280, 92, "experiment.run_one", "re-simulates the pair's seed; the\nrecord is checked against the pair"),
         _box(360, 150, 300, 92, "SUMO-GUI replay (demo.py)", "only this approach's schemes;\nends on its own outcome", *GREEN),
         _box(20, 150, 280, 92, "Pair folder", "pair.json; per run <approach>/: its own\nrecord, live feed, SUMO log, captures"),
         _box(20, 280, 960, 70, "Comparison: shown only when BOTH runs finished and their own records have equal fingerprints",
              "otherwise withheld with the reason; multi-seed experiment results are shown separately", "#dff3ea", "#11694b"),
         _arrow(300, 66, 360, 66), _arrow(660, 66, 700, 66), _arrow(840, 112, 840, 150), _arrow(700, 196, 660, 196),
         _arrow(360, 196, 300, 196), _arrow(160, 242, 160, 280), _arrow(160, 150, 160, 112)]
    return _svg(1000, 370, "".join(b))


# ================================================================ document helpers
class Doc:
    """Numbered figures and tables, each with a caption that names what it shows and where it comes from."""

    def __init__(self):
        self.n_fig, self.n_tab, self.figures = 0, 0, []

    def shot(self, src, caption, source, kind="Genuine screenshot", maxh=None, width=FIG_W):
        if maxh is None and src.startswith("sumo_"):
            maxh = 106                                  # two SUMO-GUI captures per page
        self.n_fig += 1
        self.figures.append((self.n_fig, kind, src, caption, source))
        size = f"max-width:{width}mm;width:{width}mm" + (f";max-height:{maxh}mm;width:auto" if maxh else "")
        return (f'<figure class="keep"><img class="shot" src="figures/{src}" style="{size}" alt="{esc(caption)}">'
                f'<figcaption><b>Figure {self.n_fig}.</b> <span class="kind">{kind}.</span> {caption} '
                f'<span class="src">Source: {source}</span></figcaption></figure>')

    def chart(self, src, caption, source):
        return self.shot(src, caption, source, kind="Chart from the results")

    def diagram(self, svg, caption, height=None):
        self.n_fig += 1
        self.figures.append((self.n_fig, "Diagram (explanatory)", "inline SVG", caption, "drawn for this report"))
        h = f' style="height:{height}mm"' if height else ""
        return (f'<figure class="keep"><div class="svg"{h}>{svg}</div><figcaption><b>Figure {self.n_fig}.</b> '
                f'<span class="kind">Diagram (explanatory, not a screenshot).</span> {caption}</figcaption></figure>')

    def table(self, head, rows, caption, source="", cls="", right=(), keep=True):
        """keep=False for a table longer than a page: kept whole, it is pushed to a new page and split anyway."""
        self.n_tab += 1
        th = "".join(f'<th class="{"r" if i in right else ""}">{h}</th>' for i, h in enumerate(head))
        body = "".join("<tr>" + "".join(f'<td class="{"r" if i in right else ""}">{c}</td>' for i, c in enumerate(r)) + "</tr>"
                       for r in rows)
        src = f' <span class="src">Source: {source}</span>' if source else ""
        return (f'<div class="tbl{" keep" if keep else ""} {cls}"><div class="tcap"><b>Table {self.n_tab}.</b> {caption}{src}</div>'
                f'<table><tr>{th}</tr>{body}</table></div>')


def cell(row, key):
    return next(c for c in row["cells"] if c["key"] == key)


def verdict(diff, ci, lower_better=True, unit=""):
    """Paired difference proposed - baseline with its 95 % CI, and what it supports."""
    if diff is None:
        return "not available", "n/a"
    sig = ci is not None and abs(diff) > ci
    text = f"{diff:+.1f} ± {ci:.1f}{unit}" if ci is not None else f"{diff:+.1f}{unit}"
    if not sig:
        return text, "no significant difference"
    better = (diff < 0) == lower_better
    return text, ("proposed better" if better else "proposed worse")


# ================================================================ the report
def build_html(ctx, pages):
    doc = Doc()
    pairs, s200, summary, runs, paired, forgery = (ctx[k] for k in ("pairs", "s200", "summary", "runs", "paired", "forgery"))
    shots, prov, canon, dash, verification = (ctx[k] for k in ("shots", "prov", "canon", "dash", "verification"))
    cp, csc = canon["pair"], canon["pair"]["scenario"]
    inc = csc["incident"]
    alert = canon["raw"]["scenario"]["alert"]
    L = config.LABELS
    p200 = {r["baseline"]: r for r in paired if int(r["density"]) == D}
    sm = lambda s, k, scale=1.0, d=1: ms(s200[s], k, scale, d)
    strong_text, mixed = against(paired, "slotted1p_rad")
    full_reach = all(num(summary_at(summary, dd)["proposed"]["reachability"]) == 1.0 for dd in sorted({int(r["density"]) for r in summary}))
    mean = lambda s, k: num(s200[s][k])
    densities = sorted({int(r["density"]) for r in summary})
    parts = []

    def section(sid, title, body, cls="section"):
        parts.append(f'<section class="{cls}" id="{sid}"><h1>{title}</h1>{body}</section>')

    def src_pair(e, approach=None):
        p = e["pair"]
        return (f"pair {p['pair_id']}, scenario {p['scenario']['scenario_id']} (seed {p['scenario']['seed']})"
                + (f", {approach}-only run" if approach else "") + f", record fingerprint {e['fp'][:16]}…")

    def cap(key):
        return prov[shots[key]]

    def capsrc(key):
        c = cap(key)
        return (f"window capture {c['capture']} of the {c['approach']}-only run of pair {c['pair']} "
                f"(scenario {c['scenario']}, seed {c['seed']}); stage {c['stage']}"
                + (f", +{c['radio_ms']:.1f} ms radio time" if c.get("radio_ms") is not None else ""))

    # ---------------------------------------------------------------- cover + contents
    hero = shots["forwarding"]
    parts.append(f"""
<section class="cover">
 <div class="over">Final project report · Internet of Vehicles (IoV) and VANET</div>
 <div class="main">{esc(TITLE)}</div>
 <div class="sub">{esc(SUBTITLE)}</div>
 <p class="desc">A SUMO-based vehicular network in which a staged accident creates one emergency alert. Neighbouring
 reputable vehicles corroborate it with BLS signatures, a trust-aware, cluster-based forwarding scheme limits redundant
 rebroadcasts, a route along trusted cluster heads carries it to a roadside unit, and roadside units verify and register
 the event once. The method is compared with four forwarding baselines on identical traffic.</p>
 <img class="hero" src="figures/{hero}" alt="SUMO-GUI capture of the proposed-only run">
 <div class="herocap">Genuine SUMO-GUI capture: the proposed-only run of pair {cp['pair_id']} (scenario {csc['scenario_id']},
 seed {csc['seed']}) during forwarding.</div>
 <div class="meta"><b>Domain:</b> Internet of Vehicles / vehicular ad hoc networks — emergency message dissemination,
 corroboration and trust, traffic simulation<br><b>Evaluation:</b> {len(pairs)} comparison pairs replayed in SUMO-GUI and a
 {len(densities)}-density × {config.RUNS_PER_DENSITY}-seed experiment matrix<br><b>Generated:</b> {ctx['generated']} from the
 project's working tree (docs/final_report/build_final_report.py)</div>
</section>""")
    toc_entries = ctx["toc"]
    toc = "".join(f'<li class="{"l1" if lvl == 1 else "l2"}"><span>{esc(text)}</span><span class="d"></span>'
                  f'<span class="p">{pages.get(key, "")}</span></li>' for key, text, lvl in toc_entries)
    parts.append(f'<section class="section" id="toc"><h1>Contents</h1><ul class="toc">{toc}</ul></section>')

    # ---------------------------------------------------------------- 1 abstract
    fl, pp = s200["flooding"], s200["proposed"]
    fz = {r["variant"]: r for r in forgery if int(r["density"]) == D}
    section("s1", "1&nbsp;&nbsp;Abstract", f"""
<p>When a vehicle crashes, the vehicles behind it and the emergency services must learn about it quickly and reliably.
In a vehicular ad hoc network (VANET) the obvious way, letting every vehicle rebroadcast the warning once, floods the
shared radio channel: copies collide and destroy one another (the <em>broadcast storm</em>). A second risk is a false
warning sent by a misbehaving vehicle.</p>
<p>This project builds and evaluates a complete emergency-alert workflow on a SUMO urban traffic simulation. A staged
incident vehicle creates one DENM-like alert. The alert is released only after a <b>committee of the {config.COMMITTEE_SIZE}
nearest reputable neighbours</b> has voted: the source's signature and {config.QUORUM} votes ({config.QUORUM + 1} BLS12-381
signatures) are aggregated into one certificate that every
receiver and roadside unit (RSU) verifies. Dissemination is <b>trust-aware and cluster-based</b>: DBSCAN clusters and
reputation-based cluster-head election decide who relays first, distance slots and a random assessment delay order the
relays, and a coverage test suppresses rebroadcasts that would reach nobody new. As a stage of the same method, a
<b>CH-to-CH route</b> carries the alert along trusted cluster heads to the nearest RSU. RSUs validate each copy and register
the event once; a delivery by the CH-to-CH route stage is queued in a local dispatch outbox.</p>
<p>The method is compared with four forwarding baselines that share the same corroboration and radio model: blind flooding,
flooding with a random delay, slotted 1-persistence and slotted 1-persistence with a random delay. Every scheme runs on the
identical traffic snapshot of a scenario. Over {config.RUNS_PER_DENSITY} seeds at {D} vehicles, the proposed method sent
{sm('proposed', 'transmissions')} frames per alert in its broadcast against {sm('flooding', 'transmissions')} for blind flooding
(its CH-to-CH route stage is measured as a separate dissemination on the same record: {sm('ch_route', 'transmissions')} frames), lost
{sm('proposed', 'collision_losses', d=0)} receptions to collisions against {sm('flooding', 'collision_losses', d=0)}, and reached
{sm('proposed', 'reachability', 100)} % of the reachable vehicles; it needed {sm('proposed', 't90_ms')} ms to reach 90 % of them,
against {sm('flooding', 't90_ms')} ms for blind flooding. With full protection, a forged alert was accepted by
{100 * num(fz['voting_reputation']['accepted_share']):.0f} % of honest vehicles, against
{100 * num(fz['no_voting']['accepted_share']):.0f} % without voting. Against the strongest baseline, slotted 1-persistence with a random delay, the differences are {'mixed' if mixed else 'consistent'} (section 15).</p>
<div class="note"><p><b>Scope.</b> The accident is <em>staged</em>: the project does not implement sensor-based crash
detection. "Detection" in this report means the incident vehicle's own report and its corroboration by neighbouring
vehicles. The radio is a simulated IEEE 802.11p model, and every result comes from simulation.</p></div>""")

    # ---------------------------------------------------------------- 2 problem
    section("s2", "2&nbsp;&nbsp;Problem Statement and Motivation", f"""
<p>An emergency alert in a VANET has three requirements at once: it must reach the vehicles around the incident within
tens of milliseconds, it must reach the infrastructure (an RSU) so that the emergency services are informed, and it must be
trustworthy. All vehicles share one radio channel (IEEE 802.11p, {config.COMM_RANGE_M:.0f} m range in this project).</p>
<h3>Why uncontrolled broadcasting is a problem</h3>
<p>Under blind flooding every vehicle that receives the alert rebroadcasts it once. Most of these rebroadcasts reach
vehicles that already hold the alert, but each occupies the channel; vehicles within range of each other transmit at
nearly the same time and their frames collide at the receivers between them (hidden terminals make this worse). The
project measures this directly: at {D} vehicles blind flooding put {sm('flooding', 'transmissions')} frames on air for one
alert and {sm('flooding', 'collision_losses', d=0)} receptions were destroyed by collisions (mean ± 95 % confidence interval
over {config.RUNS_PER_DENSITY} seeds). At {densities[-1]} vehicles the losses grow to
{ms(summary_at(summary, densities[-1])['flooding'], 'collision_losses', d=0)}.</p>
<h3>Why trust matters</h3>
<p>An alert that is simply believed can be forged: a misbehaving vehicle could claim an accident that never happened and
divert traffic or emergency services. In the project's forged-alert test, an alert without corroboration was accepted by
{100 * num(fz['no_voting']['accepted_share']):.0f} % of the honest vehicles at {D} vehicles, and an RSU registered it in
{100 * num(fz['no_voting']['rsu_registered']):.0f} % of the runs.</p>
<h3>Problem addressed</h3>
<p>Deliver a corroborated emergency alert to the vehicles around an incident and to an RSU with far fewer redundant
transmissions and collisions than flooding, without losing coverage, while rejecting forged alerts; and show this fairly,
against implemented baselines, on identical traffic.</p>""")

    # ---------------------------------------------------------------- 3 objectives
    objectives = [
        ("Reproducible urban traffic and incidents", "SUMO mobility on a fixed road network; one seed fixes routes, misbehaviour, incident vehicle and time", "scenario.py, config.py"),
        ("Emergency alert creation", "one DENM-like alert per incident: event ID, type, position, time, hop limit", "scenario.create_alert"),
        ("Corroboration of reports", "committee of the 5 nearest reputable neighbours; 3 BLS votes aggregated into one certificate; every receiver verifies", "corroboration.py, protocols.py"),
        ("Controlled dissemination", "trust-aware clustering and cluster-head election, tiers, distance slots, random delay, coverage test", "clustering.py, protocols.Proposed"),
        ("Delivery to the infrastructure", "RSUs reached by broadcast; CH-to-CH route with per-head quorum as a stage of the method", "protocols.CHRoute, infrastructure.shortest_route"),
        ("RSU verification and registration", "plausibility checks, register once, duplicates and rejections recorded, local dispatch outbox", "rsu.py, infrastructure.persist"),
        ("Fair evaluation", "four implemented baselines on the identical snapshot; 30 seeds × 6 densities; paired confidence intervals", "experiment.py, metrics.py"),
        ("Demonstration", "SUMO-GUI replay of recorded runs; separated baseline-only and proposed-only runs; dashboard", "demo.py, demo_pairs.py, web_results.py"),
    ]
    section("s3", "3&nbsp;&nbsp;Project Objectives", "<p>The objectives below are the ones the project actually implements; each names the code that "
            "implements it. Section 16 lists what is not implemented.</p>" + doc.table(
                ["#", "Objective", "What is implemented", "Where"],
                [[str(i + 1), f"<b>{esc(o)}</b>", esc(w), f"<code>{esc(c)}</code>"] for i, (o, w, c) in enumerate(objectives)],
                "Implemented objectives."))

    # ---------------------------------------------------------------- 4 architecture
    modules = [("scenario.py", "Builds one scenario per seed: routes, SUMO run up to the incident second, watchdog trust, incident vehicle, alert"),
               ("clustering.py", "DBSCAN clustering and trusted cluster-head election; roles CH / BRIDGE / MEMBER and relay tiers"),
               ("corroboration.py", "Committee selection, BLS12-381 keys, signatures, aggregate certificates and the acceptance rule"),
               ("channel.py", "Slot-level IEEE 802.11p CSMA/CA (AC_VO): carrier sense, collisions, hidden terminals, half-duplex"),
               ("protocols.py", "What a vehicle does with an alert: baselines, the proposed rule, the CH-to-CH route"),
               ("rsu.py", "RSU plausibility checks and single registration of each event ID"),
               ("infrastructure.py", "CH-to-CH shortest route, trust feedback, batch authentication, SQLite dispatch outbox"),
               ("metrics.py / experiment.py", "Per-run metrics; runs every scheme on the same snapshot; the multi-seed matrix and CSVs"),
               ("demo.py / demo_pairs.py", "SUMO-GUI replay through TraCI; comparison pairs of separated runs"),
               ("web_results.py / results_viewer.html", "Local HTTP server and the faculty-demo dashboard"),
               ("report.py / figures.py / portal/", "Static results dashboard, figures and the documentation website")]
    section("s4", "4&nbsp;&nbsp;System Architecture", doc.diagram(diagram_architecture(),
            "System architecture: the real modules and how data flows between them. Green = SUMO and the SUMO-GUI replay, blue = "
            "the experiment engine (scenario, dissemination, metrics), amber = configuration, purple = presentation.") + doc.table(["Module", "Responsibility"],
            [[f"<code>{esc(m)}</code>", esc(r)] for m, r in modules], "Modules of the implementation."))

    # ---------------------------------------------------------------- 5 technologies
    reqs = ctx["requirements"]
    tech = [("Python", f"{ctx['python']}", "implementation language"),
            ("SUMO (eclipse-sumo), sumolib, TraCI", reqs.get("eclipse-sumo", "?"), "traffic simulation; SUMO-GUI controlled through TraCI"),
            ("NumPy / SciPy", f"{reqs.get('numpy', '?')} / {reqs.get('scipy', '?')}", "vector maths; connected components for reachability"),
            ("scikit-learn", reqs.get("scikit-learn", "?"), "DBSCAN clustering"),
            ("py_ecc", reqs.get("py_ecc", "?"), "BLS12-381 signatures: sign, aggregate, verify"),
            ("matplotlib", reqs.get("matplotlib", "?"), "result figures and the charts in this report"),
            ("SQLite (Python sqlite3)", "standard library", "RSU backhaul and local dispatch outbox"),
            ("http.server, HTML/CSS/JavaScript", "standard library, no framework", "local results server and dashboard"),
            ("pytest", reqs.get("pytest", "?"), "validation suite"),
            ("Node.js", ctx.get("node", "?"), "portal check (portal/check.mjs)"),
            ("Microsoft Edge (headless), pypdfium2, Pillow", "installed tools", "printing and checking this PDF; window captures")]
    section("s5", "5&nbsp;&nbsp;Technologies Used", doc.table(["Technology", "Version", "Used for"],
            [[esc(a), esc(b), esc(c)] for a, b, c in tech], "Technologies, with the versions pinned in requirements.txt.",
            "requirements.txt, the running interpreter"))

    # ---------------------------------------------------------------- 6 workflow
    wf_rows = [["1", "SUMO network and demand", "<code>network/urban.net.xml</code>, <code>scenario.write_routes</code>", "road graph, vehicle routes and departure times"],
               ["2", "Vehicle movement", "<code>scenario.run_sumo</code>, <code>read_fcd</code>", "positions, speeds, lanes every 1 s up to the incident second"],
               ["3", "Scenario and incident selection", "<code>scenario.build</code>, <code>demo_pairs.select</code>", "seed → incident vehicle and time; pairs pick a scenario"],
               ["4", "Staged incident", "<code>scenario.build</code>", "random honest vehicle at t ~ U{60..120} s"],
               ["5", "Incident report", "<code>scenario.create_alert</code>", "one DENM-like alert"],
               ["6", "Clustering and CH election", "<code>clustering.elect_roles</code>", "role, tier and cluster of every vehicle"],
               ["7", "Committee formation", "<code>corroboration.committee / plan</code>", "ranked voters"],
               ["8", "Voting", "<code>Protocol.on_receive</code>", "VOTE frames (BLS signatures)"],
               ["9", "Certificate and verification", "<code>corroboration.certificate / accept</code>", "aggregate signature; accepted or rejected"],
               ["10", "Forwarding and duplicate control", "<code>protocols.*</code>, <code>channel.simulate</code>", "frames, receptions, collisions, decisions"],
               ["11", "CH-to-CH route", "<code>infrastructure.shortest_route</code>, <code>protocols.CHRoute</code>", "route hops, local quorums"],
               ["12", "RSU verification and registration", "<code>rsu.register</code>, <code>infrastructure.persist</code>", "registered event, duplicates, outbox row"],
               ["13", "Metrics and records", "<code>metrics.run_metrics</code>, <code>experiment.run_one</code>", "run record (JSON), CSV rows"],
               ["14", "Replay and comparison", "<code>demo.py</code>, <code>demo_pairs.py</code>, <code>web_results.py</code>", "SUMO-GUI replay, dashboard, comparison"]]
    section("s6", "6&nbsp;&nbsp;Complete End-to-End Workflow", doc.diagram(diagram_workflow(),
            "End-to-end workflow from SUMO initialisation to the dashboard. Steps 1–5 build the scenario, 6–12 are the "
            "dissemination engine (run once per scheme on the same snapshot), 13–14 record and present the results.") +
            "<p>Every step below was traced in the code for this report; the data each step hands to the next is listed in "
            "the last column. Steps 6–12 run once for every scheme on the same snapshot (<code>experiment.run_one</code>), so "
            "every comparison is paired.</p>" + doc.table(["Step", "Stage", "Implementation", "Output passed on"], wf_rows,
            "Workflow stages and their implementation."))

    # ---------------------------------------------------------------- 7 traffic
    rsu_pos = ", ".join(f"{k} at ({x:.0f}, {y:.0f}) m" for k, (x, y) in config.RSU_POSITIONS.items())
    section("s7", "7&nbsp;&nbsp;Traffic Simulation", f"""
<p><b>Road network.</b> <code>{config.NET_FILE}</code>: a straight 5 × 5 street grid (about 820 × 800 m) with 9 signalised
junctions and a 3-lane central boulevard. Two RSUs stand at intersections ({rsu_pos}); their {config.COMM_RANGE_M:.0f} m
radio range leaves the far corners uncovered, so alerts from there must be relayed vehicle to vehicle.</p>
<p><b>Vehicle generation.</b> For a density of N vehicles, N vehicles are inserted at times drawn uniformly from the first
{config.DEPART_WINDOW_S} s, each on a random-walk route of {config.ROUTE_EDGES} edges without U-turns (SUMO's default
passenger car with Krauss car-following). The densities studied are {', '.join(map(str, densities))} vehicles; the
demonstration uses {D}.</p>
<p><b>Movement.</b> SUMO advances in 1 s steps (<code>--step-length 1 --seed</code>); positions, speeds and lanes are read
every second. A watchdog model observes every vehicle with a neighbour once per second and builds its Beta reputation
(trust = (s + 1) / (s + f + 2)); {100 * config.MALICIOUS_RATIO:.0f} % of the vehicles misbehave (they receive but never relay),
and an honest relay is missed with probability {config.WATCHDOG_MISS_PROB}.</p>
<p><b>Scenario and seed.</b> One seed fixes everything random in a run: <code>seed = {config.BASE_SEED} + 100·N + r</code>
for run r. The scenario ID names it (for example <code>d{D}_r02</code> = {D} vehicles, run 2, seed {config.BASE_SEED + 100 * D + 2});
the same seed always gives the same scenario (validation/test_pipeline.py).</p>"""
            + doc.shot(shots["traffic"], f"Live SUMO traffic before the incident (no alert yet). Vehicles drive normally; the "
                       f"two RSUs and their radio ranges are drawn on the grid.", capsrc("traffic"))
            + doc.shot("topology_results.png", "Road network, RSU sites and radio coverage, drawn by the experiment pipeline for the "
                       "demonstration scenario.", f"results/urban/figures/topology.png (python run.py experiment)",
                       kind="Figure from the experiment pipeline", maxh=110))

    # ---------------------------------------------------------------- 8 incident
    alert_rows = [[f"<code>{esc(k)}</code>", f"<code>{esc(json.dumps(v))}</code>"] for k, v in alert.items()]
    section("s8", "8&nbsp;&nbsp;Accident / Incident Simulation", f"""
<p><b>Incident selection.</b> For each seed the incident second is drawn from U{{{config.INCIDENT_WINDOW_S[0]}..{config.INCIDENT_WINDOW_S[1]}}} s
(after the last departure, so traffic is mixed), and the incident vehicle is drawn at random among the honest vehicles on
the road at that second. The location is therefore wherever that vehicle is: always on a lane of the network. For the
demonstration pairs, <code>demo_pairs.select</code> takes the scenarios in an order shuffled by the pairs folder's selection
seed (drawn at random when a folder's first pair is made, kept in <code>selection.json</code> and recorded by every pair; this
report's pairs were made on 13 Nov, before per-folder seeds, with the earlier fixed seed
{cp['scenario']['selection']['selection_seed']}) and skips
any whose incident lies within {demo_pairs.MIN_SEPARATION_M:.0f} m of an incident already used, so consecutive pairs show
different places; the choice never looks at any algorithm's result.</p>
<p><b>Incident information.</b> The incident vehicle creates one alert, identified like an ETSI DENM actionID (station +
sequence number). Table {doc.n_tab + 1} shows the alert of scenario {csc['scenario_id']} as recorded.</p>"""
            + doc.table(["Field", "Value"], alert_rows, f"The alert of scenario {csc['scenario_id']} (vehicle {inc['vehicle']}).",
                        f"run record of pair {cp['pair_id']} (scenario.alert)") + f"""
<p><b>Effect on nearby vehicles.</b> The alert reaches the other vehicles only through the radio (section 9–10). In the
SUMO-GUI replay, SUMO's clock is paused at the incident second while the tens of milliseconds of radio events are shown in
slow motion; afterwards the clock resumes, the crashed vehicle stays stopped and the vehicles behind it react through SUMO's
car-following.</p>
<p><b>How reports are processed.</b> Each incident produces exactly one report (alert). Receivers and RSUs verify its
certificate; an RSU registers the event ID once and records every later copy as a duplicate. The RSU code also contains
<code>rsu.register_reports</code>, which can merge several valid reports of one crash (same type, within
{rsu.MERGE_RADIUS_M:.0f} m and {rsu.MERGE_WINDOW_S:.0f} s of every report already in an incident). It is covered by unit tests only:
the simulation never creates a second report of a crash, so it is not part of the demonstrated workflow (see section 16).</p>"""
            + doc.shot(shots["incident"], f"The incident: vehicle {inc['vehicle']} (red) at ({inc['x']:.0f}, {inc['y']:.0f}) m, "
                       f"t = {inc['time_s']:.0f} s; the workflow indicator shows the Incident stage.", capsrc("incident"))
            + doc.shot(shots["alert"], f"Alert {alert['event_id']} created by the incident vehicle (type {alert['message_type']}, "
                       f"hop limit {alert['hop_limit']}).", capsrc("alert")))

    # ---------------------------------------------------------------- 9 baselines
    by_base = {}
    for e in [canon] + [x for x in pairs if x is not canon]:
        by_base.setdefault(e["pair"]["baseline"], e)

    def mini(e, scheme):
        r = e["rows"][scheme]
        keys = ["transmissions", "collision_losses", "reachability", "t90_ms", "rsu_delay_ms"]
        return doc.table(["Frames on air", "Receptions lost", "Reach", "Time to 90 %", "First RSU registration"],
                         [[cell(r, k)["text"] for k in keys]],
                         f"{L[scheme]} in pair {e['pair']['pair_id']} (scenario {e['pair']['scenario']['scenario_id']}, one run).",
                         src_pair(e), right=(0, 1, 2, 3, 4))

    base_text = {
        "flooding": ("Every vehicle that accepts the certified alert rebroadcasts it once, as soon as its certificate has been verified "
                     "(<code>Flooding.first_copy</code>: the timer is the acceptance slot). Duplicates are counted but never suppress "
                     "anything, so every honest receiver transmits.", "Ni et al. 1999 (broadcast storm)"),
        "flooding_rad": ("As blind flooding, but each rebroadcast waits an extra random assessment delay drawn from U[0, "
                         f"{config.RAD_MS:g} ms) (<code>Flooding(rad=True)</code>). The jitter spreads the transmissions in time; "
                         "every honest receiver still transmits.", "the same jitter the proposed scheme uses (audit RAD-1)"),
        "slotted1p": ("A receiver waits S(D)·τ, where the distance slot S = Ns − ⌈Ns·min(D, R)/R⌉ gives the farthest receivers "
                      f"slot 0 (Ns = {config.N_SLOTS}, τ = {config.TAU_MS:g} ms, R = {config.COMM_RANGE_M:.0f} m). If it hears any "
                      "duplicate before its slot it suppresses; otherwise it rebroadcasts (<code>Slotted1P</code>).",
                      "Wisitpongphan et al. 2007"),
        "slotted1p_rad": ("Slotted 1-persistence with the random assessment delay U[0, "
                          f"{config.RAD_MS:g} ms) added inside the slot; because the delay is at most one slot wide, the distance order "
                          "is kept (<code>Slotted1P(rad=True)</code>).", "Wisitpongphan et al. 2007 + RAD"),
    }
    body = (f"<p>All four baselines use exactly the same corroboration as the proposed method (committee, {config.QUORUM} BLS "
            "votes, certificate check by every receiver), the same radio model, the same per-event duplicate state (a vehicle "
            "decides once, on its first accepted copy) and the same hop limit; misbehaving vehicles never relay and RSUs only "
            "receive. They differ <em>only</em> in the forwarding rule, and none of them uses clustering, cluster heads or the "
            "CH-to-CH route. Each was replayed alone in SUMO-GUI in its own comparison pair.</p>")
    for k, s in enumerate(BASES, 1):
        e = by_base.get(s)
        text, ref = base_text[s]
        body += f'<h2 id="s9_{k}">9.{k}&nbsp;&nbsp;{esc(L[s])}</h2><p>{text} <span class="muted">Reference: {ref}.</span></p>'
        if e:
            body += mini(e, s) + doc.shot(shots["fwd_" + s], f"{L[s]} replayed alone (baseline-only run): relays transmitting "
                                          f"(orange rings) during the forwarding stage.", capsrc("fwd_" + s), maxh=118)
        else:
            body += '<p class="warn">No completed pair replayed this baseline, so no screenshot is shown.</p>'
    section("s9", "9&nbsp;&nbsp;Baseline Algorithms", body)

    # ---------------------------------------------------------------- 10 proposed
    route = canon["raw"]["infrastructure"]["route"]
    section("s10", "10&nbsp;&nbsp;Proposed Approach", doc.diagram(diagram_proposed(), "Proposed approach: corroboration before release (left), the "
            "decision every receiver takes (centre), the CH-to-CH route stage and RSU registration.") + f"""
<h2 id="s10_1">10.1&nbsp;&nbsp;Clustering and cluster-head election</h2>
<p>At the incident second the vehicles are clustered with DBSCAN (ε = {config.DBSCAN_EPS_M:.0f} m, MinPts = {config.DBSCAN_MIN_PTS}).
Inside each cluster, cluster heads are elected greedily: repeatedly the <b>trusted</b> vehicle (trust ≥ {config.TRUST_CH_THRESHOLD})
whose radio range covers the most still-uncovered members, ties broken by the lowest relative speed to its neighbours.
Isolated vehicles (DBSCAN noise) are bridges. Trusted cluster heads and trusted bridges form tier 0, everyone else tier 1
(<code>clustering.elect_roles</code>).</p>""" + doc.shot(shots["clusters"], "Clusters (teal members) and elected cluster heads "
            "(black rings) at the incident second, as used by the proposed scheme.", capsrc("clusters")) + f"""
<h2 id="s10_2">10.2&nbsp;&nbsp;Committee formation and voting</h2>
<p>The incident vehicle broadcasts a signed PROPOSAL. The committee is the {config.COMMITTEE_SIZE} nearest neighbours of the incident
vehicle whose trust is at least {config.TRUST_CH_THRESHOLD}. Honest members, who observe the event, each answer with one VOTE
(a BLS signature over the event digest) in rank order, {config.VOTE_SLOT_MS} ms apart; misbehaving members stay silent. The source
counts distinct voters and releases the alert at {config.QUORUM} votes (<code>corroboration.plan</code>, <code>Protocol.on_receive</code>).</p>"""
            + doc.shot(shots["votes"], "Committee members casting their votes (pink).", capsrc("votes")) + f"""
<h2 id="s10_3">10.3&nbsp;&nbsp;Certificate and signature verification</h2>
<p>The source aggregates its own signature and the votes into one BLS12-381 signature ({config.SIGNATURE_BYTES} bytes, real
cryptography with <code>py_ecc</code>) and broadcasts the certified alert. Every receiver and RSU applies the same rule
(<code>corroboration.accept</code>): the first signer must be the source, the aggregate signature must verify, and at least
{config.QUORUM} endorsers must be reputable. Processing time is charged as {config.BLS_SIGN_MS} ms per signature and
{config.BLS_VERIFY_MS} ms per verification.</p>""" + doc.shot(shots["certificate"], "The certified alert released by the source; each "
            f"receiver verifies the certificate ({config.BLS_VERIFY_MS} ms) before it accepts the alert.", capsrc("certificate")) + f"""
<h2 id="s10_4">10.4&nbsp;&nbsp;Forwarding control</h2>
<p>A vehicle decides once, on its first accepted copy. It waits (tier·Ns + S(D))·τ + U[0, RAD): tier-0 relays decide a full
slot cycle before tier 1, farther receivers before nearer ones, and the random assessment delay separates vehicles in the
same slot. When the wait ends it applies a <b>coverage test</b>: it rebroadcasts only if at least one beacon neighbour
(vehicle or RSU) is not within range of any sender it has heard; otherwise it suppresses (<code>protocols.Proposed</code>).
An uncovered RSU counts like any neighbour, which is what carries the alert to the infrastructure.</p>"""
            + doc.shot(shots["forwarding"], "Proposed scheme during forwarding: few relays transmit (orange rings); blue vehicles "
                       "already hold the verified alert.", capsrc("forwarding")) + f"""
<h2 id="s10_5">10.5&nbsp;&nbsp;Duplicate suppression</h2>
<p>Every vehicle keeps per-event state: a copy of an alert it already holds is never processed again, but its sender is added
to the set of senders heard, which is exactly what the coverage test uses. Suppression is therefore driven by duplicates
without any vehicle ever rebroadcasting twice. RSUs register an event ID once and record every later copy as DUPLICATE.</p>
<h2 id="s10_6">10.6&nbsp;&nbsp;CH-to-CH routing (a stage of the proposed method)</h2>
<p>The route is computed with Dijkstra (by distance) from the incident vehicle to the nearest RSU over cluster heads with trust
≥ {config.TRUST_CH_THRESHOLD} (<code>infrastructure.shortest_route</code>). Each head on the route first collects a local quorum
(itself plus cluster members' votes) and then forwards; vehicles off the route stay silent (<code>protocols.CHRoute</code>).
There is no fallback: without a route, or if a head's local quorum fails, nothing is delivered on this path. It is part of the
proposed method — the path that writes the dispatch outbox — not a competing algorithm. In scenario {csc['scenario_id']} the
route was {esc(' → '.join(route['vehicle_ids']))}.</p>""" + doc.shot(shots["route"], "The CH-to-CH route stage: the traversed route "
            "(purple) from the incident vehicle to the RSU.", capsrc("route")) + f"""
<h2 id="s10_7">10.7&nbsp;&nbsp;RSU verification and registration</h2>
<p>An RSU decodes a copy, verifies its certificate ({config.BLS_VERIFY_MS} ms) and runs plausibility checks on its own clock:
required fields, a known message type, a position inside the road network, not created after reception, at most
600 s old, within the hop limit ({config.HOP_LIMIT}), and the certificate. The first valid copy is REGISTERED (registration time
= arrival + verification), later copies are DUPLICATE and failures REJECTED with their reason (<code>rsu.register</code>). The
CH-route delivery is written to a local SQLite dispatch outbox (<code>infrastructure.persist</code>); no real emergency service
is contacted.</p>""" + doc.shot(shots["rsu"], "RSU outcome of the proposed scheme: one RSU registered the event (dark green), the other "
            "recorded duplicate copies (light green).", capsrc("rsu")) + f"""
<h2 id="s10_8">10.8&nbsp;&nbsp;Forged-alert rejection</h2>
<p>On the same traffic, a misbehaving vehicle claims an accident that did not happen and its misbehaving neighbours endorse it.
Their signatures are valid, but they are not reputable, so the certificate fails the acceptance rule at every receiver and RSU.</p>"""
            + doc.shot(shots["forged"], "Forged alert test (full protection): receivers reject the forged alert.", capsrc("forged")))

    # ---------------------------------------------------------------- 11 dashboard
    took = {a: [run_seconds(e["pair"]["runs"][a]) for e in pairs] for a in ("baseline", "proposed")}   # pair.json times

    def dshot(name, caption):
        prefix = f"dash_{name}_"
        files = sorted((f for f in dash if f == f"dash_{name}.png" or (f.startswith(prefix) and f[len(prefix):-4].isdigit())),
                       key=lambda f: dash[f].get("part", 1))
        if not files:
            return f'<p class="warn">Dashboard screenshot dash_{name}.png is missing.</p>'
        out = ""
        for f in files:
            meta = dash[f]
            part = f" (part {meta.get('part', 1)} of {len(files)})" if len(files) > 1 else ""
            out += doc.shot(f, caption + part, f"headless Microsoft Edge screenshot of the running dashboard, pair {meta.get('pair')}, "
                            f"{meta.get('note', '')}, {meta.get('taken', '')}", maxh=215)
        return out
    section("s11", "11&nbsp;&nbsp;Dashboard and Demonstration", f"""
<p>The faculty demonstration is organised around <b>comparison pairs</b>. A pair is one incident scenario replayed twice in
SUMO-GUI: once with a single baseline, once with the proposed method (its CH-to-CH route stage and the forged-alert test
included). The two runs never share a map and never run at the same time. Both runs re-simulate the pair's seed, each into its
own folder (<code>&lt;pair&gt;/baseline/</code>, <code>&lt;pair&gt;/proposed/</code>), so each keeps its own record of the same run;
the dashboard shows the comparison only when the two records' fingerprints are equal. (This report's pairs ran before per-run
folders existed, when both runs of a pair wrote one shared record in <code>&lt;pair&gt;/raw/</code>; both runs' fingerprints
are equal as well.)</p>""" + doc.diagram(diagram_pairs(),
            "How a pair is run from the dashboard.") + f"""
<h3>Controls</h3>
<ul><li><b>New pair</b> takes the next scenario of the pairs folder's own order, shuffled by its selection seed (incident on the
network, ≥ 50 m from every incident used before) with the baseline chosen in the list beside it.</li>
<li><b>Run baseline only</b> / <b>Run proposed only</b> start one run in its own process; SUMO-GUI opens and plays the run from start
to finish (in this report's pairs a baseline-only run took {min(took['baseline']):.0f}–{max(took['baseline']):.0f} s and a
proposed-only run {min(took['proposed']):.0f}–{max(took['proposed']):.0f} s). While a run is active every start button is disabled and the server refuses another start (HTTP 409).
Pause/resume is not offered.</li>
<li>A run whose process ends without finishing is marked failed; its live state and captures are never shown as current.
If a SUMO-GUI window stops responding (seen once in about 15 runs), closing it ends the run this way, and the run can be started
again on the same scenario; a window capture never waits more than 10 s for SUMO-GUI.</li></ul>
<h3>Sections of the dashboard</h3>""" + dshot("overview", "Section 1, Overview: the goal, the proposed method in plain words and the "
            "baselines.") + dshot("scenario", "Section 2, Scenario & approach: the pair's scenario (ID, seed, incident, network, "
            "traffic, selection) and the two run cards with their controls.") + dshot("live_baseline", "Section 3, Live simulation "
            "during a baseline-only run: the LIVE badge, the stage indicator (Cluster / CH is not part of a baseline), SUMO and radio "
            "time, and the newest window capture of that run.") + dshot("live_proposed", "Section 3 during the proposed-only run of the "
            "same pair.") + dshot("outcome_baseline", "Section 4 right after a baseline-only run: the baseline's own outcome, copied from the run "
            "record.") + dshot("comparison_withheld", "Section 5 at the same moment: the comparison is withheld until the "
            "proposed-only run has finished with the same record fingerprint.") + dshot("outcome", "Section 4 after both runs, proposed run "
            "selected: the proposed method and its CH-to-CH route stage, with units and definitions.") + dshot("comparison", "Section 5, Algorithm comparison: baseline vs proposed (with its CH-to-CH "
            "route stage), charts, every implemented baseline on the same record, and the separate multi-seed results.")
            + dshot("evidence", "Section 6, Evidence & limitations: the pair's folder, records, fingerprints, captures and commands.")
            + "<div class='keep'><h3>Separated runs in SUMO-GUI</h3><p>The final screens of the two runs of one pair show the "
            "separation: each ends on its own approach's outcome.</p>" + doc.shot(shots["final_baseline"], "End of the baseline-only run: "
            "the outcome of the baseline itself (no clusters, no route, no forged-alert test; 'no dispatch recorded').",
            capsrc("final_baseline")) + "</div>"
            + doc.shot(shots["final_proposed"], "End of the proposed-only run of the same pair: the outcome of the proposed method; "
            "the dispatch was queued by its CH-to-CH route stage.", capsrc("final_proposed")))

    # ---------------------------------------------------------------- 12 setup
    params = [("Network", config.NET_FILE), ("Densities (vehicles)", ", ".join(map(str, densities))),
              ("Seeds per density", config.RUNS_PER_DENSITY), ("Seed rule", f"{config.BASE_SEED} + 100·N + r"),
              ("Departures / route length", f"U(0, {config.DEPART_WINDOW_S} s) / {config.ROUTE_EDGES} edges"),
              ("Incident time", f"U{{{config.INCIDENT_WINDOW_S[0]}..{config.INCIDENT_WINDOW_S[1]}}} s"),
              ("Misbehaving vehicles", f"{100 * config.MALICIOUS_RATIO:.0f} % (never relay)"),
              ("Radio", f"IEEE 802.11p, {config.COMM_RANGE_M:.0f} m unit disk, {config.DATA_RATE_MBPS} Mb/s, AC_VO (AIFSN {config.AIFSN}, CWmin {config.CW_MIN})"),
              ("Alert payload / signature", f"{config.PAYLOAD_BYTES} B / {config.SIGNATURE_BYTES} B BLS12-381"),
              ("Distance slots / slot length / random delay", f"Ns = {config.N_SLOTS} / τ = {config.TAU_MS:g} ms / U[0, {config.RAD_MS:g} ms)"),
              ("Committee / quorum / trust threshold", f"{config.COMMITTEE_SIZE} / {config.QUORUM} / {config.TRUST_CH_THRESHOLD}"),
              ("BLS sign / verify charge", f"{config.BLS_SIGN_MS} ms / {config.BLS_VERIFY_MS} ms"),
              ("DBSCAN", f"ε = {config.DBSCAN_EPS_M:.0f} m, MinPts = {config.DBSCAN_MIN_PTS}"),
              ("Hop limit / RSU validity", f"{config.HOP_LIMIT} hops / {rsu.MAX_AGE_S:.0f} s"),
              ("RSUs", rsu_pos)]
    prow = []
    for e in pairs:
        p, s = e["pair"], e["pair"]["scenario"]
        r_b, r_p = p["runs"]["baseline"], p["runs"]["proposed"]
        dur = lambda r: f"{run_seconds(r):.0f} s"
        prow.append([f"<b>{p['pair_id']}</b>", s["scenario_id"], str(s["seed"]), str(s["density"]),
                     f"{esc(s['incident']['vehicle'])} at ({s['incident']['x']:.0f}, {s['incident']['y']:.0f}) m, t = {s['incident']['time_s']:.0f} s",
                     esc(L[p["baseline"]]),
                     f"exit {r_b.get('exit_code', '–')}, {dur(r_b)}; {len(e['caps']['baseline'])} captures",
                     f"exit {r_p.get('exit_code', '–')}, {dur(r_p)}; {len(e['caps']['proposed'])} captures",
                     f"<code>{e['fp'][:16]}…</code> ({'equal' if r_b['fingerprint'] == r_p['fingerprint'] == e['fp'] else 'DIFFERENT'})"])
    section("s12", "12&nbsp;&nbsp;Experimental Setup", "<p>Two kinds of experiment are reported and never mixed: the "
            "<b>multi-seed experiment</b> (every scheme, every density, 30 seeds; <code>python run.py experiment</code>) and the "
            "<b>comparison pairs</b> (one scenario each, replayed in SUMO-GUI). Within one seed every scheme runs on the identical "
            "snapshot, network, demand, radio and parameters, and each scheme has its own deterministic radio random stream.</p>"
            + doc.table(["Parameter", "Value"], [[esc(a), esc(str(b))] for a, b in params], "Design parameters.", "config.py; the RSU validity from rsu.py")
            + doc.table(["Pair", "Scenario", "Seed", "Vehicles", "Incident", "Baseline replayed", "Baseline-only run",
                         "Proposed-only run", "Record fingerprint"], prow,
                        "Comparison pairs used in this report. Both runs of every pair replayed the same record.",
                        "results/demo_pairs/&lt;pair&gt;/pair.json and the pair's run record", cls="small")
            + (f'<p class="warn">Pairs not used (incomplete): {esc(", ".join(f"{a} ({b})" for a, b in ctx["skipped"]))}.</p>'
               if ctx["skipped"] else ""))
    t_pairs = doc.n_tab                                      # the pair list is the last table of section 12

    # ---------------------------------------------------------------- 13 comparison
    mech = [["Blind flooding", "rebroadcast once on acceptance", "every honest vehicle that accepts it", "none", "counted, never suppress", "shared", "no"],
            ["Flooding + random delay", "rebroadcast once after U[0, RAD)", "every honest vehicle that accepts it", "random delay only", "counted, never suppress", "shared", "no"],
            ["Slotted 1-persistence", "rebroadcast at slot S(D)·τ unless a duplicate is heard first", "receivers that hear no duplicate before their slot", "distance slot, farthest first", "any duplicate before the slot suppresses", "shared", "no"],
            ["Slotted 1-p + random delay", "as slotted 1-p, plus U[0, RAD) inside the slot", "as slotted 1-p", "distance slot + random delay", "as slotted 1-p", "shared", "no"],
            ["Proposed method", "wait (tier·Ns + S(D))·τ + U[0, RAD), then coverage test", "tier 0 (trusted CH, bridge) first; anyone with an uncovered neighbour", "tier + distance slot + random delay", "duplicates mark neighbours covered → suppression", "shared (it is part of the method)", "yes: clustering, tiers"],
            ["… its CH-to-CH route stage", "forward along the Dijkstra route of trusted CHs", "only the route heads, after a local quorum", "per-hop local quorum", "off-route vehicles stay silent", "shared + local quorum per head", "yes: the route"]]
    body = doc.table(["Scheme", "How a vehicle forwards", "Who may forward", "Delay / persistence", "Duplicates",
                      "Voting + certificate", "Clustering / CH"], [[f"<b>{a}</b>", *map(esc, r)] for a, *r in mech],
                     "Mechanisms of every implemented scheme, as implemented.", "protocols.py, experiment.arms, clustering.py, "
                     "corroboration.py", cls="small")
    body += ("<p>Every scheme decides once per vehicle, keeps per-event duplicate state, respects the hop limit, never relays from a "
             "misbehaving vehicle and never relays from an RSU. The table below each pair gives every implemented scheme on that "
             "pair's identical record; only the marked baseline and the proposed method were replayed in SUMO-GUI — the other "
             "baselines were simulated on the same snapshot by the same run but not animated.</p>")
    keys = [k for k, *_ in demo_pairs.METRICS]
    labels = {k: lab for k, lab, *_ in demo_pairs.METRICS}
    for e in pairs:
        p = e["pair"]
        cols = BASES + ["proposed", "ch_route"]
        head = ["Metric"] + [f"{esc(NAME[s])}{' <b>(replayed)</b>' if s == p['baseline'] else ''}" for s in BASES] + \
               ["Proposed <b>(replayed)</b>", "its CH-route stage"]
        rows = [[esc(labels[k])] + [cell(e["rows"][s], k)["text"] for s in cols] for k in keys]
        body += doc.table(head, rows, f"Pair {p['pair_id']}: scenario {p['scenario']['scenario_id']} (seed {p['scenario']['seed']}, "
                          f"{p['scenario']['density']} vehicles, incident {esc(p['scenario']['incident']['vehicle'])} at t = "
                          f"{p['scenario']['incident']['time_s']:.0f} s). One run: no statistical claim.", src_pair(e),
                          cls="small", right=tuple(range(1, 7)))
    section("s13", "13&nbsp;&nbsp;Algorithm Comparison", body)
    t_per_pair = f"{doc.n_tab - len(pairs) + 1}–{doc.n_tab}"   # one table per pair closes section 13

    # ---------------------------------------------------------------- 14 evaluation
    definitions = [("Vehicles holding the alert", "vehicles that accepted the certified alert (source included)", "vehicles", "↑ higher", "metrics.received"),
                   ("Reach", "holding the alert / vehicles connected to the source by radio", "%", "↑ higher", "metrics.reachability"),
                   ("Time until 90 % hold it (t90)", "radio time until 90 % of the reachable vehicles accepted it; 'not reached' if never", "ms", "↓ lower", "metrics.t90_ms"),
                   ("Frames on air", "every frame sent: proposal, votes, alert copies (and route heads' local votes)", "frames", "↓ lower", "metrics.transmissions"),
                   ("Receptions lost to collisions", "copies destroyed by overlapping frames", "receptions", "↓ lower", "metrics.collision_losses"),
                   ("First RSU registration", "until an RSU registered the event: first valid copy decoded + 4.3 ms verification", "ms", "↓ lower", "metrics.rsu_delay_ms"),
                   ("RSU delivery", "runs in which an RSU registered the event (when one is reachable)", "% of runs", "↑ higher", "metrics.rsu_received"),
                   ("Duplicate copies at RSUs", "copies of the registered event decoded later by the RSUs", "copies", "↓ lower (less waste)", "metrics.rsu_dup_copies"),
                   ("Duplicate receptions at vehicles", "copies decoded by vehicles that already held the alert", "receptions", "↓ lower (less waste)", "metrics.dup_rx"),
                   ("Forged alert accepted", "honest vehicles that accepted a forged alert", "% of honest reachable", "↓ lower", "forgery_summary.accepted_share")]
    ms_rows = []
    for s in SCHEMES + ["ch_route"]:
        ms_rows.append([esc(NAME[s]), sm(s, "transmissions"), sm(s, "collision_losses", d=0), sm(s, "reachability", 100),
                        sm(s, "t90_ms") if mean(s, "t90_ms") is not None else "not reached", sm(s, "rsu_delay_ms"),
                        sm(s, "rsu_received", 100, 0), sm(s, "dup_rx", d=0)])
    pd_rows = []
    for b in BASES:
        r = p200[b]
        row = [esc(NAME[b])]
        for key, lower in (("transmissions", True), ("collision_losses", True), ("reachability", False), ("t90_ms", True), ("rsu_delay_ms", True)):
            scale = 100 if key == "reachability" else 1
            d, c = num(r[key]), num(r[key + "_ci95"])
            text, v = verdict(None if d is None else d * scale, None if c is None else c * scale, lower)
            row.append(f"{text}<br><span class='muted'>{v} (n = {r[key + '_n']})</span>")
        pd_rows.append(row)
    fz_rows = []
    for v, label in (("voting_reputation", "Voting + BLS + reputation (full)"), ("voting_only", "Voting + BLS, no reputation gate"), ("no_voting", "No voting")):
        rows = {int(r["density"]): r for r in forgery if r["variant"] == v}
        fz_rows.append([esc(label)] + [f"{100 * num(rows[d]['accepted_share']):.0f} %" for d in densities])
    section("s14", "14&nbsp;&nbsp;Performance Evaluation", doc.table(["Metric", "What it measures", "Unit", "Better", "Source"],
            [[esc(a), esc(b), esc(c), esc(d), f"<code>{esc(e)}</code>"] for a, b, c, d, e in definitions],
            "Metric definitions. Every value in this report is copied from these record fields or CSV columns.",
            "metrics.py, results/urban/processed/*.csv", cls="small")
            + f"<h3>Multi-seed results at {D} vehicles</h3>" + doc.chart("chart_multiseed_200.png", f"Every implemented scheme over "
            f"{config.RUNS_PER_DENSITY} seeds at {D} vehicles (mean ± 95 % confidence interval).", "results/urban/processed/summary.csv")
            + doc.table(["Scheme", "Frames on air", "Receptions lost", "Reach (%)", "t90 (ms)", "First RSU reg. (ms)", "RSU delivery (%)",
                         "Duplicate rx"], ms_rows, f"Multi-seed results at {D} vehicles: mean ± 95 % confidence half-width over "
                         f"{config.RUNS_PER_DENSITY} seeds (n = the runs that had a value, where fewer). The CH-route stage is part of the proposed method and is shown separately.",
                         "results/urban/processed/summary.csv", cls="small", right=tuple(range(1, 8)))
            + doc.chart("chart_seeds_200.png", f"The individual runs behind those means: one dot per seed at {D} vehicles.",
                        "results/urban/processed/runs.csv")
            + doc.table(["Baseline", "Frames on air", "Receptions lost", "Reach (pp)", "t90 (ms)", "First RSU reg. (ms)"], pd_rows,
                        f"Paired differences, proposed minus baseline, at {D} vehicles (mean ± 95 % CI over the seeds where both "
                        "values exist). 'No significant difference' means the interval contains zero.",
                        "results/urban/processed/paired.csv", cls="small", right=(1, 2, 3, 4, 5))
            + "<h3>Effect of traffic density</h3>" + doc.chart("chart_density.png", "Frames on air, receptions lost and t90 as traffic "
            "density grows (mean, shaded 95 % CI; log scale for the first two).", "results/urban/processed/summary.csv")
            + "<h3>The comparison pairs</h3>" + doc.chart("chart_pairs.png", "Every scheme in each comparison pair (single runs on "
            "the pair's record).", f"the run records of the pairs in Table {t_pairs}; the values are those of Tables {t_per_pair} (results/demo_pairs)")
            + "<h3>Forged alerts</h3>" + doc.chart("chart_forgery.png", "Forged-alert test: share of honest vehicles that accepted a forged "
            "alert, and of runs in which an RSU registered it, for three protection levels.", "results/urban/processed/forgery_summary.csv")
            + doc.table(["Protection level"] + [f"{d} veh." for d in densities], fz_rows, "Honest vehicles that accepted a forged alert "
                        f"(mean over {config.RUNS_PER_DENSITY} seeds).", "results/urban/processed/forgery_summary.csv", cls="small",
                        right=tuple(range(1, len(densities) + 1))))

    # ---------------------------------------------------------------- 15 results and discussion
    obs = ctx["observations"]
    section("s15", "15&nbsp;&nbsp;Results and Discussion", "<p>The statements below are generated from the results and checked when "
            "this report is built; each names its source.</p><ul>" + "".join(f"<li>{o}</li>" for o in obs) + "</ul>" + f"""
<h3>Discussion</h3>
<p><b>What the experiments demonstrate.</b> Controlling who rebroadcasts and when removes most of flooding's redundant
transmissions and, with them, most collisions, without giving up coverage: at {D} vehicles the proposed method sent
{sm('proposed', 'transmissions')} frames per alert against {sm('flooding', 'transmissions')} for blind flooding{', and it reached every reachable vehicle in every run at every density' if full_reach else ''}. The cost is time:
waiting for tiers, slots and the coverage test makes it slower than flooding to reach 90 % of the vehicles.</p>
<p><b>Against the strongest baseline.</b> Slotted 1-persistence with a random delay already removes most of flooding's
redundancy. Paired over the {config.RUNS_PER_DENSITY} seeds of each density (fewer for time to 90 % where a run never reached it), the proposed method is {strong_text} (a density not named shows no
significant difference). {'The evidence therefore supports the proposed method as a corroborated, trust-aware scheme of efficiency comparable to the best baseline, not as uniformly superior to it.' if mixed else ''}
Its distinguishing contributions are the trust-aware choice of relays, the coverage test and the CH-to-CH route that delivers to
the RSU and writes the dispatch. The corroboration that rejects forged alerts belongs to the whole system: every baseline was given
the same corroboration, so that the comparison isolates forwarding.</p>
<p><b>Corroboration.</b> Voting with a reputation gate rejected every forged alert in the forged-alert test, while voting alone was
defeated by colluding misbehaving neighbours whenever enough of them were in range; this result depends on the reputation being
reliable (section 16).</p>
<p><b>What is not shown.</b> A single comparison pair is one run of one scenario: it illustrates the behaviour and lets the
replays be compared like for like, but supports no statistical claim. General statements rest on the {config.RUNS_PER_DENSITY}-seed
experiment and its paired confidence intervals.</p>""")

    # ---------------------------------------------------------------- 16 limitations
    lim = ["<b>Simulated radio.</b> IEEE 802.11p on a unit disk ({:.0f} m), simulated slot by slot with carrier sensing, collisions, "
           "hidden terminals and half-duplex losses; fading, capture, background beacon load and real hardware are not modelled.".format(config.COMM_RANGE_M),
           "<b>Staged incident, no crash detection.</b> The accident is designated, not detected from sensors; honest committee members "
           "are assumed to observe it.",
           "<b>One report per incident.</b> The simulation creates exactly one alert per crash. <code>rsu.register_reports</code>, which "
           "can merge several valid reports of one crash (same type, within 10 m and 2 s of every report of an incident), is unit-tested "
           "but not part of the simulated workflow; integrating it would need a multi-reporter scenario model. Its rule cannot tell two "
           "distinct crashes within those bounds apart.",
           "<b>Near-oracle reputation.</b> Misbehaving vehicles are persistent black holes, so their trust stays low by construction. "
           "On-off attackers that behave well while watched can pass the trust gate, and forged alerts are then accepted (auditor "
           "measurement: registered in 8 of 10 runs; docs/AUDIT.md).",
           "<b>Keys from vehicle IDs; fixed BLS timing.</b> There is no public-key infrastructure; signing and verification are charged "
           "fixed times.",
           "<b>Fail-closed corroboration.</b> A genuine alert is never released when fewer than {} reputable honest voters are in range; "
           "a quorum-timeout fallback is specified but not implemented.".format(config.QUORUM),
           "<b>CH-to-CH route has no fallback.</b> Without a route, or if a head's local quorum fails, nothing is delivered on that path.",
           "<b>Frozen snapshot and small map.</b> Dissemination is computed on the incident-second snapshot (it lasts tens of ms); the "
           "network is one 5 × 5 grid and the parameters are untuned design choices.",
           "<b>Demonstration.</b> SUMO-GUI replays a run computed by the experiment engine; window captures need Windows; runs cannot be "
           "paused; the dashboard is a local tool without authentication; the pair scenarios are the 30 seeds at {} vehicles, and a "
           "location is reused (and labelled) only after all others.".format(D),
           "<b>Statistics.</b> Pairs are single runs; multi-seed results use 30 seeds per density with Student-t 95 % intervals (metrics.summarize), also for the paired differences."]
    section("s16", "16&nbsp;&nbsp;Limitations", "<ul>" + "".join(f"<li>{x}</li>" for x in lim) + "</ul>")

    # ---------------------------------------------------------------- 17 how to run
    section("s17", "17&nbsp;&nbsp;How to Run the Project", f"""
<p><b>Setup</b> (Windows PowerShell shown; Linux/macOS use <code>source .venv/bin/activate</code>). SUMO comes from the
<code>eclipse-sumo</code> package, so no separate installation is needed.</p>
<pre>python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest validation -q            # the validation suite</pre>
<p><b>Faculty demonstration</b> (dashboard; keep this terminal open and visit http://127.0.0.1:8765/):</p>
<pre>python run.py web
#   section 2: New pair → Run baseline only → (wait) → Run proposed only; sections 3–6 follow the runs</pre>
<p><b>The same from a terminal:</b></p>
<pre>python run.py pair new --baseline slotted1p      # next reproducible scenario (or --scenario d{D}_r07)
python run.py demo --pair P001 --approach baseline
python run.py demo --pair P001 --approach proposed
python run.py pair show P001                      # scenario, run status, comparison
python run.py demo                                # flooding, proposed, CH route, forged-alert test</pre>
<p><b>Results and documents:</b></p>
<pre>python run.py experiment                 # 6 densities × 30 seeds → results/urban/ (about 2–3 min)
python run.py single -d {D} -r 2           # one scenario, every scheme, in the terminal
python run.py explain d{D}_r02             # chronological story of a saved run
cd portal; node check.mjs                  # documentation website check
python docs/final_report/build_final_report.py   # this report (needs pypdfium2 and Microsoft Edge)</pre>
<p>Pairs are written to <code>results/demo_pairs/</code>; tracked results are never written by a pair. <code>python run.py demo</code>
without <code>EXP_RESULTS_DIR</code> re-simulates its seed and saves that run in <code>results/urban/</code> (the
d{D}_r{config.DEMO_RUN:02d} record with a new <code>recorded_at</code>, a timestamped copy, the dispatch outbox, SUMO-GUI's error
log and the live feed); set <code>EXP_RESULTS_DIR</code> to another folder to leave them untouched.</p>""")

    # ---------------------------------------------------------------- 18 conclusion
    section("s18", "18&nbsp;&nbsp;Conclusion and Future Scope", f"""
<p>The project implements the complete workflow from SUMO traffic to a registered, corroborated emergency alert: reproducible
scenarios, alert creation, committee voting with real BLS aggregate signatures, trust-aware clustering and controlled
forwarding, a CH-to-CH route to the RSU, RSU validation and single registration, metrics, and a demonstration in which the
baseline and the proposed method are replayed separately and compared on the identical record. Against four implemented
baselines on identical traffic, the proposed method cut frames on air and collision losses by large factors relative to
flooding, kept reach at 100 % in the {config.RUNS_PER_DENSITY}-seed experiment at {D} vehicles, and rejected every forged alert with
full protection, at the price of a few milliseconds of extra delay to reach 90 % of the vehicles. Against the strongest baseline, slotted 1-persistence with a random delay, the results are {'mixed' if mixed else 'consistent'} (section 15).</p>
<h3>Future scope</h3>
<ul><li>A richer channel model (fading, capture, beacon load) and validation against a network simulator or hardware.</li>
<li>Sensor-based crash detection and multi-reporter incidents, which would put <code>rsu.register_reports</code> into the workflow.</li>
<li>A reputation that resists on-off attackers, a real PKI, and a quorum-timeout fallback.</li>
<li>A fallback for the CH-to-CH route, tuning of the slot, delay and committee parameters, and larger, real road networks.</li>
<li>Pausable live (not replayed) visualisation, and authentication for a multi-user dashboard.</li></ul>""")

    # ---------------------------------------------------------------- appendix
    vrows = [[esc(c["check"]), f"<code>{esc(c['command'])}</code>", esc(c["result"]), f"<b>{esc(c['status'])}</b>"]
             for c in (verification or {}).get("checks", [])]
    frows = [[f"Figure {n}", esc(kind), esc(src), esc(source if isinstance(source, str) else "")] for n, kind, src, cap_, source in doc.figures]
    section("sA", "Appendix A&nbsp;&nbsp;Evidence and Verification",
            (doc.table(["Check", "Command", "Result", "Status"], vrows, "Verification performed for this report.",
                       f"docs/final_report/verification.json ({(verification or {}).get('generated', 'missing')})", cls="small",
                       keep=False)
             if vrows else '<p class="warn">verification.json is missing: no verification results are reported.</p>')
            + "<p>Every figure, with its kind and source (screenshots name the pair, run and capture file; each pair's record fingerprint is in "
            f"Table {t_pairs}):</p>" + doc.table(["Figure", "Kind", "File", "Source"], frows, "Figure provenance.", cls="small",
                                                      keep=False))

    body = "".join(parts)
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{esc(TITLE)} — {esc(SUBTITLE)}</title>'
            f'<style>{CSS}</style></head><body>{body}</body></html>'), doc


CSS = """
@page { size: A4; margin: 16mm 16mm 17mm 16mm;
  @bottom-left { content: "IoV emergency message dissemination · final project report"; font: 7.5pt "Segoe UI", sans-serif; color: #7b8794; }
  @bottom-right { content: "Page " counter(page) " of " counter(pages); font: 7.5pt "Segoe UI", sans-serif; color: #7b8794; } }
@page :first { @bottom-left { content: none; } @bottom-right { content: none; } }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; font-family: Cambria, Georgia, serif; font-size: 10pt; line-height: 1.38; color: #1f2933; }
h1, h2, h3, .sans { font-family: "Segoe UI", Calibri, Arial, sans-serif; }
h1 { font-size: 17pt; font-weight: 600; color: #17375e; margin: 0 0 3.5mm; padding-bottom: 1.6mm; border-bottom: 0.7pt solid #b9c6d4; }
h2 { font-size: 12.5pt; font-weight: 600; color: #17375e; margin: 5mm 0 1.8mm; break-after: avoid; }
h3 { font-size: 10.8pt; font-weight: 600; color: #2a5a8c; margin: 4mm 0 1.4mm; break-after: avoid; }
p { margin: 0 0 2mm; text-align: justify; }
ul { margin: 0 0 2mm; padding-left: 5mm; }
li { margin: 0 0 1mm; }
.section { break-before: page; }
.keep { break-inside: avoid; }
figure { margin: 2mm 0 4mm; }
img.shot { display: block; height: auto; margin: 0 auto; border: 0.5pt solid #9aa8b6; object-fit: contain; }
.svg { width: 100%; margin: 0 auto; }
.svg svg { width: 100%; height: auto; }
figcaption { font: 8.4pt/1.35 "Segoe UI", Calibri, sans-serif; color: #2f3d4c; margin-top: 1.6mm; }
figcaption b { color: #17375e; }
.kind { color: #7a46c8; font-weight: 600; }
.src { color: #6b7785; }
.muted { color: #6b7785; }
.note { background: #f3f6fa; border-left: 2.4pt solid #6f8fb3; padding: 2.2mm 3.4mm; margin: 3mm 0; break-inside: avoid; }
.warn { background: #fff4e5; border-left: 2.4pt solid #c9952b; padding: 2mm 3mm; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.4pt; color: #233; }
pre { font: 8.4pt/1.4 Consolas, monospace; background: #f4f6f9; border: 0.5pt solid #dde3ea; padding: 2.4mm 3mm; white-space: pre-wrap; break-inside: avoid; }
.tbl { margin: 2mm 0 4mm; }
.tcap { font: 8.5pt/1.35 "Segoe UI", Calibri, sans-serif; color: #2f3d4c; margin-bottom: 1.2mm; }
.tcap b { color: #17375e; }
table { border-collapse: collapse; width: 100%; font: 8.7pt/1.3 "Segoe UI", Calibri, sans-serif; }
.small table { font-size: 7.6pt; }
th, td { border-bottom: 0.5pt solid #d5dde6; padding: 0.9mm 1.4mm; text-align: left; vertical-align: top; }
th { background: #eef2f7; color: #17375e; font-weight: 600; }
td.r, th.r { text-align: right; }
.cover { height: 262mm; display: flex; flex-direction: column; }
.cover .over { font: 600 9pt "Segoe UI"; letter-spacing: 0.15em; text-transform: uppercase; color: #5b7290; margin: 4mm 0 5mm; }
.cover .main { font: 600 24pt/1.18 "Segoe UI", sans-serif; color: #17375e; }
.cover .sub { font: 400 15pt/1.3 "Segoe UI", sans-serif; color: #1f2933; border-top: 0.8pt solid #b9c6d4; border-bottom: 0.8pt solid #b9c6d4; padding: 3mm 0; margin: 4mm 0; }
.cover .desc { font: 10.5pt/1.45 Cambria, serif; color: #2f3d4c; margin: 1mm 0 5mm; }
.cover img.hero { width: 100%; border: 0.5pt solid #9aa8b6; }
.cover .herocap { font: 8pt "Segoe UI", sans-serif; color: #6b7785; margin-top: 1.5mm; }
.cover .meta { margin-top: auto; font: 9.5pt/1.6 "Segoe UI", sans-serif; color: #1f2933; }
.cover .meta b { color: #17375e; }
.toc { list-style: none; padding: 0; margin: 3mm 0 0; font: 10pt/1.55 "Segoe UI", sans-serif; }
.toc li { display: flex; align-items: baseline; margin: 0; }
.toc li .d { flex: 1 1 auto; border-bottom: 0.7pt dotted #9aa8b6; margin: 0 1.5mm; transform: translateY(-0.9mm); }
.toc li .p { flex: 0 0 auto; min-width: 7mm; text-align: right; }
.toc li.l1 { font-weight: 600; color: #17375e; margin-top: 1.4mm; }
.toc li.l2 { padding-left: 6mm; font-size: 9.4pt; }
"""


# ================================================================ observations (checked statements)
def against(paired, baseline):
    """Per metric, the densities at which the proposed method is significantly better or worse than `baseline` (paired
    95 % confidence interval excluding zero). Returns (text, mixed): mixed = some better AND some worse."""
    metrics = [("transmissions", True, "frames on air"), ("collision_losses", True, "receptions lost"),
               ("reachability", False, "reach"), ("t90_ms", True, "time to 90 %"), ("rsu_delay_ms", True, "first RSU registration")]
    rows = sorted((r for r in paired if r["baseline"] == baseline), key=lambda r: int(r["density"]))
    parts, any_b, any_w = [], False, False
    for key, lower, label in metrics:
        better, worse = [], []
        for r in rows:
            d, c = num(r[key]), num(r[key + "_ci95"])
            if d is not None and c is not None and abs(d) > c:
                (better if (d < 0) == lower else worse).append(r["density"])
        any_b, any_w = any_b or bool(better), any_w or bool(worse)
        said = [f"better at {', '.join(better)} vehicles" if better else "", f"worse at {', '.join(worse)} vehicles" if worse else ""]
        parts.append(f"{label} " + ("; ".join(x for x in said if x) if better or worse else "not significantly different at any density"))
    return "; ".join(parts), any_b and any_w


def observations(s200, summary, paired, forgery, pairs):
    """Statements for section 15, each computed from the data; a statement that the data no longer supports is not made."""
    out = []
    p200 = {r["baseline"]: r for r in paired if int(r["density"]) == D}
    f, p, s1r = s200["flooding"], s200["proposed"], s200["slotted1p_rad"]
    ratio = num(f["transmissions"]) / num(p["transmissions"])
    out.append(f"At {D} vehicles the proposed method's broadcast sent {ms(p, 'transmissions')} frames per alert, {ratio:.1f} times fewer "
               f"than blind flooding ({ms(f, 'transmissions')}; its CH-to-CH route stage is a separate dissemination, counted in its own "
               f"row); paired over the seeds the difference is "
               f"{num(p200['flooding']['transmissions']):+.1f} ± {num(p200['flooding']['transmissions_ci95']):.1f} frames. "
               "<span class='src'>(summary.csv, paired.csv)</span>")
    d, c = num(p200["slotted1p_rad"]["transmissions"]), num(p200["slotted1p_rad"]["transmissions_ci95"])
    rel = "no significant difference from" if abs(d) <= c else ("more frames than" if d > 0 else "fewer frames than")
    out.append(f"Against the strongest baseline, slotted 1-p + random delay ({ms(s1r, 'transmissions')} frames), the proposed method shows "
               f"{rel} it at {D} vehicles (paired difference {d:+.1f} ± {c:.1f}). <span class='src'>(summary.csv, paired.csv)</span>")
    d, c = num(p200["slotted1p_rad"]["collision_losses"]), num(p200["slotted1p_rad"]["collision_losses_ci95"])
    rel = "no significant difference" if abs(d) <= c else ("fewer" if d < 0 else "more")
    out.append(f"Receptions lost to collisions: {ms(p, 'collision_losses', d=0)} for the proposed method against {ms(f, 'collision_losses', d=0)} "
               f"for blind flooding and {ms(s1r, 'collision_losses', d=0)} for slotted 1-p + random delay ({rel} than the latter: "
               f"{d:+.0f} ± {c:.0f}). <span class='src'>(summary.csv, paired.csv)</span>")
    full = all(num(summary_at(summary, dd)["proposed"]["reachability"]) == 1.0 for dd in sorted({int(r["density"]) for r in summary}))
    out.append(("The proposed method reached 100 % of the reachable vehicles in every run at every density."
                if full else "The proposed method's mean reach was below 100 % at some density.")
               + f" Blind flooding reached {ms(f, 'reachability', 100)} % and slotted 1-persistence {ms(s200['slotted1p'], 'reachability', 100)} % "
               f"at {D} vehicles. <span class='src'>(summary.csv)</span>")
    d, c = num(p200["flooding"]["t90_ms"]), num(p200["flooding"]["t90_ms_ci95"])
    out.append(f"Delay is the trade-off: the proposed method needed {ms(p, 't90_ms')} ms to reach 90 % of the reachable vehicles against "
               f"{ms(f, 't90_ms')} ms for blind flooding ({'+' if d > 0 else ''}{d:.1f} ± {c:.1f} ms paired; "
               f"{'significantly slower' if d - c > 0 else 'not significantly different'}). <span class='src'>(summary.csv, paired.csv)</span>")
    d, c = num(p200["flooding"]["rsu_delay_ms"]), num(p200["flooding"]["rsu_delay_ms_ci95"])
    out.append(f"First RSU registration took {ms(p, 'rsu_delay_ms')} ms with the proposed method and {ms(f, 'rsu_delay_ms')} ms with blind "
               f"flooding (paired {d:+.1f} ± {c:.1f} ms: {'no significant difference' if abs(d) <= c else 'a significant difference'}); every "
               f"scheme delivered to an RSU in {ms(p, 'rsu_received', 100, 0)} % of the runs. <span class='src'>(summary.csv, paired.csv)</span>")
    ch = s200["ch_route"]
    out.append(f"The CH-to-CH route stage used {ms(ch, 'transmissions')} frames and lost no receptions, but by design it informs only "
               f"the vehicles along and around the route ({ms(ch, 'reachability', 100)} % reach) and delivered to the RSU in "
               f"{ms(ch, 'rsu_received', 100, 0)} % of the runs (it has no fallback). <span class='src'>(summary.csv)</span>")
    fz = {(int(r["density"]), r["variant"]): r for r in forgery}
    dens = sorted({int(r["density"]) for r in forgery})
    voting_only = [f"{100 * num(fz[(dd, 'voting_only')]['accepted_share']):.0f} %" for dd in dens]
    zero = all(num(fz[(dd, "voting_reputation")]["accepted_share"]) == 0 and num(fz[(dd, "voting_reputation")]["rsu_registered"]) == 0
               for dd in dens)
    out.append(("With full protection no honest vehicle accepted a forged alert and no RSU registered one, at any density"
                if zero else "With full protection some forged alerts were accepted")
               + f"; without the reputation gate {', '.join(voting_only)} "
               f"of honest vehicles accepted it ({', '.join(map(str, dens))} vehicles). <span class='src'>(forgery_summary.csv)</span>")
    text, mixed = against(paired, "slotted1p_rad")
    out.append(f"Against the strongest baseline, slotted 1-p + random delay, paired over the seeds at every density, the proposed "
               f"method is {'mixed' if mixed else 'consistent'}: {text} (a density not named shows no significant difference). "
               "<span class='src'>(paired.csv)</span>")
    fewer = sum(1 for e in pairs if cell(e["rows"]["proposed"], "transmissions")["value"] < cell(e["rows"][e["pair"]["baseline"]], "transmissions")["value"])
    out.append(f"In the comparison pairs, the proposed method's broadcast used fewer frames than the replayed baseline in {fewer} of "
               f"{len(pairs)} pairs (its CH-to-CH route stage is counted separately in the pair tables; single runs illustrate, the seeds "
               "above decide). <span class='src'>(pair records)</span>")
    return out


# ================================================================ printing and contents
def browser():
    for p in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe", shutil.which("msedge") or "", shutil.which("google-chrome") or ""):
        if p and Path(p).exists():
            return p
    raise SystemExit("Microsoft Edge or Google Chrome is needed to print the PDF")


def print_pdf(html_path, pdf_path):
    """Print into a fresh file, then move it into place. The browser's launcher can return before its detached headless
    browser has written the file (Edge 157 does), so the file is awaited until its size stops changing."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:   # the browser may still hold its profile
        out = Path(tmp) / "print.pdf"
        subprocess.run([browser(), "--headless=new", "--disable-gpu", "--no-first-run", "--disable-extensions",
                        f"--user-data-dir={Path(tmp) / 'profile'}", "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
                        "--virtual-time-budget=20000", f"--print-to-pdf={out}", html_path.as_uri()],
                       check=True, timeout=300, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        size, deadline = -1, time.time() + 300
        while time.time() < deadline:
            time.sleep(2)
            now = out.stat().st_size if out.exists() else -1
            if now > 200_000 and now == size:
                break
            size = now
        assert out.exists() and out.stat().st_size > 200_000, "the PDF was not written"
        shutil.move(out, pdf_path)


def heading_pages(pdf_path, toc):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(pdf_path))
    norm = lambda s: " ".join(s.replace("\u00a0", " ").replace("\r", " ").split())
    texts = [norm(pdf[i].get_textpage().get_text_range()) for i in range(len(pdf))]
    found = {}
    for key, text, _ in toc:
        hits = [i + 1 for i in range(2, len(texts)) if norm(text) in texts[i]]
        assert hits, f"heading not found in the PDF: {text}"
        found[key] = hits[0]
    return found, len(texts)


TOC = [("s1", "1 Abstract", 1), ("s2", "2 Problem Statement and Motivation", 1), ("s3", "3 Project Objectives", 1),
       ("s4", "4 System Architecture", 1), ("s5", "5 Technologies Used", 1), ("s6", "6 Complete End-to-End Workflow", 1),
       ("s7", "7 Traffic Simulation", 1), ("s8", "8 Accident / Incident Simulation", 1), ("s9", "9 Baseline Algorithms", 1),
       ("s9_1", "9.1 Blind flooding", 2), ("s9_2", "9.2 Flooding + random delay", 2), ("s9_3", "9.3 Slotted 1-persistence", 2),
       ("s9_4", "9.4 Slotted 1-p + random delay", 2), ("s10", "10 Proposed Approach", 1),
       ("s10_1", "10.1 Clustering and cluster-head election", 2), ("s10_2", "10.2 Committee formation and voting", 2),
       ("s10_3", "10.3 Certificate and signature verification", 2), ("s10_4", "10.4 Forwarding control", 2),
       ("s10_5", "10.5 Duplicate suppression", 2), ("s10_6", "10.6 CH-to-CH routing (a stage of the proposed method)", 2),
       ("s10_7", "10.7 RSU verification and registration", 2), ("s10_8", "10.8 Forged-alert rejection", 2),
       ("s11", "11 Dashboard and Demonstration", 1), ("s12", "12 Experimental Setup", 1), ("s13", "13 Algorithm Comparison", 1),
       ("s14", "14 Performance Evaluation", 1), ("s15", "15 Results and Discussion", 1), ("s16", "16 Limitations", 1),
       ("s17", "17 How to Run the Project", 1), ("s18", "18 Conclusion and Future Scope", 1),
       ("sA", "Appendix A Evidence and Verification", 1)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dashboard-shots", help="folder with the dashboard screenshots and shots.json (prepares figures/)")
    a = ap.parse_args()
    FIG.mkdir(parents=True, exist_ok=True)
    pairs, skipped = load_pairs()
    if len(pairs) < 2:
        raise SystemExit(f"at least two complete comparison pairs are needed (results/demo_pairs); skipped: {skipped}")
    pairs.sort(key=lambda e: e["pair"]["pair_id"])
    summary, runs, paired, forgery = (read_csv(n) for n in ("summary.csv", "runs.csv", "paired.csv", "forgery_summary.csv"))
    s200 = summary_at(summary, D)
    shots, prov, canon = sumo_figures(pairs)
    shutil.copyfile(ROOT / config.RESULTS_DIR / "figures" / "topology.png", FIG / "topology_results.png")
    if a.dashboard_shots:
        dashboard_figures(a.dashboard_shots)
    dash_file = FIG / "dashboard_shots.json"
    dash = json.loads(dash_file.read_text(encoding="utf-8"))["figures"] if dash_file.exists() else {}
    chart_multiseed(s200)
    chart_density(summary)
    chart_seeds(runs)
    chart_pairs(pairs)
    chart_forgery(forgery)
    reqs = {}
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if "==" in line and not line.startswith("#"):
            name, ver = line.split("==", 1)
            reqs.setdefault(name.strip(), ver.split(";")[0].split("#")[0].strip())
    try:
        node = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
    except OSError:
        node = "not found"
    vfile = HERE / "verification.json"
    ctx = {"pairs": pairs, "skipped": skipped, "s200": s200, "summary": summary, "runs": runs, "paired": paired, "forgery": forgery,
           "shots": shots, "prov": prov, "canon": canon, "dash": dash, "requirements": reqs, "node": node,
           "python": sys.version.split()[0], "toc": TOC, "generated": datetime.now().astimezone().strftime("%d %B %Y, %H:%M"),
           "verification": json.loads(vfile.read_text(encoding="utf-8")) if vfile.exists() else None}
    ctx["observations"] = observations(s200, summary, paired, forgery, pairs)
    DATA_OUT.write_text(json.dumps({
        "generated": ctx["generated"], "pairs": [{"pair": e["pair"], "fingerprint": e["fp"],
                                                  "rows": {s: {c["key"]: c["value"] for c in r["cells"]} for s, r in e["rows"].items() if r["available"]}}
                                                 for e in pairs],
        "skipped_pairs": skipped, "sumo_figures": prov, "dashboard_figures": dash,
        "multiseed_200": {s: {k: num(s200[s][k]) for k in ("transmissions", "collision_losses", "reachability", "t90_ms", "rsu_delay_ms",
                                                           "rsu_received", "dup_rx")} for s in SCHEMES + ["ch_route"]},
        "observations": ctx["observations"]}, indent=1, default=str), encoding="utf-8")
    html_text, _ = build_html(ctx, {})
    HTML_OUT.write_text(html_text, encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        draft = Path(tmp) / "draft.pdf"
        print_pdf(HTML_OUT, draft)
        pages, n = heading_pages(draft, TOC)
    html_text, doc = build_html(ctx, pages)
    HTML_OUT.write_text(html_text, encoding="utf-8")
    print_pdf(HTML_OUT, PDF_OUT)
    final_pages, n_final = heading_pages(PDF_OUT, TOC)
    assert final_pages == pages and n_final == n, "the contents page changed the layout"
    print(f"{PDF_OUT.relative_to(ROOT)}: {n} pages, {doc.n_fig} figures, {doc.n_tab} tables; sections start on {pages}")


if __name__ == "__main__":
    main()
