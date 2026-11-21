"""
SUMO-GUI demonstration. A presentation layer only: it replays a run that the experiment pipeline already
simulated (results/raw/<run>.json.gz) and decides nothing itself. The demo checks that SUMO shows exactly the
snapshot (positions) and the clustering the experiment used, and that every replay ends on the recorded totals.

What you see, in the order of the workflow indicator at the top:
  live traffic   vehicles drive normally (quiet grey); no stage is active yet
  1 Incident     the incident vehicle turns red at the incident second; SUMO's clock is PAUSED from here on:
                 the GUI is repainted without simulation steps (redraw), so nothing moves during the replay
  2 Alert        the alert record (event ID, type, hop limit) created by the incident vehicle
  3 Cluster / CH the clusters and cluster heads at that second (the ones the protocols used)
  then, for each scheme on the SAME accident (blind flooding, proposed, CH route, then a forged alert):
  4 Votes        committee members' vote frames, as they are sent (counted, never ahead of the record)
  5 Certificate  the source's certified alert: BLS aggregate signature, accepted or rejected by receivers
  6 Forwarding / Route   relays transmitting (orange, this frame only) and receptions (short-lived links);
                 for the CH route this stage starts with a head's local vote, and each hop is drawn only once
                 its head has actually accepted the alert
  7 RSU          RSU decoding, verification and outcome: registered / duplicate / rejected
  finally the clock resumes: only the crashed vehicle stops; every other vehicle continues from its own speed.
The radio is a SIMULATED 802.11p model (channel.py); the dissemination is computed by the experiment engine on
this exact SUMO state and animated here in slow motion. live_feed() mirrors the indicator to the web viewer.
"""
import glob
import json
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
import incident_response
import report
from channel import geometry, ms_to_slots, slots_to_ms
from clustering import elect_roles
from scenario import build, NET_FILE

VIEW = "View #0"
# One small semantic palette (the legend lists every colour). Ordinary traffic is quiet grey; only the incident,
# cluster heads, what was on air in the frame shown, the traversed route and RSU outcomes stand out, only while relevant.
NEUTRAL = (165, 172, 184, 255)          # vehicle without the alert: ordinary traffic
HAS = (52, 120, 220, 255)               # vehicle holding the VERIFIED alert
TX = (255, 128, 0, 255)                 # vehicle whose frame was on air during the 0.5 ms animation frame shown
CRASH = (220, 30, 30, 255)              # incident vehicle / alert source
VOTE = (225, 50, 150, 255)              # vehicle that has cast a vote (Votes stage only)
MEMBER = (100, 185, 170, 255)           # cluster member (Cluster / CH stage only)
HEAD = (0, 0, 0, 255)                   # ring: cluster head
ROUTE = (122, 70, 200, 255)             # CH-to-CH route hop already traversed
REROUTED = (40, 170, 80, 255)           # vehicle rerouted around the incident edge (reroute=True, after the replay)
IDLE = NEUTRAL                          # older name, kept for callers
RSU_IDLE, RSU_OK, RSU_DUP, RSU_BAD = (170, 178, 190, 255), (16, 150, 72, 255), (150, 205, 165, 255), (210, 40, 40, 255)
STAGES = ["Incident", "Alert", "Cluster / CH", "Votes", "Certificate", "Forwarding / Route", "RSU"]
STAGE_FUTURE, STAGE_DONE, STAGE_NOW = (255, 255, 255, 255), (226, 232, 240, 255), (255, 205, 60, 255)
BIN_MS = 0.5                            # radio time shown per animation frame
LEGEND = [("square", NEUTRAL, "No alert (traffic)"), ("square", HAS, "Holds verified alert"),
          ("square", TX, f"Transmitting (last {BIN_MS:g} ms)"), ("square", CRASH, "Incident / alert source"),
          ("square", VOTE, "Committee vote"), ("square", MEMBER, "Cluster member"),
          ("ring", HEAD, "Cluster head"), ("line", ROUTE, "CH route traversed"),
          ("square", RSU_OK, "RSU registered"), ("square", RSU_DUP, "RSU duplicate copy"),
          ("square", RSU_BAD, "RSU rejected")]
SETTINGS = """<viewsettings>
  <scheme name="alert-demo">
    <background backgroundColor="241,245,250" showGrid="0"/>
    <edges laneShowBorders="1" showLinkDecals="1" streetName_show="0"/>
    <vehicles vehicleQuality="2" vehicle_minSize="1" vehicle_exaggeration="5" vehicleName_show="0"/>
    <pois poi_exaggeration="1" poiName_show="0" poiName_size="42" poiName_color="31,48,68" poiName_constantSize="1"
          poiType_show="0" poiText_show="1" poiTextParam="display_text"
          poiText_size="300" poiText_constantSize="0" poiText_color="31,48,68"/>
    <polys polyName_show="0"/>
  </scheme>
  <delay value="0"/>
</viewsettings>"""
LINK_FRAMES = 3                         # a reception link stays on screen for this many animation frames
CHAR_M = 13.2                           # width of one character of SUMO's POI text at the demo's zoom (measured)
VERIFY_MS = slots_to_ms(ms_to_slots(config.BLS_VERIFY_MS))
_labels = {}


def ring(x, y, r, n=36):
    return [(x + r * math.cos(2 * math.pi * k / n), y + r * math.sin(2 * math.pi * k / n)) for k in range(n + 1)]


def label(key, text, x, y):
    """SUMO-native text (a POI's display_text), centred on (x, y - 21). Every label uses the scheme's poiText_color:
    TraCI cannot colour one label, so states are shown by coloured markers, not by text colour."""
    if key in _labels:
        traci.poi.remove(_labels[key])
    _labels[key] = f'label-{key}'
    traci.poi.add(_labels[key], x, y - 21, (0, 0, 0, 0), layer=120, width=0, height=0)
    traci.poi.setParameter(_labels[key], 'display_text', text)


def left_text(key, text, x, y):
    """Left-aligned text in the side panel (SUMO lays a two-line text out from its left edge)."""
    label(key, text + '\n ', x, y - 21)


# ---------------------------------------------------------------- the workflow indicator and status lines
def _stage_boxes():
    """(x0, x1) of each indicator box: sized to its label, centred above the map."""
    widths = [len(s) * CHAR_M + 36 for s in STAGES]
    total = sum(widths) + 22 * (len(STAGES) - 1)
    x, boxes = 625 - total / 2, []
    for w in widths:
        boxes.append((x, x + w))
        x += w + 22
    return boxes


def indicator_init():
    for i, (name, (x0, x1)) in enumerate(zip(STAGES, _stage_boxes())):
        box = [(x0, 950), (x1, 950), (x1, 990), (x0, 990)]
        traci.polygon.add(f"stage-{i}", box, STAGE_FUTURE, fill=True, layer=100)
        traci.polygon.add(f"stage-edge-{i}", box + [box[0]], (120, 130, 145, 255), fill=False, layer=101, lineWidth=1)
        label(f"stage-label-{i}", name, (x0 + x1) / 2, 977)     # text renders ~14 m above its anchor
        if i:                                                        # a small chevron between boxes
            gx = x0 - 11
            traci.polygon.add(f"stage-arrow-{i}", [(gx - 5, 962), (gx + 5, 970), (gx - 5, 978)],
                              (120, 130, 145, 255), fill=False, layer=101, lineWidth=1.5)


def set_stage(current, rsu_done=False, reached=None):
    """Highlight ONLY the current stage. 'Done' marks a stage that really happened: one shown before (every earlier
    one unless `reached` lists them) or an RSU that already has a copy. A skipped stage, such as Forwarding / Route
    for a forged alert that every receiver rejects, stays white."""
    for i in range(len(STAGES)):
        done = (i in reached if reached is not None else current is not None and i < current) or (i == 6 and rsu_done)
        traci.polygon.setColor(f"stage-{i}", STAGE_NOW if i == current else STAGE_DONE if done else STAGE_FUTURE)


def status(line_a, line_b=""):
    """Two factual lines under the indicator, centred above the map. Never cut: the window shows ~200 characters,
    and a cut line hides its end (e.g. a rejection reason)."""
    label("status-a", line_a, 625, 930)
    label("status-b", line_b, 625, 893)


# ---------------------------------------------------------------- side panel: RSU rows and the legend
def panel_init(rsus, legend=LEGEND):
    traci.polygon.add("panel-card", [(890, 140), (1350, 140), (1350, 872), (890, 872)], (255, 255, 255, 245),
                      fill=True, layer=-1)
    left_text('panel-rsu-title', 'ROADSIDE UNITS', 928, 838)
    for i, u in enumerate(rsus):
        y = 790 - i * 44
        traci.polygon.add(f"rsu-swatch-{u['id']}", [(930, y - 12), (958, y - 12), (958, y + 12), (930, y + 12)],
                          RSU_IDLE, fill=True, layer=111)
        rsu_state(u, RSU_IDLE, "listening")
    left_text('panel-legend-title', 'LEGEND', 928, 700)
    for i, (shape, colour, caption) in enumerate(legend):
        y = 655 - i * 44
        if shape == "square":
            square = [(930, y - 12), (958, y - 12), (958, y + 12), (930, y + 12)]
            traci.polygon.add(f'legend-swatch-{i}', square, colour, fill=True, layer=111)
            traci.polygon.add(f'legend-edge-{i}', square + [square[0]], (90, 90, 90, 255), fill=False, layer=112,
                              lineWidth=1)
        elif shape == "ring":
            traci.polygon.add(f'legend-swatch-{i}', ring(944, y, 12, 14), colour, fill=False, layer=111, lineWidth=2.5)
        else:
            traci.polygon.add(f'legend-swatch-{i}', [(930, y), (958, y)], colour, fill=False, layer=111, lineWidth=4)
        left_text(f'legend-row-{i}', caption, 986, y)


def rsu_state(u, colour, state):
    """An RSU's outcome: its marker on the map and its row in the panel (same colour, full words)."""
    traci.polygon.setColor(f"site-{u['id']}", colour)
    traci.polygon.setColor(f"rsu-swatch-{u['id']}", colour)
    i = 0 if u["id"].endswith("1") else 1
    left_text(f"rsu-row-{u['id']}", f"{u['id']}: {state}", 986, 790 - i * 44)


# ---------------------------------------------------------------- what each recorded dissemination shows
def rsu_outcome(record, rsu_id):
    """(colour, state) one RSU shows for one RECORDED dissemination: the RSU that registered the event, an RSU whose
    copies were duplicates of it, an RSU whose every copy was rejected, or one that decoded nothing."""
    event = record["rsu_event"]
    copies = sorted((r for r in record["rsu_receptions"] if r["rsu"] == rsu_id), key=lambda r: r["delay_ms"])
    if event and event["receiving_rsu"] == rsu_id:
        return RSU_OK, f"registered +{event['delay_ms']:.1f} ms"
    if event and copies:
        return RSU_DUP, f"duplicate +{copies[0]['delay_ms']:.1f} ms"
    if copies:
        return RSU_BAD, "rejected"
    return RSU_IDLE, "listening"


def rsu_summary(record):
    """The RSU stage's status line for one recorded dissemination."""
    event = record["rsu_event"]
    if event:
        dups = event["duplicate_copies"]
        return (f"RSU: {event['receiving_rsu']} decoded it at +{event['arrival_ms']:.1f} ms, verified it and registered it "
                f"at +{event['delay_ms']:.1f} ms" + (f"; {dups} duplicate cop{'y' if dups == 1 else 'ies'}" if dups else ""))
    copies = record["rsu_receptions"]
    if copies:
        reason = copies[0].get("status", "REJECTED").replace("REJECTED: ", "")
        return f"RSU: rejected every copy: {reason}"
    return "RSU: no RSU received the alert"


def counters(P, alert, hi, misbehaving=frozenset()):
    """The counters the replay shows at radio time hi (ms): only events that happened before hi."""
    before = lambda ms: ms is not None and ms < hi
    done = [t for t in P["transmissions"] if t["start_ms"] < hi]
    vs = P["vehicles"]
    return {"reached": sum(before(v["rx_ms"]) for v in vs), "transmissions": len(done),
            "forwarded": max(0, sum(t["kind"] == "ALERT" for t in done) - 1),
            "suppressed": sum(v["decision"] == "SUPPRESS" and before(v["decided_ms"]) for v in vs),
            "rejected": sum(v["decision"] == "REJECT" and before(v["decided_ms"]) for v in vs),
            "collisions": sum(t["lost"] for t in P["transmissions"] if t["end_ms"] < hi),
            # honest = neither the (forging) source nor a misbehaving colluder, exactly like metrics.honest_reached
            "honest": sum(before(v["rx_ms"]) and v["id"] != alert["source_vehicle"] and v["id"] not in misbehaving
                          for v in vs)}


def stage_state(P, alert, hi, finished=False, forged=False, total=None, misbehaving=frozenset()):
    """(stage index into STAGES, status line, RSU-has-a-copy) at radio time hi (ms) of one recorded dissemination.
    Computed only from events that started before hi, so no vote, certificate, relay or RSU outcome can appear
    before it happens; `finished` (after the last recorded event) moves to the RSU stage."""
    c, src = P["corroboration"], alert["source_vehicle"]
    started = sorted((t for t in P["transmissions"] if t["start_ms"] < hi), key=lambda t: t["start_ms"])
    votes = [t for t in started if t["kind"] == "VOTE"]
    released = any(t["kind"] == "ALERT" and t["sender"] == src for t in started)
    # forwarding begins with the first frame of anyone but the source that is not a committee vote: a relayed
    # alert, or a CH-route head's local round (its CPROPOSAL and its members' CVOTEs) before it relays
    moving = [t for t in started if t["sender"] != src and t["kind"] != "VOTE"]
    relays = [t for t in moving if t["kind"] == "ALERT"]
    rsu_copy = any(r["delay_ms"] < hi for r in P["rsu_receptions"])
    n = counters(P, alert, hi, misbehaving)
    total = total if total is not None else len(P["vehicles"])
    if finished:
        if c is not None and not released:
            return 6, f"RSU: nothing to register: the alert never got {config.QUORUM} votes, so it was not released", rsu_copy
        return 6, rsu_summary(P), rsu_copy
    if c is not None and not released:
        who = "colluder vote(s) for a claim honest members cannot see" if forged else \
              f"of {len(c['committee'])} committee members have voted"
        return 3, f"Votes: {len(votes)} {who} (quorum {config.QUORUM})", rsu_copy
    if c is not None and not moving:
        signers = len(c["certificate"]["signers"]) if c["certificate"] else 0
        verdict = "receivers verify it, then accept" if c["accepted"] else f"receivers REJECT it: {c['reason']}"
        return 4, f"Certificate: {signers} BLS signatures in one {config.SIGNATURE_BYTES} B aggregate; {verdict}", rsu_copy
    if forged:
        return 5, f"Forwarding: none; {n['rejected']} receivers rejected it", rsu_copy
    line = (f"Forwarding: {len(relays)} relays  |  {n['reached']}/{total} hold the alert  |  {n['suppressed']} suppressed"
            f"  |  {n['collisions']} receptions lost")
    outcomes = [r["status"].split(":")[0] for r in P["rsu_receptions"] if r["delay_ms"] < hi]
    if outcomes:                                     # every RSU copy so far, counted once its check has finished
        dup, rej = outcomes.count("DUPLICATE"), outcomes.count("REJECTED")
        line += (f"  |  RSU copies: {outcomes.count('REGISTERED')} registered, {dup} duplicate{'' if dup == 1 else 's'}"
                 + (f", {rej} rejected" if rej else ""))
    return 5, line, rsu_copy


def route_progress(P, route, hi):
    """Prefix of the CH route (vehicle IDs ending at an RSU) traversed by radio time hi: a head counts once it has
    ACCEPTED the alert, the RSU once it has decoded a copy. Nothing of the route is shown before that."""
    if not route:
        return []
    rx = {v["id"]: v["rx_ms"] for v in P["vehicles"]}
    arrival = {}
    for r in P["rsu_receptions"]:
        arrival[r["rsu"]] = min(arrival.get(r["rsu"], math.inf), r.get("arrival_ms", r["delay_ms"]))
    done = [route[0]]
    for node in route[1:]:
        t = arrival.get(node) if node.startswith("RSU") else rx.get(node)
        if t is None or not t < hi:
            break
        done.append(node)
    return done


def final_screen(raw, name=None, route_stage=False):
    """Everything the last stage shows, from ONE recorded dissemination: by default the CH-route delivery that
    experiment.run_one stores in the backhaul / dispatch outbox (the proposed scheme if absent). A separated run
    (baseline-only or proposed-only) passes its own scheme as `name`, so it never ends on another approach's outcome;
    it then claims a queued dispatch only if it replayed the record the outbox holds (`route_stage`: the CH-to-CH route
    stage of a proposed-only run). Vehicle colours, RSU markers, the services text, the status lines and the live-feed
    fields always describe the same record."""
    sc = raw["scenario"]
    persisted = "ch_route" if "ch_route" in raw["protocols"] else "proposed"
    record, scheme = raw["protocols"][name or persisted], config.LABELS[name or persisted]
    got = {v["id"] for v in record["vehicles"] if v["rx_ms"] is not None}
    vehicles = {v["id"]: HAS if v["id"] in got else NEUTRAL for v in sc["vehicles"]}
    vehicles[sc["source_id"]] = CRASH
    event = record["rsu_event"]
    if name is None:                                          # the full walkthrough: unchanged
        rsu = f"{event['receiving_rsu']} registered it; dispatch queued locally" if event else "no RSU registered it"
        service = "SERVICES: dispatch queued (local)" if event else "SERVICES: no validated alert"
    else:
        queued = (route_stage or name == persisted) and raw["protocols"][persisted]["rsu_event"] is not None
        rsu = f"{event['receiving_rsu']} registered it" if event else "no RSU registered it"
        service = (("SERVICES: dispatch queued (local)" if name == persisted else "SERVICES: queued via CH route")
                   if queued else "SERVICES: no dispatch recorded")
    reach = f"{len(got)}/{len(sc['vehicles'])} vehicles hold the verified alert"
    # the stages this record went through (Forwarding / Route is skipped when the source reaches the RSU itself)
    reached = {0, 1, 2, 6} | {stage_state(record, sc["alert"], t["start_ms"] + 1e-6)[0] for t in record["transmissions"]}
    return {"scheme": scheme, "vehicles": vehicles, "reach": reach, "rsu": rsu, "reached": reached,
            "rsus": {u["id"]: rsu_outcome(record, u["id"]) for u in sc["rsus"]}, "service": service,
            "banner": (f"Outcome of the {scheme}: {rsu}", f"{reach}  |  traffic continues, the crashed vehicle stays stopped")}


def presentation_settings(path):
    """Configure SUMO-native text; do not load bitmap font decals."""
    root = ET.fromstring(SETTINGS)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def show(text, live):
    if live and sys.stdout.isatty():
        print("\033[H\033[J", end="")
    print(text, flush=True)


def clusters_at(step):
    """(roles, DBSCAN labels) of one second, with the project's own clustering + election code."""
    _, adj = geometry(step["xy"])
    role, _, labels = elect_roles(step["xy"], step["speed"], adj, step["trust"])
    return role, labels


def redraw():
    """Repaint SUMO-GUI WITHOUT a simulation step. Re-setting the view offset to its current value forces a
    repaint (checked on SUMO 1.27.1: polygons, vehicle colours and POI text update, while the clock, every
    position and every speed stay unchanged), so the radio replay runs with the simulation genuinely paused."""
    traci.gui.setOffset(VIEW, *traci.gui.getOffset(VIEW))


LIVE = {}            # separated runs: pair, approach, algorithm, scenario, seed, incident -- added to every live-feed write
CAPTURE = {}         # separated runs: live captures of the SUMO window for the dashboard (capture_dir of run())
CAPTURE_EVERY_S = 3.0


def live_feed(**state):
    """Mirror the live state for the web viewer (GET /api/live), written atomically. If a reader holds the file
    open at that instant (Windows), only this one frame is skipped."""
    path = os.path.join(config.RESULTS_DIR, "live_demo.json")
    data = {**LIVE, **state, "updated": time.time()}
    if LIVE:
        try:
            data["sim_time_s"] = traci.simulation.getTime() - 1.0    # the vehicle state SUMO's Time box shows
        except Exception:                                            # no SUMO connection (yet, or any more)
            pass
    if CAPTURE:
        data["snapshot"] = _live_capture(data)
    try:
        os.makedirs(config.RESULTS_DIR, exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def _live_capture(data):
    """Window captures for the dashboard's live view: one when the scheme or stage changes, then every
    CAPTURE_EVERY_S seconds. Only separated runs capture, and there every caller writes the live feed after it has set
    this state's colours, indicator and status text, so the window is repainted and captured at once: the picture is
    exactly the state its metadata describes. (Capturing at the next feed write showed the NEXT state's indicator and
    text, e.g. a route capture showing the following forged-alert replay.) Returns the newest file name (or None)."""
    c = CAPTURE
    key = (data.get("scheme"), data.get("workflow_stage"))
    if data.get("done") or key != c.get("key") or time.time() - c.get("t", 0) >= CAPTURE_EVERY_S:
        c["key"] = key
        _grab(data)
    return c["files"][-1]["file"] if c.get("files") else None


def _grab(state):
    """One capture (a failed capture or index write only costs this picture, never the run)."""
    c = CAPTURE
    c["t"] = time.time()
    name = f"{len(c['files']) + 1:03d}.png"
    try:
        redraw()                                                     # paint exactly the state being reported,
        time.sleep(0.4)                                              # let the repaint finish (as snap() does)
        if not capture_window(c["pid"], os.path.join(c["dir"], name)):
            return
        c["files"].append({"file": name, "captured": time.time(), **{k: state.get(k) for k in (
            "approach", "scheme", "workflow_stage", "status", "t_ms", "sim_time_s", "done")}})
        with open(os.path.join(c["dir"], "captures.json.tmp"), "w", encoding="utf-8") as f:
            json.dump(c["files"], f, indent=1)
        os.replace(os.path.join(c["dir"], "captures.json.tmp"), os.path.join(c["dir"], "captures.json"))
    except Exception:
        pass


# ---------------------------------------------------------------- snapshots of the live SUMO window
CAPTURE_TIMEOUT_S = 10.0


def bounded(call, timeout):
    """(finished, result) of call() run in a daemon thread for at most `timeout` seconds; an unfinished call is left
    running in its thread and its result is None."""
    import threading
    out = []
    worker = threading.Thread(target=lambda: out.append(call()), daemon=True)
    worker.start()
    worker.join(timeout)
    return (True, out[0]) if out else (False, None)


def capture_window(pid, path):
    """Save the pixels of the SUMO-GUI window owned by process `pid` (Windows PrintWindow: other windows are never
    included; a minimized window is restored first). Returns False where this is not supported."""
    if os.name != "nt":
        return False
    import ctypes
    import ctypes.wintypes as w
    from PIL import Image
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    user32.SetProcessDPIAware()                                     # physical pixels: otherwise the bitmap is clipped
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def visit(h, _):
        owner = w.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(h) and user32.GetWindowTextLengthW(h):
            found.append(h)
        return True
    user32.EnumWindows(visit, 0)
    if not found:
        return False
    h = found[0]
    if user32.IsHungAppWindow(h):                                   # SUMO-GUI not responding: no capture, never a stalled run
        return False
    if user32.IsIconic(h):
        user32.ShowWindow(h, 9)                                     # SW_RESTORE
        time.sleep(0.5)
    r = w.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    width, height = r.right - r.left, r.bottom - r.top
    hdc = user32.GetWindowDC(h)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, width, height)
    gdi32.SelectObject(mdc, bmp)
    # PrintWindow waits for SUMO-GUI's own window thread. Should that thread stop responding (seen once, 14 Nov: a run
    # stalled for 7 min), this capture is skipped after CAPTURE_TIMEOUT_S and the run goes on; the blocked call keeps
    # its GDI handles (a one-off leak) rather than having them freed under it.
    finished, ok = bounded(lambda: user32.PrintWindow(h, mdc, 2), CAPTURE_TIMEOUT_S)   # PW_RENDERFULLCONTENT
    if not finished:
        return False

    class Header(ctypes.Structure):
        _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG), ("biPlanes", w.WORD),
                    ("biBitCount", w.WORD), ("biCompression", w.DWORD), ("biSizeImage", w.DWORD),
                    ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD),
                    ("biClrImportant", w.DWORD)]
    pixels = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(mdc, bmp, 0, height, pixels, ctypes.byref(Header(ctypes.sizeof(Header), width, -height, 1, 32,
                                                                       0, 0, 0, 0, 0, 0)), 0)
    Image.frombuffer("RGBA", (width, height), pixels, "raw", "BGRA", 0, 1).convert("RGB").save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(h, hdc)
    return bool(ok)


SNAPSHOT_ORDER = ["traffic", "incident", "alert", "clusters", "votes", "certificate", "flooding", "forwarding",
                  "duplicates", "rsu", "route", "forged", "final"]


def record_fingerprint(raw):
    """SHA-256 of what a run decides (scenario, every dissemination, the forged-alert test, the CH route); the
    manifest stores it so a document built later can check that the snapshots belong to a given saved record."""
    import hashlib
    core = {k: raw[k] for k in ("scenario", "protocols", "forgery")}
    core["route"] = raw["infrastructure"]["route"]
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()


def write_manifest(folder, meta, entries):
    """snapshots.json (for tools) and snapshots.js (loaded by the static portal, also from file://)."""
    data = {**meta, "snapshots": sorted(entries, key=lambda e: SNAPSHOT_ORDER.index(e["key"]))}
    with open(os.path.join(folder, "snapshots.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    with open(os.path.join(folder, "snapshots.js"), "w", encoding="utf-8") as f:
        f.write("window.SUMO_SNAPSHOTS = " + json.dumps(data) + ";\n")


# ---------------------------------------------------------------- one alert, replayed
def replay(raw, proto="proposed", forged=None, pace=0.35, title="", snap=None, shown=(0, 1, 2)):
    """Animate one simulation's recorded frames with the workflow indicator, then check the totals shown against
    its metrics. `snap(key, stage, caption, radio_ms)` is called at the moments worth a portal snapshot."""
    sc = raw["scenario"]
    P, alert, name = report.pick(raw, proto, forged)
    title = title or name
    pos = {v["id"]: (v["x"], v["y"]) for v in sc["vehicles"]}
    pos.update({u["id"]: (u["x"], u["y"]) for u in sc["rsus"]})
    misbehaving = {v["id"] for v in sc["vehicles"] if v["malicious"]}
    src, total = alert["source_vehicle"], len(sc["vehicles"])
    route = raw["infrastructure"]["route"]["vehicle_ids"] if proto == "ch_route" and not forged else []
    base = {v: NEUTRAL for v in pos if not v.startswith("RSU")}       # what each vehicle shows between its frames
    base[src] = CRASH
    for vid, colour in base.items():
        traci.vehicle.setColor(vid, colour)
    for u in sc["rsus"]:
        rsu_state(u, RSU_IDLE, "listening")
    txs = sorted(P["transmissions"], key=lambda t: t["start_ms"])
    first_rsu = {}
    for rx in sorted(P["rsu_receptions"], key=lambda r: r["delay_ms"]):
        first_rsu.setdefault(rx["rsu"], rx["delay_ms"])
    # the replay ends after the last frame, decision, reception AND RSU registration (each can follow the last frame end)
    end = max([t["end_ms"] for t in txs] + [v["decided_ms"] or 0 for v in P["vehicles"]]
              + [v["rx_ms"] or 0 for v in P["vehicles"]] + [r["delay_ms"] for r in P["rsu_receptions"]])
    quorum = f"; {config.QUORUM} of {config.COMMITTEE_SIZE} needed" if P["corroboration"] else ""
    committee, _, certificate = report.corroboration_lines(P["corroboration"])
    halos, links, drawn_route, drawn_heads, frame, counts, taken = {}, [], [], [], 0, {}, set()
    reached = set(shown)                      # Incident, Alert and (except in a baseline-only run) Cluster / CH precede it
    released_at = next((t["start_ms"] for t in txs if t["kind"] == "ALERT" and t["sender"] == src), None)
    registering = P["rsu_event"]["receiving_rsu"] if P["rsu_event"] else None

    def draw_hops(hi):
        for node in route_progress(P, route, hi)[len(drawn_route) + 1:]:
            prev = route[len(drawn_route)]
            key = f"route-{len(drawn_route)}"
            traci.polygon.add(key, [pos[prev], pos[node]], ROUTE, fill=False, layer=93, lineWidth=4)
            drawn_route.append(key)
            if not node.startswith("RSU"):
                traci.polygon.add(f"route-head-{node}", ring(*pos[node], 20, 18), HEAD, fill=False, layer=110,
                                  lineWidth=2.5)
                drawn_heads.append(f"route-head-{node}")

    def shot(key, stage_index, caption, ms):
        if snap and key not in taken:
            taken.add(key)
            snap(key, STAGES[stage_index], caption, ms, name)      # name: the scheme being replayed

    while frame * BIN_MS <= end + BIN_MS:
        lo, hi = frame * BIN_MS, (frame + 1) * BIN_MS
        shown = min(hi, end)                      # radio time on screen: never past the last recorded event
        frame += 1
        within = lambda ms: ms is not None and lo <= ms < hi
        started = [t for t in txs if within(t["start_ms"])]
        accepted = [v for v in P["vehicles"] if v["from"] and within(v["rx_ms"])]
        decided = [v for v in P["vehicles"] if v["decision"] in ("SUPPRESS", "REJECT") and within(v["decided_ms"])]
        heard = [u for u, ms in first_rsu.items() if within(ms)]
        ended = [t for t in txs if within(t["end_ms"])]               # its losses are counted when it ends
        if not (started or accepted or decided or heard or ended or halos or links):
            continue                                                  # nothing happens in this half millisecond
        for key in [k for k, born in links if frame - born >= LINK_FRAMES]:   # short-lived reception links
            traci.polygon.remove(key)
        links = [(k, born) for k, born in links if frame - born < LINK_FRAMES]
        for key in [k for k, (_, off) in halos.items() if off < lo]:    # its frame left the air before this one:
            sender = key[0]                                           # shown for >= 1 frame, then it clears
            traci.polygon.remove(halos.pop(key)[0])
            if sender in base:
                traci.vehicle.setColor(sender, base[sender])
        if released_at is not None and lo <= released_at < hi:      # the votes are over: voters go quiet again
            for vid, colour in base.items():
                if colour == VOTE:
                    base[vid] = NEUTRAL
                    traci.vehicle.setColor(vid, NEUTRAL)
        for v in accepted:                                            # a link only where the log records a reception
            base[v["id"]] = HAS
            traci.vehicle.setColor(v["id"], HAS)
            key = f"link-{frame}-{v['id']}"
            traci.polygon.add(key, [pos[v["from"]], pos[v["id"]]], (52, 120, 220, 170), fill=False, layer=90,
                              lineWidth=0.8)
            links.append((key, frame))
        for t in started:
            if t["kind"] == "VOTE" or t["kind"].startswith("CVOTE:"):
                base[t["sender"]] = VOTE if t["kind"] == "VOTE" else base[t["sender"]]
            if t["sender"] != src:
                traci.vehicle.setColor(t["sender"], VOTE if "VOTE" in t["kind"] else TX)
            key = f"halo-{frame}-{t['sender']}"
            traci.polygon.add(key, ring(*pos[t["sender"]], 28, 18), VOTE if "VOTE" in t["kind"] else TX,
                              fill=False, layer=95, lineWidth=2)
            halos[(t["sender"], t["start_ms"])] = (key, t["end_ms"])
        for u in heard:                                               # this RSU's first copy is decoded and checked now
            rsu = next(r for r in sc["rsus"] if r["id"] == u)
            rsu_state(rsu, *rsu_outcome(P, u))
        counts = counters(P, alert, hi, misbehaving)
        stage_index, line_a, rsu_done = stage_state(P, alert, hi, forged=bool(forged), total=total,
                                                    misbehaving=misbehaving)
        if stage_index >= 5:                                          # a hop appears once it really happened, and
            draw_hops(hi)                                             # only while the route stage is shown
        if route:
            hops = route_progress(P, route, hi)
            line_a = f"Route: {' -> '.join(hops)}" + ("" if hops[-1].startswith("RSU") else " ...") + \
                     f"  |  {counts['reached']}/{total} hold the alert" if stage_index == 5 else line_a
        released = released_at is not None and released_at < hi
        votes = sum(t["kind"] == "VOTE" for t in txs if t["start_ms"] < hi)   # the committee's; a CH head's local
                                                                               # votes are not part of its quorum
        reached.add(stage_index)
        set_stage(stage_index, rsu_done, reached)
        status(line_a, f"{title}  |  +{shown:.1f} ms radio time  |  {counts['transmissions']} frames  |  t = "
                       f"{sc['incident_time_s']:.0f} s, SUMO clock paused")
        rsu_seen = bool(first_rsu) and min(first_rsu.values()) < hi
        rsu_text, delay, _ = report.rsu_lines(P["rsu_event"], True, not P["rsu_event"]) if rsu_seen else ("listening", "-", "-")
        show(report.panel({
            "scheme": name, "event_id": alert["event_id"], "type": alert["message_type"],
            "status": f"ACTIVE  +{shown:.1f} ms, slow-motion replay: {STAGES[stage_index]}: {line_a}",
            "source": src, "run_id": sc["run_id"], "seed": sc["seed"], "position": alert["incident_position"],
            "time_s": alert["incident_time_s"], "committee": committee, "votes": f"{votes} cast so far{quorum}",
            "certificate": certificate if released else "not yet released", "total": total, **counts,
            "dropped": sum(v["decision"] == "DROP" and v["rx_ms"] is not None and v["rx_ms"] < hi for v in P["vehicles"]),
            "rsu_status": rsu_text, "rsu_delay": delay,
            "rsu_dups": "(counted at the end)" if rsu_seen and P["rsu_event"] else "-"}), live=True)
        reach = f"{counts['honest']} honest vehicles accepted it" if forged else f"{counts['reached']}/{total} have the alert"
        live_feed(run_id=sc["run_id"], event_id=alert["event_id"], scheme=name, forged=bool(forged), t_ms=round(shown, 1),
                  workflow_stage=STAGES[stage_index], status=line_a, stage=line_a, frames=counts["transmissions"],
                  reach=reach, suppressed=counts["suppressed"], collisions=counts["collisions"], rsu=rsu_text, done=False)
        redraw()                                                      # the clock stays paused: no simulation step
        time.sleep(pace)
        if proto == "proposed" and not forged:
            if stage_index == 3 and votes >= 2:
                shot("votes", 3, line_a, shown)
            if stage_index == 4:
                shot("certificate", 4, line_a, shown)
            if stage_index == 5 and counts["reached"] >= total // 2:
                shot("forwarding", 5, line_a, shown)
            if any(rsu_outcome(P, u)[0] == RSU_DUP for u in heard):   # an RSU's first copy is a duplicate
                shot("duplicates", stage_index, line_a, shown)
        elif proto == "flooding" and not forged and stage_index == 5 and counts["reached"] >= total // 2:
            shot("flooding", 5, line_a, shown)
        elif route and registering in heard and stage_index == 5:
            shot("route", 5, line_a, shown)
    # every recorded event has happened: the replay ends on its RSU outcome and its recorded totals
    for key in [k for k, _ in halos.values()] + [k for k, _ in links]:
        traci.polygon.remove(key)
    for vid, colour in base.items():
        traci.vehicle.setColor(vid, NEUTRAL if colour == VOTE else colour)
    counts = counters(P, alert, math.inf, misbehaving)
    stage_index, line_a, rsu_done = stage_state(P, alert, math.inf, finished=True, forged=bool(forged), total=total,
                                                misbehaving=misbehaving)
    set_stage(stage_index, rsu_done, reached)                         # a stage it skipped stays white
    draw_hops(math.inf)                                               # the whole traversed route, at the RSU stage
    reach = f"{counts['honest']} honest vehicles accepted it" if forged else f"{counts['reached']}/{total} have the alert"
    status(line_a, f"{title}  |  done: {counts['transmissions']} frames  |  {reach}  |  {counts['collisions']} receptions lost")
    show(report.run_block(raw, proto, forged), live=True)
    live_feed(run_id=sc["run_id"], event_id=alert["event_id"], scheme=name, forged=bool(forged), t_ms=round(end, 1),
              workflow_stage=STAGES[stage_index], status=line_a, stage=line_a, frames=counts["transmissions"],
              reach=reach, suppressed=counts["suppressed"], collisions=counts["collisions"],
              rsu=report.rsu_lines(P["rsu_event"], True, not P["rsu_event"])[0] if P["rsu_receptions"] else "no copy",
              done=False)
    redraw()
    time.sleep(5 * pace)
    if route:
        shot("route", 6, line_a, end)                             # only if the RSU was not reached during stage 5
    if forged:
        shot("forged", 6, line_a, end)
    elif proto == "proposed":
        shot("rsu", 6, line_a, end)                               # the RSU outcome, once every copy has arrived
    for key in drawn_route + drawn_heads:
        traci.polygon.remove(key)
    m = P["metrics"]
    assert counts["transmissions"] == m["transmissions"] and counts["reached"] == m["received"] \
        and counts["collisions"] == m["collision_losses"], "the replay must end on the experiment's own numbers"
    assert not forged or counts["honest"] == m["honest_reached"], "the forged-alert test must count honest vehicles only"


def run(density=config.DEMO_DENSITY, run_index=config.DEMO_RUN, schemes=("flooding", "proposed", "ch_route"),
        pace=0.35, shots=None, lead_in_s=15, wait=True, forged=True, approach=None, archive=True, check=None,
        capture_dir=None, reroute=False):
    """approach=None: the full walkthrough (every scheme in `schemes` in turn, then the forged alert, ending on the
    CH-route delivery). approach="baseline" / "proposed": a SEPARATED run (demo_pairs.py) that replays only that
    approach's schemes and ends on its own outcome; a baseline run shows no clusters and no forged alert, which belong
    to the proposed method. check(raw) runs before SUMO starts; capture_dir keeps live window captures.
    reroute=True (run.py demo --reroute): once the clock resumes, the stop is detected from live telemetry and the
    vehicles that accepted the proposed scheme's verified alert are rerouted around the incident edge
    (incident_response.py, the same chain as the headless run.py incident).
    The defaults replay the fixed showcase scenario (config.DEMO_DENSITY, DEMO_RUN), labelled as such; every other
    seed has its own incident (scenario.build), which comparison pairs and the experiment matrix use."""
    print("Preparing the scenario: simulating every scheme on this seed (a few seconds)...", flush=True)
    experiment.run_one(density, run_index, archive=archive)       # (re)simulate; identical for the same seed
    raw = experiment.load_raw(f"d{density}_r{run_index:02d}")
    sc = raw["scenario"]
    if check:
        check(raw)
    showcase = approach is None and (density, run_index) == (config.DEMO_DENSITY, config.DEMO_RUN)
    x, y = sc["incident_xy"]
    print(f"Scenario {sc['run_id']} (seed {sc['seed']}): incident {sc['source_id']} at ({x:.0f}, {y:.0f}) m, "
          f"t = {sc['incident_time_s']:.0f} s." + (" This is the fixed showcase scenario (config.DEMO_DENSITY/DEMO_RUN); "
          "-d/-r replay another seed with its own incident." if showcase else ""), flush=True)
    forged = forged and approach != "baseline"
    if shots:
        os.makedirs(shots, exist_ok=True)
        stale = glob.glob(os.path.join(shots, "sumo_[0-9][0-9]_*.png")) + [os.path.join(shots, n) for n in
                                                                        ("snapshots.json", "snapshots.js")]
        for path in stale:                                        # never mix in an earlier run's pictures
            if os.path.isfile(path):
                os.remove(path)
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    error_log = os.path.abspath(os.path.join(config.RESULTS_DIR, 'sumo_gui_errors.log'))
    entries = []
    with tempfile.TemporaryDirectory() as tmp:
        live = build(density, run_index, workdir=tmp, history_s=lead_in_s)   # same seed: identical routes and traffic
        settings = os.path.join(tmp, "view.xml")
        presentation_settings(settings)
        additions = os.path.splitext(NET_FILE)[0].replace(".net", "") + ".add.xml"
        scenery_args = ["--additional-files", additions] if os.path.isfile(additions) else []
        # --quit-on-end: when TraCI closes, SUMO exits by itself and flushes its error log (killing it truncated
        # the log). Warnings stay ON: the only braking warning left comes from the crash itself.
        traci.start([os.path.join(sumo.SUMO_HOME, "bin", "sumo-gui.exe" if os.name == "nt" else "sumo-gui"), "-n", NET_FILE,
                     "-r", os.path.join(tmp, "routes.rou.xml"), "--step-length", "1", "--seed", str(sc["seed"]),
                     "--gui-settings-file", settings, "--start", "--quit-on-end", "true",
                     "--collision.action", "none", "--time-to-teleport", "-1", "--error-log", error_log,
                     "--window-size", "1500,1050"] + scenery_args)
        sumo_process = traci.getConnection('')._process
        if capture_dir:
            os.makedirs(capture_dir, exist_ok=True)
            CAPTURE.update(dir=capture_dir, pid=sumo_process.pid, files=[])
        meta = {"run_id": sc["run_id"], "seed": sc["seed"], "event_id": sc["alert"]["event_id"],
                "incident_time_s": sc["incident_time_s"], "source": sc["source_id"],
                "captured": time.strftime("%Y-%m-%d %H:%M:%S"), "density": density,
                "note": "Pixels of the live SUMO-GUI window during this demo run (PrintWindow). The radio events are "
                        "computed by the experiment engine on this exact SUMO state and animated in slow motion.",
                "record_fingerprint": record_fingerprint(raw),
                "lead_in_s": [live["history"][0]["t"], live["history"][-1]["t"]], "completed": False}

        def sim_time():
            return traci.simulation.getTime() - 1.0                  # the vehicle state SUMO's Time box shows

        def snap(key, stage, caption, radio_ms=None, scheme=None):
            """Capture the live SUMO window for the portal (only with --shots)."""
            if not shots:
                return
            time.sleep(0.4)                                          # let the repaint finish
            name = f"sumo_{SNAPSHOT_ORDER.index(key) + 1:02d}_{key}.png"
            ok = capture_window(sumo_process.pid, os.path.join(shots, name))
            entries.append({"key": key, "stage": stage, "file": name if ok else None,
                            "missing_reason": None if ok else "window capture is only supported on Windows",
                            "run_id": sc["run_id"], "scheme": scheme, "sim_time_s": sim_time(),
                            "radio_ms": None if radio_ms is None else round(radio_ms, 1), "caption": caption})
            write_manifest(shots, meta, entries)

        try:
            traci.gui.setBoundary(VIEW, -120, -90, 1370, 1020)
            _labels.clear()
            traci.vehicletype.setColor("car", NEUTRAL)               # ordinary traffic is quiet grey
            label("disclosure", "Radio is SIMULATED (802.11p model, 300 m range); radio events replayed in slow motion",
                  625, 1032)
            if approach:                                          # what this separated run shows, visible throughout
                label("approach", f"{approach.upper()}-ONLY RUN: {LIVE.get('algorithm') or config.LABELS[schemes[0]]}  |  "
                                  f"scenario {sc['run_id']}  |  seed {sc['seed']}", 625, 1068)
            else:                                                 # the full walkthrough: which scenario it shows
                label("scenario", f"FULL WALKTHROUGH  |  scenario {sc['run_id']}  |  seed {sc['seed']}" +
                      ("  |  fixed showcase scenario (-r N replays another seed)" if showcase else ""), 625, 1068)
            indicator_init()
            set_stage(None)
            for u in sc["rsus"]:
                x, y = u["x"], u["y"]                             # marker on the block corner, beside the junction
                traci.polygon.add(f"site-{u['id']}", [(x + 12, y + 12), (x + 52, y + 12), (x + 52, y + 52), (x + 12, y + 52)],
                                  RSU_IDLE, fill=True, layer=96)
                traci.polygon.add(f"range-{u['id']}", ring(x, y, config.COMM_RANGE_M), (205, 210, 218, 255), fill=False,
                                  layer=80, lineWidth=0.6)
                label(f"rsu-name-{u['id']}", u["id"], x + 100, y + 54)
            # a baseline-only run never draws clusters, cluster heads or a CH route: its legend omits them
            panel_init(sc["rsus"], *([[r for r in LEGEND if r[1] not in (MEMBER, HEAD, ROUTE)]] if approach == "baseline" else []))
            # Explicitly model infrastructure sites; these do not imply live cloud services.
            traci.polygon.add('emergency-centre', [(910, -30), (1060, -30), (1060, 60), (910, 60)],
                              (226, 235, 248, 255), fill=True, layer=96)
            left_text('service', 'SERVICES: local outbox', 1075, 15)   # starts right of the box at any length
            traci.polygon.add('hospital-cross-h', [(915, 2), (955, 2), (955, 12), (915, 12)], CRASH, fill=True, layer=97)
            traci.polygon.add('hospital-cross-v', [(930, -13), (940, -13), (940, 27), (930, 27)], CRASH, fill=True, layer=97)

            redraw()                       # one viewport for the whole run (the first repaint used to re-zoom the view)
            # live traffic: no stage is active yet. FCD timestep t is the TraCI state once the clock reads t + 1.
            print(f"Normal traffic: {density} vehicles, {len(sc['rsus'])} RSUs.", flush=True)
            lead = "Live SUMO traffic: vehicles drive normally; no alert exists yet"
            for k, step in enumerate(live["history"]):
                traci.simulationStep(step["t"] + 1)
                status(lead, f"run {sc['run_id']}  |  seed {sc['seed']}  |  t = {step['t']:.0f} s")
                live_feed(run_id=sc["run_id"], scheme="live SUMO traffic", workflow_stage="live traffic",
                          status="no alert yet", stage=f"t = {step['t']:.0f} s, live traffic", done=False)
                time.sleep(pace)
                if k == len(live["history"]) // 2:                   # normal traffic, seconds before the incident
                    redraw()                                         # show this step's status text
                    snap("traffic", "Live traffic", lead)

            # the GUI must show exactly the snapshot, and the clustering, that the experiment used
            role, labels = clusters_at(live["history"][-1])
            ids = [v["id"] for v in sc["vehicles"]]
            now = np.array([traci.vehicle.getPosition(v) for v in ids])
            drift = float(np.abs(now - np.array([[v["x"], v["y"]] for v in sc["vehicles"]])).max())
            assert set(traci.vehicle.getIDList()) == set(ids) and drift < 0.05, f"GUI differs from the recorded run ({drift} m)"
            assert list(labels) == [v["dbscan"] for v in sc["vehicles"]] and list(role) == [v["role"] for v in sc["vehicles"]], \
                "the clusters shown must be the ones the experiment used"
            paused_at = traci.simulation.getTime()
            clock = f"run {sc['run_id']}  |  t = {sc['incident_time_s']:.0f} s, SUMO clock paused for the radio replay"

            def hold(stage_index, line_a, key, frames=4):
                set_stage(stage_index)
                status(line_a, clock)
                live_feed(run_id=sc["run_id"], event_id=sc["alert"]["event_id"], scheme="incident",
                          workflow_stage=STAGES[stage_index], status=line_a, stage=line_a, done=False)
                redraw()
                time.sleep(frames * pace)
                snap(key, STAGES[stage_index], line_a)

            # 1 Incident. From here until every replay has ended the clock is PAUSED: no simulationStep, only
            # redraw(), so no vehicle is forced to stop (the old speed-0 freeze caused 97 braking warnings).
            x, y = sc["incident_xy"]
            traci.vehicle.setColor(sc["source_id"], CRASH)
            traci.polygon.add("accident-site", ring(x, y, 22, 16), CRASH, fill=True, layer=94)
            hold(0, f"Incident: {sc['source_id']} crashes at ({x:.0f}, {y:.0f}) m at t = {sc['incident_time_s']:.0f} s "
                    f"(staged incident)", "incident")
            print(f"\nINCIDENT at t = {sc['incident_time_s']:.0f} s: vehicle {sc['source_id']} at ({x:.0f}, {y:.0f}). "
                  f"SUMO's clock is paused while the radio events (tens of ms) are replayed in slow motion.", flush=True)
            # 2 Alert
            a = sc["alert"]
            hold(1, f"Alert {a['event_id']} created by {a['source_vehicle']}: type {a['message_type']}, hop limit "
                    f"{a['hop_limit']}", "alert")
            # 3 Cluster / CH: the clusters and heads of this very second (asserted equal to the recorded ones). They
            # belong to the proposed method, so a baseline-only run does not show them (the stage stays white).
            if approach != "baseline":
                heads = [ids[i] for i in range(len(ids)) if role[i] == "CH"]
                for i, vid in enumerate(ids):
                    if vid != sc["source_id"]:
                        traci.vehicle.setColor(vid, MEMBER if labels[i] != -1 else NEUTRAL)
                for i, vid in enumerate(ids):
                    if role[i] == "CH":
                        traci.polygon.add(f"ch-{vid}", ring(*now[i], 20, 18), HEAD, fill=False, layer=110, lineWidth=2.5)
                hold(2, f"Cluster / CH: {len(set(labels) - {-1})} clusters (DBSCAN {config.DBSCAN_EPS_M:.0f} m), "
                        f"{len(heads)} cluster heads (trust >= {config.TRUST_CH_THRESHOLD}), {int((labels == -1).sum())} "
                        f"isolated", "clusters", frames=8)
                for vid in heads:
                    traci.polygon.remove(f"ch-{vid}")
                for vid in ids:
                    traci.vehicle.setColor(vid, CRASH if vid == sc["source_id"] else NEUTRAL)

            # 4-7, for each scheme on the same accident (a separated run: only its own approach's schemes)
            for k, proto in enumerate(schemes, 1):
                title = (f"{approach.upper()}-ONLY: {'CH-to-CH route stage' if proto == 'ch_route' else config.LABELS[proto]}"
                         if approach else f"{config.LABELS[proto]} ({k} of {len(schemes)})")
                replay(raw, proto, None, pace, title, snap, (0, 1) if approach == "baseline" else (0, 1, 2))

            # a forged alert on the same traffic (a misbehaving vehicle claims an accident that did not happen)
            if forged and raw.get("forgery"):
                fx, fy = raw["forgery"]["alert"]["incident_position"]
                traci.polygon.setShape("accident-site", ring(fx, fy, 22, 16))
                set_stage(0)
                status(f"Forged alert test: {raw['forgery']['forger']} claims an accident that did not happen", clock)
                redraw()
                time.sleep(4 * pace)
                replay(raw, forged="voting_reputation", pace=pace, title="FORGED alert test (full protection)", snap=snap)
                traci.polygon.setShape("accident-site", ring(x, y, 22, 16))
            assert traci.simulation.getTime() == paused_at, "the replay must not advance the SUMO clock"

            # the clock resumes. One recorded dissemination (final_screen) drives every overlay; only the crashed
            # vehicle stops (deliberately abrupt; SUMO may report it as emergency braking). Every other vehicle
            # keeps its own speed and reacts to the obstacle by car-following.
            screen = final_screen(raw, schemes[0], "ch_route" in schemes) if approach else final_screen(raw)
            for vid, colour in screen["vehicles"].items():
                traci.vehicle.setColor(vid, colour)
            response = None
            if reroute:                    # the headless chain of run.py incident, on this window's live traffic
                detector = incident_response.StopDetector(traci)
                detector.update()          # every vehicle's speed at the paused incident snapshot
                response = incident_response.Response(traci, raw, dict(zip(live["ids"], live["trust"])), detector)
            incident_response.crash(traci, sc["source_id"])
            for u in sc["rsus"]:
                rsu_state(u, *screen["rsus"][u["id"]])
            left_text('service', screen["service"], 1075, 15)
            set_stage(6, True, screen["reached"] - ({2} if approach == "baseline" else set()))

            def banner():
                if response and response.watch:
                    r = response.result()
                    n = {k: sum(v["outcome"] == k for v in r["vehicles"]) for k in ("rerouted", "no_alternative")}
                    line_b = (f"stop detected from live telemetry: {n['rerouted']} alert holders rerouted around "
                              f"{r['detection']['edge']} (green), {n['no_alternative']} without an alternative"
                              if r["released"] else "stop NOT detected from telemetry: no alert released, nobody rerouted")
                    status(screen["banner"][0], f"{line_b}  |  t = {sim_time():.0f} s")
                    return
                status(screen["banner"][0], f"{screen['reach']}  |  t = {sim_time():.0f} s, clock running again: "
                                            f"only the crashed vehicle stays stopped")
            if approach:          # a separated run captures this state at once (live_feed): its own banner goes up first
                banner()
            live_feed(run_id=sc["run_id"], event_id=sc["alert"]["event_id"], scheme=screen["scheme"],
                      workflow_stage="RSU", status=screen["banner"][0], stage="traffic continues (clock resumed)",
                      reach=screen["reach"], rsu=screen["rsu"], done=False)
            for k in range(20):
                traci.simulationStep()
                if response:
                    response.step()
                    if k == 0:
                        for v in response.result()["vehicles"]:
                            if v["outcome"] == "rerouted":
                                traci.vehicle.setColor(v["id"], REROUTED)
                banner()
                time.sleep(pace / 3)
                if k == 5:
                    snap("final", "RSU", screen["banner"][0], None, screen["scheme"])   # = status line a
            if response:
                r = response.result()
                entries = sum(v["entries_onto_incident_edge"] for v in r["vehicles"] if v["outcome"] == "rerouted")
                print(f"Incident response: detected {r['released']}; rerouted "
                      f"{sum(v['outcome'] == 'rerouted' for v in r['vehicles'])}, no alternative "
                      f"{[v['id'] for v in r['vehicles'] if v['outcome'] == 'no_alternative']}; entries onto the incident "
                      f"edge by rerouted vehicles in {r['followup']['steps']} s: {entries}", flush=True)
            live_feed(run_id=sc["run_id"], event_id=sc["alert"]["event_id"], scheme=screen["scheme"], workflow_stage="RSU",
                      status=screen["banner"][0],
                      stage=f"finished, recorded totals verified; {screen['scheme']}: {screen['rsu']}",
                      reach=screen["reach"], rsu=screen["rsu"], done=True)
            if wait and sys.stdin.isatty():
                input("\nDemo finished. Press Enter to close SUMO-GUI.")
        except traci.exceptions.FatalTraCIError as exc:
            raise RuntimeError(f'SUMO closed during replay. Keep the SUMO window open until the demo finishes. '
                               f'Diagnostic log: {error_log}') from exc
        finally:
            CAPTURE.clear()
            try:
                traci.close(wait=False)
            except traci.exceptions.FatalTraCIError:
                pass  # preserve the original failure when SUMO has already disconnected
            finally:
                if sumo_process is not None:
                    try:
                        sumo_process.wait(timeout=15)             # --quit-on-end: a clean exit flushes the log
                    except subprocess.TimeoutExpired:
                        sumo_process.terminate()
                        try:
                            sumo_process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            sumo_process.kill()
                            sumo_process.wait()
    if shots:                     # only reached when every stage ran and every replay check passed: keep the run's own
        meta["completed"] = True  # evidence (SUMO's log, now complete) with the snapshots, not only in RESULTS_DIR
        if os.path.exists(error_log):
            with open(error_log, encoding="utf-8", errors="replace") as f:
                meta["sumo_log"] = [line.strip() for line in f if line.strip()]
        write_manifest(shots, meta, entries)
    return raw
