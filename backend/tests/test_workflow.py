import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
import httpx
from pydantic import SecretStr
from app.models import IncidentToken, TelemetryWindowSummary, HeapIncidentEnvelope
from app.storage import SharedContextHeap
from app.workflow import WorkflowEngine
from app.providers import ExplanationProvider
from langgraph.checkpoint.sqlite import SqliteSaver


def seed(heap,max_hops=8):
    points=[{'timestamp':f'2026-10-{day:02}T00:00:00Z','utilization_pct':70+day*.5,'workload_id':'T1-archive'} for day in range(1,29)]
    with heap.connection() as db: db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)',('a'*64,json.dumps(points)))
    env=HeapIncidentEnvelope(token=IncidentToken(priority_number=10,rack_id='R-01',tenant_id='T1',resource_type='STORAGE',max_allowed_hops=max_hops),telemetry=TelemetryWindowSummary(window_start=datetime(2026,10,1,tzinfo=timezone.utc),window_end=datetime(2026,10,28,tzinfo=timezone.utc),rack_id='R-01',tenant_id='T1',resource_type='STORAGE',current_utilization_pct=84,safety_margin_pct=20,hard_capacity_limit=100,unit='TB',raw_series_sha256='a'*64))
    heap.put_envelope(env)
    return env.token.token_id

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/'state.sqlite3'
        self.heap=SharedContextHeap(self.path)
    def tearDown(self): self.temp.cleanup()
    def test_pause_restart_defer_and_approve(self):
        token=seed(self.heap); engine=WorkflowEngine(self.heap)
        first=engine.run(token)
        self.assertTrue(first['awaiting_human_verification'])
        self.assertIsNone(first['envelope']['human_approved'])
        self.assertEqual(first['current_phase'],'HUMAN_VERIFICATION')
        with SqliteSaver.from_conn_string(engine.checkpoint_path) as saver:
            saved=engine._builder(saver).get_state({'configurable':{'thread_id':token}})
            self.assertTrue(saved.values['awaiting_human_verification'])
        count=len(first['envelope']['audit_trail'])
        self.assertEqual(len(engine.run(token)['envelope']['audit_trail']),count)
        restarted=WorkflowEngine(SharedContextHeap(self.path))
        deferred=restarted.decide(token,'defer','Investigate the workload first')
        self.assertTrue(deferred['awaiting_human_verification'])
        self.assertEqual(deferred['envelope']['risk_evaluation']['gate_decision'],'DEFERRED_BY_OPERATOR')
        done=WorkflowEngine(SharedContextHeap(self.path)).decide(token,'approve','Advisory accepted, no actuation')
        self.assertFalse(done['awaiting_human_verification'])
        self.assertTrue(done['envelope']['human_approved'])
        self.assertEqual(done['envelope']['risk_evaluation']['gate_decision'],'APPROVED_BY_OPERATOR')
        self.assertEqual(done['current_phase'],'RESOLVED')
        self.assertTrue(all(not o['mutates_live_facility_controls'] for o in done['envelope']['remediation_options']))
        self.assertAlmostEqual(done['envelope']['remediation_options'][0]['projected_lead_time_extension_weeks'],10/.5/7,places=3)
        with self.assertRaises(ValueError): restarted.decide(token,'approve')
    def test_reject_and_validation(self):
        token=seed(self.heap); engine=WorkflowEngine(self.heap)
        with self.assertRaises(ValueError): engine.decide(token,'approve')
        engine.run(token)
        with self.assertRaises(ValueError): engine.decide(token,'automatic')
        rejected=engine.decide(token,'reject','Insufficient feasibility evidence')
        self.assertFalse(rejected['envelope']['human_approved'])
        self.assertEqual(rejected['envelope']['risk_evaluation']['gate_decision'],'REJECTED_BY_OPERATOR')
    def test_loop_guard_ends_before_human_review(self):
        token=seed(self.heap,max_hops=2)
        result=WorkflowEngine(self.heap).run(token)
        self.assertTrue(result['should_halt'])
        self.assertEqual(result['current_phase'],'HALTED_LOOP_GUARD')
        self.assertFalse(result['awaiting_human_verification'])
    def test_correlations_are_source_linked_and_tenant_scoped(self):
        token=seed(self.heap)
        with self.heap.connection() as db:
            for tenant,digest in [('T1','b'*64),('T2','c'*64)]:
                points=[{'timestamp':f'2026-10-{day:02}T00:00:00Z','rack_id':'R-01','tenant_id':tenant,'resource_type':'POWER','utilization_pct':30+day} for day in range(1,29)]
                db.execute('INSERT INTO snapshots VALUES (?,?)',(digest,json.dumps(points)))
        result=WorkflowEngine(self.heap).run(token)
        text=json.dumps(result['envelope']['rca'])
        self.assertIn('b'*64,text)
        self.assertNotIn('c'*64,text)
        self.assertIn('r=1.000',text)
        self.assertTrue(all('robust-linear-daily-v1' in a['model_configuration_id'] for a in result['envelope']['audit_trail'][1:]))
    def test_provider_missing_key_and_bounded_failure(self):
        missing=SimpleNamespace(llm_provider='openai',openai_api_key=SecretStr(''))
        self.assertEqual(ExplanationProvider(missing).explain({'x':'Observed data'})['source'],'deterministic')
        count=[]
        def fail(request): count.append(request); return httpx.Response(503)
        settings=SimpleNamespace(llm_provider='openai',openai_api_key=SecretStr('test-secret'))
        result=ExplanationProvider(settings,httpx.MockTransport(fail)).explain({'x':'Observed data'})
        self.assertEqual(len(count),2)
        self.assertEqual(result['source'],'deterministic')
        self.assertNotIn('test-secret',str(result))
    def test_provider_structured_outputs_and_evidence_guard(self):
        evidence={'x':'Observed 84% utilization'}
        for mode in ('openai','gemini'):
            result_json=json.dumps({'summary':'Demand may explain observed utilization','evidence_ids':['x'],'limitation':'Cause remains uncertain'})
            def response(request):
                if mode=='openai': return httpx.Response(200,json={'output':[{'content':[{'type':'output_text','text':result_json}]}]})
                return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':result_json}]}}]})
            settings=SimpleNamespace(llm_provider=mode,**{mode+'_api_key':SecretStr('test')})
            result=ExplanationProvider(settings,httpx.MockTransport(response)).explain(evidence)
            self.assertEqual(result['source'],mode)
        def bad(request): return httpx.Response(200,json={'output':[{'content':[{'type':'output_text','text':json.dumps({'summary':'x','evidence_ids':['fake'],'limitation':'x'})}]}]})
        settings=SimpleNamespace(llm_provider='openai',openai_api_key=SecretStr('test'))
        self.assertEqual(ExplanationProvider(settings,httpx.MockTransport(bad)).explain(evidence)['source'],'deterministic')

if __name__=='__main__': unittest.main()
