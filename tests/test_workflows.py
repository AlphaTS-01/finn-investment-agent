import json
import time
import pytest
from backend import storage, monitoring as m, providers as p, routing, research, network, tickers, push, events
from backend.app import app
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'test.db')
    monkeypatch.setattr(storage,'DATA',tmp_path)

def event(identifier='one',subject='Financial Results',date='2026-11-14T10:00:00+00:00'):
    return {'id':identifier,'ticker':'TCS','subject':subject,'published_at':date,'source_url':'https://example.com/'+identifier+'.pdf',**push.classify(subject)}

def test_query_route_and_two_period_document_selection():
    plan=routing.plan('Compare quarterly results with previous quarter')
    assert plan['comparison'] and plan['topic']=='results'
    docs=[{'kind':'annual_report','title':'Annual 2026'}, {'kind':'event_filing','title':'Results 2025'}, {'kind':'event_filing','title':'Results 2026'}]
    assert [x['title'] for x in routing.select(docs,plan,2)]==['Results 2026','Results 2025']
    assert routing.plan('Who resigned as CFO?')['topic']=='management_change'
    assert routing.plan('Compare 2023 and 2024 margins')['years']==['2023','2024']

def test_late_filing_ids_baseline_and_restart():
    assert not m.observe('TCS',[event()])
    late=event('late',date='2026-11-12T10:00:00+00:00')
    assert [e['id'] for e in m.observe('TCS',[event(),late])]==['late']
    assert not m.observe('TCS',[late,event()])
    assert m.get_event('late')['published_at']==late['published_at']

def test_jobs_retry_recover_and_do_not_repeat(monkeypatch):
    m.observe('TCS',[event()]);calls=[]
    def fail(*a):calls.append(1);return {'status':'unavailable'}
    monkeypatch.setattr(events,'analyze',fail)
    assert m.process_one()
    assert not m.process_one()
    with m.db() as conn:conn.execute('UPDATE jobs SET next_run=0')
    monkeypatch.setattr(events,'analyze',lambda *a:{'status':'ok'})
    assert m.process_one() and not m.process_one()
    assert m.status()['jobs']=={'done':1}

def test_monitor_crud_and_new_filing_only():
    client=TestClient(app)
    body={'ticker':'TCS','question':'What changed in capacity?'}
    a=client.post('/monitors',json=body).json()
    assert client.post('/monitors',json=body).json()['id']==a['id']
    m.observe('TCS',[event()])
    assert m.status()['jobs']=={'pending':1} # analysis only, baseline does not run monitor
    m.observe('TCS',[event(),event('two')])
    with m.db() as conn:assert conn.execute("SELECT COUNT(*) FROM jobs WHERE kind='monitor'").fetchone()[0]==1
    assert client.delete('/monitors/'+a['id']).status_code==200
    assert not m.monitors()

def test_monitor_quote_dedup_and_briefing_only(monkeypatch):
    monitor=m.save_monitor('TCS','capacity expansion')
    doc={'url':'https://example.com/a.pdf','title':'Capacity','kind':'event_filing','hash':'same',
         'pages':[{'page':1,'text':'The company announced capacity expansion at its existing plant. '*5}]}
    monkeypatch.setattr(p,'document',lambda *a:doc)
    monkeypatch.setattr(p,'gemini',lambda *a:(json.dumps({'relevant':True,'text':'Capacity expansion announced.','source_id':'S1','quote':'The company announced capacity expansion at its existing plant.'}),'test'))
    m.monitor_event(monitor,event());m.monitor_event(monitor,event('copy'))
    assert len(storage.alerts())==1
    storage.save_setting('rules',{'mode':'briefing_only'});doc['hash']='another'
    m.monitor_event(monitor,event('new'))
    assert len(storage.alerts())==1
    assert storage.get('monitor_latest:'+monitor['id'])['event_id']=='new'

def test_unsupported_monitor_evidence_not_published(monkeypatch):
    monitor=m.save_monitor('TCS','capacity expansion')
    monkeypatch.setattr(p,'document',lambda *a:{'url':'https://example.com/a','kind':'event_filing','title':'Capacity','hash':'bad','pages':[{'page':1,'text':'Capacity expansion remains under review. '*8}]})
    monkeypatch.setattr(p,'gemini',lambda *a:(json.dumps({'relevant':True,'text':'Capacity doubled','source_id':'S1','quote':'Fabricated supporting passage'}),'test'))
    with pytest.raises(ValueError):m.monitor_event(monitor,event())
    assert not storage.alerts()

def test_exact_company_matching_without_ticker():
    storage.put(tickers.KEY,{'items':[{'ticker':'TCS','name':'Tata Consultancy Services Limited'}]})
    network.save(network.Contact(name='Engineer',employment=[network.Employment(company='Tata Consultancy Services',role='Engineer')]))
    matches=network.matches(ticker='TCS')
    assert matches and any('exact name match' in r for r in matches[0]['reasons'])
    assert not network.matches(ticker='TATASTEEL')
    network.save(network.Contact(name='Other employee',employment=[network.Employment(company='Tata Steel',role='Operations manager')]))
    assert [m['contact']['name'] for m in network.matches(ticker='TCS',company='Tata Consultancy Services Ltd',query='demand growth')]==['Engineer']

def test_revised_link_and_exact_content_grouping():
    m.observe('TCS',[event('original')]);m.observe('TCS',[event('rev','Revised Financial Results',date='2026-11-15T10:00:00+00:00')])
    assert m.get_event('rev')['previous_filing']['id']=='original'
    originals=[event('a','Acquisition'),event('b','Acquisition',date='2026-11-15T10:00:00+00:00')]
    for e in originals:storage.put('event_analysis:v3:'+e['id'],{'document_hash':'samehash'})
    assert len(events.grouped(originals))==1

def test_citation_valid_id_without_quote_is_rejected(monkeypatch):
    d={'url':'https://example.com/a','kind':'annual_report','title':'Annual','hash':'a','pages':[{'page':1,'text':'Revenue growth was 10 percent. '*12}]}
    monkeypatch.setattr(p,'discover',lambda *a:{'company':'Example','documents':[d],'warnings':[]})
    monkeypatch.setattr(p,'document',lambda *a:d)
    monkeypatch.setattr(p,'gemini',lambda *a:(json.dumps({'claims':[{'text':'Revenue grew 99 percent.','source_ids':['S1'],'support':[{'source_id':'S1','quote':'Revenue growth was 10 percent.'}]}]}),'test'))
    assert not research.research('TCS','revenue growth')['claims']
