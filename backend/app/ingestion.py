"""Validated CSV import into immutable, scope-specific telemetry windows."""
import csv
import io
import json
import hashlib
import math
from datetime import datetime, timezone
from pydantic import BaseModel,Field
from app.core.ao02_state_and_graph import ResourceType

class CSVImport(BaseModel):
    csv_text: str = Field(min_length=1,max_length=2_000_000)

UNITS={'POWER':'kW','STORAGE':'TB','NETWORK':'Gbps','VM_COMPUTE':'VM','SOFTWARE_LICENSE':'seats','THERMAL_COOLING':'C'}

def import_csv(text,heap):
    reader=csv.DictReader(io.StringIO(text))
    required={'timestamp','rack_id','tenant_id','resource_type','value','capacity','unit'}
    if not required.issubset(reader.fieldnames or []): raise ValueError('CSV requires: '+', '.join(sorted(required)))
    accepted=[]; errors=[];seen=set();groups={}
    for line,row in enumerate(reader,2):
        if line>20002: raise ValueError('Import limited to 20,000 readings')
        try:
            stamp=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
            if stamp.tzinfo is None: raise ValueError('Timestamp must include timezone')
            stamp=stamp.astimezone(timezone.utc)
            rack=row['rack_id'];tenant=row['tenant_id'];resource=ResourceType(row['resource_type']).value
            if rack not in [f'R-{i:02}' for i in range(1,13)] or tenant not in ('T1','T2','T3'): raise ValueError('Unknown rack or tenant')
            value=float(row['value']);capacity=float(row['capacity'])
            if not math.isfinite(value) or not math.isfinite(capacity) or not 0<=value<=capacity or capacity<=0: raise ValueError('Require finite 0 <= value <= capacity and capacity > 0')
            if row['unit']!=UNITS[resource]: raise ValueError('Unit must be '+UNITS[resource])
            key=(stamp.isoformat(),rack,tenant,resource)
            if key in seen: raise ValueError('Duplicate timestamp/scope in file')
            seen.add(key)
            point=dict(timestamp=stamp.isoformat(),rack_id=rack,tenant_id=tenant,resource_type=resource,value=value,capacity=capacity,unit=row['unit'],utilization_pct=100*value/capacity,safety_threshold_pct=80,workload_id=row.get('workload_id') or 'unattributed',synthetic=False)
            accepted.append(point);groups.setdefault((rack,tenant,resource),[]).append(point)
        except (ValueError,TypeError,KeyError) as exc: errors.append({'line':line,'reason':str(exc)})
    windows=[]
    with heap.connection() as db:
        for scope,points in groups.items():
            points.sort(key=lambda p:p['timestamp']);canonical=json.dumps(points,sort_keys=True,separators=(',',':'));digest=hashlib.sha256(canonical.encode()).hexdigest()
            db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)',(digest,canonical))
            windows.append({'hash':digest,'rack_id':scope[0],'tenant_id':scope[1],'resource_type':scope[2],'observations':len(points)})
    return {'accepted_count':len(accepted),'rejected_count':len(errors),'errors':errors,'windows':windows,'preview':accepted[:10]}
