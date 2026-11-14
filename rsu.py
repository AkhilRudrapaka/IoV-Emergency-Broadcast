"""
Road-side units: the infrastructure endpoint of an emergency alert.

An RSU only RECEIVES (protocols.py never lets it relay), so it cannot become a
routing bottleneck. Every RSU reports to one registry -- its backhaul to the
traffic-management centre -- so an event decoded by two RSUs, or several times
by one, is registered exactly ONCE; later copies are counted as duplicates.

Plausibility validation (what the RSU checks before it records an event):
  1. structure     every packet field is present
  2. type          the message type is a known one
  3. location      the incident position lies inside the road network
  4. time order    the alert was not created after it was received
  5. freshness     it is not older than the DENM default validity (600 s, EN 302 637-3)
  6. hop count     it has not travelled more than its hop limit
  7. certificate   the same check every vehicle applies (corroboration.accept): a valid
                   BLS aggregate signature with a quorum of reputable endorsers
  8. duplicate     an event ID already registered is not registered again
  9. same crash    (register_reports) a valid report of a crash that already has an incident --
                   same message type, within MERGE_RADIUS_M and MERGE_WINDOW_S of EVERY report of
                   that incident -- is kept with the incident instead of being registered again

This is not an authentication infrastructure and it does not detect intrusions: it
rejects alerts that are malformed, implausible or not corroborated.
"""
import math

from scenario import BOUNDS

KNOWN_TYPES = {"ACCIDENT"}
MAX_AGE_S = 600.0
# Several reports of ONE crash (both vehicles of a collision, or one vehicle reporting twice) become one incident.
# Deliberately tight bounds: a report must lie within both bounds of EVERY report already in the incident (pairwise,
# so matches cannot chain and an incident never spans more than 10 m and 2 s), and only reports that pass every check
# count. The rule cannot tell crashes apart: two distinct crashes within these bounds ARE merged (a disclosed
# limitation). Only register_reports uses it; the simulation creates one report per crash and does not call it.
MERGE_RADIUS_M = 10.0      # about two car lengths: the vehicles of one collision
MERGE_WINDOW_S = 2.0       # their detection times
REQUIRED = ("event_id", "message_type", "source_vehicle", "sequence_number",
            "incident_position", "incident_time_s", "created_s", "hop_limit")


def validate(alert, hop, received_s, certificate_check=None):
    """Returns the list of failed checks (empty = accepted).
    certificate_check: (accepted, reason) from corroboration.accept, or None when
    corroboration is switched off (the no-voting ablation)."""
    missing = [k for k in REQUIRED if k not in alert]
    if missing:
        return [f"missing field(s): {', '.join(missing)}"]
    x, y = alert["incident_position"]
    problems = []
    if alert["message_type"] not in KNOWN_TYPES:
        problems.append(f"unknown message type {alert['message_type']}")
    if not (BOUNDS[0] <= x <= BOUNDS[2] and BOUNDS[1] <= y <= BOUNDS[3]):
        problems.append("incident position outside the road network")
    if alert["created_s"] > received_s:
        problems.append("created after it was received")
    if received_s - alert["created_s"] > MAX_AGE_S:
        problems.append("older than the 600 s validity")
    if hop > alert["hop_limit"]:
        problems.append("hop limit exceeded")
    if certificate_check is not None and not certificate_check[0]:
        problems.append(f"not corroborated: {certificate_check[1]}")
    return problems


def register(alert, receptions, certificate_check=None, clock_s=None):
    """receptions: dicts {rsu, sender, arrival_ms, delay_ms, hop, transmissions_before, vehicles_reached},
    one per copy any RSU decoded. Returns (event record or None, rejected copies).
    clock_s: the RSU's OWN clock (simulation seconds) when this dissemination started; a copy is received at
    clock_s + delay. Freshness must use the receiver's clock: measured from the alert's claimed created_s (the
    fallback, for offline use only) a stale or replayed alert would always look fresh."""
    registry, rejected = {}, []
    start = alert.get("created_s", 0) if clock_s is None else clock_s
    for rx in sorted(receptions, key=lambda r: r["delay_ms"]):
        event_id = alert.get("event_id")
        if event_id in registry:
            registry[event_id]["duplicate_copies"] += 1          # same event again: not a new accident
            rx["status"] = "DUPLICATE"
            registry[event_id]["rsus_that_received"] = sorted(set(registry[event_id]["rsus_that_received"]) | {rx["rsu"]})
            continue
        problems = validate(alert, rx["hop"], start + rx["delay_ms"] / 1000, certificate_check)
        if problems:
            rx["status"] = "REJECTED: " + "; ".join(problems)
            rejected.append({**rx, "problems": problems})
            continue
        rx["status"] = "REGISTERED"                               # every copy's outcome is recorded (raw rsu_receptions)
        registry[event_id] = {
            "event_id": event_id, "status": "REGISTERED", "validation": "PASSED",
            "incident_time_s": alert["incident_time_s"], "incident_position": alert["incident_position"],
            "source_vehicle": alert["source_vehicle"],
            "receiving_rsu": rx["rsu"], "received_from": rx["sender"], "hops": rx["hop"],
            "arrival_ms": rx.get("arrival_ms", rx["delay_ms"]),   # decoded; delay_ms = after verification
            "reception_time_s": round(start + rx["delay_ms"] / 1000, 6),
            "delay_ms": rx["delay_ms"],
            "transmissions_before_reception": rx["transmissions_before"],
            "vehicles_reached_at_reception": rx["vehicles_reached"],
            "duplicate_copies": 0, "rsus_that_received": [rx["rsu"]],
        }
    return registry.get(alert.get("event_id")), rejected


def same_crash(a, b):
    """Identity of two reports (alerts). The same event ID is the same report. A different event ID is the same crash
    only with the same message type, incident positions at most MERGE_RADIUS_M apart and incident times at most
    MERGE_WINDOW_S apart."""
    if a["event_id"] == b["event_id"]:
        return True
    (xa, ya), (xb, yb) = a["incident_position"], b["incident_position"]
    return (a["message_type"] == b["message_type"] and math.hypot(xa - xb, ya - yb) <= MERGE_RADIUS_M
            and abs(a["incident_time_s"] - b["incident_time_s"]) <= MERGE_WINDOW_S)


def register_reports(reports):
    """Registers every report of any crash in ONE registry and keeps one incident per crash.
    reports: [(alert, receptions, certificate_check, clock_s)], one entry per report, each exactly the arguments of
    register(). Every entry goes through register() with its own arguments, so every check, the signature and the
    quorum rule apply unchanged: a rejected report stays rejected and is never merged, and endorsements are never
    pooled across reports. Valid reports are then taken in the order the RSUs registered them:
      * an event ID already registered is the same report again (the duplicate rule): its copies are duplicates of
        that report, never a new report or a new reporting vehicle;
      * a report of the same crash as EVERY report already in an incident (same_crash, pairwise) is not registered
        again: its first copy becomes 'MERGED: same incident as <event ID>' and it is kept in the incident's
        'reports' with its source vehicle;
      * otherwise it opens a new incident.
    Returns (incidents, rejected copies); an incident is register()'s record of its first report plus 'reports' (every
    valid report, in registration order) and 'reporting_vehicles' (distinct: a vehicle that reported twice counts
    once)."""
    registered, rejected = [], []
    for alert, receptions, check, clock_s in reports:
        event, bad = register(alert, receptions, check, clock_s)
        rejected.extend(bad)
        if event:
            registered.append((alert, event, [rx for rx in receptions if rx["status"] in ("REGISTERED", "DUPLICATE")]))
    incidents, members = [], []                                 # members[k]: the alerts of incident k
    for alert, event, copies in sorted(registered, key=lambda r: r[1]["reception_time_s"]):
        first = next(rx for rx in copies if rx["status"] == "REGISTERED")
        k = next((k for k, group in enumerate(members) if any(a["event_id"] == alert["event_id"] for a in group)), None)
        if k is not None:                                       # an event ID already registered: duplicates only
            first["status"] = "DUPLICATE"
            incident = incidents[k]
            report = next(r for r in incident["reports"] if r["event_id"] == alert["event_id"])
            report["copies"] += len(copies)
            if report is incident["reports"][0]:
                incident["duplicate_copies"] += len(copies)
                incident["rsus_that_received"] = sorted(set(incident["rsus_that_received"]) | {rx["rsu"] for rx in copies})
            continue
        report = {"event_id": event["event_id"], "source_vehicle": alert["source_vehicle"],
                  "receiving_rsu": event["receiving_rsu"], "reception_time_s": event["reception_time_s"],
                  "delay_ms": event["delay_ms"], "copies": len(copies)}
        k = next((k for k, group in enumerate(members) if all(same_crash(a, alert) for a in group)), None)
        if k is None:
            incidents.append({**event, "reports": [{**report, "status": "REGISTERED"}],
                              "reporting_vehicles": [alert["source_vehicle"]]})
            members.append([alert])
        else:                                                   # the same crash again: kept, not registered twice
            incident = incidents[k]
            first["status"] = f"MERGED: same incident as {incident['event_id']}"
            incident["reports"].append({**report, "status": "MERGED"})
            incident["reporting_vehicles"] = sorted(set(incident["reporting_vehicles"]) | {alert["source_vehicle"]})
            members[k].append(alert)
    return incidents, rejected
