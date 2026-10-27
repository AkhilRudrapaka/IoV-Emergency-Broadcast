"""
Runs every scheme on the SAME scenario snapshot (same vehicles, same positions,
same incident, same RSUs, same misbehaving set, same reputation values) -- the
comparison is paired by construction. Saves raw per-run data, then aggregates.

Each scenario is simulated as:
  * the genuine accident, under every scheme in config.PROTOCOLS
  * the forged-alert test: on the same traffic snapshot, a misbehaving vehicle
    (with its colluding neighbours) sends an alert for an accident that did not
    happen, under the three protection levels in config.FORGERY.
Every one of these simulations contains exactly one alert.
"""
import csv
import gzip
import json
import os
import random
from multiprocessing import Pool

import numpy as np

import config
import corroboration
import infrastructure
from channel import geometry, simulate, slots_to_ms
from clustering import elect_roles
from metrics import METRICS, run_metrics, summarize
from protocols import Flooding, Slotted1P, Proposed, CHRoute
from scenario import build, create_alert

RAW, PROCESSED = os.path.join(config.RESULTS_DIR, "raw"), os.path.join(config.RESULTS_DIR, "processed")
FORGERY_METRICS = ["certificate_formed", "accepted_share", "rsu_registered", "transmissions"]


def network(sc):
    """The radio nodes of a run: its vehicles followed by the fixed RSUs. The in-range
    matrix doubles as every node's beacon neighbour table (neighbour discovery)."""
    nv = len(sc["ids"])
    xy = np.vstack([sc["xy"], list(config.RSU_POSITIONS.values())])
    names = sc["ids"] + list(config.RSU_POSITIONS)
    is_rsu = np.arange(len(xy)) >= nv
    malicious = np.concatenate([sc["malicious"], np.zeros(len(xy) - nv, bool)])
    dist, adj = geometry(xy)
    return nv, names, is_rsu, malicious, dist, adj


def arms(sc, net, alert, source, genuine=True):
    """name -> (constructor of that scheme's protocol object, roles shown for it)."""
    nv, names, is_rsu, malicious, dist, adj = net
    elect = lambda **kw: elect_roles(sc["xy"], sc["speed"], adj[:nv, :nv], sc["trust"], **kw)
    roles = {"full": elect(), "no_reputation": elect(use_trust=False), "no_clustering": elect(cluster=False)}
    pad = np.zeros(len(adj) - nv, int)
    tier = {k: np.concatenate([v[1], pad]) for k, v in roles.items()}
    tier["none"] = np.zeros(len(adj), int)
    plan = lambda **kw: corroboration.plan(alert, source, dist, adj, nv, sc["trust"], malicious, genuine, **kw)
    sec, sec_norep = plan(), plan(use_reputation=False)
    route = infrastructure.shortest_route(
        np.vstack([sc['xy'], list(config.RSU_POSITIONS.values())]), adj,
        roles['full'][0], sc['trust'], sc['malicious'], source, set(np.flatnonzero(is_rsu)))

    def proposed(tiers="full", security=sec, **kw):
        return Proposed(dist, adj, malicious, tier[tiers], is_rsu, security, **kw)

    return {
        "ch_route": (lambda: CHRoute(dist, adj, malicious, route['nodes'], is_rsu, sec,
                                    roles['full'][2], sc['trust']), roles['full']),
        "flooding": (lambda: Flooding(dist, adj, malicious, is_rsu, sec), None),
        "slotted1p": (lambda: Slotted1P(dist, adj, malicious, is_rsu, sec), None),
        "proposed": (proposed, roles["full"]),
        "no_rad": (lambda: proposed(rad=False), roles["full"]),
        "no_slots": (lambda: proposed(slots=False), roles["full"]),
        "no_coverage": (lambda: proposed(coverage=False), roles["full"]),
        "no_clustering": (lambda: proposed("no_clustering"), roles["no_clustering"]),
        "no_cluster_forwarding": (lambda: proposed("none"), roles["full"]),
        "no_reputation": (lambda: proposed("no_reputation", sec_norep), roles["no_reputation"]),
        "no_security": (lambda: proposed(security=None), roles["full"]),
    }, roles["full"]


def run_arm(make, role, sc, net, alert, source, rng, genuine=True):
    nv, names, is_rsu, malicious, dist, adj = net
    proto = make()
    proto.names = names
    log = simulate(proto, adj, source, rng)
    m, event, receptions = run_metrics(adj, source, malicious, proto, log, nv, names, alert, genuine)
    record = protocol_record(sc, names, dist, adj, proto, log, role)
    record.update(metrics=m, rsu_event=event, rsu_receptions=receptions, corroboration=corroboration_record(names, proto))
    if isinstance(proto, CHRoute):
        record['cluster_consensus'] = [
            {'cluster_head': names[head], 'voters': [names[v] for v in round_['voters']],
             'votes_received': [names[v] for v in sorted(round_['received'])],
             'accepted': round_.get('accepted', False), 'certificate': round_['certificate'],
             'reason': round_.get('reason', 'insufficient distinct votes received')}
            for head, round_ in proto.rounds.items()]
    return m, record


def run_one(density, run, protocols=config.PROTOCOLS, save=True):
    from datetime import datetime
    started_at = datetime.now().astimezone()
    sc = build(density, run)
    net = network(sc)
    nv, names, is_rsu, malicious, dist, adj = net
    base = {"run_id": sc["run_id"], "density": density, "run": run, "seed": sc["seed"]}

    schemes, (role, _, labels) = arms(sc, net, sc["alert"], sc["source"])
    rows, raw = [], {"scenario": scenario_record(sc, adj, role, labels), "protocols": {}}
    for name in protocols:
        make, roles = schemes[name]
        rng = np.random.default_rng([sc["seed"], config.PROTOCOLS.index(name)])
        m, raw["protocols"][name] = run_arm(make, roles, sc, net, sc["alert"], sc["source"], rng)
        rows.append({**base, "protocol": name, "event_id": sc["alert"]["event_id"],
                     "incident_time_s": sc["incident_time_s"], "incident_vehicle": sc["source_id"],
                     "incident_x": sc["incident_xy"][0], "incident_y": sc["incident_xy"][1], **m})

    forged_rows, raw["forgery"] = forged_alert(sc, net, base)
    route = infrastructure.shortest_route(
        np.vstack([sc['xy'], list(config.RSU_POSITIONS.values())]), adj,
        role, sc['trust'], sc['malicious'], sc['source'], set(np.flatnonzero(is_rsu)))
    route['vehicle_ids'] = [names[i] for i in route['nodes']]
    raw['infrastructure'] = {'route': route, 'model': 'incident mobility snapshot'}
    if 'ch_route' in raw['protocols']:
        delivery = raw['protocols']['ch_route']
        updates = infrastructure.trust_after_event(raw['scenario']['vehicles'],
                    {tx['sender'] for tx in delivery['transmissions'] if tx['kind'] == 'ALERT'}, delivery['rsu_event'])
        raw['infrastructure']['trust_updates'] = updates
        certificates = [(sc['alert'], delivery['corroboration']['certificate'])]
        certificates.extend((sc['alert'], row['certificate']) for row in delivery['cluster_consensus'])
        authenticated, rejected = infrastructure.batch_authenticate(certificates,
                           dict(zip(sc['ids'], sc['trust'])))
        raw['infrastructure']['batch_authentication'] = {'certificates_checked': len(certificates),
            'accepted_event_ids': [item['event_id'] for item in authenticated], 'rejected': rejected,
            'method': 'per-event BLS aggregate verification; deduplicated batch API'}
        raw['infrastructure']['backhaul'] = infrastructure.persist(sc['run_id'], delivery['rsu_event'], updates, config.RESULTS_DIR,
                                                                 raw['scenario']) if save else {'storage': 'DISABLED'}
    if save:
        os.makedirs(RAW, exist_ok=True)
        raw['recorded_at'] = started_at.isoformat()
        record_id = sc['run_id'] + '__' + started_at.strftime('%Y%m%dT%H%M%S%f')
        # Preserve each invocation, even when the same seed is replayed again.
        with gzip.open(os.path.join(RAW, record_id + '.json.gz'), 'wt') as f:
            json.dump(raw, f)
        with gzip.open(os.path.join(RAW, f"{sc['run_id']}.json.gz"), "wt") as f:
            json.dump(raw, f)
    return rows, forged_rows


def forged_alert(sc, net, base):
    """The same traffic snapshot, but the one alert is a lie: a misbehaving vehicle claims
    an accident at its own position, and its misbehaving neighbours endorse it."""
    nv, names, is_rsu, malicious, dist, adj = net
    candidates = [v for v in range(nv) if malicious[v] and adj[v, :nv].any()]
    if not candidates:
        return [], None                                   # no misbehaving vehicle in this run
    forger = random.Random(sc["seed"] + 1).choice(candidates)
    alert = create_alert(sc["seed"], names[forger], sc["xy"][forger], sc["incident_time_s"])
    schemes, _ = arms(sc, net, alert, forger, genuine=False)
    rows, variants = [], {}
    for i, (variant, arm) in enumerate(zip(config.FORGERY, ("proposed", "no_reputation", "no_security"))):
        make, roles = schemes[arm]
        m, record = run_arm(make, roles, sc, net, alert, forger, np.random.default_rng([sc["seed"], 100 + i]), genuine=False)
        variants[variant] = record
        rows.append({**base, "variant": variant, "forger": names[forger],
                     "colluders": len(record["corroboration"]["voters"]) if record["corroboration"] else 0,
                     "certificate_formed": float(bool(record["corroboration"] and record["corroboration"]["certificate"])),
                     "accepted_share": m["honest_reached"] / m["honest_reachable"] if m["honest_reachable"] else float("nan"),
                     "rsu_registered": float(record["rsu_event"] is not None),
                     "transmissions": m["transmissions"]})
    return rows, {"forger": names[forger], "alert": alert, "variants": variants}


def scenario_record(sc, adj, role, labels):
    nv = len(sc["ids"])
    return {
        **{k: sc[k] for k in ("run_id", "density", "run", "seed", "incident_time_s", "source_id",
                              "incident_xy", "incident_lane", "alert")},
        "rsus": [{"id": name, "x": x, "y": y, "vehicles_in_range": int(adj[nv + i, :nv].sum())}
                 for i, (name, (x, y)) in enumerate(config.RSU_POSITIONS.items())],
        "vehicles": [{"id": v, "x": round(float(x), 2), "y": round(float(y), 2),
                      "speed": round(float(s), 2), "malicious": bool(m), "trust": round(float(tr), 3),
                      "neighbors": int(adj[i].sum()), "role": role[i], "dbscan": int(labels[i])}
                     for i, (v, (x, y), s, m, tr) in enumerate(zip(sc["ids"], sc["xy"], sc["speed"],
                                                                     sc["malicious"], sc["trust"]))],
    }


def corroboration_record(names, proto):
    """Who was on the committee, who voted and when, and the certificate that resulted."""
    sec = proto.sec
    if sec is None:
        return None
    return {"use_reputation": sec["use_reputation"], "committee": [names[v] for v in sec["committee"]],
            "voters": [names[v] for v in sec["voters"]],
            "votes": [{"voter": names[v], "sent_ms": round(slots_to_ms(t), 3)} for v, t in proto.vote_log],
            "votes_counted": [names[v] for v in proto.votes],
            "certificate": proto.cert,
            "accepted": bool(proto.cert and proto.cert_ok),
            "reason": proto.cert_reason if proto.cert else
            f"no quorum: {len(proto.votes)} of {config.QUORUM} endorsements reached the source"}


def protocol_record(sc, names, dist, adj, proto, log, roles):
    """Per-vehicle message state for this event: when it arrived, from whom, over how many
    hops, what the vehicle decided and why."""
    nv = len(sc["ids"])
    role = roles[0] if roles else None
    tier = getattr(proto, "tier", np.zeros(len(adj), int))
    vehicles = []
    for v in np.flatnonzero(proto.seen[:nv]):
        f = proto.first_from[v]
        rec = proto.rec.get(v, {})
        tx = next((x for x in log if x["sender"] == v and x["kind"] == "ALERT"), None)
        vehicles.append({
            "id": names[v], "rx_ms": round(slots_to_ms(proto.first_rx[v]), 3) if proto.has[v] else None,
            "hop": int(proto.hop[v]),
            "from": names[f] if f >= 0 else None, "dist_m": round(float(dist[v, f]), 1) if f >= 0 else 0.0,
            "neighbors": int(adj[v].sum()), "copies_heard": len(proto.heard[v]),
            "role": role[v] if role is not None else "-", "tier": int(tier[v]),
            "trust": round(float(sc["trust"][v]), 3),
            "decision": rec.get("decision", "UNDECIDED"), "reason": rec.get("reason", ""),
            "decided_ms": round(slots_to_ms(rec["t"]), 3) if "t" in rec else None,
            "uncovered": rec.get("uncovered"),
            "tx_ms": round(slots_to_ms(tx["start"]), 3) if tx else None,
        })
    return {"transmissions": [{"sender": names[x["sender"]], "kind": x["kind"],
                               "start_ms": round(slots_to_ms(x["start"]), 3),
                               "end_ms": round(slots_to_ms(x["end"]), 3), "new": x["new"],
                               "dup": x["dup"], "other": x["other"], "lost": x["lost"]} for x in log],
            "vehicles": vehicles}


def _job(args):
    return run_one(*args)


def run_matrix(densities=config.DENSITIES, runs=config.RUNS_PER_DENSITY, workers=None, progress=print):
    jobs = [(d, r) for d in densities for r in range(runs)]
    rows, forged = [], []
    with Pool(workers or min(len(jobs), os.cpu_count())) as pool:
        for i, (res, fres) in enumerate(pool.imap_unordered(_job, jobs), 1):
            rows.extend(res)
            forged.extend(fres)
            progress(f"  [{i:>3}/{len(jobs)}] {res[0]['run_id']}  vehicles={res[0]['vehicles']:>3}  "
                     f"incident t={res[0]['incident_time_s']:.0f}s at {res[0]['incident_vehicle']}")
    rows.sort(key=lambda r: (r["density"], r["run"], config.PROTOCOLS.index(r["protocol"])))
    forged.sort(key=lambda r: (r["density"], r["run"], list(config.FORGERY).index(r["variant"])))
    return rows, forged


def _write_csv(name, rows):
    with open(os.path.join(PROCESSED, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _aggregate(rows, key, groups, metrics):
    out = []
    for d in sorted({r["density"] for r in rows}):
        for g in groups:
            sel = [r for r in rows if r["density"] == d and r[key] == g]
            if not sel:
                continue
            row = {"density": d, key: g, "runs": len(sel)}
            for k in metrics:
                mean, std, ci, n = summarize([r[k] for r in sel])
                row.update({k: mean, f"{k}_std": std, f"{k}_ci95": ci, f"{k}_n": n})
            out.append(row)
    return out


def write_outputs(rows, forged):
    os.makedirs(PROCESSED, exist_ok=True)
    summary = _aggregate(rows, "protocol", config.PROTOCOLS, METRICS)
    _write_csv("runs.csv", rows)
    _write_csv("summary.csv", summary)
    forgery = _aggregate(forged, "variant", config.FORGERY, FORGERY_METRICS) if forged else []
    if forged:
        _write_csv("forgery_runs.csv", forged)
        _write_csv("forgery_summary.csv", forgery)
    return summary, forgery


def load_raw(run_id):
    with gzip.open(os.path.join(RAW, f"{run_id}.json.gz"), "rt") as f:
        return json.load(f)
