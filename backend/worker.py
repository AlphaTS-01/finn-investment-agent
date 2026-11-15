"""Run separately: python -m backend.worker [--once] [--interval 900]."""
import argparse
import json
import time
import threading
from .push import refresh_portfolio
from . import monitoring, storage, providers

def run(stop, interval=900):
    # Source outages must not hold up already queued analysis.
    def ingest():
        while not stop.is_set():
            try:
                refresh_portfolio()
                storage.put('ingestion_status',{'state':'complete','checked_at':providers.now()})
            except Exception:
                storage.put('ingestion_status',{'state':'retrying','checked_at':providers.now()})
            stop.wait(interval)
    for ticker in storage.portfolio():
        cached=storage.get(f'events:{ticker}:7')
        if cached: monitoring.observe(ticker,cached.get('items',[]))
    refresher=threading.Thread(target=ingest,daemon=True,name='finn-ingestion')
    refresher.start()
    while not stop.is_set():
        try:
            storage.put('worker_status',{'state':'running','heartbeat':providers.now()})
            if not monitoring.process_one():stop.wait(5)
        except Exception:
            storage.put('worker_status',{'state':'retrying','heartbeat':providers.now()})
            stop.wait(15)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--interval', type=int, default=900)
    args = parser.parse_args()
    if args.once:
        print(json.dumps(refresh_portfolio()), flush=True)
        for _ in range(3): monitoring.process_one()
    else:
        run(threading.Event(), max(args.interval,300))

if __name__ == '__main__':
    main()
