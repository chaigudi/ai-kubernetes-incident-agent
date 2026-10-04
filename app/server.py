"""Tiny synthetic checkout service. Infrastructure is the exercise, not app code."""
import collections
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import time
import urllib.request

SERVICE = os.environ.get('SERVICE', 'orders')
UPSTREAM = os.environ.get('INVENTORY_URL', 'http://inventory:8080/stock')
COUNTS = collections.Counter()
LOCK = threading.Lock()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        start = time.monotonic()
        status = 200
        data = {'service': SERVICE, 'status': 'ok'}
        content_type = 'application/json'
        if self.path == '/metrics':
            with LOCK:
                lines = [f'lab_requests_total{{service="{SERVICE}",status="{code}"}} {count}' for code,count in COUNTS.items()]
            payload = ('# TYPE lab_requests_total counter\n' + '\n'.join(lines) + '\n').encode()
            content_type = 'text/plain; version=0.0.4'
        else:
            if self.path in ('/healthz', '/readyz'):
                pass
            elif self.path == '/stock' and SERVICE == 'inventory':
                data['stock'] = 42
            elif self.path == '/checkout' and SERVICE == 'orders':
                try:
                    with urllib.request.urlopen(UPSTREAM, timeout=1.5) as response:
                        inventory = json.load(response)
                    data = {'status':'order-confirmed', 'stock':inventory['stock']}
                except Exception as exc:
                    status = 503
                    data = {'status':'checkout-unavailable', 'dependency':UPSTREAM, 'error':str(exc)[:250]}
            else:
                status = 404
                data = {'error':'not-found'}
            payload = json.dumps(data).encode()
            if self.path not in ('/healthz','/readyz'):
                with LOCK: COUNTS[str(status)] += 1
                print(json.dumps({'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'service':SERVICE,'path':self.path,'status':status,'duration_ms':round((time.monotonic()-start)*1000,2),'detail':data}),flush=True)
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

ThreadingHTTPServer(('0.0.0.0',8080), Handler).serve_forever()
