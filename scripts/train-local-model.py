"""Build the bundled daily-delta ridge model; training never uses validation dates."""
import json
import sys
from collections import defaultdict
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.telemetry import generate_telemetry
series=defaultdict(list)
for p in generate_telemetry()['points']:
    if 'capacity' in p: series[(p['rack_id'],p['resource_type'])].append(p['utilization_pct'])
x=[]; y=[]; validation=[]
for values in series.values():
    for i in range(8,len(values)):
        features=[1.,*np.diff(values[i-8:i]).tolist()]
        target=values[i]-values[i-1]
        if i<180: x.append(features);y.append(target)
        else: validation.append((features,target))
x=np.asarray(x);penalty=np.eye(8)*10;penalty[0,0]=0
weights=np.linalg.solve(x.T@x+penalty,x.T@np.asarray(y))
errors=[float(np.dot(f,weights)-target) for f,target in validation]
artifact={'model_id':'daily-delta-ridge-v1','algorithm':'ridge regression, seven daily change features','training_source':'seed-42 synthetic telemetry; first 180 days only','training_cases':len(y),'training_end_exclusive':'2026-04-26','validation_cases':len(errors),'validation_mae_pct':float(np.mean(np.abs(errors))),'validation_rmse_pct':float(np.sqrt(np.mean(np.square(errors)))),'weights':weights.tolist(),'limitations':'One-day daily-series estimate. Synthetic validation is not evidence of real-facility accuracy. Capacity horizon uses the separate robust trend baseline.'}
Path('backend/app/data/daily-model.json').write_text(json.dumps(artifact,indent=2),encoding='utf-8')
print({k:v for k,v in artifact.items() if k!='weights'})
