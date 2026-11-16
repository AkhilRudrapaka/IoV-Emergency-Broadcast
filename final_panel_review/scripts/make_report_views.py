"""Print-size views of the genuine captures for the report (crops only: no pixel is drawn, edited or moved).

    python final_panel_review/scripts/make_report_views.py

  view_map_*.png      map area of a SUMO-GUI capture (legend and status lines are shown once, in the full-window figure)
  view_status_*.png   stage bar and status lines of a SUMO-GUI capture, for full-width placement
  view_dash_*.png     one dashboard card cropped to its useful part
The source of every view is added to figures/FIGURE_SOURCES.json.
"""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "final_panel_review" / "figures"
MAP = (335, 340, 900, 862)        # map area of the 1518 x 1097 SUMO-GUI window
STATUS = (280, 252, 1225, 323)    # stage bar and the two status lines above the map

views = {}
for f in sorted((FIG / "sumo").glob("sumo_*.png")):
    tag = f.stem.replace("sumo_", "")
    Image.open(f).convert("RGB").crop(MAP).save(FIG / f"view_map_walk_{tag}.png")
    views[f"view_map_walk_{tag}.png"] = f"figures/sumo/{f.name}, map area {MAP}"
for tag in ("12_forged", "13_final", "07_flooding", "09_duplicates"):
    Image.open(FIG / "sumo" / f"sumo_{tag}.png").convert("RGB").crop(STATUS).save(FIG / f"view_status_walk_{tag}.png")
    views[f"view_status_walk_{tag}.png"] = f"figures/sumo/sumo_{tag}.png, status lines {STATUS}"
for approach, n in (("baseline", "014"), ("proposed", "015")):
    src = ROOT / "results" / "demo_pairs" / "P002" / approach / f"{n}.png"
    Image.open(src).convert("RGB").crop(MAP).save(FIG / f"view_map_P002_{approach}_{n}.png")
    views[f"view_map_P002_{approach}_{n}.png"] = f"results/demo_pairs/P002/{approach}/{n}.png, map area {MAP}"
    Image.open(src).convert("RGB").crop(STATUS).save(FIG / f"view_status_P002_{approach}_{n}.png")
    views[f"view_status_P002_{approach}_{n}.png"] = f"results/demo_pairs/P002/{approach}/{n}.png, status lines {STATUS}"
for src, name, box in (("dash_live_d200_r25_status.png", "view_dash_live.png", (0, 0, 1820, 1000)),
                       ("dash_d200_r02_scenario.png", "view_dash_scenario.png", (0, 0, 1820, 1345)),
                       ("dash_d200_r02_comparison_table.png", "view_dash_comparison.png", (0, 0, 1820, 1130)),
                       ("dash_d200_r02_evidence.png", "view_dash_evidence.png", (0, 0, 1820, 860))):
    Image.open(FIG / "dashboard" / src).convert("RGB").crop(box).save(FIG / "dashboard" / name)
    views[f"dashboard/{name}"] = f"figures/dashboard/{src}, crop {box}"

path = FIG / "FIGURE_SOURCES.json"
sources = json.loads(path.read_text(encoding="utf-8"))
for name, how in views.items():
    sources[name] = {"source": how + " (crop of a genuine capture, made by make_report_views.py)"}
path.write_text(json.dumps(sources, indent=1), encoding="utf-8")
print(len(views), "views written")
