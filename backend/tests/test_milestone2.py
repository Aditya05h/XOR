import tempfile, unittest, sqlite3
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.models import *
from app.storage import SharedContextHeap, PriorityTokenQueue
from app.telemetry import generate_telemetry
from app.config import Settings
from app.main import create_app

def envelope(tenant='T1', rack='R-01', priority=10):
    return HeapIncidentEnvelope(token=IncidentToken(priority_number=priority,rack_id=rack,tenant_id=tenant,resource_type='STORAGE'),telemetry=TelemetryWindowSummary(window_start=datetime(2026,1,1,tzinfo=timezone.utc),window_end=datetime(2026,2,1,tzinfo=timezone.utc),rack_id=rack,tenant_id=tenant,resource_type='STORAGE',current_utilization_pct=90,safety_margin_pct=20,hard_capacity_limit=100,unit='TB',raw_series_sha256='a'*64))

class MilestoneTwoTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.path=Path(self.temp.name)/'state.sqlite3'
        self.heap=SharedContextHeap(self.path); self.queue=PriorityTokenQueue(self.heap)
    def tearDown(self): self.temp.cleanup()
    def test_concurrent_dedup_claim_and_restart(self):
        env=envelope()
        with ThreadPoolExecutor(max_workers=4) as workers:
            results=list(workers.map(lambda _: self.heap.put_envelope(env),range(8)))
        self.assertEqual(sum(results),1)
        self.assertEqual(PriorityTokenQueue(SharedContextHeap(self.path)).snapshot()[0].token_id,env.token.token_id)
        with ThreadPoolExecutor(max_workers=4) as workers:
            claims=list(workers.map(lambda _: self.queue.dequeue(),range(4)))
        self.assertEqual(sum(c is not None for c in claims),1)
        self.assertFalse(self.heap.put_envelope(envelope()))
    def test_order_loop_and_audit(self):
        a=envelope(priority=30); b=envelope(rack='R-02',priority=5)
        self.heap.put_envelope(a); self.heap.put_envelope(b)
        self.assertEqual(self.queue.dequeue().token_id,b.token.token_id)
        for _ in range(9): final=self.heap.advance(a.token.token_id,PipelinePhase.ROOT_CAUSE_ANALYSIS)
        self.assertEqual(final.token.current_phase,PipelinePhase.HALTED_LOOP_GUARD)
        self.assertEqual(len(final.audit_trail),10)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.heap.connection() as db: db.execute('DELETE FROM audit')
    def test_validation_and_read_only_remediation(self):
        with self.assertRaises(ValidationError):
            RemediationOption(option_id='x',title='x',recommended_action='x',simulated_post_action_utilization_pct=60,projected_lead_time_extension_weeks=2,simulation_assumptions='demo',mutates_live_facility_controls=True)
        with self.assertRaises(ValidationError): CapacityForecast(confidence_interval_days=(10,5))
        env=envelope(); env.telemetry.tenant_id='T2'
        with self.assertRaises(ValidationError): HeapIncidentEnvelope.model_validate_json(env.model_dump_json())
    def test_server_authorization(self):
        client=TestClient(create_app(Settings(_env_file=None,database_path=self.path,auth_tokens={'op':{'role':'operator'},'one':{'role':'tenant','tenant_id':'T1'},'two':{'role':'tenant','tenant_id':'T2'}})))
        env=envelope(); self.heap.put_envelope(env)
        self.assertEqual(client.get('/api/telemetry').status_code,401)
        self.assertEqual(client.get('/api/incidents/'+env.token.token_id,headers={'Authorization':'Bearer two'}).status_code,404)
        self.assertEqual(client.post('/api/incidents',json=envelope(rack='R-03').model_dump(mode='json'),headers={'Authorization':'Bearer one'}).status_code,403)
        data=client.get('/api/telemetry?limit=1000',headers={'Authorization':'Bearer one'}).json()
        self.assertTrue(all(p['tenant_id']=='T1' for p in data['points']))
        self.assertEqual(data['total'],365*4*6)
    def test_seeded_dataset(self):
        first=generate_telemetry(); second=generate_telemetry()
        self.assertEqual(first['sha256'],second['sha256'])
        self.assertEqual(len(first['points']),365*(12*6+6))
        self.assertEqual(len(first['events']),5)
        self.assertNotEqual(first['sha256'],generate_telemetry(seed=43)['sha256'])

    def test_snapshot_to_incident_and_scope_validation(self):
        client=TestClient(create_app(Settings(_env_file=None,database_path=self.path,auth_tokens={'op':{'role':'operator'}})))
        headers={'Authorization':'Bearer op'}
        summary=client.get('/api/telemetry/window?rack_id=R-01&resource_type=STORAGE',headers=headers)
        self.assertEqual(summary.status_code,200)
        env=envelope(); env.telemetry=TelemetryWindowSummary.model_validate(summary.json())
        response=client.post('/api/incidents',json=env.model_dump(mode='json'),headers=headers)
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(len(response.json()['audit_trail']),1)
        self.assertEqual(client.post('/api/incidents',json=env.model_dump(mode='json'),headers=headers).status_code,409)
        env.token.token_id='another'; env.telemetry.current_utilization_pct=1
        self.assertEqual(client.post('/api/incidents',json=env.model_dump(mode='json'),headers=headers).status_code,422)

    def test_ties_and_reopen(self):
        a=envelope(); b=envelope(rack='R-02')
        a.token.token_id='a'; b.token.token_id='b'; b.token.created_at=a.token.created_at
        self.heap.put_envelope(b); self.heap.put_envelope(a)
        self.assertEqual([t.token_id for t in self.queue.snapshot()],['a','b'])
        self.heap.advance('a',PipelinePhase.RESOLVED)
        self.assertTrue(self.heap.put_envelope(envelope()))

if __name__=='__main__': unittest.main()
