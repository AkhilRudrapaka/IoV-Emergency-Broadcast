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

This is not an authentication infrastructure and it does not detect intrusions: it
rejects alerts that are malformed, implausible or not corroborated.
"""
from scenario import BOUNDS

KNOWN_TYPES = {"ACCIDENT"}
MAX_AGE_S = 600.0
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


def register(alert, receptions, certificate_check=None):
    """receptions: dicts {rsu, sender, delay_ms, hop, transmissions_before, vehicles_reached},
    one per copy any RSU decoded. Returns (event record or None, rejected copies)."""
    registry, rejected = {}, []
    for rx in sorted(receptions, key=lambda r: r["delay_ms"]):
        event_id = alert.get("event_id")
        if event_id in registry:
            registry[event_id]["duplicate_copies"] += 1          # same event again: not a new accident
            registry[event_id]["rsus_that_received"] = sorted(set(registry[event_id]["rsus_that_received"]) | {rx["rsu"]})
            continue
        problems = validate(alert, rx["hop"], alert.get("created_s", 0) + rx["delay_ms"] / 1000, certificate_check)
        if problems:
            rejected.append({**rx, "problems": problems})
            continue
        registry[event_id] = {
            "event_id": event_id, "status": "REGISTERED", "validation": "PASSED",
            "incident_time_s": alert["incident_time_s"], "incident_position": alert["incident_position"],
            "source_vehicle": alert["source_vehicle"],
            "receiving_rsu": rx["rsu"], "received_from": rx["sender"], "hops": rx["hop"],
            "reception_time_s": round(alert["created_s"] + rx["delay_ms"] / 1000, 6),
            "delay_ms": rx["delay_ms"],
            "transmissions_before_reception": rx["transmissions_before"],
            "vehicles_reached_at_reception": rx["vehicles_reached"],
            "duplicate_copies": 0, "rsus_that_received": [rx["rsu"]],
        }
    return registry.get(alert.get("event_id")), rejected
