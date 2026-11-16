"""Builds the Eraser.io freeform definition of the system architecture (explicit positions and arrow paths, so every
arrow runs in a gap between columns and no two arrows cross). Every box is a component of the implemented code; the
module behind each one is listed in system_architecture_eraser.txt.

    python make_architecture_freeform.py > system_architecture_freeform.json

Eraser draws elements in list order, so the column frames come first. Eraser's own arrow labels are too small at
print size, so labels are small white boxes placed on the arrows (drawn after them).
"""
import json

NL = "\n"
GAP = 120                                # empty corridor between columns (arrows and labels live here)
WIDTHS = [("L1", 290, "#1e40af"), ("L2", 290, "#6b21a8"), ("L3", 290, "#b45309"), ("L4", 300, "#166534"),
          ("L5", 290, "#991b1b")]
COLS, _x = {}, 0
for _c, _w, _colour in WIDTHS:
    COLS[_c] = (_x, _w, _colour)
    _x += _w + GAP
TOTAL_W = _x - GAP
HEAD = {"L1": "1 · Vehicle and Traffic", "L2": "2 · Trust and Clustering", "L3": "3 · Alert Verification",
        "L4": "4 · IoV Communication" + NL + "and Dissemination", "L5": "5 · RSU and Backend"}
TOP0, PITCH, NH = 100, 118, 96          # first row top, row pitch, node height
FRAME_BOTTOM = TOP0 + 4 * PITCH + NH + 22
PROPOSED = "#f4c9d5"                     # proposed-method-only components
SHARED = "#ffffff"                       # shared by all five approaches
FONT, HEAD_FONT, LABEL_FONT = 20, 21, 18

NODES = {   # id: (column, row 1-5, label, proposed-only?)
    "inc": ("L1", 1, "Incident generation" + NL + "random honest vehicle" + NL + "at t = 60–120 s", False),
    "sumo": ("L1", 2, "SUMO urban traffic" + NL + "5×5 grid, 50–500 vehicles" + NL + "30 seeds per density", False),
    "veh": ("L1", 3, "Vehicles by trust" + NL + "trusted (≥ 0.7) · unknown" + NL + "misbehaving 10 %", False),
    "watch": ("L2", 1, "Watchdog observations" + NL + "for each vehicle," + NL + "every second", False),
    "beta": ("L2", 2, "Beta reputation" + NL + "trust = (s+1) / (s+f+2)", False),
    "ch": ("L2", 3, "Trusted CH election" + NL + "greedy coverage;" + NL + "heads need trust ≥ 0.7", True),
    "db": ("L2", 4, "DBSCAN clustering" + NL + "ε = 40 m, ≥ 3 vehicles", True),
    "bridge": ("L2", 5, "Bridge vehicles" + NL + "unclustered vehicles;" + NL + "tier 0 if trusted", True),
    "alert": ("L3", 1, "Emergency alert creation" + NL + "event ID, position," + NL + "hop limit 10", False),
    "comm": ("L3", 2, "Five-member committee" + NL + "nearest trusted" + NL + "neighbours", False),
    "quorum": ("L3", 3, "Three-vote quorum" + NL + "alert released ≈ 12.1 ms", False),
    "bls": ("L3", 4, "BLS12-381 aggregation" + NL + "one 96-byte aggregate" + NL + "signature", False),
    "verif": ("L3", 5, "Certificate verification" + NL + "valid aggregate, ≥ 3" + NL + "distinct trusted signers", False),
    "chan": ("L4", 1, "IEEE 802.11p (simulated)" + NL + "300 m, collisions," + NL + "hidden terminals", False),
    "dup": ("L4", 2, "Duplicate filtering" + NL + "first copy: verify 4.3 ms" + NL + "later copies: no re-check", False),
    "wait": ("L4", 3, "Tier- and distance-" + NL + "based wait" + NL + "tier 0 first, far first", True),
    "cov": ("L4", 4, "Coverage-based" + NL + "suppression: forward if" + NL + "a neighbour is uncovered", True),
    "route": ("L4", 5, "CH-to-CH route stage" + NL + "Dijkstra over trusted CHs" + NL + "local quorum per head", True),
    "v2i": ("L5", 1, "V2I delivery" + NL + "RSUs receive copies," + NL + "never relay", False),
    "rsu": ("L5", 2, "RSU validation" + NL + "certificate, fields, map" + NL + "age ≤ 600 s, hop limit", False),
    "dupev": ("L5", 3, "Duplicate event handling" + NL + "register once; later" + NL + "copies DUPLICATE", False),
    "sql": ("L5", 4, "SQLite event registration" + NL + "event, dispatch outbox," + NL + "trust update", True),
    "dash": ("L5", 5, "Metrics and dashboard" + NL + "180 scenarios, SUMO-GUI" + NL + "replay, web dashboard", False),
}


def box(nid):
    col, row, _, _ = NODES[nid]
    x, w, _ = COLS[col]
    return x + 12, TOP0 + (row - 1) * PITCH, w - 24, NH          # left, top, width, height


def left(n, dy=0):
    x, t, w, h = box(n)
    return x, t + h / 2 + dy


def right(n, dy=0):
    x, t, w, h = box(n)
    return x + w, t + h / 2 + dy


def topc(n):
    x, t, w, h = box(n)
    return x + w / 2, t


def bottomc(n):
    x, t, w, h = box(n)
    return x + w / 2, t + h


frames, shapes, arrows, labels = [], [], [], []
for col, (x, w, colour) in COLS.items():
    frames.append({"id": f"frame_{col}", "tag": "Group", "x": x, "y": 0, "width": w, "height": FRAME_BOTTOM, "color": colour})
    shapes.append({"id": f"head_{col}", "tag": "Shape", "x": x + 10, "y": 10, "width": w - 20, "height": 70, "color": colour,
                   "texts": [{"text": HEAD[col], "fontSize": HEAD_FONT, "bold": True}]})
for nid, (col, row, label, proposed) in NODES.items():
    x, t, w, h = box(nid)
    shapes.append({"id": nid, "tag": "Shape", "x": x, "y": t, "width": w, "height": h,
                   "color": PROPOSED if proposed else SHARED, "texts": [{"text": label, "fontSize": FONT}]})


def edge(eid, a, b, pts):
    x0, y0 = pts[0]
    arrows.append({"id": eid, "tag": "Relationship", "from": a, "to": b, "x": x0, "y": y0,
                   "points": [[px - x0, py - y0] for px, py in pts], "color": "#1f2937", "lineWidth": 1.8,
                   "lineStyle": "solid", "endArrowhead": "triangle"})


def tag(lid, text, cx, cy, w, h=34):
    """Arrow label: a small white box centred on a point of the arrow."""
    labels.append({"id": lid, "tag": "Shape", "x": cx - w / 2, "y": cy - h / 2, "width": w, "height": h, "color": SHARED,
                   "texts": [{"text": text, "fontSize": LABEL_FONT}]})


def vertical(a, b):
    """Adjacent boxes in one column: straight arrow between them (up or down)."""
    (ax, ay), (bx, by) = (bottomc(a), topc(b)) if box(a)[1] < box(b)[1] else (topc(a), bottomc(b))
    edge(f"{a}_{b}", a, b, [(ax, ay), (bx, by)])


for a, b in [("sumo", "inc"), ("sumo", "veh"), ("watch", "beta"), ("beta", "ch"), ("db", "ch"), ("db", "bridge"),
             ("alert", "comm"), ("comm", "quorum"), ("quorum", "bls"), ("bls", "verif"),
             ("chan", "dup"), ("dup", "wait"), ("wait", "cov"),
             ("v2i", "rsu"), ("rsu", "dupev"), ("dupev", "sql"), ("sql", "dash")]:
    vertical(a, b)

gap = lambda c1, c2, f: COLS[c1][0] + COLS[c1][1] + f * GAP
col_mid = lambda c: COLS[c][0] + COLS[c][1] / 2
row_mid = lambda r: TOP0 + (r - 1) * PITCH + NH / 2
TOP_CORRIDOR, BOTTOM_CORRIDOR = -34, FRAME_BOTTOM + 34

# layer 1 -> layer 2: vehicles are observed (up) and their positions are clustered (down)
xa = gap("L1", "L2", 0.5)
edge("veh_watch", "veh", "watch", [right("veh", -16), (xa, right("veh", -16)[1]), (xa, left("watch")[1]), left("watch")])
edge("veh_db", "veh", "db", [right("veh", 16), (xa, right("veh", 16)[1]), (xa, left("db")[1]), left("db")])
tag("lab_positions", "positions", xa, (right("veh", 16)[1] + left("db")[1]) / 2 + 6, 96)
# layer 1 -> layer 3: the incident goes over the top of layer 2
xb, xc = gap("L1", "L2", 0.22), gap("L2", "L3", 0.3)
edge("inc_alert", "inc", "alert", [right("inc", -18), (xb, right("inc", -18)[1]), (xb, TOP_CORRIDOR), (xc, TOP_CORRIDOR),
                                   (xc, left("alert")[1]), left("alert")])
tag("lab_incident", "incident", col_mid("L2"), TOP_CORRIDOR, 96)
# layer 2 -> layer 3: trust selects the committee
edge("beta_comm", "beta", "comm", [right("beta"), left("comm")])
tag("lab_trust", "trust ≥ 0.7", gap("L2", "L3", 0.5), row_mid(2), 108)
# layer 3 -> layer 4: the certified alert enters the channel
xd = gap("L3", "L4", 0.45)
edge("verif_chan", "verif", "chan", [right("verif"), (xd, right("verif")[1]), (xd, left("chan")[1]), left("chan")])
tag("lab_cert", "certified" + NL + "alert", xd, (row_mid(1) + row_mid(3)) / 2, 96, 56)
# layer 2 -> layer 4: CH roles and tiers run under layer 3 (one shared bus)
xe, xf = gap("L2", "L3", 0.75), gap("L3", "L4", 0.82)
bus = lambda src, dst, dy=0: [right(src), (xe, right(src)[1]), (xe, BOTTOM_CORRIDOR), (xf, BOTTOM_CORRIDOR),
                               (xf, left(dst, dy)[1]), left(dst, dy)]
edge("ch_wait", "ch", "wait", bus("ch", "wait"))
edge("ch_route", "ch", "route", bus("ch", "route"))
edge("bridge_wait", "bridge", "wait", bus("bridge", "wait", 14))
tag("lab_roles", "CH roles and tiers", col_mid("L3"), BOTTOM_CORRIDOR, 176)
# layer 4 -> layer 5: forwarded copies and the route reach the RSU
xg, xh = gap("L4", "L5", 0.3), gap("L4", "L5", 0.66)
edge("cov_v2i", "cov", "v2i", [right("cov"), (xg, right("cov")[1]), (xg, left("v2i", -14)[1]), left("v2i", -14)])
edge("route_v2i", "route", "v2i", [right("route"), (xh, right("route")[1]), (xh, left("v2i", 14)[1]), left("v2i", 14)])

# legend
LY = BOTTOM_CORRIDOR + 44
frames.append({"id": "legend_frame", "tag": "Group", "x": 0, "y": LY, "width": TOTAL_W, "height": 76, "color": "#6b7280"})
for k, (lid, x, w, colour, text) in enumerate([
        ("legend_title", 14, 150, "#374151", "Legend"),
        ("legend_prop", 184, 500, PROPOSED, "Tinted box: proposed method only"),
        ("legend_shared", 700, 560, SHARED, "White box: shared by all five approaches"),
        ("legend_arrow", 1276, TOTAL_W - 1290, SHARED, "Arrow: data flow for one alert")]):
    shapes.append({"id": lid, "tag": "Shape", "x": x, "y": LY + 14, "width": w, "height": 48, "color": colour,
                   "texts": [{"text": text, "fontSize": 20, "bold": k == 0}]})

print(json.dumps({"title": "System architecture (implemented)", "elements": frames + shapes + arrows + labels},
                 ensure_ascii=False))
