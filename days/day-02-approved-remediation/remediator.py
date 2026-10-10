"""One fixed runbook. Runs in a Job as incident-remediator, without an LLM key."""
import datetime as dt
import hashlib
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

GOOD = 'http://inventory:8080/stock'
BAD = 'http://inventory-typo:8080/stock'
API_PATH = '/apis/apps/v1/namespaces/ai-sre-lab/deployments/orders'
FIELDS = {'runbook','namespace','deployment','deployment_uid','resource_version',
          'container','setting','before','after','created_at','expires_at','evidence',
          'expected_effect','recovery_checks','requires_human_approval'}

def digest(plan):
    return hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def validate(envelope, now=None):
    if not isinstance(envelope,dict) or envelope.get('status')!='proposed':
        raise ValueError('A proposed plan is required')
    p=envelope.get('plan')
    if not isinstance(p,dict) or set(p)!=FIELDS:raise ValueError('Unexpected plan schema')
    if envelope.get('plan_id')!=digest(p):raise ValueError('Plan digest mismatch')
    fixed={'runbook':'restore_inventory_url','namespace':'ai-sre-lab','deployment':'orders',
           'container':'orders','setting':'INVENTORY_URL','before':BAD,'after':GOOD,
           'requires_human_approval':True}
    if any(p.get(k)!=v for k,v in fixed.items()):raise ValueError('Unsupported operation')
    if p['requires_human_approval'] is not True:raise ValueError('Approval must be required')
    for k in ['deployment_uid','resource_version']:
        if not isinstance(p[k],str) or not p[k]:raise ValueError('Missing resource identity')
    created=dt.datetime.fromisoformat(p['created_at'])
    expiry=dt.datetime.fromisoformat(p['expires_at'])
    now=now or dt.datetime.now(dt.timezone.utc)
    if created.tzinfo is None or expiry.tzinfo is None:raise ValueError('Timezone required')
    if not 0 < (expiry-created).total_seconds() <= 300:raise ValueError('Invalid plan lifetime')
    if created>now+dt.timedelta(seconds=5) or now>=expiry:raise ValueError('Plan expired or future-dated; investigate again')
    evidence=p['evidence']
    if not isinstance(evidence,list) or len(evidence)!=2:raise ValueError('Two observations required')
    for e in evidence:
        if not isinstance(e,dict) or e.get('status')!=503 or e.get('dependency')!=BAD:
            raise ValueError('Unsupported failure evidence')
        when=dt.datetime.fromisoformat(e['at'])
        if when.tzinfo is None or not -5 <= (created-when).total_seconds() <= 60:
            raise ValueError('Evidence is not recent relative to proposal')
    return p

def make_patch(plan, deployment):
    meta=deployment['metadata']
    if meta['uid']!=plan['deployment_uid'] or meta['resourceVersion']!=plan['resource_version']:
        raise ValueError('Deployment changed since proposal; investigate again')
    containers=deployment['spec']['template']['spec']['containers']
    matches=[i for i,c in enumerate(containers) if c['name']=='orders']
    if len(matches)!=1:raise ValueError('Unexpected container layout')
    ci=matches[0]
    env=containers[ci].get('env',[])
    matches=[i for i,e in enumerate(env) if e.get('name')=='INVENTORY_URL']
    if len(matches)!=1:raise ValueError('Expected one explicit INVENTORY_URL')
    ei=matches[0]
    if env[ei]!={'name':'INVENTORY_URL','value':BAD}:
        raise ValueError('Current value does not match the supported fault')
    base=f'/spec/template/spec/containers/{ci}'
    return [
        {'op':'test','path':'/metadata/uid','value':plan['deployment_uid']},
        {'op':'test','path':'/metadata/resourceVersion','value':plan['resource_version']},
        {'op':'test','path':base+'/name','value':'orders'},
        {'op':'test','path':base+f'/env/{ei}','value':{'name':'INVENTORY_URL','value':BAD}},
        {'op':'replace','path':base+f'/env/{ei}/value','value':GOOD}]

class Cluster:
    def __init__(self):
        base=Path('/var/run/secrets/kubernetes.io/serviceaccount')
        self.token_path=base/'token'
        self.context=ssl.create_default_context(cafile=str(base/'ca.crt'))

    def request(self,method,path,payload=None):
        headers={'Authorization':'Bearer '+self.token_path.read_text().strip()}
        if payload is not None:headers['Content-Type']='application/json-patch+json'
        request=urllib.request.Request('https://kubernetes.default.svc'+path,
            data=None if payload is None else json.dumps(payload).encode(),headers=headers,method=method)
        with urllib.request.urlopen(request,context=self.context,timeout=15) as response:
            return json.load(response)

    def checkout(self):
        with urllib.request.urlopen('http://orders.ai-sre-lab.svc:8080/checkout',timeout=3) as response:
            return response.status==200 and json.load(response).get('status')=='order-confirmed'

def verify_recovery(cluster, uid, generation, timeout=120):
    deadline=time.monotonic()+timeout
    consecutive=0
    while time.monotonic()<deadline:
        d=cluster.request('GET',API_PATH)
        if d['metadata']['uid']!=uid or d['metadata']['generation']!=generation:
            raise ValueError('Deployment changed during recovery; manual review required')
        desired=d['spec'].get('replicas',1)
        status=d.get('status',{})
        rolled=(desired>0 and status.get('observedGeneration',0)>=generation
                and status.get('updatedReplicas',0)==desired
                and status.get('availableReplicas',0)==desired
                and status.get('replicas',0)==desired)
        if rolled:
            try:ok=cluster.checkout()
            except (urllib.error.URLError,TimeoutError,ValueError):ok=False
            consecutive=consecutive+1 if ok else 0
            print(json.dumps({'event':'checkout_probe','success':ok,'consecutive_successes':consecutive}),flush=True)
            if consecutive==6:return
        else:consecutive=0
        time.sleep(2)
    raise ValueError('Recovery not verified within deadline; manual review required, no automatic rollback')

def execute(envelope, mode, approved_id, cluster):
    plan=validate(envelope)
    if mode not in ('preview','apply'):raise ValueError('Unknown mode')
    if mode=='apply' and approved_id!=envelope['plan_id']:raise ValueError('Exact approved plan ID required')
    current=cluster.request('GET',API_PATH)
    patch=make_patch(plan,current)
    cluster.request('PATCH',API_PATH+'?dryRun=All',patch)
    print(json.dumps({'event':'preview_passed','plan_id':envelope['plan_id'],
        'before':BAD,'after':GOOD,'patch':patch}),flush=True)
    if mode=='preview':return {'status':'preview_passed','mutations':0}
    # Recheck expiry after network calls; JSON Patch tests reject concurrent changes.
    validate(envelope)
    updated=cluster.request('PATCH',API_PATH,patch)
    print(json.dumps({'event':'patch_applied','plan_id':envelope['plan_id'],
        'generation':updated['metadata']['generation'],'mutations':1}),flush=True)
    verify_recovery(cluster,plan['deployment_uid'],updated['metadata']['generation'])
    return {'status':'recovery_verified','plan_id':envelope['plan_id'],'mutations':1,'successful_probes':6}

if __name__=='__main__':
    try:
        envelope=json.loads(Path('/bundle/plan.json').read_text())
        result=execute(envelope,sys.argv[1],sys.argv[2] if len(sys.argv)>2 else '',Cluster())
        print(json.dumps(result),flush=True)
    except Exception as exc:
        # Do not print authorization headers or API response bodies.
        message=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
        print(json.dumps({'status':'stopped','reason':message,'http_status':getattr(exc,'code',None),
              'note':'Inspect current state before retrying. A submitted patch may have succeeded even if its response was lost.'}),flush=True)
        raise SystemExit(1)
