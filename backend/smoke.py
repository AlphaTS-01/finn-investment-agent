"""Opt-in live verification; uses provider quota. Run while the local API is up."""
import json
import time
import httpx

def main():
    results = []
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=240) as client:
        for path in ['/health', '/portfolio', '/docs', '/companies/TCS/announcements?days=7',
                     '/companies/TCS/prices']:
            response = client.get(path)
            response.raise_for_status()
            result = {'path': path, 'http_status': response.status_code}
            if 'application/json' in response.headers.get('content-type', ''):
                data = response.json()
                result['status'] = data.get('status', 'ok')
                if 'items' in data:
                    result['items'] = len(data['items'])
            results.append(result)
            print(json.dumps(result), flush=True)
        for ticker in ['TCS', 'ASIANPAINT']:
            for attempt in [1, 2]:
                started = time.monotonic()
                response = client.post('/research', json={'ticker': ticker, 'max_documents': 2,
                    'question': 'What did management say about demand and revenue growth in the latest available earnings call?'})
                response.raise_for_status()
                data = response.json()
                result = {'ticker': ticker, 'attempt': attempt, 'status': data['status'],
                          'cached': data['cached'], 'claims': len(data['claims']), 'sources': len(data['sources']),
                          'missing_document_types': data.get('missing_document_types', []),
                          'seconds': round(time.monotonic() - started, 2)}
                results.append(result)
                print(json.dumps(result), flush=True)
                assert data['claims'] and data['sources'], 'Research did not return grounded claims.'
                if attempt == 2:
                    assert data['cached'], 'Repeated request missed answer cache.'
    from .storage import DATA
    (DATA / 'live-verification.json').write_text(json.dumps(results, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
