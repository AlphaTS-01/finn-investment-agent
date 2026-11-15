import pytest
from fastapi.testclient import TestClient
from backend import tickers, storage, providers
from backend.app import app

@pytest.fixture(autouse=True)
def directory(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path/'test.sqlite3')
    monkeypatch.setattr(providers, 'fetch', lambda *a,**kw: (b'SYMBOL,NAME OF COMPANY\nTCS,Tata Consultancy Services Limited\nTATASTEEL,Tata Steel Limited\nINFY,Infosys Limited\n', tickers.URL))

def test_company_and_symbol_search():
    assert {x['ticker'] for x in tickers.search('tata')['items']} == {'TCS','TATASTEEL'}
    assert tickers.search('TCS')['items'][0]['ticker'] == 'TCS'
    assert tickers.search('tata steel')['items'][0]['ticker'] == 'TATASTEEL'
    assert tickers.search('infos')['items'][0]['ticker'] == 'INFY'
    assert not tickers.search('unknown-company')['items']
    assert not tickers.search('')['items']
    assert TestClient(app).get('/companies/search?q=tata').json()['total'] == 2

def test_cache_and_source_failure(monkeypatch):
    tickers.search('tata')
    def fail(*a,**kw): raise providers.ProviderError('Offline')
    monkeypatch.setattr(providers, 'fetch', fail)
    assert tickers.search('tata')['total'] == 2
    with storage.connect() as conn:
        conn.execute('UPDATE cache SET saved=0')
    assert tickers.search('tata')['stale']
    with storage.connect() as conn:
        conn.execute('DELETE FROM cache')
    with pytest.raises(providers.ProviderError): tickers.search('tata')
