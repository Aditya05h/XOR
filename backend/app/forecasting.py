"""Transparent robust trend baseline. Numerical outputs never depend on an LLM.

Intervals are approximate 90% prediction intervals from training rolling-origin
errors, residuals and linear-fit leverage, not a guarantee of coverage. Evaluation reports actual
held-out coverage separately. All look-ahead is bounded by the provided window.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from math import sqrt, isfinite
from statistics import median, mean
import numpy as np
import pandas as pd

MODEL_ID = 'robust-linear-daily-v1'


def _time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def _fit(xs, ys):
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    i,j = np.triu_indices(len(x),1)
    valid = x[j] != x[i]
    slopes = (y[j[valid]]-y[i[valid]])/(x[j[valid]]-x[i[valid]])
    slope = float(np.median(slopes)) if len(slopes) else 0.0
    intercept = float(np.median(y-slope*x))
    residuals = y-(intercept+slope*x)
    sigma = float(np.sqrt(np.sum(residuals**2)/max(1,len(x)-2)))
    return slope, intercept, sigma


def _clean(values):
    """Suppress only observed short spikes with a confirmed return to baseline."""
    cleaned = list(values)
    flags = [False]*len(values)
    for i in range(3,len(values)-3):
        before = median(values[i-3:i])
        for width in (1,2):
            after = median(values[i+width:i+width+3])
            if abs(after-before) > 3: continue
            baseline=(before+after)/2
            if all(v-baseline > 8 for v in values[i:i+width]):
                for j in range(i,i+width):
                    cleaned[j]=baseline; flags[j]=True
                break
    return cleaned, flags


def _regimes(xs, values):
    found=[]
    # A level shift must persist through two subsequent weeks. The fitted
    # pre-window trend distinguishes a jump from ordinary growth.
    for i in range(28,len(values)-14,7):
        slope, intercept, sigma = _fit(xs[i-28:i],values[i-28:i])
        errors=[values[j]-(intercept+slope*xs[j]) for j in range(i,i+14)]
        jump=median(errors)
        if abs(jump)>max(6,4*sigma) and sum(e*jump>0 for e in errors)>=12:
            # Avoid detecting the same step repeatedly.
            if not found or i-found[-1][0]>28:
                found.append((i,jump))
    return found


def forecast_series(points, horizon=60):
    if not isinstance(horizon,int) or not 1 <= horizon <= 365:
        raise ValueError('horizon must be 1–365 days')
    if not points: raise ValueError('telemetry window is empty')
    data=sorted(points,key=lambda p:_time(p['timestamp']))
    scope={(p['rack_id'],p.get('tenant_id'),p['resource_type']) for p in data}
    if len(scope)!=1: raise ValueError('forecast requires one rack, tenant and resource')
    times=list(pd.to_datetime([p['timestamp'] for p in data], utc=True).to_pydatetime())
    if len(set(times))!=len(times): raise ValueError('duplicate telemetry timestamps')
    values=[float(p['utilization_pct']) for p in data]
    if any(not isfinite(y) or not 0<=y<=100 for y in values): raise ValueError('invalid utilization')
    xs=[(t-times[0]).total_seconds()/86400 for t in times]
    cleaned,spikes=_clean(values)
    regimes=_regimes(xs,cleaned) if len(values)>=43 else []
    start=max(0,len(values)-42,regimes[-1][0] if regimes else 0)
    enough=len(values)-start>=14
    slope,intercept,sigma=_fit(xs[start:],cleaned[start:]) if enough else (0,cleaned[-1],0)
    threshold=float(data[-1].get('safety_threshold_pct',80))
    last_x=xs[-1]
    fitted_last=intercept+slope*last_x if enough else cleaned[-1]
    days_breach=0.0 if cleaned[-1]>=threshold else ((threshold-fitted_last)/slope if slope>1e-8 else None)
    days_exhaust=0.0 if cleaned[-1]>=100 else ((100-fitted_last)/slope if slope>1e-8 else None)
    if days_breach is not None and (days_breach<0 or days_breach>horizon): days_breach=None
    if days_exhaust is not None and (days_exhaust<0 or days_exhaust>horizon): days_exhaust=None
    xbar=mean(xs[start:]); sxx=sum((x-xbar)**2 for x in xs[start:])
    # Calibrate against rolling origins inside the supplied training window.
    # Calibration never sees the held-out future used by evaluate_dataset.
    calibration_errors=[]
    for origin in range(max(28,len(values)-112),len(values)-28,14):
        cs,ci,_=_fit(xs[max(0,origin-42):origin],cleaned[max(0,origin-42):origin])
        calibration_errors.extend(abs(cleaned[j]-(ci+cs*xs[j])) for j in range(origin,origin+28))
    calibration_width=float(np.quantile(calibration_errors,.9)) if calibration_errors else 0.0
    predictions=[]
    for ahead in range(1,horizon+1) if enough else []:
        x=last_x+ahead
        prediction=intercept+slope*x
        # 1.645 is the normal two-sided 90% quantile; training residual sigma
        # and leverage determine width, rather than a hardcoded confidence score.
        spread=1.645*sigma*sqrt(1+1/(len(values)-start)+(x-xbar)**2/max(sxx,1e-8))
        spread=max(spread,calibration_width*sqrt(max(1,ahead/28)))
        predictions.append({'timestamp':(times[-1]+timedelta(days=ahead)).isoformat(),'mean':round(prediction,4),'lower':round(prediction-spread,4),'upper':round(prediction+spread,4)})
    earliest=next((i+1 for i,p in enumerate(predictions) if p['upper']>=100),None)
    latest=next((i+1 for i,p in enumerate(predictions) if p['lower']>=100),None)
    interval=[0,0] if days_exhaust==0 else [earliest,latest] if earliest is not None and latest is not None else None
    model={'predicted_exhaustion_date':(times[-1]+timedelta(days=days_exhaust)).isoformat() if enough and days_exhaust is not None else None,
           'lead_time_weeks':round(days_exhaust/7,3) if enough and days_exhaust is not None else None,
           'confidence_interval_days':interval,'forecast_confidence_score':None,
           'is_transient_spike':any(spikes[-7:]),'regime_change_detected':bool(regimes),
           'regime_change_description':f'Persistent level change near {times[regimes[-1][0]].date()}; estimated shift {regimes[-1][1]:.1f} percentage points.' if regimes else None}
    gap_count=sum((times[i]-times[i-1]).total_seconds()>86400*1.5 for i in range(1,len(times)))
    return {'model':model,'history':[{**p,'cleaned_utilization_pct':round(cleaned[i],4),'is_transient_spike':spikes[i],'is_regime_shift':i in {r[0] for r in regimes}} for i,p in enumerate(data)],
            'predictions':predictions,'slope_pct_per_day':round(slope,6),'threshold_pct':threshold,
            'days_to_safety_breach':round(days_breach,2) if enough and days_breach is not None else None,
            'data_quality':{'observations':len(data),'fit_observations':len(data)-start,'missing_daily_gaps':gap_count,'sufficient_history':enough,'calibration_samples':len(calibration_errors),'interval_method':'90% training rolling-origin absolute-error quantile plus residual/leverage uncertainty; approximate, not guaranteed'},
            'model_configuration_id':MODEL_ID,'synthetic':all(p.get('synthetic',False) for p in data),
            'attribution':{'tenant_id':data[-1].get('tenant_id'),'workload_id':data[-1].get('workload_id'),'observed_growth_pct':round(cleaned[-1]-cleaned[max(0,len(cleaned)-29)],3)}}


def evaluate_dataset(dataset):
    """Chronological backtest; each forecast receives training points only.

    False alarm negative case: a series/cutoff whose next 28 observed daily
    points never reach the 80% safety threshold. A warning is threshold reached
    now or a forecast crossing within those 28 days. This is not a suppression
    rate and is distinct from the held-out point forecast error.
    """
    grouped=defaultdict(list)
    for p in dataset['points']:
        if 'utilization_pct' in p: grouped[(p['rack_id'],p.get('tenant_id'),p['resource_type'])].append(p)
    errors=[]; covered=0; negatives=0; false_alarms=0; cases=0; lead_times=[]
    # Fixed cutoffs cover ordinary growth, the known exhaustion, regime change
    # and spike. Each selected cutoff has a full future observation window.
    cutoffs=(180,230,260,300,329)
    for key,raw in grouped.items():
        series=sorted(raw,key=lambda p:_time(p['timestamp']))
        for cutoff in cutoffs:
            if cutoff+28>len(series): continue
            result=forecast_series(series[:cutoff],horizon=28)
            future=series[cutoff:cutoff+28]
            for prediction,actual in zip(result['predictions'],future):
                error=prediction['mean']-actual['utilization_pct']; errors.append(error)
                covered+=prediction['lower']<=actual['utilization_pct']<=prediction['upper']
            is_negative=max(p['utilization_pct'] for p in future)<result['threshold_pct']
            alert=result['days_to_safety_breach'] is not None
            negatives+=is_negative; false_alarms+=is_negative and alert; cases+=1
        # Evaluate warning lead time for actual first hard-capacity events.
        first_event=next((i for i,p in enumerate(series) if p['utilization_pct']>=100),None)
        if first_event is not None:
            first_warning=None
            for cutoff in range(max(42,first_event-60),first_event+1,7):
                forecast=forecast_series(series[:cutoff],60)
                if forecast['model']['predicted_exhaustion_date'] is not None:
                    first_warning=cutoff-1; break
            if first_warning is not None:
                lead_times.append((_time(series[first_event]['timestamp'])-_time(series[first_warning]['timestamp'])).total_seconds()/86400)
    n=len(errors)
    return {'synthetic':True,'model_configuration_id':MODEL_ID,'evaluation':'rolling chronological holdout; no future points passed to forecast',
            'mae_utilization_pct':round(mean(abs(e) for e in errors),4) if n else None,
            'rmse_utilization_pct':round(sqrt(mean(e*e for e in errors)),4) if n else None,
            'prediction_interval_coverage_pct':round(100*covered/n,2) if n else None,
            'nominal_interval_coverage_pct':90,'held_out_predictions':n,'series_count':len(grouped),'cutoffs':list(cutoffs),'case_count':cases,
            'false_alarm_rate_pct':round(100*false_alarms/negatives,2) if negatives else None,'false_alarm_count':false_alarms,'negative_case_count':negatives,
            'negative_case_definition':'series/cutoff with next 28 observations below 80% safety limit',
            'average_lead_time_weeks':round(mean(lead_times)/7,3) if lead_times else None,'detected_exhaustion_events':len(lead_times),
            'exhaustion_event_count':sum(any(p['utilization_pct']>=100 for p in s) for s in grouped.values()),
            'clarity_rubric':{'snapshot_hash_required':True,'forecast_configuration_recorded':True,'attribution_source':'telemetry workload_id','operator_explanation_quality':'requires human evaluation; no fabricated score'}}
