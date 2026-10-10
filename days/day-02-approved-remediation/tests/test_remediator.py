import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import copy
import datetime as dt
import unittest
from unittest.mock import Mock, patch
import remediation
import remediator as r

def envelope():
    now=dt.datetime.now(dt.timezone.utc)
    p={'runbook':'restore_inventory_url','namespace':'ai-sre-lab','deployment':'orders',
       'deployment_uid':'u1','resource_version':'123','container':'orders','setting':'INVENTORY_URL',
       'before':r.BAD,'after':r.GOOD,'created_at':now.isoformat(),
       'expires_at':(now+dt.timedelta(minutes=5)).isoformat(),'requires_human_approval':True,
       'expected_effect':'New orders pod','recovery_checks':['checkout'],
       'evidence':[{'at':(now-dt.timedelta(seconds=i)).isoformat(),'status':503,'dependency':r.BAD,'pod':'orders-1'} for i in (4,2)]}
    return {'status':'proposed','plan':p,'plan_id':r.digest(p)}

def deployment():
    return {'metadata':{'uid':'u1','resourceVersion':'123','generation':2},
            'spec':{'replicas':1,'template':{'spec':{'containers':[{'name':'orders',
            'env':[{'name':'UNRELATED','value':'preserve-me'},{'name':'INVENTORY_URL','value':r.BAD}]}]}}}}

class ExecutorTests(unittest.TestCase):
    def test_rejects_expired_and_tampered_plan(self):
        e=envelope()
        with self.assertRaisesRegex(ValueError,'expired'):
            r.validate(e,dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=6))
        e['plan']['after']='http://attacker/'
        with self.assertRaisesRegex(ValueError,'digest'):r.validate(e)
        e['plan_id']=r.digest(e['plan'])
        with self.assertRaisesRegex(ValueError,'Unsupported'):r.validate(e)

    def test_named_resource_and_schema_cannot_be_overridden(self):
        for key,value in [('namespace','kube-system'),('deployment','inventory'),('extra','command')]:
            e=envelope();e['plan'][key]=value;e['plan_id']=r.digest(e['plan'])
            with self.assertRaises(ValueError):r.validate(e)

    def test_patch_has_atomic_preconditions_and_one_replacement(self):
        d=deployment();original=copy.deepcopy(d)
        ops=r.make_patch(envelope()['plan'],d)
        self.assertEqual(d,original)
        self.assertEqual([o for o in ops if o['op']=='replace'],[{'op':'replace','path':'/spec/template/spec/containers/0/env/1/value','value':r.GOOD}])
        self.assertIn('/metadata/resourceVersion',[o['path'] for o in ops if o['op']=='test'])

    def test_stale_identity_and_secret_reference_rejected(self):
        e=envelope()
        for field in ['uid','resourceVersion']:
            d=deployment();d['metadata'][field]='changed'
            with self.assertRaises(ValueError):r.make_patch(e['plan'],d)
        d=deployment();d['spec']['template']['spec']['containers'][0]['env'][1]={'name':'INVENTORY_URL','valueFrom':{'secretKeyRef':{}}}
        with self.assertRaises(ValueError):r.make_patch(e['plan'],d)

    def test_missing_approval_makes_no_api_calls(self):
        cluster=Mock()
        with self.assertRaises(ValueError):r.execute(envelope(),'apply','',cluster)
        self.assertFalse(cluster.mock_calls)
        with patch.object(remediation,'kubectl') as kubectl:
            with self.assertRaises(ValueError):remediation.launch(envelope(),'apply','yes')
            kubectl.assert_not_called()

    def test_preview_only_sends_dry_run_patch(self):
        cluster=Mock();cluster.request.return_value=deployment()
        result=r.execute(envelope(),'preview','',cluster)
        self.assertEqual(result['mutations'],0)
        patches=[c for c in cluster.request.call_args_list if c.args[0]=='PATCH']
        self.assertEqual(len(patches),1)
        self.assertTrue(patches[0].args[1].endswith('?dryRun=All'))

    def test_apply_once_then_verify(self):
        e=envelope();cluster=Mock();cluster.request.return_value=deployment()
        with patch.object(r,'verify_recovery') as verify:
            result=r.execute(e,'apply',e['plan_id'],cluster)
        self.assertEqual(result['mutations'],1)
        self.assertEqual([c.args[1] for c in cluster.request.call_args_list if c.args[0]=='PATCH'],[r.API_PATH+'?dryRun=All',r.API_PATH])
        verify.assert_called_once_with(cluster,'u1',2)

    def test_conflict_does_not_retry_or_verify(self):
        e=envelope();cluster=Mock()
        cluster.request.side_effect=[deployment(),deployment(),ValueError('conflict')]
        with patch.object(r,'verify_recovery') as verify:
            with self.assertRaisesRegex(ValueError,'conflict'):r.execute(e,'apply',e['plan_id'],cluster)
        self.assertEqual(cluster.request.call_count,3)
        verify.assert_not_called()

    def test_recovery_requires_six_consecutive_probes(self):
        cluster=Mock();d=deployment()
        d['status']={'observedGeneration':2,'updatedReplicas':1,'availableReplicas':1,'replicas':1}
        cluster.request.return_value=d
        cluster.checkout.side_effect=[True,False]+[True]*6
        with patch.object(r.time,'sleep'):r.verify_recovery(cluster,'u1',2)
        self.assertEqual(cluster.checkout.call_count,8)

    def test_recovery_rejects_new_deployment_generation(self):
        cluster=Mock();d=deployment();d['metadata']['generation']=3
        cluster.request.return_value=d
        with self.assertRaises(ValueError):r.verify_recovery(cluster,'u1',2)
        cluster.checkout.assert_not_called()

    def test_job_has_separate_identity_no_api_key_and_no_retries(self):
        _,cm,job=remediation.job_objects(envelope(),'preview')
        self.assertTrue(cm['immutable'])
        self.assertEqual(job['spec']['backoffLimit'],0)
        spec=job['spec']['template']['spec']
        self.assertEqual(spec['serviceAccountName'],'incident-remediator')
        self.assertNotIn('env',spec['containers'][0])
        self.assertFalse(any('secret' in v for v in spec['volumes']))
