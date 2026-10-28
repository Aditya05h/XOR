from fastapi import FastAPI, Depends, HTTPException, Query
from functools import lru_cache
import json
import hashlib
from datetime import datetime
from app.auth import identity_dependency
from app.storage import SharedContextHeap, PriorityTokenQueue
from app.models import HeapIncidentEnvelope, TelemetryWindowSummary, CapacityForecast
from app.telemetry import generate_telemetry
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings
from app.contracts import BootstrapDTO, GridPosition, HealthDTO, RackLayout
from app.core.ao02_state_and_graph import ResourceType


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    heap = SharedContextHeap(settings.database_path)
    queue = PriorityTokenQueue(heap)
    identity = identity_dependency(settings)
    dataset = lru_cache(maxsize=1)(generate_telemetry)
    app = FastAPI(title=settings.app_name, version="0.3.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.middleware('http')
    async def check_write_origin(request, call_next):
        if request.method in ('POST','DELETE','PUT','PATCH') and request.headers.get('origin') and request.headers['origin'] not in settings.cors_origins:
            return JSONResponse(status_code=403,content={'detail':'Untrusted request origin'})
        return await call_next(request)

    @app.get("/api/health", response_model=HealthDTO)
    def health() -> HealthDTO:
        return HealthDTO()

    @app.get("/api/bootstrap", response_model=BootstrapDTO)
    def bootstrap() -> BootstrapDTO:
        # Public reference geometry only. No tenant or operational data is exposed.
        return BootstrapDTO(
            app_name=settings.app_name,
            resources=list(ResourceType),
            racks=[
                RackLayout(rack_id=f"R-{i + 1:02}", grid_position=GridPosition(row=i // 4, col=i % 4))
                for i in range(12)
            ],
            cooling_units=["CRAC Unit A (North)", "CRAC Unit B (South)"],
        )

    @app.get('/api/telemetry')
    def telemetry(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), principal=Depends(identity)):
        source = dataset()
        points = source['points'] if principal['role'] == 'operator' else [p for p in source['points'] if p['tenant_id'] == principal['tenant_id']]
        return {'synthetic': True, 'total': len(points), 'points': points[offset:offset+limit]}

    @app.get('/api/telemetry/events')
    def events(principal=Depends(identity)):
        return [e for e in dataset()['events'] if principal['role'] == 'operator' or e['tenant_id'] == principal['tenant_id']]

    @app.get('/api/telemetry/window', response_model=TelemetryWindowSummary)
    def window(rack_id: str, resource_type: ResourceType, principal=Depends(identity)):
        points = [p for p in dataset()['points'] if p['rack_id'] == rack_id and p['resource_type'] == resource_type and 'capacity' in p and (principal['role'] == 'operator' or p['tenant_id'] == principal['tenant_id'])]
        if not points: raise HTTPException(404, 'Telemetry window not found')
        series=json.dumps(points,sort_keys=True,separators=(',',':'))
        digest=hashlib.sha256(series.encode()).hexdigest()
        with heap.connection() as db:
            db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)',(digest,series))
        last=points[-1]
        return TelemetryWindowSummary(window_start=datetime.fromisoformat(points[0]['timestamp']),window_end=datetime.fromisoformat(last['timestamp']),rack_id=rack_id,tenant_id=last['tenant_id'],resource_type=resource_type,current_utilization_pct=last['utilization_pct'],safety_margin_pct=20,hard_capacity_limit=last['capacity'],unit=last['unit'],raw_series_sha256=digest)

    @app.get('/api/queue')
    def snapshot(principal=Depends(identity)):
        return [t for t in queue.snapshot() if principal['role'] == 'operator' or t.tenant_id == principal['tenant_id']]

    @app.post('/api/incidents', status_code=201)
    def enqueue(envelope: HeapIncidentEnvelope, principal=Depends(identity)):
        if principal['role'] != 'operator': raise HTTPException(403, 'Operator role required')
        if envelope.token.hop_count or envelope.token.current_phase.value != 'RESOURCE_MONITORING' or envelope.audit_trail:
            raise HTTPException(422, 'New incidents must start at monitoring with no audit history')
        if envelope.rca or envelope.remediation_options or envelope.risk_evaluation or envelope.human_approved is not None:
            raise HTTPException(422,'Agent analysis and human decisions must come from the workflow')
        with heap.connection() as db:
            row=db.execute('SELECT series FROM snapshots WHERE hash=?',(envelope.telemetry.raw_series_sha256,)).fetchone()
        if not row: raise HTTPException(422, 'Create a telemetry window before submitting an incident')
        points=json.loads(row[0]); first=points[0]; last=points[-1]
        t=envelope.telemetry
        if (t.rack_id,t.tenant_id,t.resource_type.value,t.hard_capacity_limit,t.unit,t.current_utilization_pct,t.window_start,t.window_end) != (last['rack_id'],last['tenant_id'],last['resource_type'],last['capacity'],last['unit'],last['utilization_pct'],datetime.fromisoformat(first['timestamp']),datetime.fromisoformat(last['timestamp'])):
            raise HTTPException(422, 'Telemetry summary does not match source snapshot')
        from app.forecasting import forecast_series
        envelope.forecast=CapacityForecast.model_validate(forecast_series(points)['model'])
        envelope.token.priority_number=queue.compute_priority_number(envelope.token.resource_type,t.current_utilization_pct,envelope.forecast.lead_time_weeks)
        if not heap.put_envelope(envelope): raise HTTPException(409, 'Incident ID or active scope already exists')
        return heap.get_envelope_for_agent(envelope.token.token_id)

    @app.get('/api/incidents/{token_id}')
    def incident(token_id: str, principal=Depends(identity)):
        try: return heap.get_tenant_isolated_view(token_id, principal)
        except (KeyError, PermissionError): raise HTTPException(404, 'Incident not found')

    from app.operations import register_operations
    register_operations(app, settings, heap, queue, identity, dataset)
    return app


app = create_app()
