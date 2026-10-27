"""Cluster-head routing, per-cluster certificates and durable local backhaul.

This layer operates on the recorded mobility snapshot. Its route cost is metres,
not measured radio latency. Dispatch is an outbox, not a real ambulance request.
"""
import heapq
import json
import sqlite3
import os
import urllib.request
import urllib.parse
from pathlib import Path

import corroboration
from config import QUORUM, TRUST_CH_THRESHOLD, HOP_LIMIT


def shortest_route(xy, adj, roles, trust, malicious, source, rsu_nodes):
    """Shortest distance path to any RSU, using reputable CHs as intermediates."""
    rsu_nodes = {int(i) for i in rsu_nodes}
    source = int(source)
    allowed = {source, *rsu_nodes}
    allowed.update(i for i, role in enumerate(roles)
                   if role == 'CH' and trust[i] >= TRUST_CH_THRESHOLD and not malicious[i])
    queue = [(0.0, 0, source, [source])]
    best = {(source, 0): 0.0}
    while queue:
        cost, hops, node, path = heapq.heappop(queue)
        if cost != best.get((node, hops)):
            continue
        if node in rsu_nodes:
            return {'status': 'ROUTE_FOUND', 'nodes': path, 'distance_m': round(cost, 3), 'hops': hops}
        if hops >= HOP_LIMIT:
            continue
        for nxt in sorted(allowed):
            if nxt in path or not adj[node, nxt]:
                continue
            distance = sum((float(a)-float(b))**2 for a, b in zip(xy[node], xy[nxt]))**0.5
            candidate = cost + distance
            key = (nxt, hops + 1)
            if candidate < best.get(key, float('inf')):
                best[key] = candidate
                heapq.heappush(queue, (candidate, hops + 1, nxt, path + [nxt]))
    return {'status': 'NO_CH_ROUTE', 'nodes': [], 'distance_m': None, 'hops': None}


def cluster_votes(alert, vehicles, adj, genuine=True):
    """Each CH collects distinct member votes; insufficient quorum stays rejected."""
    records = []
    reputation = {v['id']: v['trust'] for v in vehicles}
    for head, vehicle in enumerate(vehicles):
        if vehicle['role'] != 'CH':
            continue
        members = [v['id'] for i, v in enumerate(vehicles)
                   if i != head and v['id'] != alert['source_vehicle']
                   and v['dbscan'] == vehicle['dbscan'] and adj[head, i]
                   and v['trust'] >= TRUST_CH_THRESHOLD
                   and (not v['malicious'] if genuine else v['malicious'])]
        cert = corroboration.certificate(alert, alert['source_vehicle'], members) if len(members) >= QUORUM else None
        accepted, reason = corroboration.accept(alert, cert, reputation.get)
        records.append({'cluster_head': vehicle['id'], 'cluster': vehicle['dbscan'],
                        'voters': members, 'accepted': accepted, 'reason': reason, 'certificate': cert})
    return records


def batch_authenticate(items, reputation):
    """Authenticate multiple event certificates individually and deduplicate IDs.

    BLS aggregates signers within each event; this does not claim a multi-message
    cryptographic batch speedup.
    """
    accepted, rejected, seen = [], [], set()
    for alert, cert in items:
        ok, reason = corroboration.accept(alert, cert, reputation.get)
        if not ok:
            rejected.append({'event_id': alert['event_id'], 'reason': reason})
        elif alert['event_id'] not in seen:
            accepted.append(alert)
            seen.add(alert['event_id'])
    return accepted, rejected


def persist(run_id, event, trust_updates, output_dir, dataset=None):
    """Idempotent local storage and emergency-service outbox, no external sends."""
    folder = Path(output_dir) / 'infrastructure'
    folder.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(folder / 'backhaul.sqlite3', timeout=30) as db:
        db.execute('CREATE TABLE IF NOT EXISTS events (run_id TEXT, event_id TEXT, payload TEXT, PRIMARY KEY(run_id,event_id))')
        db.execute('CREATE TABLE IF NOT EXISTS dispatch (run_id TEXT, event_id TEXT, status TEXT, PRIMARY KEY(run_id,event_id))')
        db.execute('CREATE TABLE IF NOT EXISTS trust (run_id TEXT, vehicle_id TEXT, payload TEXT, PRIMARY KEY(run_id,vehicle_id))')
        db.execute('CREATE TABLE IF NOT EXISTS datasets (run_id TEXT PRIMARY KEY, payload TEXT)')
        if dataset is not None:
            db.execute('INSERT OR REPLACE INTO datasets VALUES (?,?)', (run_id, json.dumps(dataset)))
        if event:
            db.execute('INSERT OR REPLACE INTO events VALUES (?,?,?)', (run_id, event['event_id'], json.dumps(event)))
            db.execute('INSERT OR IGNORE INTO dispatch VALUES (?,?,?)', (run_id, event['event_id'], 'QUEUED_LOCAL'))
        for row in trust_updates:
            db.execute('INSERT OR REPLACE INTO trust VALUES (?,?,?)', (run_id, row['vehicle_id'], json.dumps(row)))
    return {'storage': 'LOCAL_SQLITE', 'database': str(folder / 'backhaul.sqlite3'),
            'dispatch': 'QUEUED_LOCAL' if event else 'NO_ACCEPTED_EVENT', 'cloud': 'NOT_CONNECTED'}


def trust_after_event(vehicles, transmitted, event):
    """One explicit simulated watchdog observation after a registered event."""
    rows = []
    for vehicle in vehicles:
        observed = bool(event and vehicle['id'] in transmitted)
        # An effective prior with weight 20; do not pretend stored trust is raw counts.
        prior = vehicle['trust']
        updated = (20 * prior + 1) / 21 if observed else prior
        rows.append({'vehicle_id': vehicle['id'], 'before': prior, 'after': round(updated, 6),
                     'observation': 'verified_forward' if observed else 'unobserved'})
    return rows


def export_backhaul(output_dir):
    folder = Path(output_dir) / 'infrastructure'
    database = folder / 'backhaul.sqlite3'
    if not database.exists():
        raise ValueError('Run a simulation first to create the backhaul database.')
    with sqlite3.connect(database) as db:
        events = [{'run_id': run, 'event_id': event, 'payload': json.loads(payload)}
                  for run, event, payload in db.execute('SELECT * FROM events ORDER BY run_id,event_id')]
        trust = [{'run_id': run, **json.loads(payload)}
                 for run, _, payload in db.execute('SELECT * FROM trust ORDER BY run_id,vehicle_id')]
        dispatch = [{'run_id': run, 'event_id': event, 'status': status}
                    for run, event, status in db.execute('SELECT * FROM dispatch ORDER BY run_id,event_id')]
        has_datasets = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='datasets'").fetchone()
        datasets = [{'run_id': run, 'dataset': json.loads(data)} for run, data in
                    db.execute('SELECT * FROM datasets ORDER BY run_id')] if has_datasets else []
    payload = {'schema_version': 1, 'events': events, 'trust_updates': trust, 'dispatch_outbox': dispatch, 'vehicle_datasets': datasets}
    path = folder / 'cloud_export.json'
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return payload, path


def analytics(output_dir):
    database = Path(output_dir) / 'infrastructure' / 'backhaul.sqlite3'
    result = {'events': 0, 'pending_dispatch': 0, 'cloud': 'NOT_CONNECTED'}
    if database.exists():
        with sqlite3.connect(database) as db:
            result['events'] = db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
            result['pending_dispatch'] = db.execute("SELECT COUNT(*) FROM dispatch WHERE status='QUEUED_LOCAL'").fetchone()[0]
    status = database.parent / 'cloud_status.json'
    if status.exists():
        result['cloud'] = json.loads(status.read_text(encoding='utf-8'))['status']
    return result


def sync_cloud(output_dir):
    """Explicit CLI operation; HTTPS endpoint must implement this JSON contract."""
    payload, path = export_backhaul(output_dir)
    endpoint = os.environ.get('IOV_CLOUD_URL', '')
    if not endpoint:
        return f'Local export saved: {path}. Cloud is not connected; set IOV_CLOUD_URL to an HTTPS ingestion endpoint.'
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('IOV_CLOUD_URL must be an HTTPS URL without embedded credentials.')
    body = json.dumps(payload).encode('utf-8')
    headers = {'Content-Type': 'application/json', 'Idempotency-Key': __import__('hashlib').sha256(body).hexdigest()}
    token = os.environ.get('IOV_CLOUD_TOKEN')
    if token:
        headers['Authorization'] = f'Bearer {token}'
    request = urllib.request.Request(endpoint, data=body, headers=headers, method='POST')
    with urllib.request.urlopen(request, timeout=30) as response:
        if not 200 <= response.status < 300:
            raise ValueError(f'Cloud rejected export (HTTP {response.status}).')
        status = response.status
    (Path(output_dir) / 'infrastructure' / 'cloud_status.json').write_text(
        json.dumps({'status': 'UPLOADED', 'http_status': status, 'endpoint': parsed.netloc}), encoding='utf-8')
    return f'Cloud export uploaded successfully (HTTP {status}). Emergency dispatch remains a local outbox.'


def dispatch_pending(output_dir):
    """Explicit dispatch adapter for a user-provided HTTPS emergency-service API."""
    payload, _ = export_backhaul(output_dir)
    endpoint = os.environ.get('IOV_EMERGENCY_URL', '')
    if not endpoint:
        return 'Emergency requests remain queued locally. Set IOV_EMERGENCY_URL to your test/service HTTPS endpoint.'
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('IOV_EMERGENCY_URL must be HTTPS without embedded credentials.')
    events = {(row['run_id'], row['event_id']): row['payload'] for row in payload['events']}
    delivered = 0
    for item in payload['dispatch_outbox']:
        if item['status'] != 'QUEUED_LOCAL':
            continue
        key = (item['run_id'], item['event_id'])
        headers = {'Content-Type': 'application/json', 'Idempotency-Key': ':'.join(key)}
        if os.environ.get('IOV_EMERGENCY_TOKEN'):
            headers['Authorization'] = 'Bearer ' + os.environ['IOV_EMERGENCY_TOKEN']
        request = urllib.request.Request(endpoint, data=json.dumps({'run_id': key[0], 'event': events[key]}).encode(),
                                         headers=headers, method='POST')
        with urllib.request.urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise ValueError(f'Dispatch rejected (HTTP {response.status}).')
        with sqlite3.connect(Path(output_dir) / 'infrastructure' / 'backhaul.sqlite3') as db:
            db.execute('UPDATE dispatch SET status=? WHERE run_id=? AND event_id=?', ('DELIVERED_REMOTE', *key))
        delivered += 1
    return f'{delivered} emergency record(s) delivered to the configured API.'
