import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock
import incident_agent as agent

class Guardrails(unittest.TestCase):
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
        self.api.read_namespaced_pod_log.return_value='x'*20000
        result=self.tools.dispatch('read_pod_logs',{'pod_name':'orders-pod'})
        self.assertEqual(len(result['logs']),8000)
        self.assertTrue(result['character_truncated'])
        self.api.read_namespaced_pod_log.assert_called_once_with('orders-pod','ai-sre-lab',container='orders',tail_lines=50,since_seconds=300,limit_bytes=12000,timestamps=True,_request_timeout=(5,15))

    def test_seven_tool_batch_rejected_before_execution(self):
        calls=[NS(id=str(i),type='function',function=NS(name='list_lab_pods',arguments='{}')) for i in range(7)]
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
