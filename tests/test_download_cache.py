import pytest
from backend import providers, storage

def test_failed_download_is_not_repeated(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'cache.sqlite3')
    calls = []
    def fail(url):
        calls.append(url)
        raise providers.ProviderError('Source exceeds the 25 MB download limit.')
    monkeypatch.setattr(providers, 'fetch', fail)
    item = {'url': 'https://example.com/report.pdf'}
    for _ in range(2):
        with pytest.raises(providers.ProviderError):
            providers.document(item)
    assert len(calls) == 1
    with pytest.raises(providers.ProviderError):
        providers.document(item, refresh=True)
    assert len(calls) == 2
