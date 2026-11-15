"""External source adapters. Provider failures never masquerade as empty results."""
import hashlib
import io
import ipaddress
import os
import re
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pypdf import PdfReader

from . import storage

load_dotenv(storage.ROOT / '.env')
HEADERS = {'User-Agent': 'Mozilla/5.0 FINN-Research-Prototype/0.1'}

class ProviderError(Exception):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def symbol(value):
    value = value.strip().upper().removesuffix('.NS')
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9&_-]{0,24}', value):
        raise ValueError('Enter an NSE ticker, for example TCS or M&M.')
    return value

def public_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.port not in (None, 443):
        raise ProviderError('Document URL must use public HTTPS.')
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443)
        if any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ProviderError('Non-public document host rejected.')
    except socket.gaierror:
        raise ProviderError('Document host could not be resolved.') from None
    return url

def fetch(url, limit=25_000_000, timeout=35):
    """Bounded download; validate every redirect before following it."""
    with httpx.Client(timeout=timeout, headers=HEADERS) as client:
        for _ in range(6):
            public_url(url)
            with client.stream('GET', url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get('location', ''))
                    continue
                if response.status_code != 200:
                    raise ProviderError(f'Source returned HTTP {response.status_code}.')
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > limit:
                        raise ProviderError('Source exceeds the 25 MB download limit.')
                    chunks.append(chunk)
                return b''.join(chunks), url
    raise ProviderError('Too many source redirects.')

def search(query, domains):
    key = os.getenv('TAVILY_API_KEY')
    if not key:
        raise ProviderError('Tavily key is not configured.')
    try:
        response = httpx.post('https://api.tavily.com/search', timeout=40,
            headers={'Authorization': f'Bearer {key}'},
            json={'query': query, 'search_depth': 'basic', 'max_results': 5,
                  'include_domains': domains, 'include_answer': False})
        if response.status_code != 200:
            raise ProviderError(f'Tavily returned HTTP {response.status_code}.')
        return response.json().get('results', [])
    except httpx.HTTPError:
        raise ProviderError('Tavily network request failed.') from None

def discover(ticker, refresh=False):
    ticker = symbol(ticker)
    key = f'discover:{ticker}'
    cached = storage.get(key, 6 * 3600)
    if cached and not refresh:
        return {**cached, 'cached': True}
    warnings, documents, company, bse_code, ir_host = [], [], ticker, None, None
    for suffix in ('/consolidated/', '/'):
        try:
            raw, page_url = fetch(f'https://www.screener.in/company/{ticker}{suffix}')
            soup = BeautifulSoup(raw, 'html.parser')
            heading = soup.find('h1')
            if not heading:
                continue
            company = heading.get_text(' ', strip=True)
            for a in soup.select('a[href]'):
                href = urljoin(page_url, a['href'])
                label = a.get_text(' ', strip=True)
                if label.lower() == 'website':
                    ir_host = urlparse(href).hostname
                if 'bseindia.com' in href:
                    match = re.search(r'/(\d{6})(?:/|$)', urlparse(href).path)
                    if match:
                        bse_code = match.group(1)
            section = soup.select_one('#documents')
            if section:
                for a in section.select('a[href]'):
                    href = urljoin(page_url, a['href'])
                    label = a.get_text(' ', strip=True)
                    parent_text = a.parent.get_text(' ', strip=True)
                    kind = ('annual_report' if re.search(r'Annual Report', label, re.I) else
                            'transcript' if re.search(r'transcript', label, re.I) else None)
                    if kind:
                        documents.append({'url': href, 'title': parent_text[:240], 'kind': kind})
            if documents:
                break
        except (ProviderError, httpx.HTTPError):
            warnings.append('Screener discovery unavailable for one page variant.')
    if company == ticker:
        try:
            from bse import BSE
            with BSE(download_folder=storage.DATA) as client:
                identity = client.lookup(ticker)
            if not identity or identity.get('symbol', '').upper() != ticker:
                raise ProviderError('Ticker could not be verified.')
            company = identity['company_name']
            bse_code = str(identity['bse_code'])
        except Exception:
            return {'ticker': ticker, 'company': ticker, 'bse_code': None, 'documents': [],
                    'fetched_at': now(), 'cached': False, 'status': 'unavailable',
                    'warnings': warnings + ['Ticker could not be verified from the company directory.']}
    domains = ['bseindia.com', 'nseindia.com'] + ([ir_host] if ir_host else [])
    for kind, phrase in [('annual_report', 'annual report PDF'), ('transcript', 'earnings call transcript PDF')]:
        if not any(d['kind'] == kind for d in documents):
            try:
                for hit in search(f'{company} {ticker} latest {phrase}', domains):
                    url = hit.get('url', '')
                    host = urlparse(url).hostname or ''
                    if any(host == d or host.endswith('.' + d) for d in domains) and '.pdf' in url.lower():
                        documents.append({'url': url, 'title': hit.get('title', kind), 'kind': kind})
            except ProviderError as exc:
                warnings.append(str(exc))
    seen = set()
    documents = [d for d in documents if not (d['url'] in seen or seen.add(d['url']))]
    result = {'ticker': ticker, 'company': company, 'bse_code': bse_code,
              'documents': documents, 'fetched_at': now(), 'cached': False,
              'warnings': warnings, 'status': 'ok' if documents else 'unavailable'}
    if documents:
        storage.put(key, result)
    return result

def document(item, refresh=False):
    key = 'doc:' + hashlib.sha256(item['url'].encode()).hexdigest()
    cached = storage.get(key, 7 * 86400)
    if cached and not refresh:
        return {**cached,**item,'url':cached['url']}
    failure = storage.get(key + ':failure', 900)
    if failure and not refresh:
        raise ProviderError(failure)
    try:
        raw, final_url = fetch(item['url'])
    except ProviderError as exc:
        storage.put(key + ':failure', str(exc))
        raise
    if not raw.startswith(b'%PDF'):
        raise ProviderError('Document link did not return a PDF.')
    try:
        reader = PdfReader(io.BytesIO(raw))
        pages = [{'page': i + 1, 'text': (page.extract_text() or '')} for i, page in enumerate(reader.pages)]
    except Exception:
        raise ProviderError('PDF could not be parsed.') from None
    if sum(len(p['text'].strip()) for p in pages) < 100:
        raise ProviderError('PDF needs OCR; no usable text extracted.')
    digest = hashlib.sha256(raw).hexdigest()
    folder = storage.DATA / 'documents'
    folder.mkdir(exist_ok=True)
    (folder / f'{digest}.pdf').write_bytes(raw)
    return storage.put(key, {**item, 'url': final_url, 'hash': digest, 'pages': pages,
                             'fetched_at': now()})

def prices(ticker, refresh=False):
    import yfinance as yf
    ticker = symbol(ticker)
    key = f'prices:{ticker}'
    cached = storage.get(key, 3600)
    if cached and not refresh:
        return {**cached, 'cached': True}
    try:
        frame = yf.Ticker(ticker + '.NS').history(period='3mo', auto_adjust=False, timeout=20)
        if frame.empty:
            raise ProviderError('No price data returned for this ticker.')
        # Exclude today's partial candle before exchange close in IST.
        from zoneinfo import ZoneInfo
        local = datetime.now(ZoneInfo('Asia/Kolkata'))
        bars = []
        for day, row in frame.iterrows():
            if day.date() == local.date() and (local.hour, local.minute) < (15, 35):
                continue
            bars.append({'date': day.date().isoformat(), 'close': float(row['Close']),
                         'volume': int(row['Volume'])})
        if len(bars) < 2:
            raise ProviderError('Insufficient completed trading sessions.')
        last, previous = bars[-1], bars[-2]
        baseline = bars[-21:-1]
        avg = sum(b['volume'] for b in baseline) / len(baseline)
        result = {'ticker': ticker, 'provider': 'yfinance', 'bars': bars,
                  'change_pct': (last['close'] / previous['close'] - 1) * 100,
                  'volume_ratio': last['volume'] / avg if avg else None,
                  'baseline_sessions': len(baseline), 'fetched_at': now(), 'cached': False}
        return storage.put(key, result)
    except ProviderError:
        raise
    except Exception:
        raise ProviderError('Price provider failed; retry later.') from None

def gemini(prompt):
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        raise ProviderError('Gemini key is not configured.')
    model = os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite')
    try:
        response = httpx.post(f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            headers={'x-goog-api-key': key}, timeout=90,
            json={'contents': [{'parts': [{'text': prompt}]}],
                  'generationConfig': {'temperature': 0.1, 'responseMimeType': 'application/json'}})
        if response.status_code != 200:
            reason={429:'rate limit or quota reached; retry later',503:'service temporarily unavailable',
                    401:'authentication failed',403:'key or account permission denied',404:'model unavailable for this account'}.get(response.status_code,'provider request failed')
            raise ProviderError(f'Gemini returned HTTP {response.status_code}: {reason}.')
        data = response.json()
        candidates=data.get('candidates') or []
        if not candidates:
            raise ProviderError('Gemini returned no candidate answer; the request may have been blocked or stopped.')
        text = ''.join(part.get('text', '') for part in candidates[0].get('content', {}).get('parts', []) if not part.get('thought'))
        if not text:
            raise ProviderError('Gemini returned no answer.')
        return text, model
    except httpx.HTTPError:
        raise ProviderError('Gemini request failed or timed out.') from None
    except (ValueError,TypeError,AttributeError,IndexError):
        raise ProviderError('Gemini returned an unreadable response.') from None
