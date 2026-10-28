import {useState} from 'react'
import {post,request} from '../../services/operations'
import type {Forecast} from '../../types/operations'
import {JsonDetails} from './EvidenceLibrary'
import {ForecastChart} from './ForecastChart'
interface Result {accepted_count:number;rejected_count:number;errors:{line:number;reason:string}[];windows:{hash:string;rack_id:string;tenant_id:string;resource_type:string;observations:number}[];preview:unknown[]}
export function DataManagement(){
 const [result,setResult]=useState<Result|null>(null)
 const [report,setReport]=useState<Forecast|null>(null)
 const [error,setError]=useState('')
 const [busy,setBusy]=useState(false)
 async function upload(file:File){setBusy(true);setError('');try{if(file.size>2_000_000)throw new Error('Maximum CSV size is 2 MB');setResult(await post<Result>('/ingestion/csv',{csv_text:await file.text()}));setReport(null)}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}}
 async function inspect(hash:string){setBusy(true);setError('');try{setReport(await request<Forecast>(`/snapshots/${hash}/forecast`))}catch(e){setError(e instanceof Error?e.message:String(e))}finally{setBusy(false)}}
 return <section><h2>Telemetry ingestion</h2><p>Upload readings to create immutable windows. Each accepted row is validated; rejected rows include their line number and reason. Imported data is separate from the built-in synthetic timeline.</p><p className="method-note">Required columns: timestamp, rack_id, tenant_id, resource_type, value, capacity, unit. Optional: workload_id. Timestamps need a timezone. Resource names match the six resource categories. Units: TB, kW, C, Gbps, VM, seats.</p><label>CSV file<input type="file" accept=".csv,text/csv" disabled={busy} onChange={e=>{const file=e.target.files?.[0];if(file)void upload(file)}}/></label>{error&&<p role="alert">{error}</p>}{busy&&<p role="status">Processing telemetry…</p>}{result&&<><h3>{result.accepted_count} accepted · {result.rejected_count} rejected</h3><div className="action-row">{result.windows.map(w=><button key={w.hash} disabled={busy} onClick={()=>void inspect(w.hash)}>Forecast {w.rack_id} / {w.resource_type} ({w.observations} readings)</button>)}</div><JsonDetails value={result}/></>}{report&&<><ForecastChart report={report}/><JsonDetails value={report}/></>}</section>
}
