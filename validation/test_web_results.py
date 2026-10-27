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
                             ('/simulation', b'id="explain"'),
                             ('/app.js', b'Introduction and Background'),
                             ('/assets/summary.csv', b'density,protocol'),
                             ('/api/runs', b'"languages"')]:
            with urllib.request.urlopen(base + path, timeout=15) as response:
                assert response.status == 200
                assert marker in response.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_all_languages_have_native_script_and_separate_caches(monkeypatch, tmp_path):
    monkeypatch.setattr(web.config, 'RESULTS_DIR', str(tmp_path))
    monkeypatch.setattr(web.report, 'run_block', lambda raw, scheme, forged: f'{scheme}:{forged}')
    calls = []
    for code, (name, _, lo, _) in web.LANGUAGES.items():
        def completion(messages, name=name, lo=lo, **kwargs):
            calls.append(messages)
            assert name in messages[0]['content']
            return chr(lo + 5) + ' explanation'
        monkeypatch.setattr(web.narrator, 'completion', completion)
        assert web.explain_result({}, 'proposed', None, code)['source'] == 'AI generated'
        assert web.explain_result({}, 'proposed', None, code)['source'] == 'cached AI'
        assert web.explain_result({}, 'proposed', 'voting_reputation', code)['source'] == 'AI generated'
    assert len(calls) == 2 * len(web.LANGUAGES)
    assert len(list(tmp_path.glob('narration/web-*.json'))) == 2 * len(web.LANGUAGES)


def test_api_failure_and_wrong_language_are_not_presented_as_translation(monkeypatch, tmp_path):
    monkeypatch.setattr(web.config, 'RESULTS_DIR', str(tmp_path))
    monkeypatch.setattr(web.report, 'run_block', lambda *args: 'facts')
    monkeypatch.setattr(web.narrator, 'completion', lambda *args, **kwargs: 'English explanation')
    response = web.explain_result({}, 'proposed', None, 'ta')
    assert response['source'] == 'unavailable'
    assert response['text'] == ''
    assert 'error' in response


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


def test_explanation_removes_markdown():
    assert web.plain_text('## Result\n**Rejected**\n* No forwarding\n1. [Details](https://example.com)') == 'Result\nRejected\nNo forwarding\nDetails'


def test_rate_limit_cooldown_prevents_repeat_api_calls(monkeypatch, tmp_path):
    import urllib.error
    monkeypatch.setattr(web.config, 'RESULTS_DIR', str(tmp_path))
    monkeypatch.setattr(web.report, 'run_block', lambda *args: 'facts')
    monkeypatch.setattr(web, '_retry_at', 0)
    calls = []
    def limited(*args, **kwargs):
        calls.append(1)
        raise urllib.error.HTTPError('https://api.groq.com', 429, 'limited', {'Retry-After': '30'}, None)
    monkeypatch.setattr(web.narrator, 'completion', limited)
    assert web.explain_result({}, 'proposed', None, 'en')['retry_seconds'] == 30
    assert web.explain_result({}, 'proposed', None, 'en')['retry_seconds'] > 0
    assert len(calls) == 1
