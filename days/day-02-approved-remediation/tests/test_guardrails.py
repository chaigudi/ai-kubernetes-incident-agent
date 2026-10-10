import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock
import incident_agent as agent

class Guardrails(unittest.TestCase):
    def test_dependency_inspection_is_scoped_and_excludes_unrelated_env(self):
        api, apps, discovery = Mock(), Mock(), Mock()
        tools=agent.Diagnostics(api,apps,discovery)
        apps.read_namespaced_deployment.return_value=NS(metadata=NS(uid='uid',resource_version='10'),spec=NS(template=NS(spec=NS(containers=[NS(name='orders',env=[NS(name='INVENTORY_URL',value_from=NS(secret_key_ref='hidden'),value=None),NS(name='PRIVATE_OTHER',value='do-not-export')])]))))
        api.read_namespaced_service.return_value=NS(spec=NS(selector={'app':'inventory'},ports=[NS(port=8080,target_port=8080,protocol='TCP')]))
        discovery.list_namespaced_endpoint_slice.return_value=NS(metadata=NS(_continue='more'),items=[NS(metadata=NS(name='slice'),endpoints=[NS(addresses=['10.0.0.1'],conditions=NS(ready=None,serving=None,terminating=None))])])
        result=tools.dispatch('inspect_orders_dependency',{})
        self.assertTrue(result['truncated'])
        self.assertIsNone(result['endpoints'][0]['ready'])
        self.assertIsNone(result['deployment']['inventory_url']['value'])
        self.assertNotIn('hidden',str(result))
        self.assertNotIn('do-not-export',str(result))
        apps.read_namespaced_deployment.assert_called_once_with('orders','ai-sre-lab',_request_timeout=(5,15))
        discovery.list_namespaced_endpoint_slice.assert_called_once_with('ai-sre-lab',label_selector='kubernetes.io/service-name=inventory',limit=20,_request_timeout=(5,15))
        apps.reset_mock();api.reset_mock();discovery.reset_mock()
        self.assertIn('error',tools.dispatch('inspect_orders_dependency',{'namespace':'kube-system'}))
        self.assertFalse(apps.mock_calls or api.mock_calls or discovery.mock_calls)

    def setUp(self):
        self.api=Mock()
        self.tools=agent.Diagnostics(self.api)

    def test_unknown_tool_and_namespace_override_rejected(self):
        self.assertIn('error',self.tools.dispatch('exec',{'command':'id'}))
        self.assertIn('error',self.tools.dispatch('list_lab_pods',{'namespace':'kube-system'}))
        self.assertFalse(self.api.mock_calls)

    def test_unlisted_pod_and_bad_argument_shape_rejected(self):
        self.assertIn('error',self.tools.dispatch('read_pod_logs',{'pod_name':'other-pod'}))
        self.assertIn('error',self.tools.dispatch('read_pod_logs',{'pod_name':['orders']}))
        self.assertIn('error',self.tools.dispatch('read_pod_logs',{'pod_name':'orders','namespace':'kube-system'}))
        self.assertFalse(self.api.mock_calls)

    def test_log_limits_and_namespace_enforced(self):
        self.tools.known={'orders-pod':['orders']}
        self.api.read_namespaced_pod_log.return_value.read.return_value=b'x'*12000
        result=self.tools.dispatch('read_pod_logs',{'pod_name':'orders-pod'})
        self.assertEqual(len(result['logs']),8000)
        self.assertTrue(result['character_truncated'])
        self.api.read_namespaced_pod_log.assert_called_once_with('orders-pod','ai-sre-lab',container='orders',tail_lines=50,since_seconds=300,limit_bytes=12000,timestamps=True,_request_timeout=(5,15),_preload_content=False)

    def test_nine_tool_batch_rejected_before_execution(self):
        calls=[NS(id=str(i),type='function',function=NS(name='list_lab_pods',arguments='{}')) for i in range(9)]
        llm=Mock()
        llm.chat.completions.create.return_value=NS(usage=None,choices=[NS(finish_reason='tool_calls',message=NS(content=None,tool_calls=calls))])
        with self.assertRaisesRegex(RuntimeError,'Tool budget exceeded'):
            agent.investigate(llm,self.tools,'test-only-placeholder')
        self.assertFalse(self.api.mock_calls)

    def test_four_requests_max_for_evidence_free_model(self):
        llm=Mock()
        llm.chat.completions.create.return_value=NS(usage=None,choices=[NS(finish_reason='stop',message=NS(content='Unsubstantiated answer',tool_calls=[]))])
        with self.assertRaisesRegex(RuntimeError,'minimum pod and log evidence'):
            agent.investigate(llm,self.tools,'test-only-placeholder')
        self.assertEqual(llm.chat.completions.create.call_count,4)
        self.assertEqual(llm.chat.completions.create.call_args.kwargs['tool_choice'],'none')

if __name__=='__main__':unittest.main()
