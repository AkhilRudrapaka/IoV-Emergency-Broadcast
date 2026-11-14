import pytest
import web_results as web


def test_portal_assets_are_confined_to_public_files():
    assert web.portal_asset('/').name == 'index.html'
    assert web.portal_asset('/styles.css').is_file()
    assert web.portal_asset('/assets/summary.csv').is_file()
    for path in ['/../.env', '/%2e%2e/.env', '/downloads/../../config.py', '/README.md', '/package.json']:
        assert web.portal_asset(path) is None


def test_documentation_and_original_results_routes():
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    server = ThreadingHTTPServer(('127.0.0.1', 0), web.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        for path, marker in [('/', b'id="documentation-buttons"'),
                             ('/index.html', b'window.RELAY_LOCAL_APP=true'),
                             ('/simulation', b'id="scope"'),
                             ('/app.js', b'Introduction and Background'),
                             ('/assets/summary.csv', b'density,protocol'),
                             ('/api/runs', b'"records"')]:
            with urllib.request.urlopen(base + path, timeout=15) as response:
                assert response.status == 200
                assert marker in response.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_selection_rejects_path_traversal_and_invalid_schemes(monkeypatch):
    monkeypatch.setattr(web, 'saved_runs', lambda: ['d200_r02'])
    for run, scheme, forged in [('../.env', 'proposed', None), ('d200_r02', 'bad', None),
                                ('d200_r02', 'proposed', 'bad')]:
        with pytest.raises(ValueError):
            web.load_selection(run, scheme, forged)


def test_forged_report_has_its_own_rejected_outcome():
    import experiment
    raw = experiment.load_raw('d200_r02')
    result = web.result_data(raw, 'proposed', 'voting_reputation')
    assert not result['accepted']
    assert 'FORGED ALERT' in result['report']
    assert 'honest vehicles' in result['report']
    assert 'REJECTED' in result['report']


def test_run_history_uses_recorded_system_time_and_hides_latest_alias(monkeypatch):
    record_id = 'd200_r02__20261008T170100123456'
    monkeypatch.setattr(web, 'saved_runs', lambda: [record_id, 'd200_r02'])
    monkeypatch.setattr(web.experiment, 'load_raw', lambda _: {
        'recorded_at': '2026-10-08T17:01:00.123456+05:30', 'scenario': {'run_id': 'd200_r02'}})
    records = web.run_metadata()
    assert len(records) == 1
    assert records[0]['id'] == record_id
    assert records[0]['saved_at'] == '2026-10-08T17:01:00.123456+05:30'
    assert records[0]['timestamp_source'] == 'recorded run time'


def test_live_feed_and_corrupt_raw_files(tmp_path, monkeypatch):
    """/api/live mirrors demo.live_feed; one unreadable raw file must not break the run list (audit DEM-10)."""
    import json
    import config
    import demo
    monkeypatch.setattr(config, 'RESULTS_DIR', str(tmp_path))
    assert web.live_state() == {}
    demo.live_feed(run_id='d200_r02', scheme='Proposed (full)', t_ms=12.5, frames=7, done=False)
    state = web.live_state()
    assert state['frames'] == 7 and state['t_ms'] == 12.5 and 'updated' in state
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / 'd50_r00.json.gz').write_bytes(b'\x1f\x8b\x08\x00broken')            # truncated gzip
    monkeypatch.setattr(web.experiment, 'RAW', str(raw))                     # load_raw's folder
    monkeypatch.setattr(web, 'saved_runs', lambda: ['d50_r00'])
    assert web.run_metadata() == []


def test_rsu_markers_show_each_recorded_outcome_and_the_final_screen_is_the_genuine_one():
    """Regression (2026-11-03 visible-demo check): the end screen kept the forged-alert test's 'RSU-2 REJECTED'
    while the banner said the event was registered. Markers now come from one recorded dissemination."""
    import demo
    import experiment
    raw = experiment.load_raw('d200_r02')
    rsus = [u['id'] for u in raw['scenario']['rsus']]
    for scheme in ('ch_route', 'proposed'):
        record = raw['protocols'][scheme]
        shown = {u: demo.rsu_outcome(record, u) for u in rsus}
        registered = record['rsu_event']['receiving_rsu']
        assert shown[registered][0] == demo.RSU_OK and shown[registered][1].startswith('registered +')
        assert all(state != 'rejected' for _, state in shown.values())      # a genuine registered event
        others = {r['rsu'] for r in record['rsu_receptions']} - {registered}
        assert all(shown[u][0] == demo.RSU_DUP and shown[u][1].startswith('duplicate +') for u in others)
        assert all(len(f'{u}: {state}') <= 26 for u, (_, state) in shown.items())   # fits the side panel
    forged = raw['forgery']['variants']['voting_reputation']
    for u in rsus:
        copies = [r for r in forged['rsu_receptions'] if r['rsu'] == u]
        assert demo.rsu_outcome(forged, u) == ((demo.RSU_BAD, 'rejected') if copies else (demo.RSU_IDLE, 'listening'))


def test_final_screen_comes_from_one_recorded_dissemination():
    """Regression (skeptic R1/R3): the end screen coloured vehicles from the proposed scheme while its RSU markers and
    banner came from the CH route. final_screen() is what run() applies; every part must come from the CH route."""
    import copy
    import demo
    import experiment
    raw = experiment.load_raw('d200_r02')
    record = raw['protocols']['ch_route']
    reached = {v['id'] for v in record['vehicles'] if v['rx_ms'] is not None}
    screen = demo.final_screen(raw)
    blue = {v for v, c in screen['vehicles'].items() if c == demo.HAS}
    assert blue == reached - {raw['scenario']['source_id']}                  # not the proposed scheme's 200
    assert screen['vehicles'][raw['scenario']['source_id']] == demo.CRASH
    registered = record['rsu_event']['receiving_rsu']
    assert screen['rsus'][registered][1].startswith('registered +') and registered in screen['rsu']
    assert 'dispatch queued' in screen['service'] and 'CH shortest-path delivery' in screen['banner'][0]
    failed = copy.deepcopy(raw)                                               # a run where the CH route delivers nothing
    failed['protocols']['ch_route']['rsu_event'] = None
    failed['protocols']['ch_route']['rsu_receptions'] = []
    screen = demo.final_screen(failed)
    assert all(state == 'listening' for _, state in screen['rsus'].values())
    assert screen['service'] == 'SERVICES: no validated alert' and screen['rsu'] == 'no RSU registered it'


def test_replay_ends_on_the_recorded_receptions_lost(tmp_path, monkeypatch):
    """Regression (skeptic R2): a frame that ends in a half millisecond with no other event was never counted, so
    the last banner / live state under-reported receptions lost. Replayed here with a stub in place of TraCI."""
    import copy
    import json
    import math
    import config
    import demo
    import experiment

    class Stub:                                                               # accepts every TraCI call
        def __getattr__(self, name):
            return self

        def __call__(self, *args, **kwargs):
            return (0.0, 0.0)

    raw = copy.deepcopy(experiment.load_raw('d200_r02'))
    P = raw['protocols']['flooding']
    end = max([t['end_ms'] for t in P['transmissions']] + [v['decided_ms'] or 0 for v in P['vehicles']]
              + [v['rx_ms'] or 0 for v in P['vehicles']])
    start = (math.floor(end / demo.BIN_MS) + 2) * demo.BIN_MS - 0.05          # after everything recorded
    P['transmissions'].append({'sender': raw['scenario']['source_id'], 'kind': 'ALERT', 'start_ms': start,
                               'end_ms': round(start + 0.655, 3), 'new': 0, 'dup': 0, 'other': 0, 'lost': 7})
    P['metrics']['transmissions'] += 1
    P['metrics']['collision_losses'] += 7
    monkeypatch.setattr(demo, 'traci', Stub())
    monkeypatch.setattr(config, 'RESULTS_DIR', str(tmp_path))
    demo.replay(raw, 'flooding', pace=0)
    live = json.loads((tmp_path / 'live_demo.json').read_text(encoding='utf-8'))
    assert live['collisions'] == P['metrics']['collision_losses'] and live['frames'] == P['metrics']['transmissions']
    assert live['workflow_stage'] == 'RSU' and live['run_id'] == raw['scenario']['run_id']


def _bins(P):
    import demo
    end = max([t['end_ms'] for t in P['transmissions']] + [v['decided_ms'] or 0 for v in P['vehicles']]
              + [v['rx_ms'] or 0 for v in P['vehicles']])
    return [(k + 1) * demo.BIN_MS for k in range(int(end / demo.BIN_MS) + 2)]


def test_workflow_indicator_never_runs_ahead_of_the_record():
    """The indicator's stage and status come only from events that started before the displayed radio time:
    no vote count, certificate, forwarding stage or RSU outcome appears early, and stages never go backwards."""
    import re
    import demo
    import experiment
    raw = experiment.load_raw('d200_r02')
    records = [(p, raw['protocols'][p], raw['scenario']['alert'], False) for p in raw['protocols']]
    records.append(('forged', raw['forgery']['variants']['voting_reputation'], raw['forgery']['alert'], True))
    for name, P, alert, forged in records:
        src, last = alert['source_vehicle'], -1
        for hi in _bins(P):
            stage, line, rsu_done = demo.stage_state(P, alert, hi, forged=forged)
            started = [t for t in P['transmissions'] if t['start_ms'] < hi]
            assert stage >= last, (name, hi, 'stage went backwards')
            last = stage
            released = any(t['kind'] == 'ALERT' and t['sender'] == src for t in started)
            if stage >= 4 and P['corroboration']:
                assert released, (name, hi, 'certificate shown before the source released it')
            if stage == 3:
                shown = int(re.match(r'Votes: (\d+)', line).group(1))
                assert shown == sum(t['kind'] == 'VOTE' for t in started), (name, hi, line)
            if P['corroboration'] and released:     # skeptic: the CH route's local round showed as 'Certificate'
                moving = any(t['sender'] != src and t['kind'] != 'VOTE' for t in started)
                assert (stage == 5) == moving, (name, hi, stage, 'forwarding = a relay or a head\'s local round')
            assert rsu_done == any(r['delay_ms'] < hi for r in P['rsu_receptions']), (name, hi)
            assert stage < 6, (name, hi, 'RSU stage before the replay finished')
            if stage == 5 and not forged:          # RSU outcomes on the forwarding line: only checks already finished
                done = [r['status'].split(':')[0] for r in P['rsu_receptions'] if r['delay_ms'] < hi]
                shown = re.search(r'RSU copies: (\d+) registered, (\d+) duplicates?(?:, (\d+) rejected)?', line)
                assert (shown is None) == (not done), (name, hi, line)
                if shown:
                    assert [int(g or 0) for g in shown.groups()] == \
                        [done.count('REGISTERED'), done.count('DUPLICATE'), done.count('REJECTED')], (name, hi, line)
        stage, line, _ = demo.stage_state(P, alert, float('inf'), finished=True, forged=forged)
        assert stage == 6 and (P['rsu_event'] is None or P['rsu_event']['receiving_rsu'] in line)


def test_route_hops_appear_only_after_the_head_accepted_the_alert():
    import demo
    import experiment
    raw = experiment.load_raw('d200_r02')
    P, route = raw['protocols']['ch_route'], raw['infrastructure']['route']['vehicle_ids']
    rx = {v['id']: v['rx_ms'] for v in P['vehicles']}
    arrival = min(r['arrival_ms'] for r in P['rsu_receptions'] if r['rsu'] == route[-1])
    for hi in _bins(P):
        for node in demo.route_progress(P, route, hi)[1:]:
            assert (arrival if node.startswith('RSU') else rx[node]) < hi, (node, hi)
    assert demo.route_progress(P, route, float('inf')) == route                   # it did reach its RSU


def test_snapshot_manifest_lists_stages_in_workflow_order(tmp_path):
    import json
    import demo
    entries = [{'key': k, 'stage': k, 'file': f'{k}.png'}
               for k in ('rsu', 'incident', 'duplicates', 'votes', 'traffic', 'clusters')]
    demo.write_manifest(str(tmp_path), {'run_id': 'd200_r02'}, entries)
    data = json.loads((tmp_path / 'snapshots.json').read_text(encoding='utf-8'))
    assert [e['key'] for e in data['snapshots']] == ['traffic', 'incident', 'clusters', 'votes', 'duplicates', 'rsu']
    assert (tmp_path / 'snapshots.js').read_text(encoding='utf-8').startswith('window.SUMO_SNAPSHOTS = ')


def _displayed(raw, tmp_path, monkeypatch):
    """Replays the three schemes and the forged test with a stand-in for TraCI that records every call, and rebuilds
    what SUMO-GUI showed at each repaint: [(scheme, frames, shots, overlays left, live states, terminal panels)], one
    frame per repaint = (stage highlighted, status line, pink vehicles, orange vehicles, live halo / link / route
    polygons, stages marked done, an RSU has a copy)."""
    import config
    import demo
    log = []
    monkeypatch.setattr(demo, 'live_feed', lambda **state: log.append((('live',), state)))
    monkeypatch.setattr(demo, 'show', lambda text, live=False: log.append((('show',), text)))

    class Recorder:
        def __init__(self, path=()):
            self.path = path

        def __getattr__(self, name):
            return Recorder(self.path + (name,))

        def __call__(self, *args, **kwargs):
            log.append((self.path, args))
            return (0.0, 0.0)

    monkeypatch.setattr(demo, 'traci', Recorder())
    monkeypatch.setattr(config, 'RESULTS_DIR', str(tmp_path))
    out = []
    for proto, forged in (('flooding', None), ('proposed', None), ('ch_route', None), ('proposed', 'voting_reputation')):
        log.clear()
        demo.replay(raw, proto, forged, pace=0, snap=lambda *a: log.append((('snap',), a)))
        stage, status, colour, alive, frames, shots, box, swatch = None, None, {}, set(), [], [], {}, {}
        lives = [args for path, args in log if path == ('live',)]
        panels = [args for path, args in log if path == ('show',)]
        for path, args in log:
            if path == ('polygon', 'setColor') and args[0].startswith('stage-'):
                box[int(args[0].split('-')[1])] = args[1]
                if args[1] == demo.STAGE_NOW:
                    stage = int(args[0].split('-')[1])
            elif path == ('polygon', 'setColor') and args[0].startswith('rsu-swatch-'):
                swatch[args[0]] = args[1]
            elif path == ('poi', 'setParameter') and args[0] == 'label-status-a':
                status = args[2]
            elif path == ('vehicle', 'setColor'):
                colour[args[0]] = args[1]
            elif path == ('polygon', 'add') and args[0].startswith(('halo-', 'link-', 'route-')):
                alive.add(args[0])
            elif path == ('polygon', 'remove'):
                alive.discard(args[0])
            elif path == ('gui', 'setOffset'):                                   # redraw(): one displayed frame
                frames.append((stage, status, {v for v, c in colour.items() if c == demo.VOTE},
                               {v for v, c in colour.items() if c == demo.TX}, set(alive),
                               {i for i, c in box.items() if c == demo.STAGE_DONE},
                               any(c != demo.RSU_IDLE for c in swatch.values())))
            elif path == ('snap',):
                shots.append((args, stage, status))
        out.append((forged or proto, frames, shots, alive, lives, panels))
    return out


def test_snapshots_carry_the_stage_the_indicator_shows_at_that_moment(tmp_path, monkeypatch):
    """Every portal snapshot is labelled with the stage the indicator highlights when it is taken, and its caption
    is the status line on screen (skeptic: the route snapshot was hard-wired to 'Forwarding / Route'). In d100_r00
    the source reaches the RSU directly (a one-hop route): no forwarding happens, so the route shows at 'RSU'."""
    import demo
    import experiment
    for run, route_stage in (('d200_r02', 'Forwarding / Route'), ('d100_r00', 'RSU')):
        keys = {}
        for scheme, _, shots, *_ in _displayed(experiment.load_raw(run), tmp_path, monkeypatch):
            for (key, stage, caption, ms, name), shown, line in shots:
                keys[key] = stage
                assert stage == demo.STAGES[shown] and caption == line, (run, scheme, key, stage, demo.STAGES[shown])
        assert keys['route'] == route_stage, (run, keys)
        if run == 'd200_r02':                  # RSU-1's first copy in the proposed scheme is a duplicate
            assert keys['duplicates'] == 'Forwarding / Route', keys
    assert set(keys) >= {'votes', 'certificate', 'rsu', 'route', 'forged'}


def test_overlays_follow_the_indicator_and_never_linger(tmp_path, monkeypatch):
    """Skeptic (display review): on the CH route a hop and the head's local round appeared while the indicator still
    said 'Certificate'. At every repaint: route lines only from 'Forwarding / Route' on, pink only during 'Votes' or
    while that vehicle's vote is on air, orange only while its frame is on air; nothing is left after a replay. The
    radio time shown never runs backwards and the finished state is not earlier than any event it summarises (RSU
    duplicates included); the terminal's vote count is the committee's only (the CH route's local votes added 5).
    Second short review: a box is marked done only if its stage happened (the forged test showed 'Forwarding / Route'
    done, though nothing was forwarded), and the forged Certificate line was cut ('... 3 need')."""
    import re
    import config
    import demo
    import experiment
    for run in ('d200_r02', 'd100_r00'):
        raw = experiment.load_raw(run)
        route = raw['infrastructure']['route']['vehicle_ids']
        for scheme, frames, _, alive, lives, panels in _displayed(raw, tmp_path, monkeypatch):
            P = demo.report.pick(raw, 'proposed' if scheme == 'voting_reputation' else scheme,
                                 'voting_reputation' if scheme == 'voting_reputation' else None)[0]
            times = [s['t_ms'] for s in lives]
            assert times == sorted(times), (run, scheme, 'radio time ran backwards')
            last = max([t['end_ms'] for t in P['transmissions']] + [r['delay_ms'] for r in P['rsu_receptions']]
                       + [v['rx_ms'] or 0 for v in P['vehicles']] + [v['decided_ms'] or 0 for v in P['vehicles']])
            assert times[-1] == round(last, 1) and lives[-1]['workflow_stage'] == 'RSU', (run, scheme, times[-1], last)
            for text in panels:
                cast = re.search(r'Votes\s*: (\d+) cast', text)
                assert not cast or int(cast.group(1)) <= config.COMMITTEE_SIZE, (run, scheme, cast.group(0))
            drawn, seen = set(), set()
            for stage, line, pink, orange, overlays, done, rsu_copy in frames:
                seen.add(stage)
                assert done <= {0, 1, 2} | seen | ({6} if rsu_copy else set()), (run, scheme, stage, sorted(done))
                hops = {k for k in overlays if k.startswith('route-')}
                drawn |= hops
                assert not hops or stage >= 5, (run, scheme, stage, sorted(hops))
                on_air = {k.split('-', 2)[2] for k in overlays if k.startswith('halo-')}
                assert stage == 3 or pink <= on_air, (run, scheme, stage, sorted(pink - on_air))
                assert orange <= on_air, (run, scheme, stage, sorted(orange - on_air))
            assert not alive, (run, scheme, sorted(alive)[:5])
            assert len(drawn) == (2 * len(route) - 3 if scheme == 'ch_route' else 0), (run, scheme, sorted(drawn))
            if scheme == 'voting_reputation':                          # its Certificate line ends with the reason
                assert all(f[1].endswith(P['corroboration']['reason']) for f in frames if f[0] == 4), run
        hops_happened = len(route) > 2                                 # one-hop route: the source reaches the RSU
        assert demo.final_screen(raw)['reached'] == {0, 1, 2, 3, 4, 6} | ({5} if hops_happened else set()), run
