"""Explanatory diagram (not a screenshot): the 13 implementation stages of one simulation run, grouped into five phases
and read left to right, each with the function or module that implements it. Drawn at the size it is printed, so the
fonts in the PDF are the sizes given here.

    python final_panel_review/scripts/make_workflow_diagram.py

Writes figures/workflow_pipeline.pdf|png (report, 6.7 in wide) and figures/sl_workflow.pdf|png (slides, 6.15 in wide,
larger fonts).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

FIG = Path(__file__).resolve().parents[1] / "figures"
plt.rcParams.update({"font.family": "DejaVu Sans"})
NL = "\n"
PHASES = [  # name, colour, stages (title, implementing code)
    ("Scenario", "#2f6db5", [("SUMO" + NL + "traffic", "scenario.run_sumo"), ("Incident", "scenario.build"),
                             ("Alert" + NL + "creation", "create_alert")]),
    ("Trust, clusters", "#8a3fb0", [("Beta" + NL + "trust", "beta_trust"), ("DBSCAN" + NL + "clusters", "elect_roles"),
                                    ("CH election," + NL + "tiers", "elect_roles")]),
    ("Corroboration", "#c9761a", [("Committee" + NL + "vote", "corroboration"), ("BLS" + NL + "certificate", "corroboration")]),
    ("Dissemination", "#2e8b57", [("Forwarding" + NL + "control", "protocols.Proposed"),
                                  ("CH-to-CH" + NL + "route", "protocols.CHRoute"), ("V2I" + NL + "delivery", "channel.py")]),
    ("RSU and results", "#c0392b", [("RSU check," + NL + "register", "rsu.py"), ("Results," + NL + "dashboard", "web_results.py")]),
]
REPORT = dict(W=6.7, H=2.75, COL_W=1.2, GAP=0.16, X0=0.03, BOX_W=1.1, BOX_H=0.56, PITCH=0.68, TOP=2.24, HEAD_Y=2.42,
              HEAD_H=0.27, F_PHASE=7.5, F_NUM=7.4, F_TITLE=7.2, F_CODE=6.3, NUM_X=0.14, TITLE_X=0.3, ROW1=0.2, ROW2=0.455,
              ARROW=9)
SLIDE = dict(W=6.15, H=2.7, COL_W=1.14, GAP=0.1, X0=0.015, BOX_W=1.1, BOX_H=0.6, PITCH=0.71, TOP=2.18, HEAD_Y=2.35,
             HEAD_H=0.3, F_PHASE=8.6, F_NUM=8.0, F_TITLE=7.9, F_CODE=6.7, NUM_X=0.15, TITLE_X=0.3, ROW1=0.21, ROW2=0.49,
             ARROW=10)


def draw(stem, g):
    fig = plt.figure(figsize=(g["W"], g["H"]))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, g["W"])
    ax.set_ylim(0, g["H"])
    ax.axis("off")
    arrow = dict(arrowstyle="-|>", mutation_scale=g["ARROW"], lw=1.0, color="#3a4552", shrinkA=0, shrinkB=0)
    k, prev = 0, None
    for c, (phase, col, stages) in enumerate(PHASES):
        x0 = g["X0"] + c * (g["COL_W"] + g["GAP"])
        ax.add_patch(FancyBboxPatch((x0, 0.06), g["COL_W"], g["H"] - 0.12, boxstyle="round,pad=0,rounding_size=0.06",
                                    fc=col, ec=col, alpha=0.07, lw=0))
        ax.add_patch(FancyBboxPatch((x0, g["HEAD_Y"]), g["COL_W"], g["HEAD_H"], boxstyle="round,pad=0,rounding_size=0.05",
                                    fc=col, ec="none"))
        ax.text(x0 + g["COL_W"] / 2, g["HEAD_Y"] + g["HEAD_H"] / 2, phase, ha="center", va="center",
                fontsize=g["F_PHASE"], fontweight="bold", color="white")
        bx = x0 + (g["COL_W"] - g["BOX_W"]) / 2
        for i, (title, code) in enumerate(stages):
            k += 1
            y = g["TOP"] - i * g["PITCH"]                  # top edge of the box
            ax.add_patch(FancyBboxPatch((bx, y - g["BOX_H"]), g["BOX_W"], g["BOX_H"],
                                        boxstyle="round,pad=0,rounding_size=0.05", fc="white", ec=col, lw=1.1))
            ax.text(bx + g["NUM_X"], y - g["ROW1"], str(k), ha="center", va="center", fontsize=g["F_NUM"],
                    fontweight="bold", color="white", bbox=dict(boxstyle="circle,pad=0.22", fc=col, ec="none"))
            ax.text(bx + g["TITLE_X"], y - g["ROW1"], title, ha="left", va="center", fontsize=g["F_TITLE"],
                    linespacing=1.1, fontweight="bold", color="#1d2733")
            ax.text(bx + g["BOX_W"] / 2, y - g["ROW2"], code, ha="center", va="center", fontsize=g["F_CODE"],
                    color="#45505c", family="DejaVu Sans Mono")
            if prev is None:
                pass
            elif prev[2] == c:                             # next stage in the same phase: straight down
                ax.add_patch(FancyArrowPatch((bx + g["BOX_W"] / 2, prev[1] - g["BOX_H"]), (bx + g["BOX_W"] / 2, y),
                                             **arrow))
            else:                                          # first stage of the next phase: right through the gap, up
                sx, sy = prev[0] + g["BOX_W"], prev[1] - g["BOX_H"] / 2
                mx = sx + (bx - sx) / 2
                ax.plot([sx, mx, mx], [sy, sy, y - g["BOX_H"] / 2], color="#3a4552", lw=1.0, solid_joinstyle="miter")
                ax.add_patch(FancyArrowPatch((mx, y - g["BOX_H"] / 2), (bx, y - g["BOX_H"] / 2), **arrow))
            prev = (bx, y, c)
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{stem}.{ext}", dpi=300)
    plt.close(fig)
    print("wrote", FIG / f"{stem}.pdf")


draw("workflow_pipeline", REPORT)
draw("sl_workflow", SLIDE)
