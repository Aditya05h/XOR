"""Inference from bundled ridge weights; no network or runtime model training."""
import json
from functools import lru_cache
from pathlib import Path
import numpy as np

@lru_cache(maxsize=1)
def model_metadata():
    return json.loads((Path(__file__).parent/'data/daily-model.json').read_text(encoding='utf-8'))

def predict_daily(values,times):
    model=model_metadata()
    result={k:v for k,v in model.items() if k!='weights'}
    result['next_day_utilization_pct']=None
    if len(values)<8 or any(abs((times[i]-times[i-1]).total_seconds()-86400)>60 for i in range(len(times)-7,len(times))):
        result['status']='Requires at least eight consecutive daily readings'
        return result
    delta=float(np.dot([1.,*np.diff(values[-8:]).tolist()],model['weights']))
    result.update(status='Bundled model inference',next_day_utilization_pct=round(float(np.clip(values[-1]+delta,0,100)),3))
    return result
