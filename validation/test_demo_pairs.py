"""Separated faculty-demo runs, comparison pairs and the dashboard (demo_pairs.py, demo.run(approach=...), web_results).

SUMO-GUI is not started here: demo.run() is driven by stand-ins for SUMO, TraCI and the experiment that answer what it
asks, and the record is the tracked demo record results/urban/raw/d200_r02.json.gz (read only). Pairs are written to
tmp_path only."""
import copy
import gzip
import json
import math
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import numpy as np
import pytest

import config
import demo
import demo_pairs
import experiment
import web_results as web

RAW = experiment.load_raw('d200_r02')
SC = RAW['scenario']


@pytest.fixture
def root(tmp_path, monkeypatch):
    path = tmp_path / 'pairs'
    monkeypatch.setattr(demo_pairs, 'ROOT', str(path))
    return path


def fake_incident(run):
    """Distinct, valid incidents at least 80 m apart (no SUMO run)."""
    return {'vehicle': f'v{run}', 'x': 100.0 + 80 * (run % 8), 'y': 100.0 + 150 * (run // 8), 'lane': 'A1A2_1',
            'time_s': 60.0 + run, 'event_id': f'EVT-{run}'}


def nan_free(v):
    return None if isinstance(v, float) and math.isnan(v) else v


SEED = 4242                                              # a selection seed for the tests


def write_record(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'wt', encoding='utf-8') as f:
        json.dump(raw, f)


def make_pair(root, raw=RAW, statuses=('finished', 'finished'), fingerprints=None, pair_id='P001', baseline='flooding',
              shared=False):
    """A pair whose scenario and records are `raw`, as its runs leave them: each finished run's own record in
    <pair>/<approach>/raw/, or (shared=True, pairs run before per-approach folders) one record in <pair>/raw/."""
    sc = raw['scenario']
    fp = demo.record_fingerprint(raw)
    folder = root / pair_id
    folder.mkdir(parents=True)
    name = f"{sc['run_id']}.json.gz"
    if shared:
        write_record(folder / 'raw' / name, raw)
    for a, status in zip(demo_pairs.APPROACHES, statuses):
        if status == 'finished' and not shared:
            write_record(folder / a / 'raw' / name, raw)
    x, y = sc['incident_xy']
    pair = {'pair_id': pair_id, 'created': demo_pairs.now(), 'baseline': baseline,
            'scenario': {'scenario_id': sc['run_id'], 'density': sc['density'], 'run': sc['run'], 'seed': sc['seed'],
                         'network': config.NET_FILE,
                         'incident': {'vehicle': sc['source_id'], 'x': x, 'y': y, 'lane': 'D3E3_1',
                                      'time_s': float(sc['incident_time_s']), 'event_id': sc['alert']['event_id']},
                         'selection': {'method': 'chosen explicitly', 'selection_seed': SEED,
                                       'rank': None, 'repeat_of': None}},
            'runs': {}}
    for a, status, f in zip(demo_pairs.APPROACHES, statuses, fingerprints or (fp, fp)):
        pair['runs'][a] = {'approach': a, 'algorithm': demo_pairs.algorithm(a, baseline),
                           'schemes': demo_pairs.schemes_for(a, baseline), 'status': status,
                           'started': None if status == 'not started' else demo_pairs.now(),
                           'finished': demo_pairs.now() if status in ('finished', 'failed') else None,
                           'fingerprint': f if status == 'finished' else None,
                           'message': 'RuntimeError: boom' if status == 'failed' else None}
        if status == 'finished':
            pair['runs'][a]['record'] = os.path.join('raw', name) if shared else os.path.join(a, 'raw', name)
    demo_pairs.save(pair)
    return pair


# ---------------------------------------------------------------- which schemes a separated run replays
def test_each_approach_replays_only_its_own_implemented_schemes():
    assert demo_pairs.BASELINES == ['flooding', 'flooding_rad', 'slotted1p', 'slotted1p_rad']
    assert all(s in config.PROTOCOLS for s in demo_pairs.BASELINES + demo_pairs.PROPOSED)
    for b in demo_pairs.BASELINES:
        assert demo_pairs.schemes_for('baseline', b) == [b] and demo_pairs.algorithm('baseline', b) == config.LABELS[b]
    # the CH-to-CH route is replayed as a stage of the proposed method, never as a competing algorithm
    assert demo_pairs.schemes_for('proposed', 'flooding') == ['proposed', 'ch_route']
    assert demo_pairs.algorithm('proposed', 'flooding') == 'Proposed (full) with its CH-to-CH route stage'
    for bad in [('baseline', 'proposed'), ('baseline', 'ch_route'), ('baseline', 'no_rad'), ('both', 'flooding')]:
        with pytest.raises(ValueError):
            demo_pairs.schemes_for(*bad)


# ---------------------------------------------------------------- reproducible, varying incidents
def test_incident_selection_is_reproducible_and_varies():
    used, picks = [], []
    for _ in range(5):
        pick = demo_pairs.select(used, SEED, incident_of=fake_incident)
        assert demo_pairs.select(used, SEED, incident_of=fake_incident) == pick    # same seed and history -> same scenario
        run, inc, repeat_of, rank = pick
        assert repeat_of is None and inc == fake_incident(run)                     # the builder's incident, unchanged
        picks.append(run)
        used.append((demo_pairs.scenario_id(run), inc['x'], inc['y']))
    assert picks == demo_pairs.order(SEED)[:5] and len(set(picks)) == 5             # the seeded order, no repeats
    assert demo_pairs.order(SEED) == demo_pairs.order(SEED) and demo_pairs.order(SEED + 1) != demo_pairs.order(SEED)
    firsts = {demo_pairs.select([], s, incident_of=fake_incident)[0] for s in range(20)}
    assert len(firsts) > 5                                                           # other seeds: other first scenarios


def test_selection_skips_nearby_and_off_network_incidents_and_flags_any_repeat():
    order = demo_pairs.order(SEED)
    a, b, c = order[:3]

    def incident_of(run):
        inc = fake_incident(run)
        if run == b:
            inc.update(x=fake_incident(a)['x'] + 30, y=fake_incident(a)['y'])         # 30 m from a: the same location
        if run == c:
            inc.update(lane='nowhere_0')                                           # not a lane of the road network
        return inc

    at = lambda run: (demo_pairs.scenario_id(run), incident_of(run)['x'], incident_of(run)['y'])
    run, _, repeat_of, _ = demo_pairs.select([at(a)], SEED, incident_of=incident_of)
    assert run == order[3] and repeat_of is None
    # only b is left: it is offered, but recorded as a repeat of a's location
    run, _, repeat_of, _ = demo_pairs.select([at(r) for r in order if r != b], SEED, incident_of=incident_of)
    assert run == b and repeat_of == demo_pairs.scenario_id(a)
    # every scenario used: the least recently used one, again flagged
    run, _, repeat_of, _ = demo_pairs.select([at(r) for r in order], SEED, incident_of=incident_of)
    assert run == a and repeat_of == demo_pairs.scenario_id(a)
    assert not demo_pairs.valid({**fake_incident(0), 'x': -500.0}) and not demo_pairs.valid({**fake_incident(0), 'lane': ''})


def test_the_incident_of_a_scenario_comes_from_the_scenario_builder():
    inc = demo_pairs.incident(SC['run'])                                               # SUMO, headless, about 1 s
    assert (inc['vehicle'], [inc['x'], inc['y']], inc['time_s'], inc['event_id']) == \
        (SC['source_id'], SC['incident_xy'], float(SC['incident_time_s']), SC['alert']['event_id'])
    assert demo_pairs.valid(inc) and demo_pairs.scenario_id(SC['run']) == SC['run_id']


def test_new_pairs_record_reproducible_distinct_scenarios(root, monkeypatch):
    monkeypatch.setattr(demo_pairs, 'incident', fake_incident)
    p1, p2 = demo_pairs.new_pair('flooding'), demo_pairs.new_pair('slotted1p')
    assert (p1['pair_id'], p2['pair_id']) == ('P001', 'P002')
    seed = json.loads((root / demo_pairs.SELECTION).read_text())['selection_seed']   # drawn once for this folder
    assert p1['scenario']['selection']['selection_seed'] == p2['scenario']['selection']['selection_seed'] == seed
    assert [p1['scenario']['run'], p2['scenario']['run']] == demo_pairs.order(seed)[:2]
    for p in (p1, p2):
        s = p['scenario']
        assert s['seed'] == config.BASE_SEED + 100 * s['density'] + s['run'] and s['scenario_id'] == f"d{s['density']}_r{s['run']:02d}"
        assert s['incident'] == fake_incident(s['run']) and s['selection']['repeat_of'] is None
        assert {a: r['status'] for a, r in p['runs'].items()} == {'baseline': 'not started', 'proposed': 'not started'}
    assert p2['runs']['baseline']['schemes'] == ['slotted1p'] and p2['runs']['proposed']['schemes'] == ['proposed', 'ch_route']
    assert demo_pairs.load('P001') == p1
    again = demo_pairs.new_pair('flooding', run=p1['scenario']['run'])               # chosen again on purpose: flagged
    assert again['scenario']['selection']['repeat_of'] == p1['scenario']['scenario_id']
    for bad in ({'baseline': 'proposed'}, {'baseline': 'flooding', 'run': 99}):
        with pytest.raises(ValueError):
            demo_pairs.new_pair(**bad)


def test_each_new_pairs_folder_draws_its_own_selection_seed_and_keeps_it(tmp_path, monkeypatch):
    # 14 Nov: every fresh pairs folder offered the same sequence (one fixed seed), so a new folder's first pair always
    # replayed d200_r23. Each folder now draws its seed at random once, records it, and keeps it for its later pairs.
    monkeypatch.setattr(demo_pairs, 'incident', fake_incident)
    other = next(s for s in range(SEED + 1, SEED + 100) if demo_pairs.order(s)[0] != demo_pairs.order(SEED)[0])
    draws = iter([SEED, other])
    monkeypatch.setattr(demo_pairs.secrets, 'randbelow', lambda n: next(draws))
    firsts = []
    for name, seed in (('a', SEED), ('b', other)):
        monkeypatch.setattr(demo_pairs, 'ROOT', str(tmp_path / name))
        made = [demo_pairs.new_pair('flooding') for _ in range(3)]
        assert {p['scenario']['selection']['selection_seed'] for p in made} == {seed}   # drawn once, then kept
        assert json.loads((tmp_path / name / demo_pairs.SELECTION).read_text())['selection_seed'] == seed
        assert [p['scenario']['run'] for p in made] == demo_pairs.order(seed)[:3]      # reproducible from the seed
        xy = [(p['scenario']['incident']['x'], p['scenario']['incident']['y']) for p in made]
        assert all(math.dist(p, q) >= demo_pairs.MIN_SEPARATION_M for i, p in enumerate(xy) for q in xy[i + 1:])
        firsts.append(made[0]['scenario']['scenario_id'])
    assert firsts[0] != firsts[1]                                                      # two folders, two first incidents
    monkeypatch.setattr(demo_pairs.secrets, 'randbelow', lambda n: pytest.fail('a folder with pairs keeps its seed'))
    monkeypatch.setattr(demo_pairs, 'ROOT', str(tmp_path / 'legacy'))                  # made before selection.json
    make_pair(tmp_path / 'legacy', shared=True)
    assert demo_pairs.selection_seed() == SEED and demo_pairs.new_pair('flooding')['scenario']['selection']['selection_seed'] == SEED


def test_three_new_pairs_get_three_different_real_incidents(root, monkeypatch):
    """With the scenario builder itself (SUMO, headless): consecutive pairs of a folder never share an incident."""
    monkeypatch.setattr(demo_pairs.secrets, 'randbelow', lambda n: 7)                 # this folder's draw, fixed here
    made = [demo_pairs.new_pair('flooding') for _ in range(3)]
    incs = [p['scenario']['incident'] for p in made]
    assert len({p['scenario']['scenario_id'] for p in made}) == 3
    assert all(p['scenario']['selection']['repeat_of'] is None for p in made)
    assert all(math.dist((a['x'], a['y']), (b['x'], b['y'])) >= demo_pairs.MIN_SEPARATION_M
               for i, a in enumerate(incs) for b in incs[i + 1:])
    for p in made:
        assert p['scenario']['incident'] == demo_pairs.incident(p['scenario']['run'])  # the seed's own incident


# ---------------------------------------------------------------- what a separated run shows
def test_final_screen_names_the_runs_own_approach_and_its_own_record():
    for b in demo_pairs.BASELINES:
        screen, record = demo.final_screen(RAW, b), RAW['protocols'][b]
        ev = record['rsu_event']
        assert screen['banner'][0] == f"Outcome of the {config.LABELS[b]}: " + (
            f"{ev['receiving_rsu']} registered it" if ev else 'no RSU registered it')
        got = {v['id'] for v in record['vehicles'] if v['rx_ms'] is not None} - {SC['source_id']}
        assert {v for v, c in screen['vehicles'].items() if c == demo.HAS} == got     # colours from its own record
        assert screen['service'] == 'SERVICES: no dispatch recorded'               # the outbox holds the CH-route delivery
    proposed = demo.final_screen(RAW, 'proposed', True)
    assert proposed['banner'][0] == f"Outcome of the Proposed (full): {RAW['protocols']['proposed']['rsu_event']['receiving_rsu']} registered it"
    assert proposed['service'] == 'SERVICES: queued via CH route'
    assert demo.final_screen(RAW, 'proposed', False)['service'] == 'SERVICES: no dispatch recorded'
    default = demo.final_screen(RAW)                                                # the full walkthrough: unchanged
    assert default['banner'][0] == 'Outcome of the CH shortest-path delivery: RSU-2 registered it; dispatch queued locally'


class _Node:
    def __init__(self, root, path):
        self.root, self.path = root, path

    def __getattr__(self, name):
        return _Node(self.root, self.path + (name,))

    def __call__(self, *args, **kwargs):
        r, p = self.root, self.path
        r.log.append((p, args))
        if p == ('simulation', 'getTime'):
            return r.t
        if p == ('simulationStep',):
            r.t = float(args[0]) if args else r.t + 1.0
        if p == ('vehicle', 'getIDList'):
            return list(r.pos)
        if p == ('vehicle', 'getPosition'):
            return r.pos[args[0]]
        if p == ('gui', 'getOffset'):
            return (0.0, 0.0)
        if p == ('getConnection',):
            return SimpleNamespace(_process=SimpleNamespace(pid=0, wait=lambda timeout=None: 0))
        return None


class _FakeTraci:
    """TraCI stand-in: records every call and answers what demo.run asks (time, vehicle IDs, positions)."""
    exceptions = SimpleNamespace(FatalTraCIError=type('FatalTraCIError', (Exception,), {}))

    def __init__(self, sc):
        self.log, self.t = [], 0.0
        self.pos = {v['id']: (v['x'], v['y']) for v in sc['vehicles']}

    def __getattr__(self, name):
        return _Node(self, (name,))


def drive(monkeypatch, tmp_path, **kwargs):
    """demo.run() on the d200_r02 record with stand-ins for SUMO, TraCI and the experiment."""
    raw = copy.deepcopy(RAW)
    sc = raw['scenario']
    out = {'replays': [], 'lives': [], 'run_one': []}
    monkeypatch.setattr(config, 'RESULTS_DIR', str(tmp_path))
    monkeypatch.setattr(experiment, 'run_one', lambda d, r, **kw: out['run_one'].append((d, r, kw.get('archive', True))))
    monkeypatch.setattr(experiment, 'load_raw', lambda run_id: raw)
    t0 = float(sc['incident_time_s'])
    monkeypatch.setattr(demo, 'build', lambda d, r, workdir=None, history_s=0: {'history': [{'t': t0 - 1}, {'t': t0}]})
    role, labels = [v['role'] for v in sc['vehicles']], np.array([v['dbscan'] for v in sc['vehicles']])
    monkeypatch.setattr(demo, 'clusters_at', lambda step: (role, labels))
    real = demo.replay

    def replay(raw_, proto='proposed', forged=None, pace=0.35, title='', snap=None, shown=(0, 1, 2)):
        out['replays'].append((proto, forged, title, tuple(shown)))
        return real(raw_, proto, forged, 0, title, snap, shown)
    monkeypatch.setattr(demo, 'replay', replay)
    fake = _FakeTraci(sc)

    def feed(**state):                                   # also: what the window shows at the moment this state is written
        texts, colour = {}, {}
        for p, args in fake.log:
            if p == ('poi', 'setParameter'):
                texts[args[0]] = args[2]
            elif p == ('polygon', 'setColor') and args[0].startswith('stage-') and args[0][6:].isdigit():
                colour[int(args[0][6:])] = args[1]
        out['lives'].append(state)
        out.setdefault('screens', []).append((texts.get('label-status-a'), [i for i, c in colour.items() if c == demo.STAGE_NOW]))
    monkeypatch.setattr(demo, 'live_feed', feed)
    monkeypatch.setattr(demo, 'show', lambda text, live=False: None)
    monkeypatch.setattr(demo, 'traci', fake)
    demo._labels.clear()
    demo.run(sc['density'], sc['run'], pace=0, wait=False, **kwargs)
    out['texts'] = {args[0]: args[2] for p, args in fake.log if p == ('poi', 'setParameter')}
    out['stage_colour'] = {}
    for p, args in fake.log:
        if p == ('polygon', 'setColor') and args[0].startswith('stage-') and args[0][6:].isdigit():
            out['stage_colour'][int(args[0][6:])] = args[1]
    return out


def test_baseline_only_run_replays_only_its_baseline_and_ends_on_it(tmp_path, monkeypatch):
    out = drive(monkeypatch, tmp_path, schemes=['slotted1p'], approach='baseline', forged=True, archive=False)
    assert [(p, f) for p, f, _, _ in out['replays']] == [('slotted1p', None)]        # no proposed, no route, no forged test
    assert out['replays'][0][2:] == ('BASELINE-ONLY: Slotted 1-persistence', (0, 1))
    assert 'Cluster / CH' not in [l.get('workflow_stage') for l in out['lives']]     # clusters belong to the proposed method
    assert {l['scheme'] for l in out['lives']} <= {'live SUMO traffic', 'incident', 'Slotted 1-persistence'}
    ev = RAW['protocols']['slotted1p']['rsu_event']
    final = out['lives'][-1]
    assert final['done'] and final['scheme'] == 'Slotted 1-persistence'
    assert out['texts']['label-status-a'] == final['status'] == f"Outcome of the Slotted 1-persistence: {ev['receiving_rsu']} registered it"
    assert out['texts']['label-approach'] == 'BASELINE-ONLY RUN: Slotted 1-persistence  |  scenario d200_r02  |  seed 30002'
    assert out['texts']['label-service'].strip() == 'SERVICES: no dispatch recorded'
    assert out['stage_colour'][2] == demo.STAGE_FUTURE                                  # Cluster / CH stays white
    legend = {t.strip() for k, t in out['texts'].items() if k.startswith('label-legend-row-')}
    assert legend and not legend & {'Cluster member', 'Cluster head', 'CH route traversed'}   # never drawn here
    assert out['run_one'] == [(200, 2, False)]                                           # a pair run keeps no archive copy


def test_proposed_only_run_replays_the_proposed_method_with_its_route_stage(tmp_path, monkeypatch):
    out = drive(monkeypatch, tmp_path, schemes=['proposed', 'ch_route'], approach='proposed', archive=False)
    assert [(p, f) for p, f, _, _ in out['replays']] == [('proposed', None), ('ch_route', None), ('proposed', 'voting_reputation')]
    assert [t for _, _, t, _ in out['replays'][:2]] == ['PROPOSED-ONLY: Proposed (full)', 'PROPOSED-ONLY: CH-to-CH route stage']
    assert 'Cluster / CH' in [l.get('workflow_stage') for l in out['lives']]
    assert not {config.LABELS[b] for b in demo_pairs.BASELINES} & {l['scheme'] for l in out['lives']}   # never a baseline
    ev = RAW['protocols']['proposed']['rsu_event']
    assert out['texts']['label-status-a'] == out['lives'][-1]['status'] == f"Outcome of the Proposed (full): {ev['receiving_rsu']} registered it"
    assert out['texts']['label-service'].strip() == 'SERVICES: queued via CH route'
    assert out['texts']['label-approach'].startswith('PROPOSED-ONLY RUN: ')
    legend = {t.strip() for k, t in out['texts'].items() if k.startswith('label-legend-row-')}
    assert {'Cluster member', 'Cluster head', 'CH route traversed'} <= legend


@pytest.mark.parametrize('kwargs', [dict(schemes=['slotted1p'], approach='baseline', forged=True, archive=False),
                                    dict(schemes=['proposed', 'ch_route'], approach='proposed', archive=False)])
def test_a_separated_run_shows_each_live_state_when_it_writes_it(tmp_path, monkeypatch, kwargs):
    # a separated run captures the window at each live-feed write (demo._live_capture), so the window must already show
    # that state: its stage box and its status line (the final screen once wrote its state before raising its banner)
    out = drive(monkeypatch, tmp_path, **kwargs)
    assert len(out['screens']) == len(out['lives']) > 20
    for state, (text, now) in zip(out['lives'], out['screens']):
        if state['workflow_stage'] == 'live traffic':
            assert now == []
        else:
            assert (text, now) == (state['status'], [demo.STAGES.index(state['workflow_stage'])]), state


def test_default_demo_run_is_the_full_walkthrough_of_the_labelled_showcase_scenario(tmp_path, monkeypatch):
    out = drive(monkeypatch, tmp_path)
    assert out['texts']['label-scenario'] == ('FULL WALKTHROUGH  |  scenario d200_r02  |  seed 30002  |  fixed showcase '
                                              'scenario (-r N replays another seed)')
    assert [(p, f, t) for p, f, t, _ in out['replays']] == [
        ('flooding', None, 'Blind flooding (1 of 3)'), ('proposed', None, 'Proposed (full) (2 of 3)'),
        ('ch_route', None, 'CH shortest-path delivery (3 of 3)'),
        ('proposed', 'voting_reputation', 'FORGED alert test (full protection)')]
    assert 'label-approach' not in out['texts'] and not any('approach' in l for l in out['lives'])
    assert out['texts']['label-status-a'] == 'Outcome of the CH shortest-path delivery: RSU-2 registered it; dispatch queued locally'
    assert out['texts']['label-service'].strip() == 'SERVICES: dispatch queued (local)'
    assert out['run_one'] == [(200, 2, True)]                                            # re-simulated, archived, as before
    legend = sorted(t.strip() for k, t in out['texts'].items() if k.startswith('label-legend-row-'))
    assert legend == sorted(caption for _, _, caption in demo.LEGEND)                   # the full legend, as before
    demo._labels.clear()
    monkeypatch.setattr(config, 'DEMO_RUN', 5)                                         # -r 2 when the showcase is r05
    assert drive(monkeypatch, tmp_path)['texts']['label-scenario'] == 'FULL WALKTHROUGH  |  scenario d200_r02  |  seed 30002'
    separated = drive(monkeypatch, tmp_path, schemes=['flooding'], approach='baseline', archive=False)
    assert 'label-scenario' not in separated['texts']                                  # a pair run names its own run


def test_snapshots_of_an_earlier_run_never_mix_with_a_new_one(tmp_path, monkeypatch):
    shots = tmp_path / 'shots'
    shots.mkdir()
    for name in ('sumo_14_old.png', 'sumo_02_incident.png', 'snapshots.json', 'snapshots.js', 'notes.txt'):
        (shots / name).write_text('earlier run')
    taken = []

    def capture(pid, path):
        taken.append(os.path.basename(path))
        with open(path, 'w') as f:
            f.write('this run')
        return True
    monkeypatch.setattr(demo, 'capture_window', capture)
    drive(monkeypatch, tmp_path, shots=str(shots))
    left = sorted(p.name for p in shots.iterdir())
    assert left == sorted(set(taken) | {'snapshots.json', 'snapshots.js', 'notes.txt'})   # only this run's pictures
    assert all((shots / n).read_text() == 'this run' for n in taken)
    manifest = json.loads((shots / 'snapshots.json').read_text())
    assert manifest['run_id'] == 'd200_r02' and manifest['completed'] and {s['file'] for s in manifest['snapshots']} == set(taken)


def test_default_demo_command_is_unchanged(monkeypatch):
    import run as entry
    calls = []
    monkeypatch.setattr(demo, 'run', lambda *a, **k: calls.append((a, k)))
    for argv in (['run.py'], ['run.py', 'demo']):
        monkeypatch.setattr(sys, 'argv', list(argv))
        entry.main()
    assert calls == [((200, 2, ['flooding', 'proposed', 'ch_route'], 0.35, None), {'wait': True, 'forged': True})] * 2


def test_a_capture_never_stalls_a_run():
    # 14 Nov: PrintWindow waited 7 min for a SUMO-GUI window that had stopped responding, and the run waited with it.
    # capture_window now runs it through bounded(): a call that does not finish is abandoned after the timeout.
    t0 = time.time()
    assert demo.bounded(lambda: time.sleep(5), 0.2) == (False, None) and time.time() - t0 < 2
    assert demo.bounded(lambda: 42, 5) == (True, 42)
    assert demo.CAPTURE_TIMEOUT_S <= 15


def test_live_feed_of_a_separated_run_carries_its_context_and_captures(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'RESULTS_DIR', str(tmp_path))
    demo.live_feed(run_id='d200_r02', done=False)                                       # the full walkthrough: unchanged
    assert set(json.loads((tmp_path / 'live_demo.json').read_text())) == {'run_id', 'done', 'updated'}
    caps = tmp_path / 'caps'
    caps.mkdir()
    monkeypatch.setattr(demo, 'LIVE', {'pair_id': 'P001', 'approach': 'baseline', 'scenario_id': 'd200_r02', 'seed': 30002})
    monkeypatch.setattr(demo, 'CAPTURE', {'dir': str(caps), 'pid': 1, 'files': []})
    shots, order = [], []

    def capture(pid, path):
        shots.append(path)
        order.append('capture')
        open(path, 'wb').write(b'png')
        return True
    monkeypatch.setattr(demo, 'capture_window', capture)
    monkeypatch.setattr(demo, 'redraw', lambda: order.append('repaint'))
    monkeypatch.setattr(demo.time, 'sleep', lambda s: order.append(f'wait {s}'))
    # Regression (13 Nov, final report): a capture taken at the NEXT feed write showed the next state's indicator and text
    # (a CH-route capture showed the following forged-alert replay). The state being reported is captured at once,
    # after a repaint, so a picture always shows exactly what its metadata says.
    demo.live_feed(scheme='Blind flooding', workflow_stage='Votes', done=False)          # a new stage: captured at once
    assert len(shots) == 1 and order == ['repaint', 'wait 0.4', 'capture']
    demo.live_feed(scheme='Blind flooding', workflow_stage='Votes', done=False)          # same stage within 3 s: no capture
    assert len(shots) == 1
    demo.live_feed(scheme='Blind flooding', workflow_stage='RSU', done=True)             # the final screen: at once
    assert order == ['repaint', 'wait 0.4', 'capture'] * 2
    index = json.loads((caps / 'captures.json').read_text())
    assert [(c['file'], c['workflow_stage'], c['approach']) for c in index] == [('001.png', 'Votes', 'baseline'), ('002.png', 'RSU', 'baseline')]
    state = json.loads((tmp_path / 'live_demo.json').read_text())
    assert (state['pair_id'], state['approach'], state['seed'], state['snapshot']) == ('P001', 'baseline', 30002, '002.png')

    def broken(pid, path):
        raise OSError('no window')
    monkeypatch.setattr(demo, 'capture_window', broken)
    demo.live_feed(scheme='Blind flooding', workflow_stage='RSU', done=True)             # a failed capture never stops a run
    assert json.loads((tmp_path / 'live_demo.json').read_text())['snapshot'] == '002.png'


# ---------------------------------------------------------------- one record per pair, or no comparison
def test_comparison_needs_both_runs_finished_on_one_record(root):
    pair = make_pair(root)
    raw, reason = demo_pairs.comparison(pair)
    assert reason is None and demo.record_fingerprint(raw) == demo.record_fingerprint(RAW)
    rows = demo_pairs.comparison_rows(pair, raw)
    assert [r['scheme'] for r in rows] == ['flooding', 'flooding_rad', 'slotted1p', 'slotted1p_rad', 'proposed', 'ch_route']
    assert rows[0]['role'] == 'baseline: replayed in this pair' and rows[-1]['role'].startswith('proposed method: its CH-to-CH route stage')
    for row in rows:
        m = RAW['protocols'][row['scheme']]['metrics']
        assert [c['value'] for c in row['cells']] == [nan_free(m[k]) for k, _, _, _ in demo_pairs.METRICS]
    for pid, statuses, fps, why in [('P002', ('finished', 'running'), None, 'waiting for: proposed'),
                                    ('P003', ('failed', 'finished'), None, 'waiting for: baseline'),
                                    ('P004', ('finished', 'finished'), ('a' * 64, 'b' * 64), 'did not replay the same record')]:
        p = make_pair(root, statuses=statuses, fingerprints=fps, pair_id=pid)
        raw, reason = demo_pairs.comparison(p)
        assert raw is None and why in reason
    for a in demo_pairs.APPROACHES:                                                     # each run has its own record
        assert demo_pairs.record_path(pair, a) == str(root / 'P001' / a / 'raw' / 'd200_r02.json.gz')
    changed = copy.deepcopy(RAW)                                                        # one record changed after the runs
    changed['protocols']['flooding']['metrics']['transmissions'] += 1
    write_record(root / 'P001' / 'baseline' / 'raw' / 'd200_r02.json.gz', changed)
    assert demo_pairs.comparison(pair)[0] is None and demo_pairs.record(pair, 'proposed') is not None
    os.remove(root / 'P001' / 'baseline' / 'raw' / 'd200_r02.json.gz')                 # ... or is missing
    raw, reason = demo_pairs.comparison(pair)
    assert raw is None and 'missing or changed' in reason and demo_pairs.record(pair, 'baseline') is None


def test_a_pair_run_before_per_approach_folders_is_still_read(root):
    pair = make_pair(root, shared=True)                                                  # one shared <pair>/raw/ record
    for a in demo_pairs.APPROACHES:
        assert demo_pairs.record_path(pair, a) == str(root / 'P001' / 'raw' / 'd200_r02.json.gz')
    raw, reason = demo_pairs.comparison(pair)
    assert reason is None and demo.record_fingerprint(raw) == demo.record_fingerprint(RAW)


def test_a_pair_run_writes_only_into_its_own_approach_folder(root, monkeypatch):
    """run.py demo --pair P --approach A (SUMO stood in for): its record, live feed, SUMO log and captures land in
    <pair>/<A>/, a re-run clears only that folder, and the other run's files are never touched."""
    import run as entry
    monkeypatch.setattr(demo, 'LIVE', {})
    make_pair(root, statuses=('not started', 'finished'))
    folder = root / 'P001'
    (folder / 'baseline').mkdir()
    (folder / 'baseline' / '009.png').write_text('an earlier baseline run')
    proposed = {p: p.read_bytes() for p in (folder / 'proposed').rglob('*') if p.is_file()}
    monkeypatch.setattr(config, 'RESULTS_DIR', str(folder / 'baseline'))               # as after the re-exec
    calls = []

    def fake_run(density, run_index, schemes, pace, **kw):
        calls.append((density, run_index, list(schemes), kw['approach'], kw['capture_dir']))
        write_record(folder / 'baseline' / 'raw' / 'd200_r02.json.gz', RAW)
        kw['check'](RAW)
        (folder / 'baseline' / 'live_demo.json').write_text('{}')
        return RAW
    monkeypatch.setattr(demo, 'run', fake_run)
    entry.pair_demo(SimpleNamespace(pair='P001', approach='baseline', pace=0.0, no_forged=False))
    assert calls == [(200, 2, ['flooding'], 'baseline', str(folder / 'baseline'))]
    assert not (folder / 'baseline' / '009.png').exists() and not (folder / 'raw').exists()   # its own leftovers only
    assert {p: p.read_bytes() for p in (folder / 'proposed').rglob('*') if p.is_file()} == proposed
    r = demo_pairs.load('P001')['runs']['baseline']
    assert (r['status'], r['record']) == ('finished', os.path.join('baseline', 'raw', 'd200_r02.json.gz'))
    assert r['fingerprint'] == demo_pairs.load('P001')['runs']['proposed']['fingerprint'] == demo.record_fingerprint(RAW)
    assert demo_pairs.comparison(demo_pairs.load('P001'))[1] is None and not (root / demo_pairs.ACTIVE).exists()


def test_missing_values_are_labelled_never_invented(root):
    pair = make_pair(root)
    raw = copy.deepcopy(RAW)
    m = raw['protocols']['slotted1p']['metrics']
    m['t90_ms'], m['rsu_delay_ms'], m['rsu_dup_copies'] = float('nan'), float('nan'), float('nan')
    raw['protocols']['slotted1p']['rsu_event'] = None
    del raw['protocols']['flooding_rad']
    rows = {r['scheme']: r for r in demo_pairs.comparison_rows(pair, raw)}
    cells = {c['key']: c for c in rows['slotted1p']['cells']}
    assert (cells['t90_ms']['value'], cells['t90_ms']['text']) == (None, 'not reached')
    assert (cells['rsu_delay_ms']['value'], cells['rsu_delay_ms']['text']) == (None, 'not registered')
    assert (cells['rsu_dup_copies']['value'], cells['rsu_dup_copies']['text']) == (None, 'not available')
    assert not rows['flooding_rad']['available'] and rows['flooding_rad']['cells'] == [] and 'not in' in rows['flooding_rad']['reason']


def test_a_record_of_another_scenario_is_refused(root):
    pair = make_pair(root)
    demo_pairs.check_record(pair, RAW)
    for change in ({'seed': 1}, {'source_id': 'v0'}, {'incident_time_s': 61}, {'incident_xy': [0.0, 0.0]}, {'run_id': 'd200_r03'}):
        other = copy.deepcopy(RAW)
        other['scenario'].update(change)
        with pytest.raises(RuntimeError, match='not this pair'):
            demo_pairs.check_record(pair, other)


# ---------------------------------------------------------------- one run at a time, stale runs marked failed
def test_one_run_at_a_time_and_ended_runs_are_marked_failed(root):
    make_pair(root, statuses=('not started', 'not started'))
    demo_pairs.acquire('P001', 'baseline')
    with pytest.raises(RuntimeError, match='another demo run is active'):
        demo_pairs.acquire('P001', 'proposed')
    demo_pairs.release()
    assert not (root / demo_pairs.ACTIVE).exists()
    sleeper = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:                                                     # a lock held by another live process blocks every start
        (root / demo_pairs.ACTIVE).write_text(json.dumps({'pair_id': 'P001', 'approach': 'proposed', 'pid': sleeper.pid,
                                                          'started': demo_pairs.now()}))
        assert demo_pairs.pid_alive(sleeper.pid)
        with pytest.raises(RuntimeError):
            demo_pairs.acquire('P001', 'baseline')
        with pytest.raises(RuntimeError):
            demo_pairs.start('P001', 'baseline')
    finally:
        sleeper.kill()
        sleeper.wait()
    assert not demo_pairs.pid_alive(sleeper.pid)
    assert demo_pairs.reconcile() == [] and not (root / demo_pairs.ACTIVE).exists()   # its lock is cleared
    demo_pairs.update_run('P001', 'baseline', status='running', pid=sleeper.pid, started=demo_pairs.now())
    assert demo_pairs.reconcile() == []                                                 # never shown as running
    r = demo_pairs.load('P001')['runs']['baseline']
    assert r['status'] == 'failed' and 'ended without finishing' in r['message']
    demo_pairs.update_run('P001', 'proposed', status='starting', pid=None, requested=demo_pairs.now())
    assert [a['approach'] for a in demo_pairs.reconcile()] == ['proposed']              # just launched: still active
    old = (datetime.now().astimezone() - timedelta(seconds=demo_pairs.STARTING_GRACE_S + 5)).isoformat(timespec='seconds')
    demo_pairs.update_run('P001', 'proposed', requested=old)
    assert demo_pairs.reconcile() == [] and demo_pairs.load('P001')['runs']['proposed']['status'] == 'failed'
    assert demo_pairs.pid_alive(os.getpid()) and not demo_pairs.pid_alive(None)


def test_start_launches_one_separated_run_and_records_its_exit(root, monkeypatch):
    make_pair(root, statuses=('not started', 'not started'))
    gate, launched = threading.Event(), []

    class Proc:
        def __init__(self, pid, code):
            self.pid, self.code = pid, code

        def wait(self):
            gate.wait(10)
            return self.code
    procs = iter([Proc(4242, 0), Proc(4343, 3)])
    monkeypatch.setattr(demo_pairs.subprocess, 'Popen', lambda cmd, **kw: launched.append((cmd, kw)) or next(procs))
    alive = {4242}
    monkeypatch.setattr(demo_pairs, 'pid_alive', lambda pid: pid in alive)
    demo_pairs.start('P001', 'baseline')
    cmd, kw = launched[0]
    assert cmd[-6:] == ['demo', '--pair', 'P001', '--approach', 'baseline', '--no-wait']
    assert kw['env']['EXP_RESULTS_DIR'] == str(root / 'P001' / 'baseline') and kw['env']['DEMO_PAIRS_DIR'] == str(root)
    assert kw['stdout'].name == str(root / 'P001' / 'baseline_console.log')            # outside the folder a re-run clears
    r = demo_pairs.load('P001')['runs']['baseline']
    assert (r['status'], r['pid']) == ('starting', 4242)
    with pytest.raises(RuntimeError, match='another demo run is active'):                # overlap refused
        demo_pairs.start('P001', 'proposed')
    alive.clear()
    gate.set()
    deadline = time.time() + 10
    while demo_pairs.load('P001')['runs']['baseline'].get('exit_code') is None and time.time() < deadline:
        time.sleep(0.05)
    assert demo_pairs.load('P001')['runs']['baseline']['exit_code'] == 0
    gate.clear()
    demo_pairs.update_run('P001', 'baseline', status='finished')
    demo_pairs.start('P001', 'proposed')                                               # this process exits with code 3
    gate.set()
    deadline = time.time() + 10
    while demo_pairs.load('P001')['runs']['proposed'].get('exit_code') is None and time.time() < deadline:
        time.sleep(0.05)
    r = demo_pairs.load('P001')['runs']['proposed']
    assert r['exit_code'] == 3 and r['status'] == 'failed' and 'exited with code 3' in r['message']


# ---------------------------------------------------------------- the dashboard
@pytest.fixture
def server():
    srv = ThreadingHTTPServer(('127.0.0.1', 0), web.Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{srv.server_port}'
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=5)


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=30) as r:
        return json.load(r)


def post(base, path, body, content_type='application/json', origin=None):
    headers = {'Content-Type': content_type, **({'Origin': origin} if origin else {})}
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method='POST', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_dashboard_shows_only_the_selected_pairs_own_data(root, server):
    make_pair(root)
    folder = root / 'P001'
    started = web._epoch(demo_pairs.load('P001')['runs']['baseline']['started'])
    (folder / 'baseline' / '001.png').write_bytes(b'\x89PNG\r\n\x1a\nfake')
    (folder / 'baseline' / '003.png').write_bytes(b'\x89PNG\r\n\x1a\nold')
    entry = {'approach': 'baseline', 'scheme': 'Blind flooding', 'workflow_stage': 'RSU', 'status': 'done', 'done': True}
    (folder / 'baseline' / 'captures.json').write_text(json.dumps([
        {**entry, 'file': '001.png', 'captured': started + 1},
        {**entry, 'file': '002.png', 'captured': started + 1},                              # no such file
        {**entry, 'file': '003.png', 'captured': started - 3600},                           # older than this run
        {**entry, 'file': '../pair.json', 'captured': started + 1},
        {**entry, 'file': '004.png', 'captured': started + 1, 'approach': 'proposed'}]))     # another approach's
    (folder / 'baseline' / 'live_demo.json').write_text(json.dumps({'pair_id': 'P001', 'approach': 'baseline', 'scheme': 'Blind flooding',
                                                                   'workflow_stage': 'RSU', 'updated': started + 1, 'done': True}))
    (folder / 'proposed' / 'live_demo.json').write_text(json.dumps({'pair_id': 'P001', 'approach': 'proposed', 'scheme': 'Proposed (full)',
                                                                   'workflow_stage': 'RSU', 'updated': started + 2, 'done': True}))
    v = get(server, '/api/pair?id=P001')
    s = v['pair']['scenario']
    assert (s['scenario_id'], s['seed'], s['incident']['vehicle'], s['incident']['event_id']) == \
        (SC['run_id'], SC['seed'], SC['source_id'], SC['alert']['event_id'])
    assert [c['file'] for c in v['captures']['baseline']] == ['001.png'] and v['captures']['proposed'] == []
    assert v['live']['approach'] == 'proposed' and v['live']['scheme'] == 'Proposed (full)'
    for a in demo_pairs.APPROACHES:
        o = v['outcomes'][a]
        assert o['available'] and [r['scheme'] for r in o['rows']] == demo_pairs.schemes_for(a, 'flooding')
        for row in o['rows']:
            assert [c['value'] for c in row['cells']] == [nan_free(RAW['protocols'][row['scheme']]['metrics'][k])
                                                         for k, _, _, _ in demo_pairs.METRICS]
    c = v['comparison']
    assert c['available'] and c['fingerprint'] == demo.record_fingerprint(RAW) and len(c['rows']) == 6
    assert c['records'] == {a: f'{a}/raw/d200_r02.json.gz' for a in demo_pairs.APPROACHES}  # one record per run
    assert [m['key'] for m in v['metrics']] == [k for k, _, _, _ in demo_pairs.METRICS] and all(m['unit'] and m['definition'] for m in v['metrics'])
    with urllib.request.urlopen(server + '/pairs/P001/baseline/001.png', timeout=10) as r:
        assert r.read().startswith(b'\x89PNG')
    for bad in ('/pairs/P001/baseline/../pair.json', '/pairs/P001/other/001.png', '/pairs/P001/baseline/1.png',
                '/pairs/..%2F..%2Fsecret/baseline/001.png', '/api/pair?id=P999', '/api/pair?id=../x'):
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(server + bad, timeout=10)
        assert e.value.code == 404
    listed = get(server, '/api/pairs')
    assert [p['pair_id'] for p in listed['pairs']] == ['P001'] and listed['active'] == []
    assert {'exit_code', 'fingerprint', 'status'} <= set(listed['pairs'][0]['runs']['baseline'])
    assert [b['scheme'] for b in listed['baselines']] == demo_pairs.BASELINES
    with urllib.request.urlopen(server + '/', timeout=10) as r:
        page = r.read().decode('utf-8')
    order = [page.index(f'id="h-{h}"') for h in ('overview', 'scenario', 'live', 'outcome', 'comparison', 'evidence')]
    assert order == sorted(order)


def test_dashboard_withholds_failed_stale_and_changed_data(root, server):
    make_pair(root, statuses=('finished', 'failed'))
    v = get(server, '/api/pair?id=P001')
    assert not v['outcomes']['proposed']['available'] and 'failed: RuntimeError: boom' in v['outcomes']['proposed']['reason']
    assert v['outcomes']['baseline']['available']                                        # the finished run keeps its own
    assert not v['comparison']['available'] and v['comparison']['rows'] == []           # no partner: no comparison
    started = web._epoch(demo_pairs.load('P001')['runs']['baseline']['started'])
    feed = {'pair_id': 'P001', 'approach': 'baseline', 'scheme': 'x', 'updated': started - 10, 'done': True}
    (root / 'P001' / 'baseline' / 'live_demo.json').write_text(json.dumps(feed))
    assert get(server, '/api/pair?id=P001')['live'] == {}                               # an earlier run's leftover
    (root / 'P001' / 'proposed').mkdir()
    (root / 'P001' / 'proposed' / 'live_demo.json').write_text(json.dumps({**feed, 'updated': started + 10}))
    assert get(server, '/api/pair?id=P001')['live'] == {}                               # a feed in another run's folder
    changed = copy.deepcopy(RAW)
    changed['protocols']['flooding']['metrics']['transmissions'] += 1
    write_record(root / 'P001' / 'baseline' / 'raw' / 'd200_r02.json.gz', changed)
    o = get(server, '/api/pair?id=P001')['outcomes']['baseline']
    assert not o['available'] and 'not the one this run replayed' in o['reason'] and 'rows' not in o


def test_dashboard_shows_a_pair_run_before_per_approach_folders(root, server):
    make_pair(root, shared=True)
    started = web._epoch(demo_pairs.load('P001')['runs']['proposed']['started'])
    (root / 'P001' / 'live_demo.json').write_text(json.dumps({'pair_id': 'P001', 'approach': 'proposed', 'scheme': 'Proposed (full)',
                                                              'updated': started + 1, 'done': True}))
    v = get(server, '/api/pair?id=P001')
    assert v['live']['approach'] == 'proposed' and all(v['outcomes'][a]['available'] for a in demo_pairs.APPROACHES)
    assert v['comparison']['available'] and v['comparison']['records'] == {a: 'raw/d200_r02.json.gz' for a in demo_pairs.APPROACHES}


def test_dashboard_controls_create_pairs_and_start_one_run_at_a_time(root, server, monkeypatch):
    monkeypatch.setattr(demo_pairs, 'incident', fake_incident)
    code, body = post(server, '/api/pairs', {'baseline': 'slotted1p_rad'})
    assert code == 201 and body['pair_id'] == 'P001' and body['runs']['baseline']['schemes'] == ['slotted1p_rad']
    started = []

    def start(pair_id, approach, pace=None):
        demo_pairs.schemes_for(approach, demo_pairs.load(pair_id)['baseline'])
        if started:
            raise RuntimeError('another demo run is active: pair P001, baseline')
        started.append((pair_id, approach))
        return 4242
    monkeypatch.setattr(demo_pairs, 'start', start)
    assert post(server, '/api/run', {'pair': 'P001', 'approach': 'both'})[0] == 400
    assert post(server, '/api/run', {'pair': '../P001', 'approach': 'baseline'})[0] == 400
    code, body = post(server, '/api/run', {'pair': 'P001', 'approach': 'baseline'})
    assert code == 202 and body['pid'] == 4242 and started == [('P001', 'baseline')]
    code, body = post(server, '/api/run', {'pair': 'P001', 'approach': 'proposed'})
    assert code == 409 and 'another demo run is active' in body['error']
    assert post(server, '/api/run', {'pair': 'P001', 'approach': 'baseline'}, content_type='text/plain')[0] == 415
    assert post(server, '/api/run', {'pair': 'P001', 'approach': 'baseline'}, origin='http://example.com')[0] == 403
    assert started == [('P001', 'baseline')]


def test_a_record_being_rewritten_is_unreadable_not_an_error(root, server):
    """Regression (P002 driven through the dashboard): while a run rewrote the pair's record, reading the half-written
    gzip raised EOFError and the server dropped the connection without an answer."""
    make_pair(root)
    path = root / 'P001' / 'baseline' / 'raw' / 'd200_r02.json.gz'
    data = path.read_bytes()
    path.write_bytes(data[:len(data) // 2])                                             # half written
    assert demo_pairs.record(demo_pairs.load('P001'), 'baseline') is None
    v = get(server, '/api/pair?id=P001')
    assert not v['outcomes']['baseline']['available'] and 'cannot be read right now' in v['outcomes']['baseline']['reason']
    assert v['outcomes']['proposed']['available']                                        # the other run's own record
    assert not v['comparison']['available'] and v['comparison']['rows'] == []
