import json
from datetime import datetime, timezone
from fastapi.testclient import TestClient
import pytest
from backend import storage, providers, push, research
from backend.app import app

@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DATA', tmp_path)
    monkeypatch.setattr(storage, 'DB', tmp_path / 'test.sqlite3')

def test_cache_expiration_and_persistence():
    storage.put('x', {'value': 42})
    assert storage.get('x', 60) == {'value': 42}
    assert storage.get('x', -1) is None
    assert storage.get('x') == {'value': 42}

def test_announcements_preserve_source_and_ist_time():
    row = {'NEWSSUB': 'Financial Results', 'NEWS_DT': '2026-11-12T15:30:00',
           'ATTACHMENTNAME': 'example.pdf'}
    result = push.normalize(row, 'TCS', 'BSE')
    assert result['published_at'] == '2026-11-12T10:00:00+00:00'
    assert result['source_url'].endswith('/example.pdf')
    assert result['id'] == push.normalize(row, 'TCS', 'BSE')['id']
    assert result['category'] == 'results'

def test_notice_is_not_prioritized_as_actual_results():
    assert push.classify('Board Meeting Intimation for Financial Results')['routine']
    assert not push.classify('Audited Financial Results')['routine']

def test_alerts_are_idempotent():
    assert storage.save_alert('event-1', {'ticker': 'TCS'})
    assert not storage.save_alert('event-1', {'ticker': 'TCS'})
    assert len(storage.alerts()) == 1

def test_citation_validation_and_cache(monkeypatch):
    item = {'url': 'https://example.com/report.pdf', 'kind': 'transcript', 'title': 'Q2 transcript'}
    monkeypatch.setattr(providers, 'discover', lambda *a: {'company': 'Example', 'documents': [item], 'warnings': []})
    monkeypatch.setattr(providers, 'document', lambda *a: {**item, 'hash': 'hash1', 'pages': [
        {'page': 3, 'text': 'Revenue growth was 10 percent for this quarter. ' * 8}]})
    calls = []
    def model(prompt):
        calls.append(prompt)
        return json.dumps({'claims': [{'text': 'Revenue grew 10%.', 'source_ids': ['S1'], 'support':[{'source_id':'S1','quote':'Revenue growth was 10 percent for this quarter.'}]},
                                      {'text': 'Invented', 'source_ids': ['S999']}], 'limitations': []}), 'test'
    monkeypatch.setattr(providers, 'gemini', model)
    result = research.research('OTHER', 'What was revenue growth?')
    assert result['status'] == 'partial'
    assert len(result['claims']) == 1
    assert result['sources'][0]['page'] == 3
    assert research.research('OTHER', 'What was revenue growth?')['cached']
    assert len(calls) == 1

def test_model_failure_returns_evidence_not_fabricated_answer(monkeypatch):
    item = {'url': 'https://example.com/report.pdf', 'kind': 'annual_report', 'title': 'Report'}
    monkeypatch.setattr(providers, 'discover', lambda *a: {'company': 'Example', 'documents': [item], 'warnings': []})
    monkeypatch.setattr(providers, 'document', lambda *a: {**item, 'hash': 'x', 'pages': [
        {'page': 1, 'text': 'Revenue and growth are discussed here. ' * 8}]})
    def unavailable(prompt):
        raise providers.ProviderError('Gemini returned HTTP 429; check quota.')
    monkeypatch.setattr(providers, 'gemini', unavailable)
    result = research.research('OTHER', 'What was revenue growth?')
    assert result['status'] == 'model_unavailable'
    assert not result['claims']
    assert result['sources']

def test_api_validation_and_configuration_do_not_leak_keys():
    client = TestClient(app)
    health = client.get('/health')
    assert health.status_code == 200
    assert all(isinstance(v, bool) for v in health.json()['providers_configured'].values())
    assert client.get('/companies/TCS/announcements?days=0').status_code == 422
    assert client.post('/research', json={'ticker': 'TCS', 'question': 'x'}).status_code == 422
    assert client.put('/settings/alerts', json={'categories': ['fake']}).status_code == 422

def test_reject_private_document_urls():
    with pytest.raises(providers.ProviderError):
        providers.public_url('https://127.0.0.1/private')
    with pytest.raises(providers.ProviderError):
        providers.public_url('file:///etc/passwd')

def test_symbol_validation():
    assert providers.symbol(' m&m.ns ') == 'M&M'
    with pytest.raises(ValueError):
        providers.symbol('../secrets')

def test_first_monitor_run_does_not_alert_historical_announcements(monkeypatch):
    monkeypatch.setattr(storage, 'portfolio', lambda: ['TCS'])
    monkeypatch.setattr(push, 'announcements', lambda *a, **kw: {'status': 'ok', 'items': [
        {'id': 'old', 'ticker': 'TCS', 'published_at': '2020-01-01T00:00:00+00:00', 'category': 'results', 'routine': False}]})
    monkeypatch.setattr(providers, 'prices', lambda *a, **kw: {'change_pct': 0, 'volume_ratio': 1,
        'baseline_sessions': 20, 'bars': [{'date': '2026-11-12'}]})
    assert push.refresh_portfolio()['companies'][0]['new_alerts'] == 0
    assert storage.get('checkpoint:TCS')
