import json
import urllib.error

import narrator


def test_missing_key_falls_back_without_network(monkeypatch, tmp_path):
    import config
    monkeypatch.setattr(config, 'RESULTS_DIR', str(tmp_path))
    monkeypatch.setattr(narrator, 'context', lambda *args: 'recorded facts')
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.setattr(narrator.urllib.request, 'urlopen', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network')))
    notes, source = narrator.prepare({}, 'proposed', 'ta')
    assert notes == narrator.fallback('ta')
    assert 'fallback' in source


def test_cache_is_bound_to_evidence_and_language(monkeypatch, tmp_path):
    import config
    monkeypatch.setattr(config, 'RESULTS_DIR', str(tmp_path))
    monkeypatch.setattr(narrator, 'context', lambda raw, *args: raw['facts'])
    calls = []
    def complete(messages):
        calls.append(messages)
        return json.dumps({stage: '\u0ba4\u0bae\u0bbf\u0bb4\u0bcd Recorded explanation' for stage in narrator.STAGES})
    monkeypatch.setattr(narrator, 'completion', complete)
    assert narrator.prepare({'facts': 'a'}, 'proposed')[1] == 'AI generated'
    assert narrator.prepare({'facts': 'a'}, 'proposed')[1] == 'cached AI'
    narrator.prepare({'facts': 'b'}, 'proposed')
    narrator.prepare({'facts': 'a'}, 'proposed', 'en')
    assert len(calls) == 3


def test_invalid_or_failed_api_does_not_break_demo(monkeypatch, tmp_path):
    import config
    monkeypatch.setattr(config, 'RESULTS_DIR', str(tmp_path))
    monkeypatch.setattr(narrator, 'context', lambda *args: 'recorded facts')
    monkeypatch.setattr(narrator, 'completion', lambda *args: 'not JSON')
    assert narrator.prepare({}, 'proposed')[0] == narrator.fallback('ta')
    def fail(*args):
        raise urllib.error.HTTPError('https://api.groq.com', 429, 'rate limited', {}, None)
    monkeypatch.setattr(narrator, 'completion', fail)
    assert narrator.prepare({}, 'proposed')[0] == narrator.fallback('ta')
    assert 'tailored answer was not generated' in narrator.answer({}, 'proposed', 'why?')


def test_replay_panel_and_explanation_are_one_argument():
    import ast
    from pathlib import Path
    tree = ast.parse((Path(narrator.__file__).parent / 'demo.py').read_text(encoding='utf-8'))
    replay = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'replay')
    calls = [node for node in ast.walk(replay) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == 'show']
    assert calls
    assert all(len(call.args) == 1 for call in calls)
