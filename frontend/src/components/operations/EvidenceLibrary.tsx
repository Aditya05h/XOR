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
export function EvidenceLibrary({mode}:{mode:'archive'|'evaluation'|'sources'}){
 const [result,setResult]=useState<{mode:string;value?:unknown;error?:string}|null>(null)
 const [query,setQuery]=useState('')
 useEffect(()=>{const abort=new AbortController();request(mode==='sources'?'/archive/sources':`/${mode}`,{signal:abort.signal}).then(value=>setResult({mode,value})).catch(e=>{if(!abort.signal.aborted)setResult({mode,error:e.message})});return()=>abort.abort()},[mode])
 const value=result?.mode===mode?result.value:null
 const error=result?.mode===mode?result.error:null
 const visible=mode==='sources'&&value&&typeof value==='object'&&'sources' in value?Object.fromEntries(Object.entries((value as {sources:Record<string,string>}).sources).filter(([path,text])=>`${path} ${text}`.toLowerCase().includes(query.toLowerCase()))):value
 const metrics=mode==='evaluation'&&value&&typeof value==='object'?value as Record<string,unknown>:null
 return <section className="evidence-library"><h2>{mode==='evaluation'?'Measured synthetic evaluation':mode==='sources'?'Archive source and embedded content':'Archive examples and original datasets'}</h2><p>{mode==='evaluation'?'Chronological held-out results calculated by the backend. Inspect sample counts, error, interval coverage and metric definitions below.':'Preserved source scenarios. Values, tenant mappings and explanations are authored examples; they are not verified backend predictions.'}</p>{metrics&&<div className="forecast-facts">{[['mae_utilization_pct','MAE · percentage points'],['average_lead_time_weeks','Warning lead time · weeks'],['false_alarm_rate_pct','False-alarm rate · %'],['prediction_interval_coverage_pct','Interval coverage · %']].map(([key,label])=><div key={key}><small>{label}</small><strong>{String(metrics[key]??'Not available')}</strong></div>)}</div>}{metrics&&<p>Evidence completeness: {String(metrics.evidence_completeness_pct??'No eligible incidents')} {metrics.evidence_completeness_pct==null?'':'%'} · {String(metrics.evidence_rubric_case_count??0)} reviewed or review-ready incidents. Explanation quality requires human scoring.</p>}{mode==='sources'&&<label>Search files and embedded content<input value={query} onChange={e=>setQuery(e.target.value)}/></label>}{error?<p role="alert">{error}</p>:value?<JsonDetails value={visible}/>:<p role="status">Loading {mode==='evaluation'?'and evaluating held-out periods':'evidence'}…</p>}</section>
}
