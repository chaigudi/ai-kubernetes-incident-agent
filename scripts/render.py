"""Regenerate milestone ConfigMaps and the shared synthetic application manifest."""
from pathlib import Path
import yaml
root=Path(__file__).resolve().parents[1]
targets=[]
for day in ['day-01-incident-detection','day-02-approved-remediation']:
    base=root/'days'/day
    targets.append((base/'deploy/agent.yaml','incident-agent-code',{'agent.py':(base/'incident_agent.py').read_text()}))
targets.append((root/'lab/demo.yaml','demo-code',{name:(root/'lab/app'/name).read_text() for name in ['server.py','traffic.py']}))
for path,name,data in targets:
    objects=list(yaml.safe_load_all(path.read_text()))
    for item in objects:
        if item['kind']=='ConfigMap' and item['metadata']['name']==name:
            item['data']=data
    path.write_text(yaml.safe_dump_all(objects,sort_keys=False),encoding='utf-8')
    print('Updated',path.relative_to(root))
