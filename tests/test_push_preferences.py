from datetime import datetime,timezone
from fastapi.testclient import TestClient
import pytest
from backend import storage,network,push,monitoring,providers
from backend.app import app

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'test.db')

def test_digest_defaults_persist_and_validate():
    c=TestClient(app)
    assert c.get('/settings/digest').json()=={'default_days':1,'ungroup_filings':False}
    assert c.put('/settings/digest',json={'default_days':7,'ungroup_filings':True}).status_code==200
    assert c.get('/settings/digest').json()['default_days']==7
    assert c.put('/settings/digest',json={'default_days':90}).status_code==422

def test_delete_contacts_clears_local_network():
    network.save(network.Contact(name='QA'))
    assert TestClient(app).delete('/network/contacts').status_code==200
    assert network.contacts()==[]

def test_executive_affiliation_requires_filing_evidence():
    network.save(network.Contact(name='Engineer',education=[{'institution':'Stanford University','major':'Engineering'}]))
    assert not network.executive_overlaps([{'name':'New CEO','background':'Stanford University','quote':'Appointed as chief executive officer.'}])
    hits=network.executive_overlaps([{'name':'New CEO','quote':'Graduated from Stanford University.'}])
    assert hits[0]['name']=='Engineer'
    assert 'unverified' in hits[0]['reason']

def test_market_trigger_records_rule_and_actual_multiple(monkeypatch):
    monkeypatch.setattr(storage,'portfolio',lambda:['TCS'])
    monkeypatch.setattr(push,'announcements',lambda *a,**kw:{'status':'ok','items':[]})
    monkeypatch.setattr(providers,'prices',lambda *a,**kw:{'change_pct':-4,'volume_ratio':2.4,'baseline_sessions':20,'bars':[{'date':'2026-11-13'}]})
    storage.save_setting('rules',{'mode':'important','price_pct':3,'volume_ratio':2,'categories':['M&A']})
    push.refresh_portfolio()
    alert=storage.alerts()[0]
    assert '±3%' in alert['trigger_reasons'][0]
    assert '2.40×' in alert['trigger_reasons'][1]
    assert alert['rule_snapshot']['volume_ratio']==2

def test_selected_announcement_types_control_alerts(monkeypatch):
    monkeypatch.setattr(storage,'portfolio',lambda:['TCS'])
    monitoring.observe('TCS',[])
    event=push.normalize({'NEWSSUB':'Financial Results','NEWS_DT':datetime.now(timezone.utc).isoformat()},'TCS','BSE')
    monkeypatch.setattr(push,'announcements',lambda *a,**kw:{'status':'ok','items':[event]})
    monkeypatch.setattr(providers,'prices',lambda *a,**kw:{'change_pct':0,'volume_ratio':1,'baseline_sessions':20,'bars':[{'date':'2026-11-13'}]})
    storage.save_setting('rules',{'mode':'important','price_pct':3,'volume_ratio':2,'categories':['M&A']})
    push.refresh_portfolio()
    assert not storage.alerts()
