import {useCallback,useEffect,useState} from 'react'
import {request,post} from '../services/operations'
import type {Principal,Facility,Forecast,Incident,WorkflowStatus} from '../types/operations'
import type {ResourceType} from '../types/ao02'

export function useObservatory(rack:string){
 const [principal,setPrincipal]=useState<Principal|null>(null)
 const [facility,setFacility]=useState<Facility|null>(null)
 const [forecast,setForecast]=useState<Forecast|null>(null)
 const [incidents,setIncidents]=useState<Incident[]>([])
 const [day,setDay]=useState(364)
 const [resource,setResource]=useState<ResourceType>('STORAGE')
 const [revision,setRevision]=useState(0)
 const [busy,setBusy]=useState(false)
 const [error,setError]=useState<string|null>(null)
 const [notice,setNotice]=useState<string|null>(null)
 const [streamConnected,setStreamConnected]=useState(false)
 const refresh=useCallback(()=>setRevision(v=>v+1),[])
 useEffect(()=>{request<Principal|null>('/session').then(setPrincipal).catch(()=>{})},[])
 useEffect(()=>{
   function expired(){setPrincipal(null);setFacility(null);setForecast(null);setIncidents([]);setNotice(null);setStreamConnected(false);setError('Your session has expired. Reconnect to continue uploading telemetry.')}
   window.addEventListener('ao02-session-expired',expired)
   return()=>window.removeEventListener('ao02-session-expired',expired)
 },[])

 useEffect(()=>{
   if(!principal)return
   const abort=new AbortController()
   Promise.all([request<Facility>(`/facility?day=${day}`,{signal:abort.signal}),request<Forecast>(`/forecasts/${rack}/${resource}?day=${day}`,{signal:abort.signal}).catch(()=>null),request<Incident[]>('/incidents',{signal:abort.signal})])
    .then(([f,p,i])=>{setFacility(f);setForecast(p);setIncidents(i);setError(p?null:'Select an authorized rack with sufficient telemetry')})
    .catch(e=>{if(!abort.signal.aborted){setForecast(null);setError(String(e.message))}})
   return()=>abort.abort()
 },[principal,day,resource,rack,revision])
 useEffect(()=>{
   if(!principal)return
   const base=import.meta.env.VITE_API_BASE_URL || location.origin
   const url=new URL('/api/stream',base);url.protocol=url.protocol==='https:'?'wss:':'ws:'
   let stopped=false
   let socket:WebSocket|undefined
   let timer:ReturnType<typeof setTimeout>|undefined
   function connect(){
     if(stopped)return
     socket=new WebSocket(url)
     socket.onopen=()=>{if(!stopped)setStreamConnected(true)}
     socket.onmessage=event=>{if(!stopped){const data=JSON.parse(event.data);if(data.type==='incidents')setIncidents(data.incidents)}}
     socket.onclose=()=>{
       if(stopped)return
       setStreamConnected(false)
       request<Principal|null>('/session').then(p=>{
         if(stopped)return
         if(!p)window.dispatchEvent(new Event('ao02-session-expired'))
         else timer=setTimeout(connect,1500)
       }).catch(()=>{if(!stopped)timer=setTimeout(connect,5000)})
     }
   }
   connect()
   return()=>{stopped=true;clearTimeout(timer);socket?.close()}

 },[principal])
 async function action<T>(fn:()=>Promise<T>,success?:string){setBusy(true);setError(null);try{const result=await fn();refresh();if(success)setNotice(success);return result}catch(e){setError(e instanceof Error?e.message:String(e));return null}finally{setBusy(false)}}
 async function login(token?:string){const p=await action(()=>token?post<Principal>('/session',{token}):post<Principal>('/session/local'),'Operator workspace connected');if(p)setPrincipal(p)}
 async function logout(){await action(()=>request('/session',{method:'DELETE'}));setPrincipal(null);setFacility(null);setForecast(null);setIncidents([])}
 async function scan(){await action(async()=>{const result=await post<{created:string[]}>('/monitor',{rack_id:rack,day});setNotice(`${result.created.length} incident(s) created; duplicate active scopes retained`);return result})}
 async function run(id?:string){await action(()=>post<WorkflowStatus>(id?`/incidents/${id}/run`:'/workflow/run-next'),'Workflow advanced; inspect the evidence and human-review state')}
 async function decide(id:string,decision:'approve'|'reject'|'defer',notes:string){await action(()=>post(`/incidents/${id}/decision`,{decision,notes}),`Operator decision recorded: ${decision}`)}
 return {principal,facility,forecast,incidents,day,setDay,resource,setResource,busy,error,notice,streamConnected,login,logout,scan,run,decide,refresh,clearNotice:()=>setNotice(null)}
}
export type Observatory=ReturnType<typeof useObservatory>
