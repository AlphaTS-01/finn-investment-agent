"""Windowed announcements and idempotent in-app alerts."""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from . import providers as p, storage

RULES = [
    ('management_change', r'resign|appoint.*(?:director|officer|ceo|cfo)|chief executive|chief financial', 80),
    ('M&A', r'acquisition|merger|demerger|joint venture', 85),
    ('litigation', r'litigation|penalty|regulatory order|insolvency', 75),
    ('capex', r'capex|capacity expansion|new plant', 75),
    ('results', r'financial results|quarterly results|audited results', 70),
    ('earnings_call', r'transcript|earnings call|conference call|concall', 50),
    ('credit_rating', r'credit rating|rating.*(?:upgrade|downgrade|reaffirm)', 60),
    ('fund_raise', r'rights issue|preferential|qualified institutional|buyback|fund rais', 65),
    ('pledging', r'pledge|pledging|encumbrance', 65),
    ('insider_trading', r'insider|disclosure.*acquisition.*shares', 45),
    ('dividend', r'dividend', 45), ('bonus_split', r'bonus|stock split|sub.division', 45),
    ('investor_meetings', r'investor meet|analyst meet|investor conference', 20),
    ('postal_ballot', r'postal ballot', 20), ('agm_egm', r'annual general|extraordinary general|agm|egm', 20),
    ('press_release', r'press release|order win|partnership', 40),
]

def classify(subject):
    routine_notice = bool(re.search(r'board meeting.*(?:intimation|notice)|newspaper|publication|trading window|loss of.*certificate|compliance certificate',subject,re.I))
    for category, pattern, score in RULES:
        if re.search(pattern, subject, re.I):
            if routine_notice:
                score = min(score, 20)
            reasons = {'management_change':'A leadership change may affect continuity and execution.',
                       'M&A':'An acquisition or restructuring may change capital allocation and the business mix.',
                       'litigation':'A legal or regulatory development may create financial or operating exposure.',
                       'capex':'New capacity commitments may affect funding and future execution.',
                       'results':'Reported financial performance warrants comparison with prior periods.',
                       'credit_rating':'Review whether the rating changed; a reaffirmation is different from a downgrade.',
                       'earnings_call':'Management commentary or a call document may add context.'}
            return {'category': category, 'priority': score, 'routine': score <= 20,
                    'priority_reason': 'Administrative notice retained for completeness.' if routine_notice else reasons.get(category,'Relevant corporate update; review the original filing for magnitude.'),
                    'priority_basis':'Subject-based triage, not a verified materiality judgment.',
                    'attention':'needs_attention' if score>=65 else 'worth_reviewing' if score>20 else 'routine'}
    return {'category': 'unclassified', 'priority': 10, 'routine': True,
            'priority_reason': 'No subject rule matched; original filing retained.',
            'priority_basis':'Unclassified does not mean immaterial.', 'attention':'routine'}

def event_date(value):
    if not value:
        return None
    from dateutil.parser import parse
    try:
        dt = parse(str(value), dayfirst=False)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo('Asia/Kolkata'))
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None

def normalize(row, ticker, provider):
    subject = str(row.get('NEWSSUB') or row.get('desc') or row.get('subject') or '')
    date = event_date(row.get('NEWS_DT') or row.get('an_dt') or row.get('dt'))
    url = row.get('ATTACHMENTNAME') or row.get('attchmntFile') or ''
    if url and not str(url).startswith('http'):
        url = 'https://www.bseindia.com/xml-data/corpfiling/AttachLive/' + url
    identifier = hashlib.sha256(f'{ticker}|{provider}|{row.get("NEWSID") or url or subject}|{date}'.encode()).hexdigest()[:24]
    return {'id': identifier, 'ticker': ticker, 'provider': provider, 'subject': subject,
            'published_at': date.isoformat() if date else None, 'source_url': url or None,
            'fetched_at': p.now(), **classify(subject)}

def cached_window(ticker, days):
    """Reuse the freshest covering snapshot and reapply the rolling date window."""
    candidates=[]
    with storage.connect() as conn:
        import json
        for key,value in conn.execute('SELECT key,value FROM cache WHERE key LIKE ?', (f'events:{ticker}:%',)):
            try:
                if int(key.rsplit(':',1)[1])>=days:
                    candidates.append(json.loads(value))
            except (ValueError,TypeError): pass
    if not candidates:return None
    latest=max(candidates,key=lambda x:x.get('fetched_at',''))
    now=datetime.now(timezone.utc);start=now-timedelta(days=days)
    fetched=event_date(latest.get('fetched_at'))
    fresh=bool(fetched and (now-fetched).total_seconds()<=1200)
    return {**latest,'items':[e for e in latest.get('items',[]) if e.get('published_at') and start<=datetime.fromisoformat(e['published_at'])<=now],
            'cached':True,'status':'ok' if fresh else 'stale','window_start':start.isoformat(),'window_end':now.isoformat()}

def announcements(ticker, days=1, refresh=False):
    ticker = p.symbol(ticker)
    key = f'events:{ticker}:{days}'
    cached = storage.get(key, 300)
    if cached and not refresh:
        return {**cached, 'cached': True}
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    local_start, local_end = (d.astimezone(ZoneInfo('Asia/Kolkata')).replace(tzinfo=None) for d in (start, end))
    warnings, rows, provider, success = [], [], None, False
    try:
        from bse import BSE
        with BSE(download_folder=storage.DATA) as client:
            code = storage.get(f'bse_code:{ticker}')
            if not code:
                code = client.getScripCode(ticker)
                storage.put(f'bse_code:{ticker}', str(code))
            for page in range(1, 21):
                data = client.announcements(scripcode=str(code), from_date=local_start,
                                            to_date=local_end, page_no=page)
                batch = data.get('Table', [])
                rows.extend(batch)
                total = int(data.get('Table1', [{}])[0].get('ROWCNT', len(rows)))
                if not batch or len(rows) >= total:
                    break
            else:
                warnings.append('Result limited to 20 exchange pages; narrow the window.')
            provider, success = 'BSE', True
    except Exception:
        warnings.append('BSE unavailable; tried NSE fallback.')
    if not success:
        try:
            from nse import NSE
            with NSE(download_folder=storage.DATA) as client:
                rows = client.announcements(symbol=ticker, from_date=local_start, to_date=local_end)
                provider, success = 'NSE', True
        except Exception:
            warnings.append('NSE unavailable.')
    if not success:
        old = storage.get(key)
        if old:
            return {**old, 'status': 'stale', 'cached': True, 'warnings': warnings}
        return {'ticker': ticker, 'status': 'unavailable', 'items': [], 'warnings': warnings,
                'cached': False, 'fetched_at': p.now()}
    events = [normalize(row, ticker, provider) for row in rows]
    events = [e for e in events if e['published_at'] and start <= datetime.fromisoformat(e['published_at']) <= end]
    events = list({e['id']: e for e in events}.values())
    events.sort(key=lambda e: (e['priority'], e['published_at']), reverse=True)
    return storage.put(key, {'ticker': ticker, 'status': 'ok', 'provider': provider,
                            'items': events, 'warnings': warnings, 'cached': False,
                            'fetched_at': p.now(), 'window_start': start.isoformat(), 'window_end': end.isoformat()})

def refresh_portfolio():
    """First observation establishes a baseline: no historical announcement flood."""
    rules = storage.setting('rules', {'price_pct': 3.0, 'volume_ratio': 2.0,
                                    'categories': ['results', 'management_change', 'M&A', 'capex', 'litigation']})
    mode = rules.get('mode','important')
    from . import monitoring
    reports = []
    tracked=set(storage.portfolio())
    for ticker in sorted(tracked | {m['ticker'] for m in monitoring.monitors()}):
        report = {'ticker': ticker, 'new_alerts': 0}
        checkpoint = storage.get(f'checkpoint:{ticker}')
        events = announcements(ticker, days=7, refresh=True)
        report['announcements_status'] = events['status']
        if events['status'] == 'ok':
            new_events = monitoring.observe(ticker, events['items'])
            for event in new_events:
                event = {**event, **classify(event['subject'])} if 'subject' in event else event
                eligible = event['category'] in rules['categories'] and not event['routine']
                if ticker in tracked and mode!='briefing_only' and eligible:
                    report['new_alerts'] += storage.save_alert(event['id'], {'type': 'announcement', **event,
                        'trigger_reasons':[f"Matches your selected announcement type: {event['category'].replace('_',' ')}."],
                        'rule_snapshot':rules,'created_at':p.now()})
            storage.put(f'checkpoint:{ticker}', p.now())
        try:
            data = p.prices(ticker, refresh=True)
            triggers = []
            if abs(data['change_pct']) >= rules['price_pct']:
                triggers.append('price')
            if data['volume_ratio'] is not None and data['baseline_sessions'] >= 20 and data['volume_ratio'] >= rules['volume_ratio']:
                triggers.append('volume')
            date = data['bars'][-1]['date']
            if ticker in tracked and triggers and mode!='briefing_only':
                reasons=[]
                if 'price' in triggers:reasons.append(f"Price {data['change_pct']:+.2f}% exceeds your ±{rules['price_pct']:g}% threshold.")
                if 'volume' in triggers:reasons.append(f"Volume {data['volume_ratio']:.2f}× the preceding 20-session average exceeds your {rules['volume_ratio']:g}× threshold.")
                report['new_alerts'] += storage.save_alert(f'market:{ticker}:{date}',
                    {'type': 'market', 'ticker': ticker, 'trading_date': date, 'triggers': triggers,
                     'trigger_reasons':reasons,'rule_snapshot':rules,
                     'change_pct': data['change_pct'], 'volume_ratio': data['volume_ratio'], 'created_at': p.now()})
            report['prices_status'] = 'ok'
        except p.ProviderError as exc:
            report['prices_status'] = str(exc)
        reports.append(report)
    return {'refreshed_at': p.now(), 'companies': reports}
