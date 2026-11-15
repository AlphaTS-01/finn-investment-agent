"""Small persistent cache and portfolio store. No credentials are persisted here."""
import json
import os
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.getenv('FINN_DATA_DIR', str(ROOT / 'data')))
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'finn.sqlite3'
DEFAULT_PORTFOLIO = ['TCS', 'INFY', 'RELIANCE', 'HDFCBANK', 'ICICIBANK', 'ITC',
                     'HINDUNILVR', 'LT', 'SUNPHARMA', 'MARUTI', 'TITAN',
                     'ULTRACEMCO', 'TATASTEEL', 'BEL', 'PIDILITIND']

class ClosingConnection(sqlite3.Connection):
    """Commit/rollback on context exit, then release the file handles immediately."""
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect():
    db = sqlite3.connect(DB, timeout=20, factory=ClosingConnection)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, saved REAL)')
        db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, value TEXT, created REAL)')
    except BaseException:
        db.close()
        raise
    return db

def get(key, ttl=None):
    with connect() as db:
        row = db.execute('SELECT value,saved FROM cache WHERE key=?', (key,)).fetchone()
    if row and (ttl is None or time.time() - row[1] < ttl):
        return json.loads(row[0])
    return None

def put(key, value):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO cache VALUES (?,?,?)',
                   (key, json.dumps(value, allow_nan=False), time.time()))
    return value

def setting(key, default=None):
    with connect() as db:
        row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    return json.loads(row[0]) if row else default

def save_setting(key, value):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value)))

def portfolio():
    return setting('portfolio', DEFAULT_PORTFOLIO)

def save_alert(identifier, value):
    with connect() as db:
        cur = db.execute('INSERT OR IGNORE INTO alerts VALUES (?,?,?)',
                         (identifier, json.dumps(value), time.time()))
        return cur.rowcount == 1

def alerts():
    with connect() as db:
        rows = db.execute('SELECT value FROM alerts ORDER BY created DESC LIMIT 200').fetchall()
    return [json.loads(row[0]) for row in rows]
