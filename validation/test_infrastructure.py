import json
import sqlite3

import numpy as np
import pytest

import infrastructure
import corroboration
from channel import geometry, simulate
from protocols import CHRoute
from scenario import create_alert


def test_shortest_route_excludes_untrusted_and_non_heads():
    xy = np.array([[0., 0.], [100., 0.], [200., 0.], [400., 0.]])
    _, adj = geometry(xy)
    result = infrastructure.shortest_route(xy, adj, ['MEMBER', 'CH', 'CH'],
                     [.9, .9, .9], [False]*3, 0, {3})
    assert result['status'] == 'ROUTE_FOUND'
    assert result['nodes'][0] == 0 and result['nodes'][-1] == 3
    assert result['distance_m'] == 400
    json.dumps(result)  # persisted route contains plain Python types
    blocked = infrastructure.shortest_route(xy, adj, ['MEMBER', 'MEMBER', 'CH'],
                     [.9, .9, .1], [False]*3, 0, {3})
    assert blocked['status'] == 'NO_CH_ROUTE'


def test_local_storage_is_idempotent_and_exportable(tmp_path, monkeypatch):
    event = {'event_id': 'one', 'status': 'REGISTERED'}
    trust = [{'vehicle_id': 'v1', 'before': .8, 'after': .81}]
    for _ in range(2):
        infrastructure.persist('run1', event, trust, tmp_path, {'vehicles': [{'id': 'v1', 'speed': 10, 'x': 1, 'y': 2}]})
    payload, path = infrastructure.export_backhaul(tmp_path)
    assert len(payload['events']) == len(payload['dispatch_outbox']) == len(payload['trust_updates']) == 1
    assert path.exists() and payload['dispatch_outbox'][0]['status'] == 'QUEUED_LOCAL'
    assert payload['vehicle_datasets'][0]['dataset']['vehicles'][0]['speed'] == 10
    assert infrastructure.analytics(tmp_path)['pending_dispatch'] == 1
    monkeypatch.delenv('IOV_CLOUD_URL', raising=False)
    assert 'not connected' in infrastructure.sync_cloud(tmp_path)
    monkeypatch.setenv('IOV_CLOUD_URL', 'http://example.invalid')
    with pytest.raises(ValueError, match='HTTPS'):
        infrastructure.sync_cloud(tmp_path)


def test_cluster_head_requires_received_quorum_before_forwarding():
    xy = np.array([[0., 0.], [250., 0.], [260., 10.], [260., -10.], [530., 0.]])
    dist, adj = geometry(xy)
    alert = create_alert(42, 'v0', xy[0], 90)
    security = {'alert': alert, 'committee': [1, 2, 3], 'voters': [1, 2, 3],
                'reputation': np.array([.9]*4), 'use_reputation': True}
    proto = CHRoute(dist, adj, np.zeros(5, bool), [0, 1, 4],
                    np.array([False]*4+[True]), security, np.array([-1, 0, 0, 0]), np.array([.9]*4))
    proto.names = ['v0', 'v1', 'v2', 'v3', 'rsu']
    log = simulate(proto, adj, 0, np.random.default_rng(10))
    assert proto.rounds[1]['accepted']
    assert len(proto.rounds[1]['received']) >= 3
    assert any(tx['kind'].startswith('CVOTE:') for tx in log)
    assert proto.has[4]
    assert not any(tx['kind'] == 'ALERT' and tx['sender'] in (2, 3) for tx in log)


def test_cluster_head_stops_when_members_cannot_vote():
    xy = np.array([[0., 0.], [250., 0.], [260., 10.], [260., -10.], [530., 0.]])
    dist, adj = geometry(xy)
    alert = create_alert(42, 'v0', xy[0], 90)
    security = {'alert': alert, 'committee': [1, 2, 3], 'voters': [1, 2, 3],
                'reputation': np.array([.9]*4), 'use_reputation': True}
    # Low local reputation excludes the two members, while the initial source
    # committee uses a distinct supplied prior in this isolated failure test.
    proto = CHRoute(dist, adj, np.zeros(5, bool), [0, 1, 4],
                    np.array([False]*4+[True]), security, np.array([-1, 0, 0, 0]), np.array([.9, .9, .1, .1]))
    proto.names = ['v0', 'v1', 'v2', 'v3', 'rsu']
    log = simulate(proto, adj, 0, np.random.default_rng(10))
    assert not proto.has[4]
    assert not any(tx['kind'] == 'ALERT' and tx['sender'] == 1 for tx in log)


def test_dispatch_marks_only_successful_requests_and_does_not_resend(tmp_path, monkeypatch):
    infrastructure.persist('run1', {'event_id': 'one', 'status': 'REGISTERED'}, [], tmp_path)
    monkeypatch.setenv('IOV_EMERGENCY_URL', 'https://example.invalid/events')
    requests = []
    class Response:
        status = 201
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def post(request, timeout):
        requests.append(request)
        assert json.loads(request.data)['event']['status'] == 'REGISTERED'
        return Response()
    monkeypatch.setattr(infrastructure.urllib.request, 'urlopen', post)
    assert infrastructure.dispatch_pending(tmp_path).startswith('1 emergency')
    assert infrastructure.dispatch_pending(tmp_path).startswith('0 emergency')
    assert len(requests) == 1


def test_failed_dispatch_remains_queued(tmp_path, monkeypatch):
    infrastructure.persist('run1', {'event_id': 'one', 'status': 'REGISTERED'}, [], tmp_path)
    monkeypatch.setenv('IOV_EMERGENCY_URL', 'https://example.invalid/events')
    def fail(*args, **kwargs):
        raise OSError('Endpoint unavailable')
    monkeypatch.setattr(infrastructure.urllib.request, 'urlopen', fail)
    with pytest.raises(OSError):
        infrastructure.dispatch_pending(tmp_path)
    payload, _ = infrastructure.export_backhaul(tmp_path)
    assert payload['dispatch_outbox'][0]['status'] == 'QUEUED_LOCAL'


def test_batch_authentication_deduplicates_and_rejects_tampering():
    alert = create_alert(99, 'v0', (10, 20), 90)
    cert = corroboration.certificate(alert, 'v0', ['v1', 'v2', 'v3'])
    tampered = {**alert, 'incident_position': [20, 20]}
    accepted, rejected = infrastructure.batch_authenticate(
        [(alert, cert), (alert, cert), (tampered, cert)], {f'v{i}': .9 for i in range(4)})
    assert len(accepted) == 1
    assert len(rejected) == 1 and 'invalid' in rejected[0]['reason']
