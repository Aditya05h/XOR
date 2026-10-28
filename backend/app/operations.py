"""Authorized forecasting, monitoring, durable workflow and preview APIs."""
import asyncio
import hashlib
import json
import secrets
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import Depends, HTTPException, Request, Response, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, Field
from app.models import HeapIncidentEnvelope, IncidentToken, TelemetryWindowSummary, CapacityForecast
from app.core.ao02_state_and_graph import ResourceType
from app.forecasting import forecast_series, evaluate_dataset
from app.workflow import WorkflowEngine
from app.ingestion import CSVImport, import_csv

class ScanRequest(BaseModel):
    rack_id: str | None = None
    day: int = Field(default=364,ge=30,le=364)
    snapshot_hash: str | None = Field(default=None,pattern=r'^[a-f0-9]{64}$')
class DecisionRequest(BaseModel):
    decision: Literal['approve','reject','defer']
    notes: str = Field(min_length=1,max_length=2000)
class LoginRequest(BaseModel):
    token: str = Field(min_length=1,max_length=512)

def register_operations(app, settings, heap, queue, identity, dataset):
    engine=WorkflowEngine(heap,settings)
    app.state.workflow=engine
    data_dir=Path(__file__).parent/'data'

    @lru_cache(maxsize=1)
    def grouped():
        groups={}
        for p in dataset()['points']:
            if 'capacity' in p: groups.setdefault((p['rack_id'],p['resource_type']),[]).append(p)
        return groups

    def series(rack,resource,principal,day=364):
        points=grouped().get((rack,resource),[])[:day+1]
        if not points or principal['role']!='operator' and points[0]['tenant_id']!=principal['tenant_id']:
            raise HTTPException(404,'Resource not found')
        return points

    def operator(principal):
        if principal['role']!='operator': raise HTTPException(403,'Operator role required')

    def traced_forecast(points):
        report=forecast_series(points)
        canonical=json.dumps(points,sort_keys=True,separators=(',',':'))
        digest=hashlib.sha256(canonical.encode()).hexdigest()
        report['telemetry_snapshot_sha256']=digest
        report_id=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        report['forecast_id']=report_id
        with heap.connection() as db:
            db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)',(digest,canonical))
            db.execute('INSERT OR IGNORE INTO forecasts VALUES (?,?,?)',(report_id,digest,json.dumps(report)))
        return report

    def envelopes(principal):
        with heap.connection() as db: ids=[r[0] for r in db.execute('SELECT id FROM incidents ORDER BY created DESC')]
        output=[]
        for token in ids:
            try: output.append(heap.get_tenant_isolated_view(token,principal).model_dump(mode='json'))
            except PermissionError: pass
        return output

    def session(response,principal):
        token=secrets.token_urlsafe(32)
        identity.sessions[token]={'principal':principal,'expires':time.time()+28800}
        response.set_cookie('ao02_session',token,httponly=True,samesite='strict',max_age=28800,secure=settings.environment=='production')
        return principal

    def trusted_origin(request):
        origin=request.headers.get('origin')
        if origin and origin not in settings.cors_origins: raise HTTPException(403,'Untrusted origin')

    @app.post('/api/session')
    def login(body: LoginRequest,request: Request,response: Response):
        trusted_origin(request)
        for token,principal in settings.auth_tokens.items():
            if secrets.compare_digest(token,body.token): return session(response,principal.model_dump())
        raise HTTPException(401,'Invalid credentials')

    @app.post('/api/session/demo')
    def demo(request: Request,response: Response):
        trusted_origin(request)
        if not settings.demo_mode or settings.environment!='development' or request.client.host not in ('127.0.0.1','::1','testclient'):
            raise HTTPException(403,'Local synthetic preview is disabled')
        return session(response,{'role':'operator','tenant_id':None})

    @app.get('/api/session')
    def current(request:Request):
        try: return identity(request,None)
        except HTTPException: return None

    @app.delete('/api/session')
    def logout(request: Request,response: Response):
        trusted_origin(request)
        identity.sessions.pop(request.cookies.get('ao02_session',''),None)
        response.delete_cookie('ao02_session')
        return {'signed_out':True}

    @app.get('/api/facility')
    def facility(day: int=Query(364,ge=0,le=364),principal=Depends(identity)):
        readings=[]
        for points in grouped().values():
            p=points[day]
            if principal['role']=='operator' or p['tenant_id']==principal['tenant_id']: readings.append(p)
        cooling=[p for p in dataset()['points'] if p['tenant_id'] is None and p['timestamp'].startswith(readings[0]['timestamp'][:10])] if readings and principal['role']=='operator' else []
        return {'synthetic':True,'day':day,'readings':readings,'cooling':cooling}

    @app.get('/api/forecasts/{rack_id}/{resource}')
    def forecast(rack_id:str,resource:ResourceType,day:int=Query(364,ge=0,le=364),principal=Depends(identity)):
        return traced_forecast(series(rack_id,resource.value,principal,day))

    @lru_cache(maxsize=1)
    def evaluation(): return evaluate_dataset(dataset())

    @app.get('/api/evaluation')
    def metrics(principal=Depends(identity)):
        operator(principal)
        return evaluation()

    @app.post('/api/monitor')
    def monitor(body:ScanRequest,principal=Depends(identity)):
        operator(principal)
        created=[]; suppressed=0
        groups=grouped()
        if body.snapshot_hash:
            with heap.connection() as db: row=db.execute('SELECT series FROM snapshots WHERE hash=?',(body.snapshot_hash,)).fetchone()
            if not row: raise HTTPException(404,'Snapshot not found')
            imported=json.loads(row[0]);groups={(imported[0]['rack_id'],imported[0]['resource_type']):imported}
        for (rack,resource),all_points in groups.items():
            if body.rack_id and body.rack_id!=rack: continue
            points=all_points[:body.day+1]
            report=traced_forecast(points)
            model=CapacityForecast.model_validate(report['model'])
            if model.is_transient_spike: suppressed+=1; continue
            breach=report.get('days_to_safety_breach')
            if points[-1]['utilization_pct']<80 and (breach is None or breach>60): continue
            canonical=json.dumps(points,sort_keys=True,separators=(',',':'))
            digest=hashlib.sha256(canonical.encode()).hexdigest()
            with heap.connection() as db: db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)',(digest,canonical))
            p=points[-1]
            token=IncidentToken(rack_id=rack,tenant_id=p['tenant_id'],resource_type=resource,priority_number=queue.compute_priority_number(ResourceType(resource),p['utilization_pct'],model.lead_time_weeks))
            telemetry=TelemetryWindowSummary(window_start=datetime.fromisoformat(points[0]['timestamp']),window_end=datetime.fromisoformat(p['timestamp']),rack_id=rack,tenant_id=p['tenant_id'],resource_type=resource,current_utilization_pct=p['utilization_pct'],safety_margin_pct=20,hard_capacity_limit=p['capacity'],unit=p['unit'],raw_series_sha256=digest)
            if heap.put_envelope(HeapIncidentEnvelope(token=token,telemetry=telemetry,forecast=model)): created.append(token.token_id)
        return {'created':created,'suppressed_transients':suppressed,'synthetic':not bool(body.snapshot_hash)}

    @app.post('/api/ingestion/csv')
    def ingest(body:CSVImport,principal=Depends(identity)):
        operator(principal)
        try: return import_csv(body.csv_text,heap)
        except ValueError as exc: raise HTTPException(422,str(exc))

    @app.get('/api/snapshots/{digest}/forecast')
    def imported_forecast(digest:str,principal=Depends(identity)):
        with heap.connection() as db: row=db.execute('SELECT series FROM snapshots WHERE hash=?',(digest,)).fetchone()
        if not row: raise HTTPException(404,'Snapshot not found')
        points=json.loads(row[0])
        if principal['role']!='operator' and any(p['tenant_id']!=principal['tenant_id'] for p in points): raise HTTPException(404,'Snapshot not found')
        try: return traced_forecast(points)
        except ValueError as exc: raise HTTPException(422,str(exc))

    @app.get('/api/incidents')
    def incident_list(principal=Depends(identity)): return envelopes(principal)

    @app.post('/api/workflow/run-next')
    def run_next(principal=Depends(identity)):
        operator(principal)
        token=queue.dequeue()
        if token is None: return {'empty':True}
        try: return engine.run(token.token_id)
        except (ValueError,KeyError) as exc: raise HTTPException(409,str(exc))

    @app.post('/api/incidents/{token_id}/run')
    def run(token_id:str,principal=Depends(identity)):
        operator(principal)
        try: return engine.run(token_id)
        except KeyError: raise HTTPException(404,'Incident not found')
        except ValueError as exc: raise HTTPException(409,str(exc))

    @app.get('/api/incidents/{token_id}/workflow')
    def status(token_id:str,principal=Depends(identity)):
        try: heap.get_tenant_isolated_view(token_id,principal)
        except (KeyError,PermissionError): raise HTTPException(404,'Incident not found')
        return engine.status(token_id)

    @app.post('/api/incidents/{token_id}/decision')
    def decide(token_id:str,body:DecisionRequest,principal=Depends(identity)):
        operator(principal)
        try: return engine.decide(token_id,body.decision,body.notes)
        except KeyError: raise HTTPException(404,'Incident not found')
        except ValueError as exc: raise HTTPException(409,str(exc))

    @app.get('/api/archive')
    def archive(principal=Depends(identity)):
        operator(principal)
        return json.loads((data_dir/'archive.json').read_text(encoding='utf-8'))

    @app.get('/api/archive/sources')
    def sources(principal=Depends(identity)):
        operator(principal)
        return json.loads((data_dir/'archive-source.json').read_text(encoding='utf-8'))

    @app.websocket('/api/stream')
    async def stream(socket:WebSocket):
        origin=socket.headers.get('origin')
        record=identity.sessions.get(socket.cookies.get('ao02_session',''))
        if origin not in settings.cors_origins or not record or record['expires']<=time.time():
            await socket.close(code=4401); return
        await socket.accept()
        previous=None
        try:
            while record['expires']>time.time():
                if socket.cookies.get('ao02_session','') not in identity.sessions: break
                payload=await asyncio.to_thread(envelopes,record['principal'])
                digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
                if digest!=previous:
                    await socket.send_json({'type':'incidents','incidents':payload}); previous=digest
                await asyncio.sleep(1)
        except (WebSocketDisconnect,RuntimeError): pass
        finally:
            try: await socket.close()
            except RuntimeError: pass
