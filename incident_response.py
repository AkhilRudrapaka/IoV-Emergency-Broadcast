"""
End-to-end incident response on live SUMO traffic (TraCI), on top of the unchanged communication pipeline:

  staged abrupt stop -> on-board detection from live telemetry -> the recorded alert is released only for a
  detection that binds to it -> committee + BLS certificate (the experiment's record, re-checked here with
  corroboration.accept) -> vehicles that accepted it and whose route still crosses the incident edge -> TraCI
  rerouting to the same destination -> follow-up window: rerouted vehicles must never drive onto the incident edge.

Rerouting methods (config.REROUTE_METHOD): "detour" (default) bypasses the incident edge and rejoins the vehicle's own
remaining route after it (detour()); "shortest" replaces the whole remaining route by the travel-time shortest path to
the destination (reroute(), the earlier method, kept as the comparison baseline); "none" reroutes nobody (scenario B of
incident_routing.py).

The dissemination is experiment.run_one's record for this seed, computed on the SUMO snapshot of the incident second,
so the radio, trust, clustering and security code is used as it is. A forged-alert session on the same traffic is the
negative control: the full protection rejects that alert, so it must change no route.
The incident is staged (TraCI stops the vehicle); it is not a SUMO collision. Simulation only.
"""
import csv
import gzip
import json
import os
import sys
import tempfile
import time
from multiprocessing import Pool

import numpy as np
import traci

import config
import corroboration
import experiment
from scenario import SUMO_BIN, build, decision_trust

STEP_S = 1.0                              # every SUMO run in this project uses --step-length 1
OUT = os.path.join("results", "incident")  # never the tracked results/urban


def crash(tc, vid):
    """The staged incident: vid stops dead within one step and stays there (speed and lane-change checks off)."""
    tc.vehicle.setSpeedMode(vid, 0)
    tc.vehicle.setLaneChangeMode(vid, 0)
    tc.vehicle.setSpeed(vid, 0)


class StopDetector:
    """On-board impact trigger that every vehicle runs on its own speed, each step: the speed fell by more than its
    vehicle type's emergency deceleration (+ CRASH_DECEL_MARGIN) within one step and it is now at standstill.
    SUMO's car-following never brakes harder than emergencyDecel, so ordinary braking cannot trigger it."""

    def __init__(self, tc):
        self.tc, self.prev, self.limit, self.events = tc, {}, {}, []

    def update(self):
        """Read the state SUMO has just computed; returns this step's new detections."""
        tc, speeds, new = self.tc, {}, []
        t = tc.simulation.getTime() - STEP_S        # the state's own time (FCD time t = TraCI clock t + 1)
        for v in tc.vehicle.getIDList():
            s = speeds[v] = tc.vehicle.getSpeed(v)
            if v not in self.prev:
                continue
            if v not in self.limit:
                self.limit[v] = tc.vehicletype.getEmergencyDecel(tc.vehicle.getTypeID(v)) + config.CRASH_DECEL_MARGIN
            drop = self.prev[v] - s
            if drop > self.limit[v] * STEP_S and s <= config.CRASH_STOP_SPEED:
                x, y = tc.vehicle.getPosition(v)
                new.append({"t_s": t, "vehicle": v, "speed_drop_mps": round(drop, 3), "speed_mps": round(s, 3),
                            "threshold_mps2": self.limit[v], "edge": tc.vehicle.getRoadID(v),
                            "lane": tc.vehicle.getLaneID(v), "lane_pos_m": round(tc.vehicle.getLanePosition(v), 2),
                            "xy": [round(x, 2), round(y, 2)]})
        self.prev = speeds
        self.events += new
        return new


def bind(detections, alert):
    """The recorded alert (its dissemination, committee and certificate) is released only for a detection of its own
    source vehicle within one step of the snapshot that dissemination was computed on. No detection: no alert."""
    return next((d for d in detections if d["vehicle"] == alert["source_vehicle"]
                 and 0 <= d["t_s"] - alert["created_s"] <= STEP_S), None)


def holders(record, alert):
    """Vehicles that took the alert in, certificate or not (the source excluded)."""
    return [v["id"] for v in record["vehicles"] if v["rx_ms"] is not None and v["id"] != alert["source_vehicle"]]


def accepted_by(record, alert, trust):
    """Vehicles that accepted the alert through the certificate + committee check: the recorded certificate must be
    accepted AND verify again here (corroboration.accept, the rule every receiver applies); then only the vehicles
    whose own check passed. No certificate (no voting) or a rejected one: nobody. Returns (ids, check)."""
    c = record["corroboration"]
    if c is None:
        return [], {"recorded": None, "reverified": False, "reason": "no certificate"}
    enforced = (c["committee"],) if config.ENFORCE_COMMITTEE else ()   # Block G: the committee the simulator rebuilt;
    ok, reason = corroboration.accept(alert, c["certificate"], trust.get, c["use_reputation"], *enforced)   # default: as before
    check = {"recorded": c["accepted"], "reverified": ok, "reason": reason}
    if not (ok and c["accepted"]):
        return [], check
    return [v["id"] for v in record["vehicles"] if v["verified"] and v["rx_ms"] is not None
            and v["id"] != alert["source_vehicle"]], check


def upcoming(tc, v):
    """Edges v has still to enter (the edge it is on, or the edge before the junction it is crossing, excluded)."""
    return tc.vehicle.getRoute(v)[tc.vehicle.getRouteIndex(v) + 1:]


def crossing(tc, edge, stop_pos, exclude):
    """Every live vehicle whose path crosses the incident: 'upstream' = already on the incident edge behind the stop
    (it cannot avoid the edge any more), 'ahead' = the incident edge is still in its route. Returns {id: (where, road)}."""
    out = {}
    for v in tc.vehicle.getIDList():
        road = tc.vehicle.getRoadID(v)
        if v in exclude:
            continue
        if road == edge and tc.vehicle.getLanePosition(v) < stop_pos:
            out[v] = "upstream", road
        elif edge in upcoming(tc, v):
            out[v] = "ahead", road
    return out


def reroute(tc, v, edge):
    """v learns that the incident edge is practically closed (its own travel-time knowledge only) and reroutes by
    travel time to its unchanged destination. Returns (outcome, reason, destination)."""
    dest = tc.vehicle.getRoute(v)[-1]
    if dest == edge:
        return "no_alternative", "its destination is the incident edge", dest
    tc.vehicle.setAdaptedTraveltime(v, edge, config.BLOCKED_EDGE_TT_S)
    tc.vehicle.rerouteTraveltime(v, False)                  # False: no global edge-weight storage, nothing shared
    if tc.vehicle.getRoute(v)[-1] != dest:
        return "destination_changed", "SUMO changed the destination", dest
    if edge in upcoming(tc, v):          # e.g. on the junction into it, or too close to the junction to turn elsewhere
        return "no_alternative", "SUMO's reroute from its position still uses the incident edge", dest
    return "rerouted", "", dest


def remaining(tc, v):
    """The route still to drive: [current edge (or the edge before the junction being crossed), ...]."""
    return list(tc.vehicle.getRoute(v)[tc.vehicle.getRouteIndex(v):])


def planned_m(tc, edges):
    """Length (m) of the edges still to enter (edges[0] excluded; junction-internal lanes not counted)."""
    return round(sum(tc.lane.getLength(e + "_0") for e in edges[1:]), 2)


def _probe(tc, v, edge, target):
    """The vehicle's own router from where it is now: it keeps the next edge when the vehicle is too close to the
    junction to turn elsewhere (SUMO's own rule), so a detour never forces a last-second turn. Transactional: the
    route and the travel-time knowledge are restored before returning, and the restoration is checked."""
    keep = remaining(tc, v)
    tc.vehicle.setAdaptedTraveltime(v, edge, config.BLOCKED_EDGE_TT_S)
    try:
        tc.vehicle.changeTarget(v, target)
        path = remaining(tc, v)
    except traci.TraCIException:
        path = None
    tc.vehicle.setRoute(v, keep)
    tc.vehicle.setAdaptedTraveltime(v, edge)                 # no value: SUMO removes the entry again
    if remaining(tc, v) != keep:
        raise RuntimeError(f"{v}: a route probe could not be undone")
    return path


def verify(R, new, orig, edge, splices):
    """Why `new` cannot replace the remaining route R ([] = it can). orig[i] = index in R of new[i] (None: detour)."""
    kept = [(i, o) for i, o in enumerate(orig) if o is not None]
    s0, jl = splices[0]["split_index"], splices[-1]["rejoin_index"]
    checks = {"does not start on the current edge": new[0] != R[0],
              "destination changed": new[-1] != R[-1] or orig[-1] != len(R) - 1,
              "incident edge still ahead": edge in new[1:],
              "an edge repeated back to back": any(a == b for a, b in zip(new, new[1:])),
              "kept original edges altered or out of order": any(new[i] != R[o] for i, o in kept)
                                                             or [o for _, o in kept] != sorted({o for _, o in kept}),
              "prefix up to the first split not kept": orig[:s0 + 1] != list(range(s0 + 1)),
              "suffix from the last rejoin not kept": orig[len(orig) - (len(R) - jl):] != list(range(jl, len(R)))}
    return [k for k, bad in checks.items() if bad]


def detour(tc, v, edge):
    """Route-preserving detour around every future occurrence of the incident edge: keep the remaining route up to a
    split edge before it, bypass it with SUMO's router, rejoin the original route at an edge after it. Splits are tried
    from the latest (longest kept prefix), rejoins from the earliest (longest kept suffix); every position is a route
    index, never an edge-value lookup. A split at the edge the vehicle is on uses the vehicle's own router (_probe);
    inside a junction the next edge is fixed, so the earliest split is the edge after it. Later splits use
    simulation.findRoute, which sees the incident edge through the global weight respond() sets for this method.
    Nothing is installed unless the whole route passes verify() and SUMO's own check.
    Returns (outcome, reason, info): info holds the original and final routes, every splice and the probe count."""
    R = remaining(tc, v)
    info = {"original_route": R, "final_route": R, "splices": [], "probes": 0}
    if R[-1] == edge:
        return "no_alternative", "its destination is the incident edge", info
    first = 1 if tc.vehicle.getRoadID(v).startswith(":") else 0
    vtype = tc.vehicle.getTypeID(v)
    new, orig, pos = list(R), list(range(len(R))), 0
    while (k := next((i for i in range(pos + 1, len(new)) if new[i] == edge), None)) is not None:
        found = None
        for s in range(k - 1, max(pos, first) - 1, -1):
            for j in range(k + 1, len(new)):
                if new[j] in (edge, new[s]):
                    continue
                info["probes"] += 1
                path = _probe(tc, v, edge, new[j]) if s == 0 else list(tc.simulation.findRoute(new[s], new[j], vtype).edges)
                if path and path[0] == new[s] and path[-1] == new[j] and edge not in path:
                    found = s, j, path
                    break
            if found:
                break
        if found is None:
            return "no_alternative", ("committed: crossing the junction onto the incident edge" if first and k == 1 else
                                      "no detour from any split before the incident edge to any rejoin after it (too "
                                      "close to the junction to turn elsewhere, or the incident edge is the only exit)"), info
        s, j, path = found
        info["splices"].append({"split_index": orig[s], "split_edge": new[s], "rejoin_index": orig[j],
                                "rejoin_edge": new[j], "detour_edges": path[1:-1], "replaced_edges": new[s + 1:j]})
        new, orig = new[:s] + path + new[j + 1:], orig[:s + 1] + [None] * (len(path) - 2) + orig[j:]
        pos = s + len(path) - 1                                  # the rejoin edge's index in the new route
    problems = verify(R, new, orig, edge, info["splices"])
    if problems:
        return "no_alternative", "rejected before install: " + "; ".join(problems), info
    try:
        tc.vehicle.setRoute(v, new)
    except traci.TraCIException as exc:
        if remaining(tc, v) != R:
            raise RuntimeError(f"{v}: a refused route changed the vehicle") from exc
        return "no_alternative", f"SUMO refused the route: {exc}", info
    if remaining(tc, v) != new or not tc.vehicle.isRouteValid(v):
        tc.vehicle.setRoute(v, R)
        return "no_alternative", "SUMO installed a different or invalid route: original route restored", info
    info["final_route"] = new
    return "rerouted", "", info


def preserved(row, edge):
    """Re-check a detour from its record alone: rebuilding it from the original route and the recorded splices gives
    the final route, which keeps the current edge and the destination and never again uses the incident edge."""
    R, F, out, at = row["original_route"], row["final_route"], [], 0
    for x in row["splices"]:
        if R[x["split_index"] + 1:x["rejoin_index"]] != x["replaced_edges"]:
            return False
        out += R[at:x["split_index"] + 1] + x["detour_edges"]
        at = x["rejoin_index"]
    return out + R[at:] == F and F[0] == R[0] and F[-1] == R[-1] and edge not in F[1:]


def respond(tc, alert, record, edge, stop_pos, trust, method=None):
    """Rerouting decision for every vehicle whose path crosses `edge`, given `record` (this alert's dissemination).
    Only a vehicle that accepted the alert is told anything; every other one keeps its route and is listed.
    method: "detour" | "shortest" | "none" (default config.REROUTE_METHOD)."""
    method = method or config.REROUTE_METHOD
    accepted, check = accepted_by(record, alert, trust)
    rows, timing = [], {}
    if edge.startswith(":"):
        return {"certificate": check, "alert_accepted_by": len(accepted), "method": method, "vehicles": rows,
                "note": "stop on a junction-internal lane: edge rerouting not supported, nobody rerouted"}
    told = set(accepted)
    paths = crossing(tc, edge, stop_pos, {alert["source_vehicle"]})
    before = {v: tc.vehicle.getRoute(v) for v in tc.vehicle.getIDList()}
    weight = method == "detour" and any(v in told and w == "ahead" for v, (w, _) in paths.items())
    if weight:      # only simulation.findRoute reads it: no vehicle has a rerouting device, nobody else re-plans
        tc.edge.adaptTraveltime(edge, config.BLOCKED_EDGE_TT_S)
    for v, (where, road) in paths.items():
        row = {"id": v, "where": where, "road": road, "accepted_alert": v in told}
        if not row["accepted_alert"]:
            row.update(outcome="not_informed", reason="did not accept the alert: keeps its route")
        elif where == "upstream":
            row.update(outcome="unavoidable", reason="already on the incident edge behind the stop")
        elif method == "none":
            row.update(outcome="not_rerouted", reason="rerouting disabled (comparison scenario B)")
        else:
            R, t0 = remaining(tc, v), time.perf_counter()
            if method == "shortest":
                outcome, reason, dest = reroute(tc, v, edge)
                info = {"original_route": R, "final_route": remaining(tc, v)}
            else:
                outcome, reason, info = detour(tc, v, edge)
                dest = R[-1]
            timing[v] = round((time.perf_counter() - t0) * 1e3, 3)
            row.update(outcome=outcome, reason=reason, destination=dest, **info,
                       planned_before_m=planned_m(tc, R), planned_after_m=planned_m(tc, info["final_route"]))
            if row["outcome"] == "no_alternative":                  # where it was, so each case can be traced
                lane = tc.vehicle.getLaneID(v)
                row.update(lane=lane, lane_pos_m=round(tc.vehicle.getLanePosition(v), 2),
                           lane_length_m=round(tc.lane.getLength(lane), 2), speed_mps=round(tc.vehicle.getSpeed(v), 2))
        rows.append(row)
    rx = [v["rx_ms"] for v in record["vehicles"] if v["id"] in told]
    return {"certificate": check, "alert_accepted_by": len(accepted), "max_rx_ms": max(rx) if rx else None,
            "method": method, "global_edge_weight": weight, "vehicles": rows, "compute_ms": timing,
            "route_changes": [v for v, r in before.items() if tc.vehicle.getRoute(v) != r]}


class Watch:
    """Follow-up window: how often each tracked vehicle drives onto the incident edge (an entry = from another edge
    onto it), whether it keeps its destination, and whether the stopped vehicle stays exactly where it stopped."""

    def __init__(self, tc, edge, stopped, rows):
        self.tc, self.edge, self.stopped, self.rows = tc, edge, stopped, rows
        self.on = {r["id"]: tc.vehicle.getRoadID(r["id"]) == edge for r in rows}
        self.entries, self.gone, self.steps = dict.fromkeys(self.on, 0), set(), 0
        self.odometer = {v: tc.vehicle.getDistance(v) for v in self.on}     # distance driven, last value while alive
        self.at, self.lane = (tc.vehicle.getPosition(stopped), tc.vehicle.getLaneID(stopped)) if stopped else (None, None)
        self.max_speed = self.max_move = 0.0
        self.lane_kept = True

    def update(self):
        tc = self.tc
        live = set(tc.vehicle.getIDList())
        for v in self.on:
            if v not in live:
                self.gone.add(v)                               # arrived at its destination (teleport is disabled)
                continue
            on = tc.vehicle.getRoadID(v) == self.edge
            self.entries[v] += on and not self.on[v]
            self.on[v] = on
            self.odometer[v] = tc.vehicle.getDistance(v)
        if self.stopped:
            self.max_speed = max(self.max_speed, tc.vehicle.getSpeed(self.stopped))
            self.max_move = max(self.max_move, float(np.hypot(*np.subtract(tc.vehicle.getPosition(self.stopped), self.at))))
            self.lane_kept &= tc.vehicle.getLaneID(self.stopped) == self.lane
        self.steps += 1

    def result(self):
        tc = self.tc
        for r in self.rows:
            v = r["id"]
            r["entries_onto_incident_edge"] = self.entries[v]
            r["arrived_in_window"] = v in self.gone
            r["odometer_m"] = round(self.odometer[v], 2)
            if "destination" in r and v not in self.gone:
                r["destination_kept"] = tc.vehicle.getRoute(v)[-1] == r["destination"]
                r["route_avoids_edge_at_end"] = self.edge not in upcoming(tc, v) and tc.vehicle.getRoadID(v) != self.edge
        out = {"steps": self.steps}
        if self.stopped:
            out["stopped_vehicle"] = {"id": self.stopped, "lane": self.lane, "max_speed_mps": self.max_speed,
                                      "max_displacement_m": round(self.max_move, 4), "lane_kept": self.lane_kept}
        return out


class Response:
    """The chain after the staged stop, one step() per SUMO step, shared by the headless session and the SUMO-GUI demo.
    The first step after the stop: the detector reads live speeds; a detection that binds to the recorded alert
    releases it and the vehicles that accepted it are rerouted. Every later step: the follow-up window is watched.
    `det` must already hold the speeds of the snapshot before the stop. method: see respond()."""

    def __init__(self, tc, raw, trust, det, scheme="proposed", method=None):
        sc = raw["scenario"]
        self.tc, self.alert, self.record, self.trust, self.det = tc, sc["alert"], raw["protocols"][scheme], trust, det
        self.stopped, self.scheme, self.hit, self.res, self.watch = sc["source_id"], scheme, None, {"vehicles": []}, None
        self.method, self.truth = method or config.REROUTE_METHOD, None

    def step(self):
        self.det.update()
        if self.watch is not None:
            self.watch.update()
            return
        tc, stopped = self.tc, self.stopped          # who crosses the stopped vehicle's edge: for analysis only, read-only
        edge = tc.vehicle.getRoadID(stopped)
        self.truth = {"edge": edge, "crossing": {v: w for v, (w, _) in crossing(
            tc, edge, tc.vehicle.getLanePosition(stopped), {stopped}).items()}}
        self.hit = bind(self.det.events, self.alert)
        if self.hit:
            self.res = respond(tc, self.alert, self.record, self.hit["edge"], self.hit["lane_pos_m"], self.trust,
                               self.method)
        self.watch = Watch(tc, self.hit and self.hit["edge"], stopped, self.res["vehicles"])

    def result(self):
        hit, out = self.hit, {"detection": self.hit, "released": self.hit is not None, "event_id": self.alert["event_id"],
                              "scheme": self.scheme, "method": self.method, "ground_truth": self.truth}
        if hit is None:
            out["reason"] = "the stop was not detected from telemetry: no alert released, no vehicle rerouted"
        else:
            out["position_offset_m"] = round(float(np.hypot(*np.subtract(hit["xy"], self.alert["incident_position"]))), 3)
        return {**out, **self.res, "followup": self.watch.result(), "detections": self.det.events}


def snapshot_drift(tc, vehicles):
    """Largest coordinate difference (m) between live SUMO and the recorded snapshot; the same vehicles must exist."""
    ids = [v["id"] for v in vehicles]
    if set(tc.vehicle.getIDList()) != set(ids):
        return float("inf")
    now = np.array([tc.vehicle.getPosition(v) for v in ids])
    return float(np.abs(now - np.array([[v["x"], v["y"]] for v in vehicles])).max())


def session(raw, routes, trust, log, followup_s, scheme="proposed", forged=False, method=None, stop=True, extra=()):
    """One headless SUMO run of this seed: up to the incident snapshot, then the genuine response (staged stop,
    detection, release, rerouting with `method`, follow-up window) or the forged-alert negative control.
    stop=False: the same traffic without an incident (comparison scenario A). extra: further SUMO options."""
    sc = raw["scenario"]
    traci.start([SUMO_BIN, "-n", config.NET_FILE, "-r", routes, "--step-length", str(STEP_S), "--seed", str(sc["seed"]),
                 "--collision.action", "none", "--time-to-teleport", "-1",       # the same options as the SUMO-GUI demo
                 "--no-step-log", "true", "--error-log", log, *extra])
    try:
        det = StopDetector(traci)
        while traci.simulation.getTime() < sc["incident_time_s"] + STEP_S:     # FCD time t = TraCI clock t + 1
            traci.simulationStep()
            det.update()
        drift = snapshot_drift(traci, sc["vehicles"])
        if not drift < 0.05:
            raise RuntimeError(f"live SUMO differs from the recorded snapshot of {sc['run_id']} ({drift} m)")
        out = {"sumo": traci.getVersion()[1], "snapshot_drift_m": round(drift, 4), "sumo_log": log}
        if not stop:
            for _ in range(1 + int(followup_s)):
                if traci.simulation.getMinExpectedNumber() == 0:
                    break
                traci.simulationStep()
            out["end_s"] = traci.simulation.getTime()
            return out
        if forged:
            f = raw["forgery"]
            claimant = f["forger"]
            edge, pos = traci.vehicle.getRoadID(claimant), traci.vehicle.getLanePosition(claimant)
            traci.simulationStep()                                               # the instant the genuine response acts
            det.update()
            before = {v: traci.vehicle.getRoute(v) for v in traci.vehicle.getIDList()}
            out.update(claimant=claimant, claimed_edge=edge, event_id=f["alert"]["event_id"],
                       **respond(traci, f["alert"], f["variants"]["voting_reputation"], edge, pos, trust, method))
            out["routes_changed"] = sum(traci.vehicle.getRoute(v) != r for v, r in before.items())
            ahead = {r["id"] for r in out["vehicles"] if r["where"] == "ahead"}
            out["counterfactual_not_applied"] = {
                name: {"certificate_accepted": (f["variants"][name]["corroboration"] or {}).get("accepted"),
                       "holders": len(holders(f["variants"][name], f["alert"])),
                       "would_reroute_if_acted_on": len(ahead & set(holders(f["variants"][name], f["alert"])))}
                for name in ("voting_only", "no_voting")}
            out["detections"] = det.events
            return out
        src = sc["source_id"]
        out["staged_stop"] = {"vehicle": src, "t_s": sc["incident_time_s"], "lane": traci.vehicle.getLaneID(src),
                              "speed_before_mps": round(traci.vehicle.getSpeed(src), 3)}
        crash(traci, src)
        response = Response(traci, raw, trust, det, scheme, method)
        for k in range(1 + int(followup_s)):                  # the detection step, then the follow-up window
            if k and traci.simulation.getMinExpectedNumber() == 0:
                break
            traci.simulationStep()
            response.step()
        out.update(response.result())
        out["end_s"] = traci.simulation.getTime()
        return out
    finally:
        traci.close()


def acceptance(g, f):
    """The milestone's acceptance criteria, evaluated on one seed's record."""
    rows = g["vehicles"]
    rer = [r for r in rows if r["outcome"] == "rerouted"]
    stop = g["followup"]["stopped_vehicle"]
    detour = g["method"] == "detour"
    allowed = {r["id"] for r in (rer if detour else [r for r in rows if "destination" in r])}
    return {
        "only_authorized_routes_changed": set(g.get("route_changes", [])) <= allowed,   # detour: failed attempts untouched
        "detours_rebuilt_from_record": all(preserved(r, g["detection"]["edge"]) for r in rer) if detour else None,
        "detected_from_telemetry": g["detection"] is not None,
        "only_accepting_vehicles_rerouted": all(r["accepted_alert"] for r in rows if "destination" in r),
        "destinations_kept": all(r.get("destination_kept", True) for r in rer)
                             and not any(r["outcome"] == "destination_changed" for r in rows),
        "rerouted_never_enter_incident_edge": all(r["entries_onto_incident_edge"] == 0
                                                  and r.get("route_avoids_edge_at_end", True) for r in rer),
        "no_alternative_listed": [r["id"] for r in rows if r["outcome"] == "no_alternative"],
        "forged_alert_zero_reroutes": None if f is None else
        (f["routes_changed"] == 0 and not any("destination" in r for r in f["vehicles"])),
        "stopped_vehicle_stationary": stop["max_speed_mps"] == 0 and stop["max_displacement_m"] < 0.01 and stop["lane_kept"],
        "no_other_detection": [d for d in g["detections"] if d is not g["detection"]] == []
                              and (f is None or f["detections"] == []),
    }


def dissemination(density, run_index, out_dir):
    """experiment.run_one's record for this seed, written under out_dir (never the tracked results/urban)."""
    saved = experiment.RAW, config.RESULTS_DIR
    experiment.RAW, config.RESULTS_DIR = os.path.join(out_dir, "raw"), out_dir
    try:
        experiment.run_one(density, run_index, archive=False)
        return experiment.load_raw(f"d{density}_r{run_index:02d}")
    finally:
        experiment.RAW, config.RESULTS_DIR = saved


def run(density, run_index, out_dir=OUT, followup_s=None, scheme="proposed", method=None):
    """The whole chain for one seed; writes <out_dir>/<run_id>.json and returns the record."""
    followup_s = config.INCIDENT_FOLLOWUP_S if followup_s is None else followup_s
    method = method or config.REROUTE_METHOD
    run_id = f"d{density}_r{run_index:02d}"
    raw = dissemination(density, run_index, out_dir)
    import demo                                                    # demo imports this module: import here, not on top
    path, same = os.path.join(experiment.RAW, run_id + ".json.gz"), None   # an earlier saved record of this seed, if any
    if os.path.exists(path):
        with gzip.open(path, "rt") as fh:
            old = json.load(fh)
        dump = lambda rec: json.dumps([rec["scenario"], rec["protocols"][scheme], rec["forgery"]], sort_keys=True)
        same = {"path": path, "recorded_at": old.get("recorded_at"),
                "identical": demo.record_fingerprint(old) == demo.record_fingerprint(raw),
                "identical_parts_used_here": dump(old) == dump(raw)}           # scenario, this scheme, forgery test
    logs = os.path.join(out_dir, "logs")
    os.makedirs(logs, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        sc = build(density, run_index, workdir=tmp)                # same seed: the routes SUMO replays + the exact trust
        routes, trust = os.path.join(tmp, "routes.rou.xml"), dict(zip(sc["ids"], decision_trust(sc)))   # = Beta trust
                                                                                                    # unless Block G flags
        genuine = session(raw, routes, trust, os.path.join(logs, run_id + "_genuine.log"), followup_s, scheme, method=method)
        forged = session(raw, routes, trust, os.path.join(logs, run_id + "_forged.log"), 0, scheme, True, method) \
            if raw.get("forgery") else None
    timing = {"genuine": genuine.pop("compute_ms", {}), "forged": (forged or {}).pop("compute_ms", {})}
    rec = {"run_id": run_id, "density": density, "run": run_index, "seed": raw["scenario"]["seed"],
           "command": f"python run.py incident -d {density} -r {run_index} --method {method}",
           "parameters": {k: getattr(config, k) for k in ("CRASH_DECEL_MARGIN", "CRASH_STOP_SPEED", "BLOCKED_EDGE_TT_S",
                                                           "TRUST_CH_THRESHOLD", "QUORUM", "COMMITTEE_SIZE",
                                                           "ML_TRUST_MODE")} | {"INCIDENT_FOLLOWUP_S": followup_s,
                                                                                "REROUTE_METHOD": method},
           "dissemination_record": {"path": os.path.join(out_dir, "raw", run_id + ".json.gz"),
                                    "fingerprint": demo.record_fingerprint(raw), "saved_record": same},
           "genuine": genuine, "forged": forged,
           "reroute_compute_ms": timing}      # wall clock, machine-dependent: kept apart from the deterministic record
    rec["acceptance"] = acceptance(genuine, forged)
    with open(os.path.join(out_dir, run_id + ".json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    return rec


SUMMARY = ["run_id", "seed", "incident_vehicle", "speed_before_mps", "detected", "released", "alert_accepted_by",
           "crossing", "rerouted", "no_alternative", "unavoidable", "not_informed", "rerouted_entries",
           "destinations_kept", "stopped_stationary", "other_detections", "forged_accepted", "forged_routes_changed",
           "voting_only_would_reroute", "no_voting_would_reroute", "max_rx_ms", "saved_record_identical",
           "saved_parts_used_identical"]


def summary_row(rec):
    g, f, a = rec["genuine"], rec["forged"], rec["acceptance"]
    n = lambda kind: sum(r["outcome"] == kind for r in g["vehicles"])
    cf = (f or {}).get("counterfactual_not_applied", {})
    saved = rec["dissemination_record"]["saved_record"]
    return {"run_id": rec["run_id"], "seed": rec["seed"], "incident_vehicle": g["staged_stop"]["vehicle"],
            "speed_before_mps": g["staged_stop"]["speed_before_mps"], "detected": int(a["detected_from_telemetry"]),
            "released": int(g["released"]), "alert_accepted_by": g.get("alert_accepted_by", 0),
            "crossing": len(g["vehicles"]), "rerouted": n("rerouted"), "no_alternative": n("no_alternative"),
            "unavoidable": n("unavoidable"), "not_informed": n("not_informed"),
            "rerouted_entries": sum(r["entries_onto_incident_edge"] for r in g["vehicles"] if r["outcome"] == "rerouted"),
            "destinations_kept": int(a["destinations_kept"]), "stopped_stationary": int(a["stopped_vehicle_stationary"]),
            "other_detections": len(g["detections"]) - (g["detection"] is not None) + len((f or {}).get("detections", [])),
            "forged_accepted": "" if f is None else int(f["certificate"]["reverified"]),
            "forged_routes_changed": "" if f is None else f["routes_changed"],
            "voting_only_would_reroute": cf.get("voting_only", {}).get("would_reroute_if_acted_on", ""),
            "no_voting_would_reroute": cf.get("no_voting", {}).get("would_reroute_if_acted_on", ""),
            "max_rx_ms": g.get("max_rx_ms", ""),
            "saved_record_identical": "" if saved is None else int(saved["identical"]),
            "saved_parts_used_identical": "" if saved is None else int(saved["identical_parts_used_here"])}


def _job(args):
    density, run_index, out_dir, method = args
    return summary_row(run(density, run_index, out_dir, method=method))


def run_many(density, runs, out_dir=OUT, workers=None, method=None):
    """Seeds 0..runs-1 in parallel; one JSON per seed plus <out_dir>/summary_d<density>.csv."""
    with Pool(workers or min(runs, os.cpu_count())) as pool:
        rows = sorted(pool.imap_unordered(_job, [(density, r, out_dir, method) for r in range(runs)]),
                      key=lambda r: r["run_id"])
    path = os.path.join(out_dir, f"summary_d{density}.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, SUMMARY)
        w.writeheader()
        w.writerows(rows)
    return rows, path


def describe(rec):
    g, f, a = rec["genuine"], rec["forged"], rec["acceptance"]
    s = summary_row(rec)
    lines = [f"{rec['run_id']} (seed {rec['seed']}, {g['sumo']}, rerouting: {g['method']}): staged stop of {s['incident_vehicle']} at "
             f"{s['speed_before_mps']:.2f} m/s on {g['staged_stop']['lane']}, t = {g['staged_stop']['t_s']:.0f} s"]
    if g["detection"]:
        d = g["detection"]
        lines.append(f"  detected from telemetry at t = {d['t_s']:.0f} s: speed drop {d['speed_drop_mps']:.2f} m/s in one "
                     f"step > {d['threshold_mps2']:.1f} m/s^2, edge {d['edge']}; alert {g['event_id']} released")
        lines.append(f"  certificate re-verified: {g['certificate']['reverified']} ({g['certificate']['reason']}); "
                     f"accepted by {s['alert_accepted_by']} vehicles, last at {g['max_rx_ms']} ms")
        lines.append(f"  route crosses the incident edge: {s['crossing']}  rerouted {s['rerouted']}  no alternative "
                     f"{s['no_alternative']}  unavoidable (already upstream) {s['unavoidable']}  not informed {s['not_informed']}")
        lines.append(f"  follow-up {g['followup']['steps']} s: entries onto the incident edge by rerouted vehicles "
                     f"{s['rerouted_entries']}; destinations kept {a['destinations_kept']}")
    else:
        lines.append(f"  NOT detected: {g['reason']}")
    lines.append(f"  stopped vehicle stationary: {a['stopped_vehicle_stationary']}; other detections: {s['other_detections']}")
    if f:
        lines.append(f"  forged alert {f['event_id']} by {f['claimant']}: certificate {f['certificate']['reason']}; "
                     f"routes changed {f['routes_changed']} (voting only would reroute {s['voting_only_would_reroute']}, "
                     f"no voting {s['no_voting_would_reroute']}; not applied)")
    lines.append(f"  acceptance: " + ", ".join(f"{k}={v}" for k, v in a.items()))
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe(run(int(sys.argv[1]), int(sys.argv[2]))))
