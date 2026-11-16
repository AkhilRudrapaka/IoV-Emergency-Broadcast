"""Copy and crop the genuine screenshots used by the report and the presentation (no pixel is drawn or edited; crops
only remove the SUMO-GUI toolbars and status bar around the map view).

    python final_panel_review/scripts/prepare_screenshots.py <dashboard_capture_dir>

Inputs
  figures/sumo/sumo_NN_*.png + snapshots.json   13 captures of one complete `python run.py demo --shots` run
  results/demo_pairs/P002/<approach>/NNN.png     live captures of evidence pair P002 (baseline-only, proposed-only)
  <dashboard_capture_dir>/dash_*.png              headless-Edge captures of the running dashboard (cropped per section)
Outputs: figures/shot_*.png, figures/dashboard/*.png, figures/FIGURE_SOURCES.json
"""
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "final_panel_review" / "figures"
BOX = (280, 180, 1225, 935)            # the map view of the 1518 x 1097 SUMO-GUI window (labels, indicator, legend)
sources = {}

man = json.loads((FIG / "sumo" / "snapshots.json").read_text(encoding="utf-8"))
for s in man["snapshots"]:
    name = "shot_" + s["file"].replace("sumo_", "walk_")
    Image.open(FIG / "sumo" / s["file"]).convert("RGB").crop(BOX).save(FIG / name)
    sources[name] = {"source": f"figures/sumo/{s['file']} (cropped to the map view)", "run": man["run_id"], "seed": man["seed"],
                     "stage": s["stage"], "scheme": s["scheme"], "caption_in_manifest": s["caption"],
                     "captured": man["captured"], "record_fingerprint": man["record_fingerprint"][:16]}
shutil.copy2(FIG / "sumo" / "sumo_01_traffic.png", FIG / "shot_window_traffic.png")
sources["shot_window_traffic.png"] = {**sources["shot_walk_01_traffic.png"], "source": "figures/sumo/sumo_01_traffic.png (full window)"}

pair = json.loads((ROOT / "results" / "demo_pairs" / "P002" / "pair.json").read_text(encoding="utf-8"))
for approach, numbers in (("baseline", ["014", "016"]), ("proposed", ["006", "015", "030", "035", "037"])):
    caps = {c["file"]: c for c in json.loads((ROOT / "results" / "demo_pairs" / "P002" / approach / "captures.json").read_text(encoding="utf-8"))}
    for n in numbers:
        src = ROOT / "results" / "demo_pairs" / "P002" / approach / f"{n}.png"
        name = f"shot_pair_P002_{approach}_{n}.png"
        Image.open(src).convert("RGB").crop(BOX).save(FIG / name)
        c = caps[f"{n}.png"]
        sources[name] = {"source": f"results/demo_pairs/P002/{approach}/{n}.png (cropped to the map view)", "pair": "P002",
                         "scenario": pair["scenario"]["scenario_id"], "seed": pair["scenario"]["seed"], "approach": approach,
                         "algorithm": pair["runs"][approach]["algorithm"], "stage": c.get("workflow_stage"),
                         "scheme": c.get("scheme"), "status": c.get("status"),
                         "record_fingerprint": pair["runs"][approach]["fingerprint"][:16]}

dash_in = Path(sys.argv[1])
(FIG / "dashboard").mkdir(exist_ok=True)
log = json.loads((dash_in / "log.json").read_text(encoding="utf-8"))
for shot in log["shots"]:
    for f in shot["saved"]:
        shutil.copy2(dash_in / f, FIG / "dashboard" / f)
        sources[f"dashboard/{f}"] = {"source": "headless Microsoft Edge capture of the running dashboard (python run.py web), "
                                               "cropped to one section card", "pair": shot["pair"], "note": shot["note"],
                                     "taken": shot["taken"], "taken_with": log["taken_with"]}
(FIG / "FIGURE_SOURCES.json").write_text(json.dumps(sources, indent=1), encoding="utf-8")
print(len(sources), "figures prepared")
