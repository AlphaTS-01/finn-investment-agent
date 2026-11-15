from datetime import datetime,timedelta,timezone
from backend import storage,push

def test_fresh_covering_snapshot_replaces_old_window(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db.sqlite')
    now=datetime.now(timezone.utc)
    old={'id':'old','published_at':(now-timedelta(days=2)).isoformat()}
    recent={'id':'new','published_at':(now-timedelta(hours=1)).isoformat()}
    storage.put('events:TCS:1',{'ticker':'TCS','fetched_at':(now-timedelta(days=2)).isoformat(),'items':[old]})
    storage.put('events:TCS:7',{'ticker':'TCS','fetched_at':now.isoformat(),'items':[old,recent]})
    result=push.cached_window('TCS',1)
    assert result['status']=='ok'
    assert [e['id'] for e in result['items']]==['new']
    assert push.cached_window('TCS',30) is None

def test_old_snapshot_stays_labeled_cached(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DB',tmp_path/'db.sqlite')
    storage.put('events:TCS:7',{'ticker':'TCS','fetched_at':(datetime.now(timezone.utc)-timedelta(days=2)).isoformat(),'items':[]})
    assert push.cached_window('TCS',1)['status']=='stale'
