"""Small, explicit research plans; dates describe requested coverage, not guarantees."""
import re

def plan(question):
    q = question.lower()
    category = next((cat for cat, pattern in [
        ('management_change',r'resign|appoint|ceo|cfo|management change'),
        ('M&A',r'acquisit|merger|takeover'), ('capex',r'capex|capacity|capital expenditure'),
        ('litigation',r'litigat|lawsuit|court'), ('results',r'quarter|qoq|yoy|financial results')]
        if re.search(pattern,q)), None)
    comparison = bool(re.search(r'compar|versus|\bvs\b|changed|previous|qoq|yoy|last [234] quarters', q))
    historical = re.findall(r'\b20\d{2}\b',q)
    kinds = (['event_filing','transcript'] if category else ['annual_report','transcript'])
    return {'topic': category or 'company_research', 'comparison':comparison,
            'period': ', '.join(historical) if historical else ('recent comparable periods' if comparison else 'latest available'),
            'years':historical, 'required_document_types':kinds,
            'minimum_documents':2 if comparison else 1}

def select(documents, request, limit):
    # Known dates/years rank before discovery order; undated sources remain explicit.
    def rank(d):
        title=d.get('title','')
        years=re.findall(r'\b20\d{2}\b',title)
        requested=not request['years'] or any(y in title for y in request['years'])
        return (requested, max(years,default='0000'), d.get('published_at',''))
    ranked=sorted(documents,key=rank,reverse=True)
    chosen=[]
    for kind in request['required_document_types']:
        take=2 if request['comparison'] else 1
        chosen.extend([d for d in ranked if d['kind']==kind][:take])
    chosen=chosen[:limit]
    for d in ranked:
        if len(chosen)>=limit: break
        if d not in chosen: chosen.append(d)
    return chosen
