"""Validated CSV import into immutable, scope-specific telemetry windows."""
import csv
import io
import json
import hashlib
import math
from datetime import datetime, timezone
from pydantic import BaseModel,Field
from zoneinfo import ZoneInfo
from app.core.ao02_state_and_graph import ResourceType

class CSVImport(BaseModel):
    csv_text: str = Field(min_length=1,max_length=25_000_000)

    mapping: dict[str,str] = Field(default_factory=dict)
    defaults: dict[str,str] = Field(default_factory=dict)
    metrics: dict[str,str] = Field(default_factory=dict)
    timezone: str = 'UTC'

ALIASES={
 'timestamp':['timestamp','time','date','datetime','recorded_at'],
 'rack_id':['rack_id','rack','rack_name','asset_id','resource_id'],
 'tenant_id':['tenant_id','tenant','customer','customer_id'],
 'resource_type':['resource_type','resource','metric','metric_type'],
 'value':['value','usage','consumption','used','reading'],
 'capacity':['capacity','limit','max_capacity','total','capacity_limit'],
 'unit':['unit','units'], 'workload_id':['workload_id','workload','application']
}
RESOURCE_ALIASES={'STORAGE':'STORAGE','DISK':'STORAGE','POWER':'POWER','NETWORK':'NETWORK','BANDWIDTH':'NETWORK','COOLING':'THERMAL_COOLING','TEMPERATURE':'THERMAL_COOLING','THERMAL_COOLING':'THERMAL_COOLING','VM':'VM_COMPUTE','COMPUTE':'VM_COMPUTE','VM_COMPUTE':'VM_COMPUTE','LICENSE':'SOFTWARE_LICENSE','LICENSES':'SOFTWARE_LICENSE','SOFTWARE_LICENSE':'SOFTWARE_LICENSE'}

def inspect_csv(text):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    headers=reader.fieldnames or []
    normalized={h.strip().lower().replace(' ','_'):h for h in headers}
    mapping={field:next((normalized[a] for a in names if a in normalized),'') for field,names in ALIASES.items()}
    return {'headers':headers,'mapping':mapping,'preview':[row for _,row in zip(range(5),reader)]}

UNITS={'POWER':'kW','STORAGE':'TB','NETWORK':'Gbps','VM_COMPUTE':'VM','SOFTWARE_LICENSE':'seats','THERMAL_COOLING':'C'}

def import_csv(text,heap,options=None):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    options=options or CSVImport(csv_text=text)
    mapping=inspect_csv(text)['mapping'] if not options.mapping else options.mapping
    defaults=options.defaults
    try: zone=ZoneInfo(options.timezone)
    except Exception: raise ValueError('Unknown timezone; use UTC or an IANA name such as Asia/Kolkata')
    accepted=[]; errors=[];seen=set();groups={}
    def rows():
        for line,source in enumerate(reader,2):
            if line>250001: raise ValueError('Import limited to 250,000 rows')
            row={field:source.get(mapping.get(field,'')) or defaults.get(field,'') for field in ALIASES}
            row['synthetic']=source.get('synthetic','false').strip().lower() in ('true','1','yes')
            if options.metrics:
                for resource,column in options.metrics.items():
                    if source.get(column,'').strip(): yield line,dict(row,resource_type=resource,value=source[column],capacity=defaults.get(resource+'_capacity') or row['capacity'],unit=UNITS.get(resource,''))
            else: yield line,row
    for line,row in rows():
        try:
            stamp=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
            if stamp.tzinfo is None: stamp=stamp.replace(tzinfo=zone)
            stamp=stamp.astimezone(timezone.utc)
            rack=row['rack_id'];tenant=row['tenant_id'];resource=ResourceType(RESOURCE_ALIASES.get(row['resource_type'].strip().upper(),row['resource_type'].strip().upper())).value
            if rack not in [f'R-{i:02}' for i in range(1,13)] or tenant not in ('T1','T2','T3'): raise ValueError('Unknown rack or tenant')
            value=float(row['value']);capacity=float(row['capacity'])
            if not math.isfinite(value) or not math.isfinite(capacity) or not 0<=value<=capacity or capacity<=0: raise ValueError('Require finite 0 <= value <= capacity and capacity > 0')
            row['unit']=row['unit'] or UNITS[resource]
            if row['unit']!=UNITS[resource]: raise ValueError('Unit must be '+UNITS[resource])
            key=(stamp.isoformat(),rack,tenant,resource)
            if key in seen: raise ValueError('Duplicate timestamp/scope in file')
            seen.add(key)
            point=dict(timestamp=stamp.isoformat(),rack_id=rack,tenant_id=tenant,resource_type=resource,value=value,capacity=capacity,unit=row['unit'],utilization_pct=100*value/capacity,safety_threshold_pct=80,workload_id=row.get('workload_id') or 'unattributed',synthetic=row['synthetic'])
            accepted.append(point);groups.setdefault((rack,tenant,resource),[]).append(point)
        except (ValueError,TypeError,KeyError) as exc: errors.append({'line':line,'reason':str(exc)})
    windows=[]
    with heap.connection() as db:
        for scope,points in groups.items():
            points.sort(key=lambda p:p['timestamp']);canonical=json.dumps(points,sort_keys=True,separators=(',',':'));digest=hashlib.sha256(canonical.encode()).hexdigest()
            db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)',(digest,canonical))
            windows.append({'hash':digest,'rack_id':scope[0],'tenant_id':scope[1],'resource_type':scope[2],'observations':len(points)})
    return {'accepted_count':len(accepted),'rejected_count':len(errors),'errors':errors,'windows':windows,'preview':accepted[:10]}
