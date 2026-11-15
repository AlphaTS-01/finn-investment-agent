"""Local single-investor prototype API. Run with python -m uvicorn backend.app:app."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import threading
from typing import Annotated, Literal

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import providers, push, research, storage, network, events, tickers, monitoring

@asynccontextmanager
async def lifespan(app):
    from .worker import run
    stop=threading.Event()
    worker=threading.Thread(target=run,args=(stop,),daemon=True,name='finn-worker')
    worker.start()
    yield
    stop.set()
    worker.join(timeout=2)

app = FastAPI(title='FINN backend', version='0.1.0', lifespan=lifespan,
              description='On-demand primary-source research and portfolio monitoring. Local demo, one investor.')
app.mount('/assets', StaticFiles(directory=storage.ROOT / 'frontend'), name='assets')

@app.get('/', include_in_schema=False)
def frontend():
    return FileResponse(storage.ROOT / 'frontend' / 'index.html')

@app.exception_handler(providers.ProviderError)
def provider_error(request: Request, exc):
    return JSONResponse(status_code=502, content={'status': 'unavailable', 'detail': str(exc)})

@app.exception_handler(ValueError)
def invalid_input(request: Request, exc):
    return JSONResponse(status_code=422, content={'detail': str(exc)})

@app.get('/health')
def health():
    import os
    return {'status': 'ok', 'mode': 'local_single_investor',
            'providers_configured': {'gemini': bool(os.getenv('GEMINI_API_KEY')), 'tavily': bool(os.getenv('TAVILY_API_KEY'))}}

@app.get('/portfolio')
def portfolio():
    return {'tickers': storage.portfolio()}

@app.get('/companies/search')
def search_companies(q: Annotated[str, Query(max_length=100)] = ''):
    return tickers.search(q)

@app.put('/portfolio/{ticker}')
def add_ticker(ticker: str):
    ticker = providers.symbol(ticker)
    tickers = storage.portfolio()
    if ticker not in tickers:
        if len(tickers) >= 25:
            raise ValueError('Prototype portfolio limit: 25 companies.')
        # Verify against the exchange-backed company directory before saving.
        company = providers.discover(ticker)
        if company['status'] != 'ok':
            raise providers.ProviderError('Could not verify this ticker; portfolio unchanged.')
        tickers.append(ticker)
        storage.save_setting('portfolio', tickers)
    return {'tickers': tickers}

@app.delete('/portfolio/{ticker}')
def remove_ticker(ticker: str):
    ticker = providers.symbol(ticker)
    tickers = [t for t in storage.portfolio() if t != ticker]
    storage.save_setting('portfolio', tickers)
    return {'tickers': tickers}

@app.get('/companies/{ticker}/documents')
def documents(ticker: str, refresh: bool = False):
    return providers.discover(ticker, refresh)

@app.get('/companies/{ticker}/prices')
def prices(ticker: str, refresh: bool = False):
    return providers.prices(ticker, refresh)

@app.get('/companies/{ticker}/announcements')
def announcements(ticker: str, days: Annotated[int, Query(ge=1, le=90)] = 1, refresh: bool = False):
    return push.announcements(ticker, days, refresh)

@app.get('/briefing')
def briefing(days: Annotated[int, Query(ge=1, le=90)] = 1, refresh: bool = False):
    def company_feed(ticker):
        if not refresh:
            cached = push.cached_window(ticker,days)
            if cached:
                return cached
        return push.announcements(ticker, days, refresh=refresh)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(company_feed, storage.portfolio()))
    items = [item for result in results for item in result['items']]
    items.sort(key=lambda e: (e['priority'], e['published_at']), reverse=True)
    groups = events.grouped(items)
    for item in [member for group in groups for member in [group,*group.get('related_filings',[])]]:
        item['network_matches'] = network.matches(ticker=item['ticker'],query=item['subject'],category=item['category'])[:2]
        if item.get('analysis'):
            item['analysis']['executive_overlaps']=network.executive_overlaps(item['analysis'].get('executives',[]))
    return {'items': items, 'groups':groups, 'companies': [{k: v for k, v in r.items() if k != 'items'} for r in results],
            'status': 'ok' if all(r['status'] == 'ok' for r in results) else 'partial'}

class ResearchRequest(BaseModel):
    ticker: str
    question: str = Field(min_length=3, max_length=2000)
    refresh: bool = False
    max_documents: int = Field(default=3, ge=2, le=4)
    event_id: str | None = None

@app.post('/research')
def ask(body: ResearchRequest):
    result = research.research(body.ticker, body.question, body.refresh, body.max_documents, body.event_id)
    result['network_matches'] = network.matches(query=body.question,ticker=providers.symbol(body.ticker),company=result.get('company',''))
    return result

class AlertRules(BaseModel):
    mode: Literal['briefing_only','important','custom'] = 'important'
    price_pct: float = Field(default=3, gt=0, le=100)
    volume_ratio: float = Field(default=2, gt=1, le=100)
    categories: list[str] = Field(default_factory=lambda: ['results', 'management_change', 'M&A', 'capex', 'litigation'])

@app.get('/settings/alerts')
def alert_rules():
    return {**AlertRules().model_dump(),**storage.setting('rules', {})}

@app.put('/settings/alerts')
def update_rules(body: AlertRules):
    allowed = {r[0] for r in push.RULES} | {'unclassified'}
    if any(c not in allowed for c in body.categories):
        raise ValueError('Unknown announcement category.')
    storage.save_setting('rules', body.model_dump())
    return body

@app.get('/alerts')
def alerts():
    return {'items': [{**a,'network_matches':network.matches(ticker=a.get('ticker',''),query=a.get('subject',''),category=a.get('category',''))[:1]} for a in storage.alerts()]}

class DigestPreferences(BaseModel):
    default_days: Literal[1,7,30] = 1
    ungroup_filings: bool = False

@app.get('/settings/digest')
def digest_preferences():
    return {**DigestPreferences().model_dump(),**storage.setting('digest',{})}

@app.put('/settings/digest')
def save_digest_preferences(body: DigestPreferences):
    storage.save_setting('digest',body.model_dump())
    return body

@app.delete('/network/contacts')
def delete_all_contacts():
    for contact in network.contacts():network.delete(contact['id'])
    return {'deleted':True}

class MonitorRequest(BaseModel):
    ticker: str
    question: str = Field(min_length=3,max_length=2000)

@app.post('/monitors')
def create_monitor(body: MonitorRequest):
    return monitoring.save_monitor(body.ticker,body.question)

@app.get('/monitors')
def list_monitors():
    return {'items':[{**m,'latest':storage.get('monitor_latest:'+m['id'])} for m in monitoring.monitors()],**monitoring.status()}

@app.delete('/monitors/{identifier}')
def remove_monitor(identifier: str):
    monitoring.remove_monitor(identifier)
    return {'deleted':True}

@app.post('/refresh')
def refresh():
    return push.refresh_portfolio()

@app.get('/network')
def list_contacts(q: str = '', ticker: str = ''):
    return {'contacts':network.contacts(), 'matches':network.matches(query=q,ticker=ticker) if q or ticker else [],
            'expertise':sorted({tag for c in network.contacts() for tag in c['expertise']})}

@app.post('/network/contacts')
def create_contact(body: network.Contact):
    value = network.save(body)
    value['portfolio_overlaps'] = sorted({j['ticker'] for j in value['employment'] if j['ticker'] in storage.portfolio()})
    return value

@app.put('/network/contacts/{identifier}')
def edit_contact(identifier: str, body: network.Contact):
    return network.save(body,identifier)

@app.delete('/network/contacts/{identifier}')
def delete_contact(identifier: str):
    network.delete(identifier)
    return {'deleted':True}

@app.get('/network/contacts/{identifier}/overlaps')
def contact_overlaps(identifier: str):
    return {'items':network.overlaps(identifier)}

class ProfileRequest(BaseModel):
    linkedin_url: str = Field(default='',max_length=500)
    profile_text: str = Field(default='',max_length=16000)

@app.post('/network/prefill')
def profile_prefill(body: ProfileRequest):
    return network.prefill(body.linkedin_url,body.profile_text)

@app.post('/network/demo')
def demo_contacts():
    return {'contacts':network.add_demo()}

@app.get('/network/matches')
def context_matches(ticker: str = '', q: str = '', category: str = ''):
    return {'items':network.matches(query=q,ticker=ticker,category=category)}

@app.get('/events/{identifier}/analysis')
def event_analysis(identifier: str, refresh: bool = False):
    result = events.analyze(identifier,refresh)
    event = events.find(identifier)
    result['network_matches'] = network.matches(ticker=event['ticker'],query=event['subject'],category=event['category'])
    result['executive_overlaps']=network.executive_overlaps(result.get('executives',[]))
    return result
