"""Reproducible daily synthetic readings, never represented as live facility data."""
import calendar
import hashlib
import json
import math
import random
from datetime import date, timedelta

CAPACITIES = {'POWER':(15,'kW'),'THERMAL_COOLING':(35,'C'),'STORAGE':(100,'TB'),'NETWORK':(100,'Gbps'),'VM_COMPUTE':(200,'VM'),'SOFTWARE_LICENSE':(500,'seats')}

def generate_telemetry(seed=42, end=date(2026,10,28)):
    rng=random.Random(seed)
    start=end.replace(year=end.year-1, day=min(end.day,calendar.monthrange(end.year-1,end.month)[1]))
    points=[]; events=[]
    for day in range((end-start).days):
        stamp=(start+timedelta(days=day)).isoformat()+'T00:00:00Z'
        for rack in range(1,13):
            tenant='T'+str((rack-1)%3+1)
            for resource,(capacity,unit) in CAPACITIES.items():
                growth=day*.08
                shift=8 if day>=290 and rack in (2,4,8) else 0
                spike=18 if day in (330,331) and rack==9 else 0
                usage=30+rack+growth+shift+spike+math.sin(day/7)*2+rng.uniform(-.5,.5)
                # A known past exhaustion and recovery scenario for later held-out evaluation.
                if rack==4 and resource=='STORAGE': usage=40+day*.23 if day<270 else 48+(day-270)*.12
                pct=round(min(100,max(0,usage)),3)
                points.append(dict(timestamp=stamp,rack_id=f'R-{rack:02}',tenant_id=tenant,resource_type=resource,
                    value=round(capacity*pct/100,4),capacity=capacity,unit=unit,utilization_pct=pct,
                    safety_threshold_pct=80,workload_id=f'{tenant}-{resource.lower()}-{rack}',synthetic=True))
        for index in range(2):
            for metric,value,unit in [('supply_temperature',13.2+index*.3,'C'),('return_temperature',26.8+index*.6+math.sin(day/14),'C'),('fan_speed',1422+index*28+round(math.sin(day/7)*15),'RPM')]:
                points.append(dict(timestamp=stamp,rack_id=f'CRAC-{index+1:02}',tenant_id=None,resource_type='THERMAL_COOLING',metric=metric,value=round(value,3),unit=unit,synthetic=True))
        if day in (261,270,290,330,332):
            events.append(dict(timestamp=stamp,kind={261:'exhaustion',270:'recovery',290:'workload_regime_change',330:'transient_spike',332:'spike_recovery'}[day],rack_id='R-04' if day<290 else 'R-02' if day==290 else 'R-09',tenant_id='T1' if day<290 else 'T2' if day==290 else 'T3'))
    encoded=json.dumps(points,sort_keys=True,separators=(',',':')).encode()
    return dict(seed=seed,start=start.isoformat(),end_exclusive=end.isoformat(),synthetic=True,sha256=hashlib.sha256(encoded).hexdigest(),points=points,events=events)
