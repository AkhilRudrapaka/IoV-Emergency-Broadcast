"""
One run = one SUMO mobility scenario with exactly ONE incident.

A single seed fixes everything random in the run: the vehicles' routes and
departure times, which vehicles misbehave, SUMO's driver imperfection, the
watchdog's observation noise, the incident time and the incident vehicle.
Same seed -> same scenario (tests/test_pipeline.py checks this).
"""
import os
import random
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import numpy as np
import sumo

from config import (NET_FILE, BASE_SEED, DEPART_WINDOW_S, ROUTE_EDGES, INCIDENT_WINDOW_S,
                    MALICIOUS_RATIO, WATCHDOG_MISS_PROB, COMM_RANGE_M, HOP_LIMIT)
from clustering import beta_trust

SUMO_BIN = os.path.join(sumo.SUMO_HOME, "bin", "sumo.exe" if os.name == "nt" else "sumo")


def seed_for(density, run):
    return BASE_SEED + 100 * density + run


def _road_graph():
    root = ET.parse(NET_FILE).getroot()
    ends = {e.get("id"): (e.get("from"), e.get("to"))
            for e in root.findall("edge") if e.get("function") != "internal"}
    nxt = {}
    for c in root.findall("connection"):
        if c.get("from") in ends and c.get("to") in ends:
            nxt.setdefault(c.get("from"), set()).add(c.get("to"))
    # Bounding box of the drivable lanes (not of the junction centres: border lanes lie outside those).
    pts = [tuple(map(float, p.split(","))) for e in root.findall("edge") for lane in e.findall("lane")
           for p in lane.get("shape").split()]
    half = max(float(lane.get("width", 3.2)) for e in root.findall("edge") for lane in e.findall("lane")) / 2
    bounds = (min(x for x, _ in pts) - half, min(y for _, y in pts) - half,
              max(x for x, _ in pts) + half, max(y for _, y in pts) + half)
    # sorted everywhere: set order of strings changes between Python processes
    return sorted(nxt), {k: sorted(v) for k, v in nxt.items()}, ends, bounds


EDGES, NEXT, ENDS, BOUNDS = _road_graph()       # BOUNDS = (xmin, ymin, xmax, ymax) of the road network


def write_routes(path, n, rng):
    """n vehicles, departures ~ U(0, DEPART_WINDOW_S), random-walk routes without U-turns."""
    lines = ['<routes>', '  <vType id="car"/>']                  # SUMO default passenger car (Krauss)
    for i, dep in enumerate(sorted(rng.uniform(0, DEPART_WINDOW_S) for _ in range(n))):
        route = [rng.choice(EDGES)]
        while len(route) < ROUTE_EDGES:
            here = route[-1]
            opts = [e for e in NEXT.get(here, []) if ENDS[e][1] != ENDS[here][0]] or NEXT.get(here, [])
            if not opts:
                break
            route.append(rng.choice(opts))
        lines.append(f'  <vehicle id="v{i}" type="car" depart="{dep:.2f}" departLane="best">'
                     f'<route edges="{" ".join(route)}"/></vehicle>')
    lines.append('</routes>')
    with open(path, "w") as f:
        f.write("\n".join(lines))


def run_sumo(routes, seed, end_s, fcd):
    subprocess.run([SUMO_BIN, "-n", NET_FILE, "-r", routes, "--begin", "0", "--end", str(end_s),
                    "--step-length", "1", "--seed", str(seed), "--fcd-output", fcd,
                    "--no-step-log", "true", "--no-warnings", "true", "--duration-log.disable", "true"],
                   check=True, capture_output=True)


def read_fcd(fcd):
    """Yields (time, ids, xy, speed, angle, lane) per 1 s step, vehicles sorted by id."""
    for _, ts in ET.iterparse(fcd):
        if ts.tag != "timestep":
            continue
        vs = sorted(ts.findall("vehicle"), key=lambda v: int(v.get("id")[1:]))
        yield (float(ts.get("time")),
               [v.get("id") for v in vs],
               np.array([[float(v.get("x")), float(v.get("y"))] for v in vs]).reshape(-1, 2),
               np.array([float(v.get("speed")) for v in vs]),
               np.array([float(v.get("angle")) for v in vs]),
               [v.get("lane") for v in vs])
        ts.clear()


def create_alert(seed, source_id, position, time_s, sequence_number=1):
    """The emergency packet. Identified like an ETSI DENM actionID: originating station +
    sequence number (EN 302 637-3). One alert per event; relays copy it unchanged except
    for the hop count carried by each frame."""
    return {
        "event_id": f"EVT-{seed}-{source_id}-{sequence_number}",
        "message_type": "ACCIDENT",
        "source_vehicle": source_id,
        "sequence_number": sequence_number,
        "incident_position": [round(float(c), 2) for c in position],
        "incident_time_s": time_s,          # detection time
        "created_s": time_s,                # the alert is generated the instant the crash is detected
        "hop_limit": HOP_LIMIT,
    }


def build(density, run, workdir=None, history_s=0):
    """history_s > 0 also returns the last seconds of traffic (ids, positions, speeds and
    the reputation known at each second), which the SUMO-GUI demo uses to show clustering."""
    seed = seed_for(density, run)
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)
    malicious_ids = set(f"v{i}" for i in rng.sample(range(density), round(MALICIOUS_RATIO * density)))
    t_incident = rng.randint(*INCIDENT_WINDOW_S)

    with tempfile.TemporaryDirectory() as tmp:
        work = workdir or tmp
        routes, fcd = os.path.join(work, "routes.rou.xml"), os.path.join(tmp, "fcd.xml")
        write_routes(routes, density, rng)
        run_sumo(routes, seed, t_incident + 1, fcd)

        # Watchdog trust: once per 1 s beacon period, every vehicle that has at
        # least one neighbour is observed relaying (or not) by that neighbour.
        ok, bad, history = {}, {}, []
        for t, ids, xy, speed, angle, lane in read_fcd(fcd):
            if len(ids) > 1:
                d = np.hypot(xy[:, 0, None] - xy[None, :, 0], xy[:, 1, None] - xy[None, :, 1])
                seen = (d <= COMM_RANGE_M).sum(1) > 1
            else:
                seen = np.zeros(len(ids), bool)
            miss = np_rng.random(len(ids)) < WATCHDOG_MISS_PROB
            for i, vid in enumerate(ids):
                if seen[i]:
                    failed = vid in malicious_ids or miss[i]
                    bad[vid] = bad.get(vid, 0) + failed
                    ok[vid] = ok.get(vid, 0) + (not failed)
            last = (t, ids, xy, speed, angle, lane)
            if t > t_incident - history_s:
                history.append({"t": t, "ids": ids, "xy": xy, "speed": speed,
                                "trust": np.array([beta_trust(ok.get(v, 0), bad.get(v, 0)) for v in ids])})

    t, ids, xy, speed, angle, lane = last
    assert t == t_incident, f"SUMO stopped at {t}, expected incident step {t_incident}"
    malicious = np.array([v in malicious_ids for v in ids])
    source = ids.index(rng.choice([v for v, m in zip(ids, malicious) if not m]))   # the ONE incident
    return {
        "run_id": f"d{density}_r{run:02d}", "density": density, "run": run, "seed": seed,
        "incident_time_s": t, "source": source, "source_id": ids[source],
        "incident_xy": [round(float(c), 2) for c in xy[source]], "incident_lane": lane[source],
        "ids": ids, "xy": xy, "speed": speed, "angle": angle, "lane": lane, "malicious": malicious,
        "trust": np.array([beta_trust(ok.get(v, 0), bad.get(v, 0)) for v in ids]),
        "alert": create_alert(seed, ids[source], xy[source], t),
        "history": history,
    }
