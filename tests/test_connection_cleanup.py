import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend import storage, monitoring, network
from backend.app import app


@pytest.mark.parametrize('factory', [storage.connect, monitoring.db, network.db])
def test_connection_closes_and_commits(factory, tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'test.sqlite3')
    # Retain references so garbage collection cannot mask leaked connections.
    connections = []
    for i in range(100):
        with factory() as conn:
            conn.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', ('test', str(i)))
            connections.append(conn)
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute('SELECT 1')
    assert storage.setting('test') == 99


def test_connection_rolls_back_and_closes(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'DB', tmp_path / 'test.sqlite3')
    with pytest.raises(RuntimeError):
        with storage.connect() as conn:
            conn.execute('INSERT INTO settings VALUES (?, ?)', ('test', '1'))
            raise RuntimeError('abort')
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute('SELECT 1')
    assert storage.setting('test') is None


def test_unexpected_api_error_is_safe_json(monkeypatch):
    def fail():
        raise RuntimeError('private internal details')
    monkeypatch.setattr(storage, 'portfolio', fail)
    response = TestClient(app, raise_server_exceptions=False).get('/portfolio')
    assert response.status_code == 500
    assert 'try again' in response.json()['detail']
    assert 'private internal details' not in response.text
