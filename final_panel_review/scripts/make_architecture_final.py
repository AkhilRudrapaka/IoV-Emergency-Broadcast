"""Final architecture figures for the panel presentation.

  architecture/architecture_implemented.{png,pdf,svg}   five stages, implemented functionality only
  architecture/future_cloud_integration.{png,pdf,svg}   proposed cloud extensions, clearly marked as not implemented

Every box of the first figure is checked against the code (module in brackets):
  1 SUMO traffic, random honest accident 60-120 s, alert with event ID/position/time/hop limit   (scenario.build, create_alert)
  2 watchdog observation every 1 s -> Beta trust (s+1)/(s+f+2), trusted >= 0.7 -> DBSCAN 40 m/3 -> trusted CHs
                                                                     (scenario.build, clustering.beta_trust, elect_roles)
  3 committee = 5 nearest trusted neighbours, quorum 3, BLS12-381 96-byte certificate, no quorum -> not released
                                                                                                    (corroboration.py)
  4 V2V over simulated 802.11p: tier/distance wait, duplicate never forwarded twice, coverage check, CH-to-CH route
                                                                     (protocols.py, channel.py, infrastructure.shortest_route)
  5 V2I: RSUs only receive; validation incl. certificate; one registration per event; local SQLite store and dispatch
    outbox; dashboard                                     (rsu.py, infrastructure.persist, web_results.py, demo.py)
No cloud service is connected (infrastructure.sync_cloud only exports locally unless IOV_CLOUD_URL is set), so the cloud
appears only in the future-scope figure.

    python final_panel_review/scripts/make_architecture_final.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import to_rgb  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "architecture"
plt.rcParams.update({"font.family": ["Arial", "DejaVu Sans"], "svg.fonttype": "none", "pdf.fonttype": 42})
INK, MUTE, ARROW = "#1F2328", "#4B5563", "#6B7280"


def tint(hex_color, keep):
    r, g, b = to_rgb(hex_color)
    return (1 - keep + keep * r, 1 - keep + keep * g, 1 - keep + keep * b)


def rbox(ax, x, y, w, h, fc, ec, lw=1.2, r=0.08, ls="-", z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw,
                                linestyle=ls, zorder=z))


def arrow(ax, p, q, color=ARROW, lw=2.0, ls="-", ms=16):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=ms, lw=lw, color=color, linestyle=ls,
                                 shrinkA=0, shrinkB=0, zorder=5))


def canvas(w, h):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    return fig, ax


def save(fig, name):
    for ext, kw in (("png", {"dpi": 300}), ("pdf", {}), ("svg", {})):
        fig.savefig(OUT / f"{name}.{ext}", facecolor="white", **kw)
    plt.close(fig)


# ===================================================================== 1. implemented architecture
STAGES = [
    ("#1E40AF", "Traffic & Emergency\nGeneration", [
        ("SUMO traffic", "5×5 city grid,\n50 to 500 vehicles"),
        ("Random accident", "one honest vehicle\ncrashes (60–120 s)"),
        ("Emergency alert", "ID, position, time,\nhop limit")]),
    ("#6B21A8", "Trust Evaluation &\nClustering", [
        ("Behaviour monitor", "checks neighbours\nforward, every 1 s"),
        ("Beta trust score", "(good+1)/(good+bad+2)\ntrusted at ≥ 0.7"),
        ("DBSCAN clusters", "within 40 m,\nat least 3 vehicles"),
        ("Cluster heads", "trusted vehicles\ncovering each group")]),
    ("#B45309", "Emergency Alert\nVerification", [
        ("Trusted voters", "the 5 nearest with\ntrust ≥ 0.7"),
        ("3-of-5 quorum", "no quorum: the alert\nis not released"),
        ("BLS aggregation", "BLS12-381: one\n96-byte certificate")]),
    ("#166534", "Controlled Message\nDissemination", [
        ("Tier & distance", "trusted first, then\nfarther vehicles"),
        ("Duplicate filter", "no vehicle forwards\nthe same alert twice"),
        ("Coverage check", "forward only if a\nneighbour lacks it"),
        ("CH-to-CH route", "trusted heads relay\ntoward an RSU")]),
    ("#991B1B", "RSU Processing &\nMonitoring", [
        ("Validation", "location, age, hops,\nBLS certificate"),
        ("Duplicate events", "each event is\nregistered once"),
        ("Event registry", "local event store,\ndispatch outbox"),
        ("Live dashboard", "run view, metrics,\ncomparison")]),
]
PATH = ["Crash: alert created", "Trust scores and\ncluster heads ready", "3 of 5 confirm:\ncertificate made",
        "V2V broadcast:\nvehicle → vehicle", "V2I delivery: vehicle\n→ RSU, registered once"]

W, H = 13.33, 5.75
fig, ax = canvas(W, H)
M, GAP = 0.1, 0.22
CW = (W - 2 * M - 4 * GAP) / 5
HEAD_T, HEAD_H = H - 0.08, 0.95
PANEL_T, PANEL_B = HEAD_T - HEAD_H, 1.0
for i, (col, title, cards) in enumerate(STAGES):
    x = M + i * (CW + GAP)
    # header with stage number and title
    rbox(ax, x, PANEL_B, CW, HEAD_T - PANEL_B, tint(col, 0.07), col, lw=1.4, r=0.1, z=1)
    rbox(ax, x, PANEL_T, CW, HEAD_H, col, col, lw=1.4, r=0.1, z=2)
    ax.text(x + CW / 2, HEAD_T - 0.2, f"STAGE {i + 1}", ha="center", va="center", fontsize=10.5, weight="bold",
            color=tint("#FFFFFF", 1), alpha=0.85, zorder=3)
    ax.text(x + CW / 2, PANEL_T + 0.36, title, ha="center", va="center", fontsize=14, weight="bold", color="white",
            linespacing=1.05, zorder=3)
    # component cards fill the panel height evenly
    pad, cgap = 0.1, 0.08
    ch = (PANEL_T - PANEL_B - 2 * pad - (len(cards) - 1) * cgap) / len(cards)
    for k, (name, desc) in enumerate(cards):
        cy = PANEL_T - pad - k * (ch + cgap)
        rbox(ax, x + 0.1, cy - ch, CW - 0.2, ch, "white", tint(col, 0.45), lw=1.1, r=0.07, z=3)
        mid = cy - ch / 2
        ax.text(x + CW / 2, mid + 0.2, name, ha="center", va="center", fontsize=15, weight="bold", color=col, zorder=4)
        ax.text(x + CW / 2, mid - 0.12, desc, ha="center", va="center", fontsize=12.5, color=INK, linespacing=1.1,
                zorder=4)
    if i < 4:
        y = PANEL_T + HEAD_H / 2
        arrow(ax, (x + CW + 0.02, y), (x + CW + GAP - 0.02, y), ms=15)
# the path of one alert, under the stages
for i, text in enumerate(PATH):
    col = STAGES[i][0]
    x = M + i * (CW + GAP)
    rbox(ax, x, 0.12, CW, 0.74, tint(col, 0.13), col, lw=1.3, r=0.12, z=2)
    ax.text(x + CW / 2, 0.49, text, ha="center", va="center", fontsize=12.5, color=INK, linespacing=1.1, zorder=3,
            weight="bold" if i >= 3 else "normal")
    if i < 4:
        arrow(ax, (x + CW + 0.02, 0.49), (x + CW + GAP - 0.02, 0.49), ms=14)
save(fig, "architecture_implemented")

# ===================================================================== 2. future scope: cloud integration
FUT = "#5B21B6"
W2, H2 = 13.33, 4.9
fig, ax = canvas(W2, H2)
ax.text(0.15, H2 - 0.38, "Future Enhancement: Cloud Integration", ha="left", va="center", fontsize=21,
        weight="bold", color=INK)
rbox(ax, 7.55, H2 - 0.66, 5.63, 0.56, "#FEF3C7", "#B45309", lw=1.6, r=0.1)
ax.text(7.55 + 5.63 / 2, H2 - 0.38, "Proposed Future Enhancements — Not Yet Implemented", ha="center",
        va="center", fontsize=13.5, weight="bold", color="#92400E", zorder=3)
# implemented today (solid)
RSU = "#991B1B"
x0, y0, w0, h0 = 0.15, 0.75, 3.35, 3.35
rbox(ax, x0, y0, w0, h0, tint(RSU, 0.07), RSU, lw=1.6, r=0.12, z=1)
ax.text(x0 + w0 / 2, y0 + h0 - 0.28, "IMPLEMENTED TODAY", ha="center", va="center", fontsize=11, weight="bold",
        color=RSU)
ax.text(x0 + w0 / 2, y0 + h0 - 0.62, "Stage 5: RSU side", ha="center", va="center", fontsize=15, weight="bold",
        color=INK)
for k, (name, desc) in enumerate([("Event registry", "local event store and\ndispatch outbox"),
                                  ("Two RSUs", "share one local registry\n(each event once)"),
                                  ("Live dashboard", "local web view")]):
    cy = y0 + h0 - 0.95 - k * 0.8
    rbox(ax, x0 + 0.15, cy - 0.74, w0 - 0.3, 0.74, "white", tint(RSU, 0.45), lw=1.1, r=0.07, z=2)
    ax.text(x0 + w0 / 2, cy - 0.2, name, ha="center", va="center", fontsize=13.5, weight="bold", color=RSU, zorder=3)
    ax.text(x0 + w0 / 2, cy - 0.5, desc, ha="center", va="center", fontsize=11.5, color=INK, linespacing=1.05,
            zorder=3)
# proposed cloud (dashed)
cx0, cy0, cw, chh = 4.35, 0.75, W2 - 4.35 - 0.15, 3.35
rbox(ax, cx0, cy0, cw, chh, tint(FUT, 0.05), FUT, lw=1.8, r=0.14, ls=(0, (6, 4)), z=1)
ax.text(cx0 + cw / 2, cy0 + chh - 0.3, "Cloud platform (proposed)", ha="center", va="center", fontsize=15,
        weight="bold", color=FUT)
arrow(ax, (x0 + w0 + 0.05, y0 + h0 / 2), (cx0 - 0.05, y0 + h0 / 2), color=FUT, lw=2.2, ls=(0, (5, 3)), ms=18)
ax.text((x0 + w0 + cx0) / 2, y0 + h0 / 2 + 0.3, "proposed\nupload", ha="center", va="center", fontsize=11.5,
        color=FUT, style="italic", linespacing=1.0)
items = [("Cloud trust management", "share trust scores\nacross RSUs and regions"),
         ("Central analytics", "city-wide traffic and\nemergency statistics"),
         ("Historical event storage", "long-term record of\nvalidated alerts"),
         ("Multi-RSU coordination", "hand-over and de-duplication\nacross many RSUs"),
         ("Traffic intelligence", "large-scale planning from\nmany incidents and regions")]
iw, ih = (cw - 0.3 - 2 * 0.2) / 3, 1.05
for k, (name, desc) in enumerate(items):
    row, colk = divmod(k, 3)
    n_in_row = 3 if row == 0 else 2
    offset = 0 if row == 0 else (iw + 0.2) / 2
    x = cx0 + 0.15 + offset + colk * (iw + 0.2)
    y = cy0 + chh - 0.6 - (row + 1) * ih - row * 0.18
    rbox(ax, x, y, iw, ih, "white", FUT, lw=1.3, r=0.08, ls=(0, (4, 3)), z=2)
    ax.text(x + iw / 2, y + ih - 0.27, name, ha="center", va="center", fontsize=13.5, weight="bold", color=FUT,
            zorder=3)
    ax.text(x + iw / 2, y + 0.36, desc, ha="center", va="center", fontsize=11.5, color=INK, linespacing=1.1, zorder=3)
ax.text(0.15, 0.36, "Solid = built and tested in this project.   Dashed = proposed, not implemented.   "
        "Today no cloud service is connected; events stay on the local machine.", ha="left", va="center",
        fontsize=11.5, color=MUTE)
save(fig, "future_cloud_integration")
print("written: architecture_implemented.{png,pdf,svg}, future_cloud_integration.{png,pdf,svg}")
