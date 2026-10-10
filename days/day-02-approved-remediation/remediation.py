"""Human-operated lab launcher. Never expose this program as an LLM tool."""
import argparse
import datetime as dt
import getpass
import json
from pathlib import Path
import subprocess
import time
import uuid
import remediator

ROOT=Path(__file__).resolve().parent
AUDIT=ROOT/'remediation-audit'

def kubectl(*args,payload=None):
    p=subprocess.run(['kubectl','--request-timeout=20s',*args],input=None if payload is None else json.dumps(payload),
        text=True,capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.strip())
    return p.stdout

def investigate():
    AUDIT.mkdir(exist_ok=True,mode=0o700)
    previous=ROOT/'plan.json'
    if previous.exists():
        previous.rename(AUDIT/('previous-plan-'+uuid.uuid4().hex[:8]+'.json'))
    # Retain old logs before replacing the one-shot investigator.
    p=subprocess.run(['kubectl','logs','incident-investigator','-n','ai-agent'],capture_output=True,text=True)
    if p.returncode==0:(AUDIT/('previous-investigation-'+uuid.uuid4().hex[:8]+'.log')).write_text(p.stdout)
    print(kubectl('delete','pod','incident-investigator','-n','ai-agent','--ignore-not-found'),flush=True)
    manifest=ROOT/'incident-agent-v3.yaml'
    if not manifest.exists():manifest=ROOT/'deploy'/'agent.yaml'
    print(kubectl('apply','-f',str(manifest)),flush=True)
    deadline=time.monotonic()+390
    while time.monotonic()<deadline:
        pod=json.loads(kubectl('get','pod','incident-investigator','-n','ai-agent','-o','json'))
        if pod['status']['phase'] in ('Succeeded','Failed'):break
        time.sleep(3)
    else:raise RuntimeError('Investigator timed out; inspect pod status')
    logs=kubectl('logs','incident-investigator','-n','ai-agent')
    report=AUDIT/('investigation-'+uuid.uuid4().hex[:8]+'.log')
    report.write_text(logs)
    print('Investigation report:',report,flush=True)
    if pod['status']['phase']!='Succeeded':raise RuntimeError('Investigator failed; inspect saved report')
    proposals=[]
    for line in logs.splitlines():
        marker=' propose_inventory_url_fix '
        if line.startswith('TOOL ') and marker in line:
            proposals.append(json.loads(line.split(marker,1)[1]))
    if not proposals:raise RuntimeError('No proposal tool result found')
    result=proposals[-1]
    if result.get('status')!='proposed':
        print(json.dumps(result,indent=2))
        return
    remediator.validate(result)
    previous.write_text(json.dumps(result,indent=2))
    print(previous.read_text(),flush=True)
    print('Saved plan.json. Review it, then run: python3 remediation.py preview',flush=True)

def job_objects(envelope,mode):
    name='incident-remediation-'+uuid.uuid4().hex[:10]
    cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':name,'namespace':'ai-agent'},
        'immutable':True,'data':{'plan.json':json.dumps(envelope),
        'remediator.py':(ROOT/'remediator.py').read_text()}}
    args=['python','-u','/bundle/remediator.py',mode]
    if mode=='apply':args.append(envelope['plan_id'])
    job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name,'namespace':'ai-agent',
         'annotations':{'lab/plan-id':envelope['plan_id'],'lab/mode':mode}},
         'spec':{'backoffLimit':0,'activeDeadlineSeconds':240,'ttlSecondsAfterFinished':86400,
         'template':{'metadata':{'labels':{'app':'incident-remediator'}},'spec':{
         'serviceAccountName':'incident-remediator','automountServiceAccountToken':True,
         'restartPolicy':'Never','securityContext':{'runAsNonRoot':True,'runAsUser':1000,
         'runAsGroup':1000,'seccompProfile':{'type':'RuntimeDefault'}},
         'containers':[{'name':'executor','image':'python:3.12-slim','command':args,
         'securityContext':{'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,
         'capabilities':{'drop':['ALL']}},'resources':{'requests':{'cpu':'50m','memory':'64Mi'},
         'limits':{'cpu':'250m','memory':'128Mi'}},
         'volumeMounts':[{'name':'bundle','mountPath':'/bundle','readOnly':True}]}],
         'volumes':[{'name':'bundle','configMap':{'name':name}}]}}}}
    return name,cm,job

def launch(envelope,mode,confirmation=None):
    remediator.validate(envelope)
    if mode=='apply' and confirmation!='APPROVE '+envelope['plan_id']:
        raise ValueError('Exact approval phrase required')
    name,cm,job=job_objects(envelope,mode)
    AUDIT.mkdir(exist_ok=True,mode=0o700)
    record={'mode':mode,'plan_id':envelope['plan_id'],'job':name,
            'operator_local_user':getpass.getuser(),'at':dt.datetime.now(dt.timezone.utc).isoformat(),
            'approval_phrase_matched':mode=='apply','plan':envelope['plan']}
    (AUDIT/(name+'.json')).write_text(json.dumps(record,indent=2))
    kubectl('create','-f','-',payload=cm)
    try:kubectl('create','-f','-',payload=job)
    except Exception:
        print('Job creation outcome uncertain. Inspect job '+name+' before retrying.',flush=True)
        raise
    print('Started',name,'as ai-agent/incident-remediator; mode='+mode,flush=True)
    deadline=time.monotonic()+270
    while time.monotonic()<deadline:
        current=json.loads(kubectl('get','job',name,'-n','ai-agent','-o','json'))
        if any(c['type'] in ('Complete','Failed') and c['status']=='True' for c in current.get('status',{}).get('conditions',[])):break
        time.sleep(2)
    else:raise RuntimeError('Job status unknown; inspect '+name+' before retrying')
    logs=kubectl('logs','job/'+name,'-n','ai-agent')
    (AUDIT/(name+'.log')).write_text(logs)
    print(logs,flush=True)
    if not current.get('status',{}).get('succeeded'):raise RuntimeError('Executor stopped; inspect audit log. No automatic retry.')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['investigate','preview','approve'])
    args=parser.parse_args()
    if args.action=='investigate':return investigate()
    path=ROOT/'plan.json'
    if not path.exists():raise ValueError('No plan.json. Run investigate first.')
    envelope=json.loads(path.read_text())
    plan=remediator.validate(envelope)
    print(json.dumps({'plan_id':envelope['plan_id'],'namespace':plan['namespace'],
        'deployment':plan['deployment'],'setting':plan['setting'],'before':plan['before'],
        'after':plan['after'],'expires_at':plan['expires_at']},indent=2),flush=True)
    if args.action=='preview':return launch(envelope,'preview')
    phrase='APPROVE '+envelope['plan_id']
    print('This will change orders and replace its pod. Type exactly: '+phrase,flush=True)
    confirmation=input('Approval: ').strip()
    launch(envelope,'apply',confirmation)

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,FileNotFoundError,EOFError) as exc:
        print('STOPPED:',str(exc),flush=True)
        raise SystemExit(1)
