import json
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from backend import storage, network, events, providers, push, research
from backend.app import app

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'test.sqlite3')
    monkeypatch.setattr(storage,'DATA',tmp_path)

def person(name='Alex',**kw):
    return network.Contact(name=name,occupation='Engineer',expertise=['Steel','capacity expansion'],
        employment=[network.Employment(company='Tata Steel',ticker='TATASTEEL',role='Operations',start_year=2010,end_year=2020)],
        education=[network.Education(institution='IIT Kanpur',major='Mechanical Engineering',degree='BTech',start_year=2005,end_year=2009)],**kw)

def test_contact_crud_and_search_by_major_ticker_and_expertise():
    c=network.save(person())
    for q in ['Mechanical Engineering','TATASTEEL','capacity expansion']:
        result=network.matches(q)
        assert result and result[0]['contact']['id']==c['id']
        assert result[0]['reasons']
    assert not network.matches('UnrelatedName999')
    network.save(person(name='Alex Updated'),c['id'])
    assert network.contacts()[0]['name']=='Alex Updated'
    network.delete(c['id']);assert network.contacts()==[]

def test_affiliation_overlap_is_not_friendship_and_requires_dates():
    a=network.save(person())
    network.save(person(name='Blair'))
    overlap=network.overlaps(a['id'])
    assert overlap and all(x['inferred'] for x in overlap)
    assert all('does not establish' in x['caveat'] for x in overlap)

def test_invalid_tenure_and_linkedin_url_rejected():
    with pytest.raises(ValueError):network.Employment(company='A',start_year=2025,end_year=2020)
    with pytest.raises(ValueError):network.Contact(name='A',linkedin_url='https://linkedin.com.evil.test/in/a')
    with pytest.raises(ValueError):network.Contact(name=' ')

def test_explicit_introductions_and_reconnect():
    a=network.save(person())
    b=network.save(person(name='Blair',introduced_by=a['id'],last_contacted=date(2020,1,1)))
    match=next(m for m in network.matches('steel') if m['contact']['id']==b['id'])
    assert 'Alex → Blair' in match['connection_path']
    assert match['reconnect']
    with pytest.raises(ValueError):network.save(person(introduced_by=b['id']),a['id'])
    network.delete(a['id']);assert network.contacts()[0]['introduced_by'] is None

def test_profile_prefill_requires_review_and_does_not_save(monkeypatch):
    monkeypatch.setattr(providers,'gemini',lambda _: (json.dumps({'name':'Alex','education':[{'institution':'IIT Kanpur','major':'Physics'}]}),'test'))
    draft=network.prefill(profile_text='Alex studied Physics at IIT Kanpur.')
    assert draft['status']=='review_required'
    assert draft['draft']['education'][0]['major']=='Physics'
    assert network.contacts()==[]

def test_blocked_profile_returns_manual_fallback(monkeypatch):
    def fail(*a,**kw):raise providers.ProviderError('Blocked')
    monkeypatch.setattr(providers,'fetch',fail)
    monkeypatch.setattr(providers,'search',fail)
    result=network.prefill('https://www.linkedin.com/in/example-person')
    assert result['status']=='needs_profile_text'
    assert not network.contacts()

def test_indexed_profile_matches_exact_url_only(monkeypatch):
    def blocked(*a,**kw): raise providers.ProviderError('HTTP 999')
    monkeypatch.setattr(providers,'fetch',blocked)
    wrong={'url':'https://www.linkedin.com/in/alex-other','content':'Wrong person '*20}
    right={'url':'https://in.linkedin.com/in/alex/?trk=search','content':'Alex is an engineer at Example. Education: Stanford, MS Materials Science. '*3}
    monkeypatch.setattr(providers,'search',lambda *a:[wrong,right])
    prompts=[]
    def extract(prompt):
        prompts.append(prompt)
        return json.dumps({'name':'Alex','education':[{'institution':'Stanford','degree':'MS','major':'Materials Science'}]}),'test'
    monkeypatch.setattr(providers,'gemini',extract)
    result=network.prefill('https://www.linkedin.com/in/alex,')
    assert result['source']=='indexed_profile'
    assert result['draft']['linkedin_url']=='https://www.linkedin.com/in/alex'
    assert 'Wrong person' not in prompts[0]
    assert not network.contacts()
    monkeypatch.setattr(providers,'search',lambda *a:[wrong])
    assert network.prefill('https://www.linkedin.com/in/alex')['status']=='needs_profile_text'

def test_grouping_preserves_every_filing():
    items=[push.normalize({'NEWSSUB':s,'NEWS_DT':'2026-11-12T15:30:00','ATTACHMENTNAME':str(i)+'.pdf'},'TCS','BSE')
           for i,s in enumerate(['Financial Results','Newspaper Publication of Financial Results','Earnings call transcript','Acquisition'])]
    grouped=events.grouped(items)
    assert len(grouped)==2
    assert sum(1+len(g['related_filings']) for g in grouped)==4
    assert grouped[1]['related_filings'] or grouped[0]['related_filings']

def test_quote_checked_and_quarterly_comparisons():
    rows=[]
    for period,end,value in [('current','2026-09-30',120),('previous','2026-06-30',100),('year_ago','2025-09-30',80)]:
        rows.append({'metric':'Revenue','period':period,'period_end':end,'value':value,'months':3,
                     'basis':'consolidated','unit':'INR crore','page':1,'quote':f'Revenue {value} INR crore','period_header':'Quarter ended 2026-09-30 2026-06-30 2025-09-30'})
    pages={1:'Quarter ended 2026-09-30 2026-06-30 2025-09-30 Revenue 120 INR crore Revenue 100 INR crore Revenue 80 INR crore'}
    result=events.comparisons(rows,pages)[0]
    assert result['qoq_pct']==20 and result['yoy_pct']==50
    rows[1]['months']=6
    assert events.comparisons(rows,pages)[0]['qoq_pct'] is None
    rows[1]['months']=3;rows[1]['basis']='standalone'
    assert events.comparisons(rows,pages)[0]['qoq_pct'] is None
    rows[0]['value']=999
    assert events.comparisons(rows,pages)[0]['status']=='not_verified'

def test_unquoted_summary_discarded():
    assert events.validate_fact({'text':'Invented','page':1,'quote':'not present in source'}, {1:'Real source text here'}) is None

def test_briefing_only_suppresses_alerts_not_filings(monkeypatch):
    storage.save_setting('rules',{'mode':'briefing_only','price_pct':1,'volume_ratio':2,'categories':['results']})
    storage.put('checkpoint:TCS','2020-01-01T00:00:00+00:00')
    monkeypatch.setattr(storage,'portfolio',lambda:['TCS'])
    event=push.normalize({'NEWSSUB':'Financial Results','NEWS_DT':'2026-11-12T15:30:00'},'TCS','BSE')
    monkeypatch.setattr(push,'announcements',lambda *a,**kw:{'status':'ok','items':[event]})
    monkeypatch.setattr(providers,'prices',lambda *a,**kw:{'change_pct':20,'volume_ratio':5,'baseline_sessions':20,'bars':[{'date':'2026-11-12'}]})
    push.refresh_portfolio();assert not storage.alerts()
    client=TestClient(app)
    assert len(client.get('/briefing?days=7').json()['items'])==1

def test_contact_endpoints_and_profile_validation():
    c=TestClient(app)
    result=c.post('/network/contacts',json=person().model_dump(mode='json'))
    assert result.status_code==200
    assert result.json()['portfolio_overlaps']==['TATASTEEL']
    assert c.get('/network?q=mechanical').json()['matches']
    assert c.post('/network/contacts',json={'name':'a','linkedin_url':'http://127.0.0.1'}).status_code==422

def test_event_research_includes_actual_filing(monkeypatch):
    event=push.normalize({'NEWSSUB':'Acquisition','NEWS_DT':'2026-11-12','ATTACHMENTNAME':'event.pdf'},'TCS','BSE')
    storage.put('events:TCS:7',{'items':[event]})
    monkeypatch.setattr(providers,'discover',lambda *a:{'company':'TCS','documents':[],'warnings':[]})
    monkeypatch.setattr(providers,'document',lambda item,*a:{**item,'hash':'eventhash','pages':[{'page':1,'text':'Acquisition of a subsidiary was announced for cash consideration. '*8}]})
    prompts=[]
    def answer(prompt):prompts.append(prompt);return json.dumps({'claims':[{'text':'Acquisition announced.','source_ids':['S1'],'support':[{'source_id':'S1','quote':'Acquisition of a subsidiary was announced for cash consideration.'}]}],'limitations':[]}), 'test'
    monkeypatch.setattr(providers,'gemini',answer)
    result=research.research('TCS','Explain this acquisition.',event_id=event['id'])
    assert result['event_filing_included']
    assert result['documents_used'][0]['kind']=='event_filing'
    assert 'Acquisition of a subsidiary' in prompts[0]
