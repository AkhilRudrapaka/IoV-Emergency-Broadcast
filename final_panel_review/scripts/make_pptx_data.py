"""Collect every number and image size the PowerPoint deck needs into generated/pptx_data.json.
Reads only experiment outputs (results/urban/processed, results/urban/sensitivity/onoff_*), the generated
macro files and the figure files; writes nothing else.

    python final_panel_review/scripts/make_pptx_data.py
"""
import csv
import json
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "final_panel_review"
PROC, SENS = ROOT / "results" / "urban" / "processed", ROOT / "results" / "urban" / "sensitivity"
D0 = 200
SCHEMES = ["flooding", "flooding_rad", "slotted1p", "slotted1p_rad", "proposed"]
METRICS = {"transmissions": 1.0, "collision_losses": 1.0, "reachability": 100.0, "t90_ms": 1.0}


def read(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


summary = {(int(r["density"]), r["protocol"]): r for r in read(PROC / "summary.csv")}
paired = {(int(r["density"]), r["baseline"]): r for r in read(PROC / "paired.csv")}
dens = sorted({d for d, p in summary if p in SCHEMES})


def mc(row, key, scale):
    return [float(row[key]) * scale, float(row[key + "_ci95"]) * scale]


data = {
    "densities": dens,
    "at200": {p: {k: mc(summary[(D0, p)], k, s) for k, s in METRICS.items()} for p in SCHEMES},
    "frames_by_density": {p: [float(summary[(d, p)]["transmissions"]) for d in dens] for p in SCHEMES},
    # paired difference proposed minus strongest baseline (mean, 95 % CI half-width)
    "paired_vs_strongest": {str(d): {k: mc(paired[(d, "slotted1p_rad")], k, s) for k, s in METRICS.items()}
                            for d in dens},
}


def forgery(path):
    out = {}
    for r in read(path):
        t = out.setdefault(f'{int(r["density"])}|{r["variant"]}', [0, 0])
        t[0] += 1
        t[1] += int(float(r["rsu_registered"]) > 0)
    return out


forg = forgery(PROC / "forgery_runs.csv")
data["forgery_persistent"] = [forg[f"{D0}|{v}"] for v in ("no_voting", "voting_only", "voting_reputation")]
data["forgery_onoff"] = [forgery(SENS / f"onoff_{c}" / "processed" / "forgery_runs.csv")[f"{D0}|voting_reputation"]
                         for c in ("0", "0.5", "0.9")]

macros = {}
for name in ("numbers.tex", "slide_numbers.tex"):
    for k, v in re.findall(r"\\newcommand\{\\(\w+)\}\{([^}]*)\}", (OUT / "generated" / name).read_text("utf-8")):
        macros[k] = v.replace("$-$", "\u2212")
data["macros"] = macros

data["images"] = {}
for p in [OUT / "logo.png", *sorted((OUT / "figures").glob("*.png"))]:
    with Image.open(p) as im:
        data["images"][p.name] = list(im.size)

(OUT / "generated" / "pptx_data.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
print("densities", dens, "| persistent", data["forgery_persistent"], "| on-off", data["forgery_onoff"])
