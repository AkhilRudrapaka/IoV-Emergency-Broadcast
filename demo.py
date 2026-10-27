"""
SUMO-GUI demonstration. A presentation layer only: it replays a run that the
experiment pipeline already simulated (results/raw/<run>.json.gz) and decides
nothing itself. Clusters are recomputed each second with the project's own
DBSCAN + election code on the vehicles' real positions, and the demo checks
that the GUI shows exactly the snapshot and the clustering the experiment used.

What you see:
  1. normal traffic; every second DBSCAN regroups the vehicles (one colour per
     cluster, white = isolated, black ring = elected cluster representative)
  2. the accident vehicle turns red and stops; the alert is created
  3. corroboration: the committee votes (violet), the certified alert is released
  4. the certified alert spreading, in slow motion. Dissemination takes tens of
     milliseconds while one traffic step is 1 s, so traffic is frozen meanwhile
  5. each scheme in turn on the SAME accident (flooding first: the storm)
  6. the RSU validating and registering the event: "ALERT RECEIVED"
  7. a forged alert from a misbehaving vehicle: certified by colluders, rejected
     by every receiver and by the RSU
  8. traffic resuming around the crashed vehicle
"""
import math
import os
import sys
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

import numpy as np
import sumo
import traci

import config
import experiment
import report
from channel import geometry
from clustering import elect_roles
from scenario import build, NET_FILE

VIEW = "View #0"
IDLE, HAS, FORWARD, SUPPRESS, DROP, CRASH, VOTE, REJECT = (
    (255, 220, 0, 255), (42, 120, 214, 255), (235, 104, 52, 255), (150, 150, 150, 255),
    (120, 80, 200, 255), (227, 30, 30, 255), (151, 102, 225, 255), (255, 255, 255, 255))
ISOLATED = (255, 255, 255, 255)
PALETTE = [(42, 120, 214), (235, 104, 52), (27, 175, 122), (237, 161, 0), (232, 123, 164), (0, 131, 0),
           (120, 80, 200), (227, 73, 72), (0, 170, 200), (150, 110, 60)]
RSU_IDLE, RSU_OK, RSU_BAD = (0, 150, 200, 255), (0, 170, 60, 255), (227, 30, 30, 255)
LEGEND_CLUSTERS = [((42, 120, 214, 255), "one colour = one DBSCAN cluster"), (ISOLATED, "white: isolated vehicle"),
                   ((0, 0, 0, 255), "black ring: cluster representative"), (RSU_IDLE, "RSU listening")]
LEGEND_ALERT = [(IDLE, "no alert yet"), (VOTE, "committee member voting"), (HAS, "accepted the alert"),
                (FORWARD, "rebroadcast (ring = its range)"), (SUPPRESS, "suppressed: stays silent"),
                (DROP, "misbehaving: never relays"), (REJECT, "white: rejected the alert"), (CRASH, "alert source"),
                (RSU_OK, "RSU: alert validated"), (RSU_BAD, "RSU: alert rejected")]
SETTINGS = """<viewsettings>
  <scheme name="alert-demo">
    <background backgroundColor="241,245,250" showGrid="0"/>
    <edges laneShowBorders="1" showLinkDecals="1" streetName_show="0"/>
    <vehicles vehicleQuality="2" vehicle_minSize="1" vehicle_exaggeration="3.2" vehicleName_show="0"/>
    <pois poi_exaggeration="1" poiName_show="0" poiName_size="42" poiName_color="31,48,68" poiName_constantSize="1"
          poiType_show="0" poiText_show="1" poiTextParam="display_text"
          poiText_size="300" poiText_constantSize="0" poiText_color="31,48,68"/>
    <polys polyName_show="0"/>
  </scheme>
  <delay value="0"/>
</viewsettings>"""
BIN_MS = 0.5                       # radio time shown per animation frame
_labels, _legend = {}, []
_presentation_dir = None
DISPLAY_FONT = 'Trebuchet MS'


def ring(x, y, r, n=36):
    return [(x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]


def label(key, text, x, y, color=(0, 0, 0, 255)):
    """Use SUMO's own font renderer instead of resampled image lettering."""
    if key in _labels:
        traci.poi.remove(_labels[key])
    _labels[key] = f'label-{key}'
    traci.poi.add(_labels[key], x, y - 21, (0, 0, 0, 0), layer=120, width=0, height=0)
    traci.poi.setParameter(_labels[key], 'display_text', text)


def banner(text):
    label("banner", text, 400, 905)


def presentation_settings(path):
    """Configure SUMO-native text; do not load bitmap font decals."""
    global _presentation_dir
    _presentation_dir = os.path.dirname(path)
    root = ET.fromstring(SETTINGS)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def render_legend(items, image_file):
    """Draw fixed pixel rows and a separate footer, with supersampled glyphs."""
    from PIL import Image, ImageDraw, ImageFont
    from matplotlib import font_manager
    scale = 3
    canvas = Image.new('RGB', (460 * scale, 740 * scale), 'white')
    draw = ImageDraw.Draw(canvas)
    regular = font_manager.findfont(DISPLAY_FONT)
    bold = font_manager.findfont(font_manager.FontProperties(family=DISPLAY_FONT, weight='bold'))
    def text(x, y, value, size, color='#20344c', heavy=False):
        font = ImageFont.truetype(bold if heavy else regular, size * scale)
        draw.text((x * scale, y * scale), value, font=font, fill=color, anchor='lt')
    text(40, 36, 'City control', 34, heavy=True)
    text(40, 88, 'Live vehicle and alert states', 19, '#718096')
    draw.line((40*scale, 126*scale, 420*scale, 126*scale), fill='#e6edf5', width=scale)
    captions = {
        'no alert yet': 'Alert pending', 'committee member voting': 'Committee vote',
        'accepted the alert': 'Verified alert', 'rebroadcast (ring = its range)': 'Rebroadcasting',
        'suppressed: stays silent': 'Duplicate suppressed', 'misbehaving: never relays': 'Relay withheld',
        'white: rejected the alert': 'Alert rejected', 'alert source': 'Incident vehicle',
        'RSU: alert validated': 'RSU validated', 'RSU: alert rejected': 'RSU rejected',
        'one colour = one DBSCAN cluster': 'Colour: vehicle cluster',
        'white: isolated vehicle': 'Isolated vehicle', 'black ring: cluster representative': 'Ring: cluster head',
        'RSU listening': 'RSU listening'}
    for i, (color, caption) in enumerate(items):
        y = 158 + i * 44
        draw.rounded_rectangle((40*scale, y*scale, 68*scale, (y+28)*scale), radius=7*scale,
                               fill=color[:3], outline='#dce5f0', width=scale)
        text(88, y + 2, captions.get(caption, caption), 23)
    draw.rounded_rectangle((28*scale, 622*scale, 432*scale, 714*scale), radius=14*scale, fill='#f3f5fb')
    text(46, 642, 'Incident  /  Consensus  /  RSU', 19, '#6651aa', heavy=True)
    text(46, 675, 'Live simulation · Signed alerts', 17, '#718096')
    # Match the default viewport's on-screen panel size to avoid aggressive
    # OpenGL texture minification, which broke strokes in the previous panel.
    canvas.resize((354, 570), Image.Resampling.LANCZOS).save(image_file)
    return image_file


def legend(items):
    if _legend:
        for key in list(_labels):
            if key.startswith('legend-'):
                traci.poi.remove(_labels.pop(key))
        for i in range(len(_legend)):
            traci.polygon.remove(f'legend-swatch-{i}')
    _legend[:] = items
    def left_text(key, text, x, y):
        label(key, text + '\n ', x, y - 21)
    left_text('legend-title', 'CITY CONTROL', 928, 800)
    left_text('legend-subtitle', 'Vehicle and alert states', 928, 752)
    captions = ['Alert pending', 'Committee vote', 'Verified alert', 'Rebroadcasting',
                'Duplicate suppressed', 'Relay withheld', 'Alert rejected', 'Incident vehicle',
                'RSU validated', 'RSU rejected'] if len(items) == 10 else [
                'Vehicle cluster', 'Isolated vehicle', 'Cluster head', 'RSU listening']
    for i, (color, _) in enumerate(items):
        y = 674 - i * 45
        traci.polygon.add(f'legend-swatch-{i}', [(930,y-12),(958,y-12),(958,y+12),(930,y+12)],
                          color, fill=True, layer=111)
        left_text(f'legend-row-{i}', captions[i], 986, y)
    left_text('legend-footer', 'Incident / Consensus / RSU', 928, 170)


def show(text, live):
    if live and sys.stdout.isatty():
        print("\033[H\033[J", end="")
    print(text, flush=True)


# ---------------------------------------------------------------- 1. clustering, second by second
def show_clusters(step, previous, rings):
    """Colours every vehicle by its DBSCAN cluster and rings the elected representatives.
    Returns (vehicle -> colour index, ring ids, roles, labels) for the next second."""
    ids, xy = step["ids"], step["xy"]
    _, adj = geometry(xy)
    role, _, labels = elect_roles(xy, step["speed"], adj, step["trust"])
    # DBSCAN numbers its clusters arbitrarily each second: keep a cluster's colour by
    # giving it the colour most of its members had a second ago
    colour, used = {}, set()
    for c in sorted(set(labels) - {-1}, key=lambda c: -(labels == c).sum()):
        members = [ids[i] for i in np.flatnonzero(labels == c)]
        old = [previous[v] for v in members if previous.get(v, -1) >= 0]
        pick = max(set(old), key=old.count) if old else None
        if pick is None or pick in used:
            pick = next(k for k in range(10 ** 6) if k not in used)
        used.add(pick)
        colour.update({v: pick for v in members})
    for r in rings:
        traci.polygon.remove(r)
    rings = []
    for i, v in enumerate(ids):
        k = colour.get(v, -1)
        traci.vehicle.setColor(v, ISOLATED if k < 0 else (*PALETTE[k % len(PALETTE)], 255))
        if role[i] == "CH":
            traci.polygon.add(f"rep-{v}", ring(*xy[i], 16, 14), (0, 0, 0, 255), fill=False, layer=110, lineWidth=2.5)
            rings.append(f"rep-{v}")
    moved = sum(previous.get(v, -1) != colour.get(v, -1) for v in ids) if previous else 0
    n = len(set(labels) - {-1})
    line = (f"t = {step['t']:.0f} s   DBSCAN: {n} clusters, {int((role == 'CH').sum())} representatives, "
            f"{int((labels == -1).sum())} isolated   {moved} vehicles changed cluster")
    banner("CLUSTERING  " + line)
    print(line, flush=True)
    return {v: colour.get(v, -1) for v in ids}, rings, role, labels


# ---------------------------------------------------------------- 3-7. one alert, replayed
def replay(raw, proto="proposed", forged=None, pace=0.35, shot=None, notes=None):
    """Animate one simulation's recorded frames, then check the totals shown against its metrics."""
    sc = raw["scenario"]
    P, alert, name = report.pick(raw, proto, forged)
    pos = {v["id"]: (v["x"], v["y"]) for v in sc["vehicles"]}
    lines, rings, counts, frame = [], [], {}, 0
    for vid in pos:
        traci.vehicle.setColor(vid, IDLE)
    traci.vehicle.setColor(alert["source_vehicle"], CRASH)
    label("accident", ("FORGED ALERT " if forged else "ACCIDENT ") + alert["event_id"],
          alert["incident_position"][0], alert["incident_position"][1] + 45, CRASH)
    for u in sc["rsus"]:
        label(u["id"], f"{u['id']}: listening", u["x"] + 32, u["y"] + 75)
        traci.polygon.setColor(f"site-{u['id']}", RSU_IDLE)
    txs = sorted(P["transmissions"], key=lambda t: t["start_ms"])
    first_rsu = {}
    for rx in P["rsu_receptions"]:
        first_rsu.setdefault(rx["rsu"], rx["delay_ms"])
    end = max([t["end_ms"] for t in txs] + [v["decided_ms"] or 0 for v in P["vehicles"]])
    alerts = [t for t in txs if t["kind"] == "ALERT"]
    busiest = max(range(int(end / BIN_MS) + 1),
                  key=lambda k: sum(k * BIN_MS <= t["start_ms"] < (k + 1) * BIN_MS for t in alerts[1:]))
    quorum = f"; {config.QUORUM} of {config.COMMITTEE_SIZE} needed" if P["corroboration"] else ""
    committee, _, certificate = report.corroboration_lines(P["corroboration"])
    while frame * BIN_MS <= end + BIN_MS:
        lo, hi = frame * BIN_MS, (frame + 1) * BIN_MS
        frame += 1
        within = lambda ms: ms is not None and lo <= ms < hi
        before = lambda ms: ms is not None and ms < hi
        started = [t for t in txs if within(t["start_ms"])]
        accepted = [v for v in P["vehicles"] if v["from"] and within(v["rx_ms"])]
        decided = [v for v in P["vehicles"] if v["decision"] in ("SUPPRESS", "REJECT") and within(v["decided_ms"])]
        heard = [u for u, ms in first_rsu.items() if within(ms)]
        if not (started or accepted or decided or heard or rings):
            continue                                              # nothing happens in this half millisecond
        for r in rings:
            traci.polygon.remove(r)
        rings = []
        for v in accepted:
            traci.vehicle.setColor(v["id"], DROP if v["decision"] == "DROP" else HAS)
            line = f"link-{frame}-{v['id']}"
            traci.polygon.add(line, [pos[v["from"]], pos[v["id"]]], (42, 120, 214, 160), fill=False, layer=90, lineWidth=0.6)
            lines.append(line)
        for v in decided:
            traci.vehicle.setColor(v["id"], SUPPRESS if v["decision"] == "SUPPRESS" else REJECT)
        for t in started:
            colour = ({"PROPOSAL": CRASH, "VOTE": VOTE, "ALERT": FORWARD}.get(t["kind"],
                      VOTE if t['kind'].startswith('CVOTE:') else (0, 170, 160, 255)))
            if t["sender"] != alert["source_vehicle"]:
                traci.vehicle.setColor(t["sender"], colour)
            rid = f"ring-{frame}-{t['sender']}"
            traci.polygon.add(rid, ring(*pos[t["sender"]], config.COMM_RANGE_M), colour, fill=False, layer=95, lineWidth=1.5)
            rings.append(rid)
        for u in heard:
            rsu = next(r for r in sc["rsus"] if r["id"] == u)
            ok = P["rsu_event"] is not None
            label(u, f"{u}: ALERT RECEIVED, validated +{first_rsu[u]:.1f} ms" if ok else f"{u}: ALERT REJECTED, not corroborated",
                  rsu["x"] + 32, rsu["y"] + 75)
            traci.polygon.setColor(f"site-{u}", RSU_OK if ok else RSU_BAD)
        done = [t for t in txs if t["start_ms"] < hi]
        votes = sum(t["kind"] == "VOTE" or t['kind'].startswith('CVOTE:') for t in done)
        released = any(t["kind"] == "ALERT" for t in done)
        counts = {"reached": sum(before(v["rx_ms"]) for v in P["vehicles"]), "transmissions": len(done),
                  "forwarded": max(0, sum(t["kind"] == "ALERT" for t in done) - 1),
                  "suppressed": sum(v["decision"] == "SUPPRESS" and before(v["decided_ms"]) for v in P["vehicles"]),
                  "collisions": sum(t["lost"] for t in txs if t["end_ms"] < hi)}
        if not P["corroboration"]:
            stage = "alert spreading"
        elif released:
            stage = "certified alert spreading" if P["corroboration"]["accepted"] else "certificate REJECTED by receivers"
        else:
            stage = f"corroboration: {votes}/{config.QUORUM} votes"
        rsu_seen = bool(first_rsu) and min(first_rsu.values()) < hi
        status, delay, _ = report.rsu_lines(P["rsu_event"], True, not P["rsu_event"]) if rsu_seen else ("listening", "-", "-")
        explanation_stage = 'rsu' if rsu_seen else ('spreading' if released or not P['corroboration'] else 'voting')
        explanation = ('\nEXPLANATION: ' + notes[explanation_stage]) if notes else ''
        show(report.panel({
            "scheme": name, "event_id": alert["event_id"], "type": alert["message_type"],
            "status": f"ACTIVE  +{hi:.1f} ms, slow-motion replay: {stage}", "source": alert["source_vehicle"],
            "run_id": sc["run_id"], "seed": sc["seed"], "position": alert["incident_position"],
            "time_s": alert["incident_time_s"], "committee": committee, "votes": f"{votes} cast so far{quorum}",
            "certificate": certificate if released else "not yet released",
            "total": len(pos), **counts,
            "dropped": sum(v["decision"] == "DROP" and before(v["rx_ms"]) for v in P["vehicles"]),
            "rsu_status": status, "rsu_delay": delay, "rsu_dups": "(counted at the end)" if rsu_seen and P["rsu_event"] else "-"})
            + explanation, live=True)
        banner(f"{name.upper()}   +{hi:.1f} ms   {stage}   {counts['transmissions']} frames   "
               + (f"{counts['reached'] - 1} honest vehicles accepted it" if forged else f"{counts['reached']}/{len(pos)} accepted"))
        # Capture stable stages after replay instead of queuing a screenshot
        # during active radio rings (Windows SUMO can stall at that point).
        traci.simulationStep()                                    # redraw; every vehicle is frozen
        time.sleep(pace)
    for r in rings:
        traci.polygon.remove(r)
    show(report.run_block(raw, proto, forged), live=True)
    # Windows SUMO's OpenGL screenshot capture may block after overlay-heavy
    # replay. Introductory map/incident captures remain available on Windows.
    if shot and os.name != 'nt':
        traci.gui.screenshot(VIEW, shot)
    traci.simulationStep()
    time.sleep(5 * pace)
    for line in lines:
        traci.polygon.remove(line)
    m = P["metrics"]
    assert counts["transmissions"] == m["transmissions"] and counts["reached"] == m["received"], \
        "the replay must end on the experiment's own numbers"


def freeze(ids, frozen):
    for vid in ids:
        traci.vehicle.setSpeedMode(vid, 0 if frozen else 31)
        traci.vehicle.setLaneChangeMode(vid, 0 if frozen else 1621)
        traci.vehicle.setSpeed(vid, 0 if frozen else -1)


def run(density=config.DEMO_DENSITY, run_index=config.DEMO_RUN, schemes=("flooding", "proposed", "ch_route"),
        pace=0.35, shots=None, lead_in_s=15, wait=True, forged=True,
        narration=False, language='ta', offline=False):
    experiment.run_one(density, run_index)                        # (re)simulate; identical for the same seed
    raw = experiment.load_raw(f"d{density}_r{run_index:02d}")
    sc = raw["scenario"]
    narrations = {}
    if narration:
        import narrator
        for scheme in schemes:
            notes, source = narrator.prepare(raw, scheme, language, offline=offline)
            narrations[scheme] = notes
            print(f'Explanation for {scheme}: {source}', flush=True)
        if forged and raw.get('forgery'):
            narrations['forged'], source = narrator.prepare(raw, 'proposed', language,
                                                           forged='voting_reputation', offline=offline)
            print(f'Forged-alert explanation: {source}', flush=True)
    first_notes = narrations.get(schemes[0]) if schemes else None
    shot = (lambda name: os.path.join(shots, name)) if shots else (lambda name: None)
    if shots:
        os.makedirs(shots, exist_ok=True)
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    error_log = os.path.abspath(os.path.join(config.RESULTS_DIR, 'sumo_gui_errors.log'))
    with tempfile.TemporaryDirectory() as tmp:
        live = build(density, run_index, workdir=tmp, history_s=lead_in_s)   # same seed: identical routes and traffic
        settings = os.path.join(tmp, "view.xml")
        presentation_settings(settings)
        additions = os.path.splitext(NET_FILE)[0].replace(".net", "") + ".add.xml"
        scenery_args = ["--additional-files", additions] if os.path.isfile(additions) else []
        traci.start([os.path.join(sumo.SUMO_HOME, "bin", "sumo-gui.exe" if os.name == "nt" else "sumo-gui"), "-n", NET_FILE,
                     "-r", os.path.join(tmp, "routes.rou.xml"), "--step-length", "1", "--seed", str(sc["seed"]),
                     "--gui-settings-file", settings, "--start", "--quit-on-end", "false",
                     "--collision.action", "none", "--time-to-teleport", "-1", "--error-log", error_log,
                     "--window-size", "1500,1050", "--no-warnings", "true"] + scenery_args)
        sumo_process = traci.getConnection('')._process
        try:
            traci.gui.setBoundary(VIEW, -120, -90, 1370, 1020)
            traci.polygon.add("legend-card", [(890, 100), (1350, 100), (1350, 840), (890, 840)],
                              (255, 255, 255, 245), fill=True, layer=-1)
            _labels.clear()
            _legend.clear()
            traci.polygon.add('heading-card', [(-50,930),(990,930),(990,1015),(-50,1015)],
                              (255,255,255,255), fill=True, layer=100)
            label('heading-title', 'GARDEN CITY | EMERGENCY INTELLIGENCE', 470, 990)
            label('heading-subtitle', 'Live mobility / Signed consensus / Trusted RSU delivery', 470, 950)
            for u in sc["rsus"]:
                x, y = u["x"], u["y"]                             # marker on the block corner, beside the junction
                traci.polygon.add(f"site-{u['id']}", [(x + 12, y + 12), (x + 52, y + 12), (x + 52, y + 52), (x + 12, y + 52)],
                                  RSU_IDLE, fill=True, layer=96)
                traci.polygon.add(f"range-{u['id']}", ring(x, y, config.COMM_RANGE_M), (90, 90, 90, 255), fill=False,
                                  layer=80, lineWidth=0.8)
                label(u["id"], f"{u['id']}: listening", x + 32, y + 75)
            legend(LEGEND_CLUSTERS)
            # Explicitly model infrastructure sites; these do not imply live cloud services.
            traci.polygon.add('emergency-centre', [(910, -30), (1060, -30), (1060, 60), (910, 60)],
                              (226, 235, 248, 255), fill=True, layer=96)
            label('service', 'EMERGENCY SERVICES: local outbox', 1120, 15, (65, 85, 125, 255))
            traci.polygon.add('hospital-cross-h', [(915, 2), (955, 2), (955, 12), (915, 12)], CRASH, fill=True, layer=97)
            traci.polygon.add('hospital-cross-v', [(930, -13), (940, -13), (940, 27), (930, 27)], CRASH, fill=True, layer=97)

            # 1. normal traffic with live clustering. FCD timestep t is the TraCI state once the clock reads t + 1.
            print(f"Normal traffic: {density} vehicles, {len(sc['rsus'])} RSUs. Clusters are recomputed every second "
                  f"(DBSCAN eps = {config.DBSCAN_EPS_M:.0f} m, MinPts = {config.DBSCAN_MIN_PTS}).", flush=True)
            colours, reps = {}, []
            if first_notes:
                print(first_notes['clustering'], flush=True)
            for step in live["history"]:
                traci.simulationStep(step["t"] + 1)
                colours, reps, role, labels = show_clusters(step, colours, reps)
                time.sleep(pace)
            if shots:
                traci.gui.screenshot(VIEW, shot("sumo_1_clusters.png"))

            # the GUI must show exactly the snapshot, and the clustering, that the experiment used
            ids = [v["id"] for v in sc["vehicles"]]
            now = np.array([traci.vehicle.getPosition(v) for v in ids])
            drift = float(np.abs(now - np.array([[v["x"], v["y"]] for v in sc["vehicles"]])).max())
            assert set(traci.vehicle.getIDList()) == set(ids) and drift < 0.05, f"GUI differs from the recorded run ({drift} m)"
            assert list(labels) == [v["dbscan"] for v in sc["vehicles"]] and list(role) == [v["role"] for v in sc["vehicles"]], \
                "the clusters shown must be the ones the experiment used"

            # 2. the one accident
            freeze(ids, True)
            traci.simulationStep()                                # takes the cluster screenshot; vehicles are frozen now
            x, y = sc["incident_xy"]
            traci.vehicle.setColor(sc["source_id"], CRASH)
            traci.polygon.add("accident-site", ring(x, y, 22, 16), CRASH, fill=True, layer=94)
            label("accident", f"ACCIDENT {sc['alert']['event_id']}", x, y + 45, CRASH)
            banner(f"ACCIDENT at t = {sc['incident_time_s']:.0f} s: alert {sc['alert']['event_id']} created")
            print(f"\nACCIDENT at t = {sc['incident_time_s']:.0f} s: vehicle {sc['source_id']} at ({x:.0f}, {y:.0f}).\n"
                  f"Alert {sc['alert']['event_id']} created. Traffic is frozen while the radio events (tens of "
                  "milliseconds) are replayed in slow motion.", flush=True)
            if shots:
                traci.gui.screenshot(VIEW, shot("sumo_2_accident.png"))
            traci.simulationStep()
            time.sleep(4 * pace)
            if first_notes:
                print(first_notes['accident'], flush=True)
            legend(LEGEND_ALERT)

            # 3-6. the same alert under each scheme (cluster representatives keep their black ring)
            for i, proto in enumerate(schemes):
                route_lines = []
                if proto == 'ch_route':
                    coordinates = {v['id']: (v['x'], v['y']) for v in sc['vehicles']}
                    coordinates.update({u['id']: (u['x'], u['y']) for u in sc['rsus']})
                    route = raw['infrastructure']['route']['vehicle_ids']
                    for k, (left, right) in enumerate(zip(route, route[1:])):
                        key = f'planned-route-{k}'
                        traci.polygon.add(key, [coordinates[left], coordinates[right]], (122, 91, 216, 255),
                                          fill=False, layer=93, lineWidth=3)
                        route_lines.append(key)
                replay(raw, proto, None, pace, shot(f"sumo_{3 + i}_{proto}.png"), notes=narrations.get(proto))
                for key in route_lines:
                    traci.polygon.remove(key)

            # 7. a forged alert on the same traffic
            if forged and raw.get("forgery"):
                fx, fy = raw["forgery"]["alert"]["incident_position"]
                traci.polygon.setShape("accident-site", ring(fx, fy, 22, 16))
                replay(raw, forged="voting_reputation", pace=pace, shot=shot("sumo_7_forged.png"), notes=narrations.get('forged'))
                traci.polygon.setShape("accident-site", ring(x, y, 22, 16))
                label("accident", f"ACCIDENT {sc['alert']['event_id']}", x, y + 45, CRASH)

            # 8. traffic resumes around the crashed vehicle
            freeze([v for v in ids if v != sc["source_id"]], False)
            delivery = raw['protocols'].get('ch_route', raw['protocols']['proposed'])
            accepted = delivery['rsu_event'] is not None
            label('service', 'EMERGENCY SERVICES: queued locally' if accepted else 'EMERGENCY SERVICES: no validated alert',
                  1120, 15, RSU_OK if accepted else RSU_BAD)
            banner('TRAFFIC RESUMES  |  ' + ('RSU registered; trust saved; dispatch queued locally' if accepted else 'No validated CH delivery; inspect route and quorum'))
            for _ in range(8):
                traci.simulationStep()
                time.sleep(pace / 3)
            if shots and os.name != 'nt':
                traci.gui.screenshot(VIEW, shot("sumo_9_after.png"))
                traci.simulationStep()
            if first_notes:
                print('Simulation complete. Inspect each scheme and forged-alert result separately.', flush=True)
            if wait and sys.stdin.isatty():
                input("\nDemo finished. Press Enter to close SUMO-GUI.")
        except traci.exceptions.FatalTraCIError as exc:
            raise RuntimeError(f'SUMO closed during replay. Keep the SUMO window open until the demo finishes. '
                               f'Diagnostic log: {error_log}') from exc
        finally:
            try:
                traci.close(wait=False)
            except traci.exceptions.FatalTraCIError:
                pass  # preserve the original failure when SUMO has already disconnected
            finally:
                if sumo_process is not None and sumo_process.poll() is None:
                    sumo_process.terminate()
                    try:
                        sumo_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        sumo_process.kill()
                        sumo_process.wait()
    return raw
