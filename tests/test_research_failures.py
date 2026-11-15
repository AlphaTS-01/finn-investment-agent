import json
import httpx
import pytest
from backend import research, providers, storage


def test_empty_gemini_candidates(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test')
    monkeypatch.setattr(httpx,'post',lambda *a,**k:httpx.Response(200,json={'candidates':[]}))
    with pytest.raises(providers.ProviderError,match='no candidate'):
        providers.gemini('test')


def test_repair_and_preserve_evidence(monkeypatch,tmp_path):
    monkeypatch.setattr(storage,'DB',tmp_path/'test.db')
    doc=dict(url='https://example.com/report',title='Report',kind='annual_report',hash='test',pages=[dict(page=1,text='Revenue growth was 10.0 percent. '*10)])
    monkeypatch.setattr(providers,'discover',lambda *a:dict(company='Example',documents=[doc],warnings=[]))
    monkeypatch.setattr(providers,'document',lambda *a:doc)
    valid=dict(claims=[dict(text='Revenue growth was 10 percent.',source_ids=['S1'],support=[dict(source_id='S1',quote='Revenue growth was 10.0 percent.')])])
    responses=iter(['{}',json.dumps(valid)])
    monkeypatch.setattr(providers,'gemini',lambda *a:(next(responses),'test'))
    result=research.research('OTHER','revenue growth')
    assert result['claims'] and result['diagnostics']['model_attempts']==2
    valid['claims'][0]['text']='Revenue growth was -10 percent.'
    monkeypatch.setattr(providers,'gemini',lambda *a:(json.dumps(valid),'test'))
    result=research.research('OTHER','revenue growth',refresh=True)
    assert not result['claims'] and result['sources']
    assert result['failure_reason']=='answer_validation_failed'
