"""Company-name and symbol lookup from the NSE equity directory."""
import csv
import io
import re
from . import providers as p, storage

URL = 'https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv'
KEY = 'nse_equity_directory:v1'

def directory():
    cached = storage.get(KEY, 86400)
    if cached:
        return {**cached, 'stale': False}
    try:
        raw, _ = p.fetch(URL, limit=5_000_000)
        rows = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        items = [{'ticker': r['SYMBOL'].strip(), 'name': r['NAME OF COMPANY'].strip()} for r in rows]
        if not items:
            raise ValueError('Empty directory')
        return storage.put(KEY, {'items': items, 'source_url': URL, 'fetched_at': p.now(), 'stale': False})
    except Exception:
        cached = storage.get(KEY)
        if cached:
            return {**cached, 'stale': True}
        raise p.ProviderError('Company search unavailable. Enter an NSE ticker directly.') from None

def normalize(value):
    return re.sub(r'[^a-z0-9]', '', value.lower())

def company_key(value):
    return normalize(re.sub(r'\b(limited|ltd|incorporated|inc|plc)\b\.?','',value,flags=re.I))

def recorded_identity(company):
    # Matching uses the locally cached official directory; never a fuzzy auto-save.
    cached=storage.get(KEY) or {}
    matches=[d for d in cached.get('items',[]) if company_key(d['name'])==company_key(company)]
    return matches[0] if len(matches)==1 else None

def search(query):
    q = normalize(query)
    if not q:
        return {'items': [], 'total': 0, 'stale': False}
    data = directory()
    terms = re.findall(r'[a-z0-9]+', query.lower())
    ranked = []
    for item in data['items']:
        symbol, name = normalize(item['ticker']), normalize(item['name'])
        words = re.findall(r'[a-z0-9]+', item['name'].lower())
        score = (0 if q == symbol else 1 if symbol.startswith(q) else
                 2 if name.startswith(q) else 3 if all(any(w.startswith(t) for w in words) for t in terms)
                 else 4 if q in symbol or q in name else None)
        if score is not None:
            ranked.append((score, item['ticker'], item))
    ranked.sort(key=lambda row: (row[0], row[1]))
    return {**{k:v for k,v in data.items() if k != 'items'}, 'items': [r[2] for r in ranked], 'total': len(ranked)}
