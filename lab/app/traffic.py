import json
import time
import urllib.request
while True:
    start=time.monotonic()
    try:
        with urllib.request.urlopen('http://orders:8080/checkout',timeout=3) as response:
            status=response.status
            body=response.read().decode()
    except Exception as exc:
        status=getattr(exc,'code',0)
        body=str(exc)
    print(json.dumps({'timestamp':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'path':'/checkout','status':status,'duration_ms':round((time.monotonic()-start)*1000,2),'body':body[:250]}),flush=True)
    time.sleep(2)
