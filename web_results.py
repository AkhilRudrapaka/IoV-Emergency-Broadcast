"""Local results viewer and faculty-demo dashboard. Run separately from the SUMO presentation.

The dashboard (results_viewer.html) follows one comparison pair (demo_pairs.py): its scenario, a baseline-only run and a
proposed-only run (each started here, one at a time, in its own SUMO-GUI), the selected run's live state and outcome, and
the side-by-side comparison, which is shown only when both runs replayed the same record. Every value comes from the
pair's own files; the multi-seed experiment results are served separately (/api/experiment)."""
import csv
import json
import math
import mimetypes
import os
import re
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import config
import demo_pairs
import experiment
import report

PORTAL_ROOT = Path(__file__).resolve().parent / 'portal'


def portal_asset(url_path):
    """Resolve public portal files without exposing neighboring project files."""
    relative = unquote(url_path).lstrip('/') or 'index.html'
    root = PORTAL_ROOT.resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        return None
    allowed = {'index.html', 'styles.css', 'app.js', 'data.js'}
    if relative not in allowed and not relative.startswith(('assets/', 'downloads/')):
        return None
    return candidate if candidate.is_file() else None


def saved_runs():
    paths = sorted(Path(config.RESULTS_DIR, 'raw').glob('*.json.gz'), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.name[:-8] for p in paths]


_metadata = {}                       # (run id, file mtime) -> list entry: each file is decompressed once


def run_metadata():
    from datetime import datetime
    items = []
    archived = {run_id.split('__')[0] for run_id in saved_runs() if '__' in run_id}
    for run_id in saved_runs()[:50]:                     # newest 50: bounded cost, readable selector
        if '__' not in run_id and run_id in archived:
            continue
        path = Path(config.RESULTS_DIR, 'raw', run_id + '.json.gz')
        try:
            key = (run_id, path.stat().st_mtime_ns)
        except OSError:
            key = (run_id, None)
        if key not in _metadata:
            try:
                raw = experiment.load_raw(run_id)
                _metadata[key] = {'id': run_id, 'saved_at': raw.get('recorded_at') or
                                  datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(),
                                  'timestamp_source': 'recorded run time' if raw.get('recorded_at') else 'file save time',
                                  'scenario': raw['scenario']['run_id']}
            except Exception:                         # still being written, or corrupt: list the others
                continue
        items.append(_metadata[key])
    return items


def live_state():
    """The SUMO demo's live counters (demo.live_feed), or {} when no demo has written any."""
    try:
        return json.loads(Path(config.RESULTS_DIR, 'live_demo.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def load_selection(run_id, scheme, forged):
    if not isinstance(run_id, str) or not re.fullmatch(r'd\d+_r\d+(?:__\d{8}T\d{12})?', run_id) or run_id not in saved_runs():
        raise ValueError('Choose an available saved run.')
    if scheme not in config.PROTOCOLS or forged not in (None, *config.FORGERY):
        raise ValueError('Choose a valid result.')
    raw = experiment.load_raw(run_id)
    if forged and not raw.get('forgery'):
        raise ValueError('This run has no forged-alert result.')
    if not forged and scheme not in raw['protocols']:
        raise ValueError('This scheme is not available in this run.')
    return raw


def result_data(raw, scheme, forged):
    record, alert, label = report.pick(raw, scheme, forged)
    return {'label': label, 'alert': alert, 'metrics': record['metrics'],
            'accepted': record['rsu_event'] is not None,
            'report': report.run_block(raw, scheme, forged)}


# ---------------------------------------------------------------- comparison pairs (faculty demo)
CAPTURE_FILE = re.compile(r'\d{3}\.png')
LIVE_FRESH_S = 15                    # a live state older than this is not 'live' any more
_start_lock = threading.Lock()       # one start request at a time (a double click cannot start two runs)


def _json_file(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _epoch(iso):
    try:
        return datetime.fromisoformat(iso).timestamp() if iso else None
    except ValueError:
        return None


def pair_summary(pair):
    s = pair['scenario']
    return {'pair_id': pair['pair_id'], 'created': pair['created'], 'baseline': pair['baseline'],
            'baseline_label': config.LABELS[pair['baseline']], 'scenario': s,
            'runs': {a: {k: r.get(k) for k in ('approach', 'algorithm', 'schemes', 'status', 'requested', 'started',
                                               'finished', 'message', 'fingerprint', 'exit_code')}
                     for a, r in pair['runs'].items()}}


def run_outcome(pair, approach, raw):
    """The selected run's own result, only for a finished run whose record is the one on disk; otherwise the reason."""
    from demo import record_fingerprint
    r = pair['runs'][approach]
    if r['status'] != 'finished':
        reason = {'not started': 'This run has not been started yet.',
                  'starting': 'The run is starting.',
                  'running': 'The run is in progress; its outcome appears when it has finished.',
                  'failed': f"The run failed: {r.get('message')}"}.get(r['status'], r['status'])
        return {'available': False, 'reason': reason}
    if raw is None:
        return {'available': False, 'reason': "This run's record cannot be read right now (it may be being rewritten "
                                              "by a run in progress)."}
    if record_fingerprint(raw) != r.get('fingerprint'):
        return {'available': False, 'reason': 'The record on disk is not the one this run replayed, so it is not shown.'}
    return {'available': True, 'fingerprint': r['fingerprint'],
            'rows': [row for row in demo_pairs.comparison_rows(pair, raw) if row['scheme'] in r['schemes']]}


def pair_view(pair_id):
    """Everything the dashboard shows for one pair, read from that pair's folder only: each run's outcome, live state
    and captures from that run's own folder. Live state and captures are shown for a run only if they were written
    after that run started (never an earlier run's leftovers); the live view is the most recently updated run's."""
    active = demo_pairs.reconcile()
    pair = demo_pairs.load(pair_id)
    folder = demo_pairs.pair_dir(pair_id)
    since = {a: _epoch(r.get('started') or r.get('requested')) for a, r in pair['runs'].items()}
    feeds = [(a, _json_file(os.path.join(demo_pairs.approach_dir(pair_id, a), 'live_demo.json'), {}))
             for a in demo_pairs.APPROACHES]
    feeds.append((None, _json_file(os.path.join(folder, 'live_demo.json'), {})))   # a pair run before per-approach folders
    feeds = [f for a, f in feeds if isinstance(f, dict) and f.get('pair_id') == pair_id and f.get('approach') in since
             and a in (None, f['approach']) and since[f['approach']] is not None
             and isinstance(f.get('updated'), (int, float)) and f['updated'] >= since[f['approach']]]
    live = max(feeds, key=lambda f: f['updated'], default={})
    if live:
        live['age_s'] = round(time.time() - live['updated'], 1)
        live['fresh'] = live['age_s'] < LIVE_FRESH_S
    captures = {}
    for a in demo_pairs.APPROACHES:
        captures[a] = [c for c in _json_file(os.path.join(folder, a, 'captures.json'), [])
                       if isinstance(c, dict) and c.get('approach') == a and CAPTURE_FILE.fullmatch(str(c.get('file')))
                       and since[a] is not None and c.get('captured', 0) >= since[a]
                       and os.path.isfile(os.path.join(folder, a, c['file']))]
    comparable, reason = demo_pairs.comparison(pair)
    return {'pair': pair_summary(pair), 'active': active, 'live': live, 'captures': captures,
            'outcomes': {a: run_outcome(pair, a, demo_pairs.record(pair, a)) for a in demo_pairs.APPROACHES},
            'comparison': {'available': comparable is not None, 'reason': reason,
                           'rows': demo_pairs.comparison_rows(pair, comparable) if comparable else [],
                           'fingerprint': pair['runs']['proposed'].get('fingerprint') if comparable else None,
                           'records': {a: os.path.relpath(demo_pairs.record_path(pair, a), folder).replace(os.sep, '/')
                                       for a in demo_pairs.APPROACHES}},
            'metrics': [{'key': k, 'label': l, 'unit': u, 'definition': d} for k, l, u, d in demo_pairs.METRICS],
            'folder': folder}


def experiment_summary():
    """Multi-seed results at the demo density from the experiment's processed/summary.csv: the mean, 95 % confidence
    half-width and number of seeds per value. Never mixed with a pair's single-run values."""
    path = Path(config.RESULTS_DIR, 'processed', 'summary.csv')
    keys = ['reachability', 't90_ms', 'transmissions', 'collision_losses', 'rsu_received', 'rsu_delay_ms']

    def num(text):
        try:
            v = float(text)
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if int(r['density']) == config.DEMO_DENSITY and r['protocol'] in demo_pairs.BASELINES + demo_pairs.PROPOSED:
                rows.append({'scheme': r['protocol'], 'label': config.LABELS[r['protocol']], 'runs': int(r['runs']),
                             'values': {k: {'mean': num(r.get(k)), 'ci95': num(r.get(k + '_ci95')),
                                            'n': int(float(r[k + '_n'])) if num(r.get(k + '_n')) is not None else None}
                                        for k in keys}})
    order = demo_pairs.BASELINES + demo_pairs.PROPOSED
    rows.sort(key=lambda r: order.index(r['scheme']))
    return {'source': str(path).replace('\\', '/'), 'density': config.DEMO_DENSITY, 'rows': rows,
            'modified': datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec='seconds')}


def capture_path(url_path):
    """/pairs/<pair>/<approach>/<NNN>.png -> that file of the pair's folder (nothing else is served)."""
    parts = unquote(url_path).strip('/').split('/')
    if len(parts) != 4 or parts[0] != 'pairs' or parts[2] not in demo_pairs.APPROACHES or not CAPTURE_FILE.fullmatch(parts[3]):
        return None
    try:
        path = Path(demo_pairs.pair_dir(parts[1]), parts[2], parts[3])
    except ValueError:
        return None
    return path if path.is_file() else None


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        # Some recorded metrics are NaN when a delay is undefined.
        def clean(value):
            if isinstance(value, float):
                import math
                return value if math.isfinite(value) else None
            if isinstance(value, dict):
                return {k: clean(v) for k, v in value.items()}
            if isinstance(value, list):
                return [clean(v) for v in value]
            return value
        self.respond(json.dumps(clean(data), ensure_ascii=False).encode(), 'application/json; charset=utf-8', status)

    def respond(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        try:
            if url.path in ('/', '/simulation', '/simulation/'):
                self.respond(Path(__file__).with_name('results_viewer.html').read_bytes(), 'text/html; charset=utf-8')
            elif url.path == '/api/runs':
                self.send_json({'runs': saved_runs(), 'records': run_metadata()})
            elif url.path == '/api/live':
                self.send_json(live_state())
            elif url.path == '/api/results':
                query = parse_qs(url.query)
                run_id = query.get('run', [''])[0]
                raw = load_selection(run_id, 'proposed', None)
                results = [{'scheme': scheme, 'forged': None, **result_data(raw, scheme, None)}
                           for scheme in raw['protocols'] if scheme in config.PROTOCOLS]
                if raw.get('forgery'):
                    results += [{'scheme': 'proposed', 'forged': variant, **result_data(raw, 'proposed', variant)}
                                for variant in raw['forgery']['variants'] if variant in config.FORGERY]
                self.send_json({'run': run_id, 'results': results})
            elif url.path == '/api/pairs':
                active = demo_pairs.reconcile()
                self.send_json({'pairs': [pair_summary(p) for p in demo_pairs.pairs()], 'active': active,
                                'baselines': [{'scheme': b, 'label': config.LABELS[b]} for b in demo_pairs.BASELINES]})
            elif url.path == '/api/pair':
                try:
                    self.send_json(pair_view(parse_qs(url.query).get('id', [''])[0]))
                except (ValueError, OSError):
                    self.send_json({'error': 'Choose an existing comparison pair.'}, 404)
                except Exception as exc:                      # never drop the connection without an answer
                    self.send_json({'error': f'The pair could not be read ({type(exc).__name__}); try again.'}, 500)
            elif url.path == '/api/experiment':
                try:
                    self.send_json(experiment_summary())
                except (OSError, KeyError, ValueError):
                    self.send_json({'error': 'No multi-seed results yet: run python run.py experiment.'}, 404)
            elif url.path.startswith('/pairs/'):
                path = capture_path(url.path)
                if path is None:
                    self.send_json({'error': 'Not found'}, 404)
                else:
                    self.respond(path.read_bytes(), 'image/png')
            else:
                asset = portal_asset(url.path)
                if asset is None:
                    self.send_json({'error': 'Not found'}, 404)
                else:
                    body = asset.read_bytes()
                    if asset.name == 'index.html':
                        body = body.replace(b'</head>', b'<script>window.RELAY_LOCAL_APP=true;</script></head>')
                    content_type = mimetypes.guess_type(asset.name)[0] or 'application/octet-stream'
                    if asset.suffix in ('.html', '.css', '.js'):
                        content_type += '; charset=utf-8'
                    self.respond(body, content_type)
        except (ValueError, KeyError, OSError):
            self.send_json({'error': 'Saved result could not be loaded. Choose a valid run.'}, 400)

    def do_POST(self):
        """Create a comparison pair, or start ONE separated run. A local tool: only JSON from this page is accepted, so a
        cross-site form or request cannot start a SUMO run."""
        url = urlparse(self.path)
        origin = self.headers.get('Origin')
        if origin and origin != f"http://{self.headers.get('Host')}":
            return self.send_json({'error': 'Cross-origin request refused.'}, 403)
        if (self.headers.get('Content-Type') or '').split(';')[0].strip() != 'application/json':
            return self.send_json({'error': 'Send JSON.'}, 415)
        try:
            length = int(self.headers.get('Content-Length') or 0)
            if length > 4096:
                raise ValueError('request too large')
            body = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(body, dict):
                raise ValueError('expected a JSON object')
            if url.path == '/api/pairs':
                self.send_json(pair_summary(demo_pairs.new_pair(body.get('baseline', 'flooding'))), 201)
            elif url.path == '/api/run':
                with _start_lock:
                    pid = demo_pairs.start(body.get('pair'), body.get('approach'))
                self.send_json({'started': True, 'pid': pid, 'pair_id': body.get('pair'), 'approach': body.get('approach')}, 202)
            else:
                self.send_json({'error': 'Not found'}, 404)
        except RuntimeError as exc:                                   # another run is active
            self.send_json({'error': str(exc)}, 409)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            self.send_json({'error': str(exc) or 'Invalid request.'}, 400)


def serve(port=8765):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'Results viewer: http://127.0.0.1:{port}\nKeep this terminal open. Run SUMO in another terminal.', flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
