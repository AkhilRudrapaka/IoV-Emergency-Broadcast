"""
Every figure is drawn from results/processed/*.csv or results/raw/<run>.json.gz --
never from numbers typed here. Colours follow the entity (a scheme keeps its
colour in every figure); decision states use shape + colour, never colour alone.
"""
import csv
import math
import os
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, Polygon
import numpy as np
import sumolib

import config

FIG_DIR = os.path.join(config.RESULTS_DIR, "figures")
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
COLOR = {"ch_route": "#7759da", "flooding": "#2a78d6", "slotted1p": "#eb6834", "proposed": "#1baf7a",
         "no_reputation": "#eda100", "no_security": "#4a3aa7",
         # the forged-alert test runs the same three configurations
         "voting_reputation": "#1baf7a", "voting_only": "#eda100", "no_voting": "#4a3aa7"}
CLUSTER_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
FORWARD, SOURCE = "#eb6834", INK

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "Arial", "DejaVu Sans"],
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    "legend.frameon": False, "lines.linewidth": 2,
    "axes.unicode_minus": False,
})


def _save(fig, name):
    os.makedirs(FIG_DIR, exist_ok=True)
    path = os.path.join(FIG_DIR, name)
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


def _read(path):
    with open(path) as f:
        return [{k: _num(v) for k, v in r.items()} for r in csv.DictReader(f)]


def _num(v):
    try:
        return float(v)
    except ValueError:
        return v


# ------------------------------------------------------------------ comparison over density
PANELS = [("transmissions", "Frames on air per alert (proposal + votes + alerts)", False),
          ("collision_losses", "Receptions lost to collisions (log)", True),
          ("reachability", "Reachability (share of reachable vehicles)", False),
          ("t90_ms", "Time to reach 90 % of vehicles (ms)", False),
          ("cbr_100ms", "Channel busy ratio, first 100 ms", False),
          ("suppression_ratio", "Suppression ratio", False)]


RSU_PANELS = [("rsu_relay_received", "RSU reception success (relayed alerts)", False),
              ("rsu_relay_delay_ms", "Incident to RSU delay, relayed alerts (ms)", False),
              ("rsu_relay_tx_before", "Frames on air until an RSU has the alert", False),
              ("rsu_dup_copies", "Duplicate copies decoded by RSUs (all alerts)", False)]


def comparison(summary, protocols, name, title, panels=PANELS, note=""):
    ncols = 3 if len(panels) > 4 else len(panels)
    nrows = math.ceil(len(panels) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4.1 * nrows), squeeze=False)
    for ax, (key, label, log) in zip(axes.flat, panels):
        for p in protocols:
            rows = [r for r in summary if r["protocol"] == p]
            x = [r["density"] for r in rows]
            y = [r[key] for r in rows]
            ax.errorbar(x, y, yerr=[r[f"{key}_ci95"] for r in rows], color=COLOR[p], marker="o",
                        markersize=6, capsize=3, label=config.LABELS[p])
        ax.set_title(label, loc="left")
        ax.set_xlabel("Vehicles in the network")
        ax.set_xticks(sorted({r["density"] for r in summary}))
        if log:
            ax.set_yscale("log")
        if key in ("reachability", "suppression_ratio", "rsu_relay_received"):
            ax.set_ylim(None if key == "reachability" else -0.02, 1.02)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=len(protocols), bbox_to_anchor=(0.5, 1.0 + 0.04 / nrows))
    fig.suptitle(title, y=1.0 + 0.16 / nrows, fontsize=13, fontweight="bold")
    fig.text(0.5, -0.02, f"Mean of {summary[0]['runs']:.0f} independent SUMO scenarios per density (one incident each); "
             f"error bars = 95 % confidence interval (Student t). {note}", ha="center", color=INK2)
    fig.tight_layout()
    return _save(fig, name)


# ------------------------------------------------------------------ one-run maps
_NET = None


def _roads(ax):
    global _NET
    _NET = _NET or sumolib.net.readNet(config.NET_FILE)
    scenery = os.path.splitext(config.NET_FILE)[0].replace(".net", "") + ".add.xml"
    if os.path.isfile(scenery):
        for poly in ET.parse(scenery).getroot().findall("poly"):
            points = [tuple(map(float, p.split(","))) for p in poly.get("shape").split()]
            color = tuple(float(c) / 255 for c in poly.get("color").split(","))
            ax.add_patch(Polygon(points, facecolor=color, edgecolor="none", zorder=-1))
    for e in _NET.getEdges():
        xs, ys = zip(*e.getShape())
        ax.plot(xs, ys, color="#cbd5e1", linewidth=9, solid_capstyle="round", zorder=0)
        ax.plot(xs, ys, color="#e7edf3", linewidth=6, solid_capstyle="round", zorder=0)


def _decision_map(ax, raw, proto, title, annotate=0):
    sc = raw["scenario"]
    pos = {v["id"]: (v["x"], v["y"]) for v in sc["vehicles"]}
    got = {v["id"]: v for v in raw["protocols"][proto]["vehicles"]}
    _roads(ax)
    unreached = [pos[v] for v in pos if v not in got]
    groups = {
        "REJECT": dict(marker="o", s=16, facecolors="none", edgecolors=MUTED, linewidths=0.9, label="Received, rejected"),
        "SUPPRESS": dict(marker="o", s=16, color=MUTED, label="Accepted, suppressed"),
        "DROP": dict(marker="x", s=30, color=INK, linewidths=1.2, label="Misbehaving (never relays)"),
        "FORWARD": dict(marker="^", s=60, color=FORWARD, edgecolors=SURFACE, linewidths=0.8, label="Rebroadcast"),
    }
    if unreached:
        ax.scatter(*zip(*unreached), marker="o", s=18, facecolors="none", edgecolors=INK2,
                   linewidths=0.9, label="Not reached", zorder=2)
    for dec, style in groups.items():
        pts = [pos[i] for i, v in got.items() if v["decision"] == dec]
        if pts:
            ax.scatter(*zip(*pts), zorder=3, **style)
    for i, v in got.items():                         # relay backbone: who each forwarder got it from
        if v["decision"] == "FORWARD" and v["from"]:
            (x0, y0), (x1, y1) = pos[v["from"]], pos[i]
            ax.annotate("", (x1, y1), (x0, y0), arrowprops=dict(arrowstyle="-|>", color=FORWARD,
                        lw=0.8, alpha=0.6, shrinkA=3, shrinkB=3), zorder=2)
    sx, sy = sc["incident_xy"]
    ax.add_patch(Circle((sx, sy), config.COMM_RANGE_M, fill=False, ls="--", lw=1, color=INK2, zorder=1))
    ax.scatter([sx], [sy], marker="*", s=320, color=SOURCE, edgecolors=SURFACE, zorder=5,
               label=f"Incident ({sc['source_id']})")
    first = {}
    for rx in raw["protocols"][proto]["rsu_receptions"]:
        first.setdefault(rx["rsu"], rx["delay_ms"])
    for i, u in enumerate(sc["rsus"]):
        ok = u["id"] in first
        ax.scatter([u["x"]], [u["y"]], marker="s", s=150, zorder=5, linewidths=1.6, edgecolors=INK,
                   facecolors=INK if ok else SURFACE, label="RSU (filled = alert received)" if i == 0 else None)
        ax.annotate(f"{u['id']}: {first[u['id']]:.1f} ms" if ok else f"{u['id']}: no alert", (u["x"], u["y"]),
                    (9, -14), textcoords="offset points", fontsize=8, fontweight="bold", color=INK, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.2", fc=SURFACE, ec=GRID, lw=0.6))
    if annotate:
        fw = sorted((v for v in got.values() if v["decision"] == "FORWARD" and v["from"]), key=lambda v: v["tx_ms"])
        sup = sorted((v for v in got.values() if v["decision"] == "SUPPRESS"), key=lambda v: v["decided_ms"])
        placed = []                                   # a label box is ~340 m wide x ~90 m tall in map units
        for group, quota in ((fw, annotate - 2), (sup, 2)):
            for v in group:
                x, y = pos[v["id"]]
                if quota == 0:
                    break
                left = x > 480                        # labels near the right edge extend leftwards
                x0 = x - 340 if left else x
                if any(x0 < a + 340 and a < x0 + 340 and abs(y - b) < 90 for a, b in placed):
                    continue                          # would overlap an existing label
                placed.append((x0, y))
                quota -= 1
                extra = f", {v['uncovered']} uncovered" if v.get("uncovered") is not None else ""
                ax.annotate(f"{v['id']}: {v['decision']}\n{v['dist_m']:.0f} m from sender, "
                            f"{v['neighbors']} nbrs{extra}", (x, y), (-8 if left else 8, 8),
                            textcoords="offset points", ha="right" if left else "left",
                            fontsize=7.5, color=INK, zorder=6,
                            bbox=dict(boxstyle="round,pad=0.25", fc=SURFACE, ec=GRID, lw=0.6))
    tx = raw["protocols"][proto]["transmissions"]
    voters = [pos[t["sender"]] for t in tx if t["kind"] == "VOTE"]
    if voters:
        ax.scatter(*zip(*voters), marker="D", s=90, facecolors="none", edgecolors="#4a3aa7", linewidths=1.4,
                   zorder=4, label="Committee member that voted")
    ax.set_title(f"{title}\n{len(tx)} frames on air, {sum(t['lost'] for t in tx)} receptions lost to collisions",
                 loc="left", fontsize=10)
    ax.set_aspect("equal")
    ax.set_xlim(-40, 840)
    ax.set_ylim(-40, 840)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)


def incident_maps(raw):
    fig, axes = plt.subplots(1, 3, figsize=(18, 6.6))
    for ax, p in zip(axes, config.BASELINES):
        _decision_map(ax, raw, p, config.LABELS[p])
    entries = {}
    for ax in axes:                                   # "Not reached" may appear in only one panel
        entries.update(zip(ax.get_legend_handles_labels()[1], ax.get_legend_handles_labels()[0]))
    fig.legend(entries.values(), entries.keys(), loc="lower center", ncol=len(entries), bbox_to_anchor=(0.5, -0.04))
    sc = raw["scenario"]
    fig.suptitle(f"Run {sc['run_id']}: one incident at t = {sc['incident_time_s']:.0f} s, "
                 f"{len(sc['vehicles'])} vehicles, same snapshot for every scheme "
                 f"(dashed circle = {config.COMM_RANGE_M:.0f} m radio range)", fontweight="bold", y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    return _save(fig, f"incident_map_{sc['run_id']}.png")


def decision_map(raw):
    fig, ax = plt.subplots(figsize=(9.5, 9.5))
    _decision_map(ax, raw, "proposed", "Proposed scheme: who rebroadcast, who suppressed, and why", annotate=6)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
    return _save(fig, f"decisions_{raw['scenario']['run_id']}.png")


def timeline(raw):
    sc = raw["scenario"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 4.8))
    reach = raw["protocols"]["flooding"]["metrics"]["reachable"]
    for p in config.BASELINES:
        rx = sorted(v["rx_ms"] for v in raw["protocols"][p]["vehicles"] if v["rx_ms"] is not None)
        a1.step(rx, np.arange(1, len(rx) + 1) / reach, where="post", color=COLOR[p], label=config.LABELS[p])
        tx = sorted(t["start_ms"] for t in raw["protocols"][p]["transmissions"])
        a2.step(tx, np.arange(1, len(tx) + 1), where="post", color=COLOR[p], label=config.LABELS[p])
        a2.annotate(f"{len(tx)} frames", (tx[-1], len(tx)), (5, 0), textcoords="offset points", fontsize=8.5,
                    color=INK2, va="center")
    a1.axhline(0.9, color=AXIS, lw=1, ls=":")
    a1.legend(loc="lower right")
    a1.set_title("Share of reachable vehicles that have accepted the alert", loc="left")
    a1.set_ylabel("Share reached")
    a2.set_title("Cumulative frames on air (the broadcast storm)", loc="left")
    a2.set_ylabel("Frames")
    quorum = raw["protocols"]["proposed"]["metrics"]["quorum_ms"]
    for a in (a1, a2):
        a.set_xlabel("Time since the alert was created (ms)")
        a.axvline(quorum, color=MUTED, lw=1, ls="--")
    a1.annotate("certified alert released\n(3 of 5 votes in)", (quorum, 0.45), (-6, 0), textcoords="offset points",
                ha="right", fontsize=8.5, color=INK2)
    a2.legend(loc="center right")
    fig.suptitle(f"Message propagation timeline, run {sc['run_id']}", fontweight="bold")
    fig.tight_layout()
    return _save(fig, f"timeline_{sc['run_id']}.png")


# ------------------------------------------------------------------ explanatory diagrams
def _box(ax, x, y, w, h, text, fc="#eef5fd", ec="#86b6ef"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04",
                                fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9, color=INK, wrap=True)


def _arrow(ax, a, b):
    ax.annotate("", b, a, arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.2))


def architecture():
    """The pipeline, top to bottom, with the code that owns each stage."""
    fig, ax = plt.subplots(figsize=(10.5, 16.0))
    ax.set_xlim(0, 10.5)
    ax.set_ylim(-3.6, 12.4)
    ax.axis("off")
    green, orange, plain = ("#e8f7f1", "#1baf7a"), ("#fdf0ea", "#eb6834"), ("#eef5fd", "#86b6ef")
    chain = [("SUMO traffic\nseeded routes, 5x5 signalised grid", "scenario.py: write_routes, run_sumo", plain),
             ("ONE accident\nrandom time and vehicle", "scenario.py: build", green),
             ("Emergency alert\nevent ID, position, time, hop limit", "scenario.py: create_alert", plain),
             ("Corroboration\ncommittee vote, BLS aggregate certificate", "corroboration.py; protocols.py: Protocol", green),
             None,                                    # the decision engine, drawn below
             ("V2V dissemination\n802.11p CSMA/CA: contention, collisions", "channel.py: simulate", orange),
             ("RSU reception\nreceive-only endpoint", "protocols.py: Protocol.on_alert", plain),
             ("Plausibility validation, event registration\nchecked, registered once", "rsu.py: validate, register", green),
             ("Metrics and backhaul\ntrust updates, storage, dispatch outbox", "metrics.py; infrastructure.py", plain)]
    y, mids = 11.6, []
    for item in chain:
        if item is None:
            ax.add_patch(FancyBboxPatch((0.5, y - 1.95), 9.5, 2.1, boxstyle="round,pad=0,rounding_size=0.08",
                                        fc="#f5f4f0", ec=AXIS, lw=1))
            ax.text(5.25, y - 0.12, "Vehicle decision engine: verify the certificate, then decide once: forward or suppress",
                    ha="center", fontweight="bold", fontsize=9.5)
            for i, (txt, own) in enumerate([("Neighbour discovery\nbeacon tables (300 m)", "experiment.py: network"),
                                            ("Reputation\nBeta model", "clustering.py: beta_trust"),
                                            ("Clustering\nDBSCAN + representatives", "clustering.py: elect_roles"),
                                            ("Forwarding\ncoverage / CH shortest path", "protocols.py: Proposed, CHRoute")]):
                _box(ax, 0.75 + i * 2.32, y - 1.35, 2.1, 0.9, txt, *green)
                ax.text(0.75 + i * 2.32 + 1.05, y - 1.62, own, ha="center", fontsize=7.5, color=INK2, family="monospace")
            mids.append((y + 0.15, y - 1.95))
            y -= 2.75
            continue
        txt, own, (fc, ec) = item
        _box(ax, 3.0, y - 0.75, 4.5, 0.9, txt, fc, ec)
        ax.text(7.7, y - 0.3, own, va="center", fontsize=8, color=INK2, family="monospace")
        mids.append((y + 0.15, y - 0.75))
        y -= 1.4
    for (_, bottom), (top, _) in zip(mids, mids[1:]):
        _arrow(ax, (5.25, bottom - 0.04), (5.25, top + 0.04))
    for x, txt, own in ((1.2, "Dashboard, figures, explainer", "figures.py, report.py"),
                        (5.6, "SUMO-GUI demonstration", "demo.py")):
        _box(ax, x, y - 0.75, 3.7, 0.9, txt, *plain)
        ax.text(x + 1.85, y - 1.0, own, ha="center", fontsize=8, color=INK2, family="monospace")
        _arrow(ax, (5.25, mids[-1][1] - 0.04), (x + 1.85, y + 0.19))
    ax.set_title(config.TITLE + "\nSystem architecture (every stage with its owner in the code)", loc="left", fontsize=11)
    return _save(fig, "architecture.png")


def flow():
    rows = [["1. Seed: routes,\nSUMO mobility", "2. Beacons:\nneighbours,\nreputation", "3. DBSCAN clusters,\nrepresentatives\nelected",
             "4. ONE incident:\nalert created,\nsigned (BLS)", "5. Committee\nvotes; BLS\ncertificate"],
            ["6. Certified alert\nbroadcast", "7. Channel:\nwho decodes it", "8. Receiver verifies,\nwaits, then\ndecides: forward\nor suppress",
             "9. RSU validates,\nregisters the\nevent once", "10. Trust, storage,\ndispatch outbox;\ncompare schemes"]]
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.set_xlim(0, 10.4)
    ax.set_ylim(0, 4.6)
    ax.axis("off")
    for r, steps in enumerate(rows):
        y = 2.6 - r * 2.2
        for i, s in enumerate(steps):
            hi = "ONE" in s or "decides" in s or "RSU" in s or "votes" in s
            _box(ax, 0.1 + i * 2.08, y, 1.7, 1.3, s, "#e8f7f1" if hi else "#eef5fd", "#1baf7a" if hi else "#86b6ef")
            if i:
                _arrow(ax, (i * 2.08 - 0.26, y + 0.65), (0.1 + i * 2.08 - 0.02, y + 0.65))
    ax.annotate("", (0.95, 1.73), (9.28, 2.58),
                arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.2, connectionstyle="arc3,rad=-0.08"))
    ax.text(4.6, 0.05, "steps 7-8 repeat until no vehicle has a pending decision (tens of milliseconds)",
            ha="center", fontsize=8.5, color=INK2)
    ax.set_title("Simulation flow (one run)", loc="left")
    return _save(fig, "flow.png")


def topology(raw):
    """The road network, the RSU sites and their radio coverage, with one run's traffic."""
    sc = raw["scenario"]
    fig, ax = plt.subplots(figsize=(8.6, 8.6))
    _roads(ax)
    for n in _NET.getNodes():
        if n.getType() == "traffic_light":
            ax.scatter(*n.getCoord()[:2], marker="P", s=42, color=MUTED, zorder=2,
                       label="Signalised junction" if n.getID() == "B1" else None)
    ax.scatter([v["x"] for v in sc["vehicles"]], [v["y"] for v in sc["vehicles"]], s=10, color=COLOR["flooding"],
               zorder=3, label=f"Vehicles ({len(sc['vehicles'])}, run {sc['run_id']})")
    for i, u in enumerate(sc["rsus"]):
        ax.add_patch(Circle((u["x"], u["y"]), config.COMM_RANGE_M, fc=INK, alpha=0.06, ec="none", zorder=1))
        ax.add_patch(Circle((u["x"], u["y"]), config.COMM_RANGE_M, fill=False, ls="--", lw=1, color=INK2, zorder=1))
        ax.scatter([u["x"]], [u["y"]], marker="s", s=170, color=INK, edgecolors=SURFACE, zorder=5,
                   label=f"RSU and its {config.COMM_RANGE_M:.0f} m range" if i == 0 else None)
        ax.annotate(u["id"], (u["x"], u["y"]), (10, 10), textcoords="offset points", fontweight="bold", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.2", fc=SURFACE, ec=GRID, lw=0.6))
    ax.set_title("Topology: 5x5 signalised grid, 200 m blocks. RSUs sit at 4-arm junctions;\n"
                 "the corners outside both circles can only reach an RSU through vehicle relays", loc="left", fontsize=10)
    ax.set_aspect("equal")
    ax.set_xlim(-130, 930)
    ax.set_ylim(-130, 930)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.09), ncol=3)
    return _save(fig, "topology.png")


def propagation(raw, schemes=("flooding", "proposed"), step_ms=1.0, max_ms=70.0):
    """Animated replay of the transmission log: the same incident under two schemes."""
    from matplotlib.animation import FuncAnimation, PillowWriter
    sc = raw["scenario"]
    xy = {v["id"]: (v["x"], v["y"]) for v in sc["vehicles"]}
    data = {p: (raw["protocols"][p]["transmissions"],
                {v["id"]: v["rx_ms"] for v in raw["protocols"][p]["vehicles"] if v["rx_ms"] is not None}, {}) for p in schemes}
    for p in schemes:
        for rx in raw["protocols"][p]["rsu_receptions"]:
            data[p][2].setdefault(rx["rsu"], rx["delay_ms"])
    end = min(max_ms, max(tx[-1]["end_ms"] for tx, _, _ in data.values()) + 2 * step_ms)
    fig, axes = plt.subplots(1, len(schemes), figsize=(6.4 * len(schemes), 6.9))

    def draw(k):
        t = k * step_ms
        for ax, p in zip(axes, schemes):
            txs, rx, rsu_rx = data[p]
            ax.clear()
            _roads(ax)
            sent = {x["sender"] for x in txs if x["start_ms"] <= t and x["kind"] == "ALERT"}
            voted = {x["sender"] for x in txs if x["start_ms"] <= t and x["kind"] == "VOTE"} - sent
            live = [x["sender"] for x in txs if x["start_ms"] <= t < x["end_ms"] + step_ms]
            have = {v for v, ms in rx.items() if ms <= t} - sent
            rest = set(xy) - have - sent
            for group, style in ((rest, dict(marker="o", s=14, facecolors="none", edgecolors=MUTED, linewidths=0.8)),
                                 (have, dict(marker="o", s=16, color=COLOR["flooding"])),
                                 (voted, dict(marker="D", s=70, facecolors="none", edgecolors="#4a3aa7", linewidths=1.4)),
                                 (sent, dict(marker="^", s=52, color=FORWARD, edgecolors=SURFACE, linewidths=0.6))):
                if group:
                    ax.scatter(*zip(*(xy[v] for v in group)), zorder=3, **style)
            for v in live:
                ax.add_patch(Circle(xy[v], config.COMM_RANGE_M, fill=False, lw=0.8, color=FORWARD, alpha=0.5, zorder=2))
            for u in sc["rsus"]:
                ok = rsu_rx.get(u["id"], 1e9) <= t
                ax.scatter([u["x"]], [u["y"]], marker="s", s=150, zorder=5, linewidths=1.6, edgecolors=INK,
                           facecolors=INK if ok else SURFACE)
                ax.annotate(f"{u['id']}: ALERT RECEIVED" if ok else u["id"], (u["x"], u["y"]), (9, -14),
                            textcoords="offset points", fontsize=8, fontweight="bold", zorder=6,
                            bbox=dict(boxstyle="round,pad=0.2", fc=SURFACE, ec=GRID, lw=0.6))
            ax.scatter(*sc["incident_xy"], marker="*", s=300, color=SOURCE, edgecolors=SURFACE, zorder=6)
            ax.set_title(f"{config.LABELS[p]}   t = {t:4.1f} ms\n{sum(x['start_ms'] <= t for x in txs)} frames on air, "
                         f"{len(have | (sent & set(rx)))}/{len(xy)} vehicles have accepted the alert", loc="left", fontsize=10)
            ax.set_aspect("equal")
            ax.set_xlim(-40, 840)
            ax.set_ylim(-40, 840)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.grid(False)

    fig.suptitle(f"Run {sc['run_id']}: star = accident, diamond = committee vote, triangle = sent the certified alert, "
                 "ring = transmitting now, dot = accepted the alert, square = RSU", fontsize=10, color=INK2, y=0.02)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    os.makedirs(FIG_DIR, exist_ok=True)
    path = os.path.join(FIG_DIR, f"propagation_{sc['run_id']}.gif")
    FuncAnimation(fig, draw, frames=int(end / step_ms) + 1).save(path, writer=PillowWriter(fps=4), dpi=70)
    plt.close(fig)
    return path


TITLES = {"transmissions": "Frames on air per alert", "reachability": "Reachability",
          "t90_ms": "Time to 90 % (ms)", "t_last_ms": "Time until the last vehicle (ms)",
          "accepted_share": "Honest vehicles accepting a FORGED alert", "rsu_registered": "Forged event registered by an RSU"}


def sensitivity(rows, param, label, protocols, keys, group="protocol", labels=config.LABELS):
    """rows: list of (value, summary_rows) for one density."""
    fig, axes = plt.subplots(1, len(keys), figsize=(5 * len(keys), 4.3), squeeze=False)
    for ax, key in zip(axes.flat, keys):
        for p in protocols:
            pts = [(v, r) for v, s in rows for r in s if r[group] == p]
            ax.errorbar([v for v, _ in pts], [r[key] for _, r in pts], yerr=[r[f"{key}_ci95"] for _, r in pts],
                        color=COLOR[p], marker="o", markersize=6, capsize=3, label=labels[p])
        ax.set_title(TITLES[key], loc="left")
        ax.set_xlabel(label)
        ax.set_xticks([v for v, _ in rows])
        if key in ("accepted_share", "rsu_registered", "reachability"):
            ax.set_ylim(-0.03 if key != "reachability" else None, 1.03)
    axes.flat[0].legend(loc="best")
    first = rows[0][1][0]
    fig.suptitle(f"Sensitivity to {label} (density {first['density']:.0f}, {first['runs']:.0f} seeds per value)", fontweight="bold")
    fig.tight_layout()
    return _save(fig, f"sensitivity_{param}.png")


def ablation(summary, densities=(200, 500)):
    """The full method against the same method with one component removed."""
    variants = ["proposed"] + config.ABLATIONS
    densities = [d for d in densities if any(r["density"] == d for r in summary)] or sorted({r["density"] for r in summary})[-1:]
    panels = [("transmissions", "Frames on air per alert", False), ("collision_losses", "Receptions lost to collisions (log)", True),
              ("t90_ms", "Time to reach 90 % of vehicles (ms)", False), ("reachability", "Reachability", False)]
    fig, axes = plt.subplots(1, 4, figsize=(19, 5.2), sharey=True)
    shades = ["#86b6ef", "#1c5cab"]                    # one hue, light to dark = fewer to more vehicles
    y = np.arange(len(variants))
    h = 0.8 / len(densities)
    for ax, (key, title, log) in zip(axes, panels):
        for i, d in enumerate(densities):
            rows = [next(r for r in summary if r["density"] == d and r["protocol"] == p) for p in variants]
            vals = [r[key] for r in rows]
            ax.barh(y + (i - (len(densities) - 1) / 2) * h, vals, h * 0.9, xerr=[r[f"{key}_ci95"] for r in rows],
                    color=shades[i % 2], error_kw=dict(ecolor=INK2, lw=1, capsize=2), label=f"{d:.0f} vehicles")
            if key == "transmissions":
                for yy, r in zip(y + (i - (len(densities) - 1) / 2) * h, rows):
                    ax.text(r[key] + r[f"{key}_ci95"], yy, f"  {r[key]:.0f}", va="center", fontsize=8, color=INK2)
        ax.set_title(title, loc="left")
        if log:
            ax.set_xscale("log")
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(y, [config.LABELS[p] for p in variants])
    axes[0].invert_yaxis()
    axes[0].legend(loc="lower right")
    fig.suptitle("Ablation: the full method, and the same method with one component removed", fontweight="bold")
    fig.text(0.5, -0.02, f"Mean of {summary[0]['runs']:.0f} scenarios per density; bars = 95 % confidence interval. "
             "Without voting + BLS the alert is cheaper and faster, but a forged alert is accepted (see the forged-alert chart).",
             ha="center", color=INK2)
    fig.tight_layout()
    return _save(fig, "ablation.png")


def forgery(rows):
    """The forged-alert test across densities: share of honest vehicles that accept a false alert."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.3))
    for ax, (key, title) in zip(axes, [("certificate_formed", "Forger finds 3 colluders in range"),
                                       ("accepted_share", "Honest vehicles accepting the forged alert"),
                                       ("rsu_registered", "Forged event registered by an RSU")]):
        for v in config.FORGERY:
            sel = [r for r in rows if r["variant"] == v]
            if key == "certificate_formed" and v == "no_voting":
                continue                                # no certificate exists without voting
            ax.errorbar([r["density"] for r in sel], [r[key] for r in sel], yerr=[r[f"{key}_ci95"] for r in sel],
                        color=COLOR[v], marker="o", markersize=6, capsize=3, label=config.FORGERY[v])
        ax.set_title(title, loc="left")
        ax.set_xlabel("Vehicles in the network")
        ax.set_xticks(sorted({r["density"] for r in rows}))
        ax.set_ylim(-0.03, 1.03)
    axes[1].legend(loc="center right")
    fig.suptitle("Forged-alert test: a misbehaving vehicle and its colluding neighbours claim an accident that did not happen",
                 fontweight="bold")
    fig.text(0.5, -0.02, f"Share of {rows[0]['runs']:.0f} scenarios per density (10 % of vehicles misbehave); error bars = 95 % CI.",
             ha="center", color=INK2)
    fig.tight_layout()
    return _save(fig, "forgery.png")


def clusters(raw):
    """The DBSCAN clustering used at the incident second, straight from the saved run."""
    sc = raw["scenario"]
    fig, ax = plt.subplots(figsize=(8.6, 8.6))
    _roads(ax)
    for group, style, label in (
            ([v for v in sc["vehicles"] if v["dbscan"] == -1],
             dict(marker="o", s=22, facecolors="none", edgecolors=INK2, linewidths=1), "Isolated vehicle (bridge)"),
            ([v for v in sc["vehicles"] if v["dbscan"] != -1 and v["role"] != "CH"], dict(marker="o", s=22), "Cluster member"),
            ([v for v in sc["vehicles"] if v["role"] == "CH"],
             dict(marker="*", s=230, edgecolors=INK, linewidths=0.9), "Cluster representative (elected)")):
        if group:
            colors = None if "facecolors" in style else [CLUSTER_COLORS[v["dbscan"] % len(CLUSTER_COLORS)] for v in group]
            ax.scatter([v["x"] for v in group], [v["y"] for v in group], c=colors, zorder=4 if "*" in style["marker"] else 3,
                       label=label, **style)
    n = len({v["dbscan"] for v in sc["vehicles"]} - {-1})
    ax.set_title(f"DBSCAN clusters at the incident second (run {sc['run_id']}): {n} clusters, "
                 f"{sum(v['role'] == 'CH' for v in sc['vehicles'])} representatives,\n"
                 f"{sum(v['dbscan'] == -1 for v in sc['vehicles'])} isolated vehicles. Colour = cluster ID "
                 f"(colours repeat; a cluster is one group of nearby vehicles)", loc="left", fontsize=10)
    ax.set_aspect("equal")
    ax.set_xlim(-40, 840)
    ax.set_ylim(-40, 840)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    leg = ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.08), ncol=3)
    for handle in leg.legend_handles[1:]:
        handle.set_color(MUTED)
    return _save(fig, f"clusters_{sc['run_id']}.png")
