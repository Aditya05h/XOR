import {useEffect,useState} from 'react'
import {request} from '../../services/operations'
function JsonNode({name,value}:{name:string;value:unknown}){
 const [open,setOpen]=useState(false)
 return <details onToggle={e=>setOpen(e.currentTarget.open)}><summary>{name.replaceAll('_',' ')} <small>{Array.isArray(value)?`${value.length} records`:value&&typeof value==='object'?`${Object.keys(value).length} fields`:String(value??'Not available').slice(0,100)}</small></summary>{open&&<div>{value&&typeof value==='object'?<JsonDetails value={value}/>:<pre>{String(value??'Not available')}</pre>}</div>}</details>
}
export function JsonDetails({value}:{value:unknown}){
 if(value===null||typeof value!=='object')return <span>{String(value??'Not available')}</span>
 return <div className="json-tree">{Object.entries(value).map(([key,item])=><JsonNode key={key} name={key} value={item}/>)}</div>
}
export function EvidenceLibrary({mode}:{mode:'evaluation'}){
 const [value,setValue]=useState<Record<string,unknown>|null>(null)
 const [error,setError]=useState('')
 useEffect(()=>{const abort=new AbortController();request<Record<string,unknown>>('/evaluation',{signal:abort.signal}).then(setValue).catch(e=>{if(!abort.signal.aborted)setError(e.message)});return()=>abort.abort()},[mode])
 return <section className="evidence-library"><h2>Measured synthetic evaluation</h2><p>Local forecasts evaluated against later synthetic readings. These results measure the supplied dataset, not real-facility accuracy.</p>{error?<p role="alert">{error}</p>:value?<><div className="forecast-facts">{[['mae_utilization_pct','MAE · percentage points'],['average_lead_time_weeks','Warning lead time · weeks'],['false_alarm_rate_pct','False-alarm rate · %'],['prediction_interval_coverage_pct','Interval coverage · %']].map(([key,label])=><div key={key}><small>{label}</small><strong>{String(value[key]??'Not available')}</strong></div>)}</div><JsonDetails value={value}/></>:<p role="status">Evaluating held-out periods…</p>}</section>
}
