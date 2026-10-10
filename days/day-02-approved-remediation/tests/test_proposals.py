import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import datetime as dt
import json
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock
import incident_agent as agent

GOOD='http://inventory:8080/stock'
BAD='http://inventory-typo:8080/stock'

class Proposals(unittest.TestCase):
    def setUp(self):
        self.api,self.apps=Mock(),Mock()
        self.tools=agent.Diagnostics(self.api,self.apps,Mock())
        self.snapshot={'deployment':{'uid':'u1','resource_version':'10','inventory_url':{'source':'literal','value':BAD}},'truncated':False,'endpoints':[{'ready':True,'terminating':False}], 'service':{'selector':{'app':'inventory'},'ports':[{'port':8080,'target_port':8080,'protocol':'TCP'}]}}
        self.tools.inspect_orders_dependency=Mock(return_value=self.snapshot)
        pod=NS(metadata=NS(name='orders-1',deletion_timestamp=None),status=NS(phase='Running'),spec=NS(containers=[NS(name='orders',env=[NS(name='INVENTORY_URL',value=BAD,value_from=None)])]))
        self.api.list_namespaced_pod.return_value=NS(metadata=NS(_continue=None),items=[pod])
        self.apps.read_namespaced_deployment.return_value=NS(metadata=NS(uid='u1',resource_version='10'))
        self.set_logs()

    def set_logs(self, age=1, status=503):
        stamp=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=age)).isoformat()
        self.api.read_namespaced_pod_log.return_value.read.return_value=('\n'.join(stamp+' '+json.dumps({'service':'orders','path':'/checkout','status':status,'detail':{'dependency':BAD}}) for _ in range(2))).encode()

    def test_healthy_does_not_propose(self):
        self.snapshot['deployment']['inventory_url']['value']=GOOD
        self.assertEqual(self.tools.propose_inventory_url_fix()['status'],'no_change_needed')
        self.assertFalse(self.api.mock_calls or self.apps.mock_calls)

    def test_unsupported_configuration_is_manual(self):
        self.snapshot['deployment']['inventory_url']['value']='http://other/stock'
        self.assertEqual(self.tools.propose_inventory_url_fix()['status'],'manual_review')

    def test_stale_or_successful_logs_block_plan(self):
        for age,status in [(120,503),(1,200)]:
            self.set_logs(age,status)
            self.assertEqual(self.tools.propose_inventory_url_fix()['status'],'manual_review')

    def test_changed_deployment_blocks_plan(self):
        self.apps.read_namespaced_deployment.return_value.metadata.resource_version='11'
        self.assertEqual(self.tools.propose_inventory_url_fix()['status'],'manual_review')

    def test_missing_endpoints_blocks_plan(self):
        self.snapshot['endpoints']=[]
        self.assertEqual(self.tools.propose_inventory_url_fix()['status'],'manual_review')

    def test_supported_plan_is_bounded_and_never_mutates(self):
        result=self.tools.dispatch('propose_inventory_url_fix',{})
        self.assertEqual(result['status'],'proposed')
        self.assertEqual(result['plan']['after'],GOOD)
        self.assertTrue(result['plan']['requires_human_approval'])
        self.assertEqual(len(result['plan_id']),64)
        plan=result['plan']
        self.assertEqual((dt.datetime.fromisoformat(plan['expires_at'])-dt.datetime.fromisoformat(plan['created_at'])).total_seconds(),300)
        for call in self.api.mock_calls+self.apps.mock_calls:
            self.assertTrue(call[0].startswith(('read_','list_')),call)
        self.api.reset_mock();self.apps.reset_mock()
        self.assertIn('error',self.tools.dispatch('propose_inventory_url_fix',{'approved':True}))
        self.assertFalse(self.api.mock_calls or self.apps.mock_calls)
