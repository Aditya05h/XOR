import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

class EndToEndTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'end.sqlite3'
  self.settings=Settings(_env_file=None,database_path=self.path,demo_mode=True,auth_tokens={'tenant-one-test':{'role':'tenant','tenant_id':'T1'},'tenant-two-test':{'role':'tenant','tenant_id':'T2'}})
  self.client=TestClient(create_app(self.settings));self.client.post('/api/session/demo')
 def tearDown(self): self.temp.cleanup()
 def test_full_scenario_pause_restart_and_decision(self):
  result=self.client.post('/api/monitor',json={'rack_id':'R-04','day':230})
  self.assertEqual(result.status_code,200,result.text)
  ids=result.json()['created'];self.assertTrue(ids)
  token=ids[0]
  run=self.client.post('/api/incidents/'+token+'/run').json()
  self.assertTrue(run['awaiting_human_verification'])
  self.assertIsNone(run['envelope']['human_approved'])
  restart=TestClient(create_app(self.settings));restart.post('/api/session/demo')
  deferred=restart.post('/api/incidents/'+token+'/decision',json={'decision':'defer','notes':'Capacity owner review tomorrow'})
  self.assertEqual(deferred.status_code,200,deferred.text)
  self.assertTrue(deferred.json()['awaiting_human_verification'])
  approved=restart.post('/api/incidents/'+token+'/decision',json={'decision':'approve','notes':'Advisory accepted for independent feasibility review'})
  self.assertEqual(approved.status_code,200,approved.text)
  self.assertTrue(approved.json()['envelope']['human_approved'])
  self.assertFalse(approved.json()['awaiting_human_verification'])
  self.assertTrue(all(o['mutates_live_facility_controls'] is False for o in approved.json()['envelope']['remediation_options']))
  self.assertEqual(restart.post('/api/incidents/'+token+'/decision',json={'decision':'approve','notes':'repeat'}).status_code,409)
 def test_session_tenant_filter_and_websocket(self):
  self.client.post('/api/monitor',json={'rack_id':'R-04','day':230})
  other=TestClient(create_app(self.settings))
  other.post('/api/session',json={'token':'tenant-two-test'})
  self.assertEqual(other.get('/api/archive').status_code,403)
  self.assertEqual(other.get('/api/forecasts/R-04/STORAGE').status_code,404)
  self.assertTrue(all(p['tenant_id']=='T2' for p in other.get('/api/facility').json()['readings']))
  with other.websocket_connect('/api/stream',headers={'origin':'http://127.0.0.1:5173'}) as ws:
   message=ws.receive_json();self.assertTrue(all(i['token']['tenant_id']=='T2' for i in message['incidents']))
  self.assertEqual(other.post('/api/monitor',json={}).status_code,403)
  self.assertEqual(self.client.post('/api/workflow/run-next',headers={'origin':'https://untrusted.example'}).status_code,403)
 def test_import_rejections_provenance_and_archive(self):
  csv='timestamp,rack_id,tenant_id,resource_type,value,capacity,unit\n2026-01-01T00:00:00Z,R-01,T1,STORAGE,50,100,TB\ninvalid,R-01,T1,STORAGE,51,100,TB\n'
  response=self.client.post('/api/ingestion/csv',json={'csv_text':csv});self.assertEqual(response.status_code,200,response.text)
  result=response.json();self.assertEqual((result['accepted_count'],result['rejected_count']),(1,1))
  report=self.client.get('/api/snapshots/'+result['windows'][0]['hash']+'/forecast')
  self.assertEqual(report.status_code,200,report.text);self.assertIsNone(report.json()['model']['lead_time_weeks'])
  archive=self.client.get('/api/archive').json()
  self.assertEqual(len(archive['ao02']['INITIAL_SPATIAL_RACKS']),12)
  self.assertEqual(len(archive['ao02']['INITIAL_ENVELOPES']),4)
  self.assertEqual(len(archive['legacy']['INITIAL_ALERTS']),5)
  self.assertEqual(len(archive['ao02']['timeSeries']['STORAGE']),425)
  sources=self.client.get('/api/archive/sources').json()['sources']
  self.assertIn('src/context/DataContext.tsx',sources)

 def test_recent_transient_does_not_hide_a_persistent_breach(self):
  from app.forecasting import forecast_series
  def with_recent_spike(points):
   report=forecast_series(points)
   report['model']['is_transient_spike']=True
   return report
  with patch('app.operations.forecast_series',side_effect=with_recent_spike):
   response=self.client.post('/api/monitor',json={'rack_id':'R-04','day':230})
  self.assertEqual(response.status_code,200,response.text)
  self.assertTrue(response.json()['created'])



 def test_flexible_year_import_and_wide_metrics(self):
  from datetime import datetime,timedelta
  rows=['Date,Asset,Customer,Disk,Electricity']
  for i in range(365): rows.append(f"{(datetime(2025,1,1)+timedelta(days=i)).isoformat()},R-01,T1,{30+i/10},5")
  text='\n'.join(rows)
  self.assertEqual(self.client.post('/api/session/local').status_code,200)
  preview=self.client.post('/api/ingestion/preview',json={'csv_text':text}).json()
  self.assertEqual(preview['mapping']['timestamp'],'Date')
  result=self.client.post('/api/ingestion/csv',json={'csv_text':text,'mapping':{'timestamp':'Date','rack_id':'Asset','tenant_id':'Customer'},'metrics':{'STORAGE':'Disk','POWER':'Electricity'},'defaults':{'STORAGE_capacity':'100','POWER_capacity':'15'},'timezone':'UTC'})
  self.assertEqual(result.status_code,200,result.text)
  data=result.json();self.assertEqual(data['accepted_count'],730);self.assertEqual(data['rejected_count'],0)
  self.assertEqual(len(data['windows']),2)
  report=self.client.get('/api/snapshots/'+data['windows'][0]['hash']+'/forecast')
  self.assertEqual(report.status_code,200,report.text)
 def test_aliases_and_explicit_defaults(self):
  result=self.client.post('/api/ingestion/csv',json={'csv_text':'date,usage,limit\n2026-01-01,45,100','defaults':{'rack_id':'R-01','tenant_id':'T1','resource_type':'disk'}})
  self.assertEqual(result.status_code,200,result.text)
  self.assertEqual(result.json()['accepted_count'],1)
  other=TestClient(create_app(self.settings));other.post('/api/session',json={'token':'tenant-one-test'})
  self.assertEqual(other.post('/api/ingestion/preview',json={'csv_text':'date,value\n2026-01-01,1'}).status_code,403)

 def test_annual_download_and_local_model(self):
  import csv,io
  response=self.client.get('/api/telemetry/sample.csv')
  self.assertEqual(response.status_code,200)
  rows=list(csv.DictReader(io.StringIO(response.text)))
  self.assertEqual(len(rows),26280)
  report=self.client.get('/api/forecasts/R-01/STORAGE').json()['offline_ml']
  self.assertIsNotNone(report['next_day_utilization_pct'])
  self.assertEqual(report['training_cases'],12384)
  self.assertEqual(report['validation_cases'],13320)
  other=TestClient(create_app(self.settings));other.post('/api/session',json={'token':'tenant-one-test'})
  self.assertEqual(other.get('/api/telemetry/sample.csv').status_code,403)
