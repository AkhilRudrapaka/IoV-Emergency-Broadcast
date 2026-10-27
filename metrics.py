"""
Metrics, computed only from what the channel simulation logged.

Corroboration metrics:
  transmissions     every frame on air: the proposal, the votes, and every certified alert
  alert_tx / vote_tx  the certified-alert frames / the vote frames among them
  accepted          1 if the alert obtained a quorum certificate that receivers accept
  quorum_ms         incident -> the source releases the certified alert

Vehicle metrics (definitions after Ni et al. 1999 unless noted):
  reachability      r / e: vehicles that received / vehicles connected to the source
                    in the radio graph (reachable in principle, same e for every scheme)
  srb               saved rebroadcast (r - t) / r, t = certified-alert frames incl. the source's
  suppression_ratio share of honest non-source receivers that chose not to rebroadcast
  redundant_tx      certified-alert frames that delivered the alert to no new vehicle or RSU
  dup_rx            successful receptions by vehicles that already had the alert
  collision_losses  in-range receptions destroyed by an overlapping transmission
  t90_ms            time until 90 % of the e reachable vehicles have the alert
  cbr_100ms         channel busy ratio over the first 100 ms (ETSI TS 102 687 T_CBR),
                    averaged over the reachable vehicles

RSU metrics (rsu.py registers the event; NaN when no RSU is reachable / none received):
  rsu_received      1 if an RSU registered the event, 0 if one was reachable but none did
  rsu_delay_ms      incident -> first RSU registration
  rsu_tx_before     transmissions on air up to that registration
  rsu_dup_copies    further copies of the same event decoded by RSUs afterwards
  rsu_hops          hops the registered copy had travelled
  rsu_relay_*       the same three, only for incidents OUTSIDE direct RSU range, i.e. the
                    alerts that had to be relayed vehicle-to-vehicle to reach infrastructure
"""
import math
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from scipy.stats import t as student_t

import rsu
from channel import slots_to_ms, ms_to_slots
from config import CBR_WINDOW_MS

METRICS = ["transmissions", "alert_tx", "vote_tx", "accepted", "quorum_ms",
           "redundant_tx", "dup_rx", "collision_losses", "collision_ratio",
           "reachability", "srb", "suppression_ratio", "t90_ms", "t_last_ms", "mean_delay_ms",
           "cbr_100ms", "cbr_peak", "airtime_ms",
           "rsu_received", "rsu_delay_ms", "rsu_tx_before", "rsu_dup_copies", "rsu_hops",
           "rsu_relay_received", "rsu_relay_delay_ms", "rsu_relay_tx_before"]
NAN = float("nan")


def reachable(adj, source):
    _, comp = connected_components(csr_matrix(adj), directed=False)
    return comp == comp[source]


def run_metrics(adj, source, malicious, proto, log, n_vehicles, names, alert, genuine=True):
    """adj covers vehicles then RSUs; the first n_vehicles nodes are vehicles.
    Returns (metrics dict, RSU event record or None, every copy an RSU decoded)."""
    nv = n_vehicles
    comp = reachable(adj[:nv, :nv], source)                  # RSUs never relay, so they add no connectivity
    e, got = int(comp.sum()), proto.has[:nv]
    alerts = [tx for tx in log if tx["kind"] == "ALERT"]
    r, t = int(got.sum()), len(alerts)
    released = bool(alerts)
    rx = np.sort(proto.first_rx[:nv][got])                   # slots; source = 0
    k90 = math.ceil(0.9 * e)
    honest = got & ~malicious[:nv]
    honest[source] = False

    ok = sum(tx["new"] + tx["dup"] + tx["other"] for tx in log)
    lost = sum(tx["lost"] for tx in log)
    end = max((tx["end"] for tx in log), default=0)
    busy = np.zeros((nv, max(end, 1)), bool)
    for tx in log:
        busy[np.flatnonzero(adj[tx["sender"], :nv]), tx["start"]:tx["end"]] = True
        busy[tx["sender"], tx["start"]:tx["end"]] = True
    win = ms_to_slots(CBR_WINDOW_MS)
    cbr = busy[comp, :win].sum(1) / win

    # ---- road-side units
    rsu_nodes = np.flatnonzero(proto.rsu)
    rsu_reachable = bool(adj[np.ix_(rsu_nodes, np.flatnonzero(comp))].any()) if rsu_nodes.size else False
    needs_relay = rsu_reachable and not adj[source, rsu_nodes].any()
    receptions = [{"rsu": names[u], "sender": names[s], "delay_ms": round(slots_to_ms(slot), 3), "hop": hop,
                   "transmissions_before": sum(tx["end"] <= slot for tx in log),
                   "vehicles_reached": int((got & (proto.first_rx[:nv] <= slot)).sum())}
                  for u, s, slot, hop in proto.rsu_rx]
    event, rejected = rsu.register(alert, receptions, (proto.cert_ok, proto.cert_reason) if proto.sec else None)
    assert not (genuine and rejected), f"a genuine alert failed RSU validation: {rejected}"
    rsu_first = len({rx_["rsu"] for rx_ in receptions})      # first copies at each RSU are not vehicle duplicates

    m = {
        "vehicles": nv, "reachable": e, "received": r,
        "transmissions": len(log), "alert_tx": t, "vote_tx": sum(tx["kind"] == "VOTE" or tx['kind'].startswith('CVOTE:') for tx in log),
        "accepted": float(released and proto.cert_ok),
        "quorum_ms": slots_to_ms(proto.rec[source]["released"]) if "released" in proto.rec[source] else NAN,
        "redundant_tx": sum(tx["new"] == 0 for tx in alerts),
        "dup_rx": sum(tx["dup"] for tx in log) - (len(receptions) - rsu_first),
        "collision_losses": lost,
        "collision_ratio": lost / (ok + lost) if ok + lost else 0.0,
        "reachability": r / e if e > 1 else NAN,
        "srb": (r - t) / r if released else NAN,
        "suppression_ratio": 1 - (t - 1) / honest.sum() if honest.sum() else NAN,
        "honest_reached": int(honest.sum()),
        "honest_reachable": int((comp & ~malicious[:nv]).sum()) - (0 if malicious[source] else 1),
        "t90_ms": slots_to_ms(rx[k90 - 1]) if r >= k90 and e > 1 else NAN,
        "t_last_ms": slots_to_ms(rx[-1]),
        "mean_delay_ms": slots_to_ms(rx[1:].mean()) if r > 1 else NAN,
        "cbr_100ms": float(cbr.mean()),
        "cbr_peak": float(cbr.max()),
        "airtime_ms": slots_to_ms(busy[comp].sum(1).mean()),
        "rsu_reachable": int(rsu_reachable),
        "rsu_received": (1.0 if event else 0.0) if rsu_reachable else NAN,
        "rsu_delay_ms": event["delay_ms"] if event else NAN,
        "rsu_tx_before": event["transmissions_before_reception"] if event else NAN,
        "rsu_dup_copies": event["duplicate_copies"] if event else NAN,
        "rsu_hops": event["hops"] if event else NAN,
        "rsu_needs_relay": int(needs_relay),
        "rsu_relay_received": (1.0 if event else 0.0) if needs_relay else NAN,
        "rsu_relay_delay_ms": event["delay_ms"] if event and needs_relay else NAN,
        "rsu_relay_tx_before": event["transmissions_before_reception"] if event and needs_relay else NAN,
    }
    check(m)
    return m, event, receptions


def check(m):
    """Sanity bounds every run must satisfy (a failure means a simulator bug)."""
    for k in ("reachability", "srb", "suppression_ratio", "collision_ratio", "cbr_100ms", "cbr_peak", "rsu_received"):
        assert math.isnan(m[k]) or 0.0 <= m[k] <= 1.0 + 1e-9, (k, m[k])
    for k in ("transmissions", "redundant_tx", "dup_rx", "collision_losses", "t_last_ms", "airtime_ms"):
        assert m[k] >= 0, (k, m[k])
    assert m["transmissions"] >= 1 and m["received"] <= m["reachable"] and m["alert_tx"] <= m["transmissions"]
    assert math.isnan(m["rsu_delay_ms"]) or (m["rsu_delay_ms"] > 0 and m["rsu_tx_before"] >= 1)


def summarize(values):
    """mean, sample std, 95 % CI half-width (Student t), n -- NaNs (undefined runs) excluded."""
    v = np.array([x for x in values if not math.isnan(x)], float)
    if v.size == 0:
        return NAN, NAN, NAN, 0
    std = v.std(ddof=1) if v.size > 1 else 0.0
    ci = student_t.ppf(0.975, v.size - 1) * std / math.sqrt(v.size) if v.size > 1 else 0.0
    return float(v.mean()), float(std), float(ci), int(v.size)
