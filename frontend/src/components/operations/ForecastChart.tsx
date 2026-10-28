import {useState,useEffect,useRef} from 'react'
import {createScope,createTimeline} from 'animejs'
import type {Forecast} from '../../types/operations'
export function ForecastChart({report}:{report:Forecast}){
 const [hover,setHover]=useState<number|null>(null)
 const root=useRef<HTMLDivElement>(null)
 useEffect(()=>{if(!root.current)return;const scope=createScope({root:root.current,mediaQueries:{reduced:'(prefers-reduced-motion: reduce)'}}).add(self=>{if(self?.matches.reduced)return;createTimeline().add('.forecast-history',{opacity:[.6,1],duration:180}).add('.forecast-band',{opacity:[0,.12],duration:220},0)});return()=>scope.revert()},[report])
 const history=report.history.slice(-90)
 const length=history.length+report.predictions.length
 const x=(i:number)=>40+i/Math.max(1,length-1)*820
 const y=(v:number)=>220-Math.min(130,Math.max(0,v))/130*190
 const path=(values:{i:number;v:number}[])=>values.map((p,i)=>`${i?'L':'M'}${x(p.i)},${y(p.v)}`).join(' ')
 const past=history.map((p,i)=>({i,v:p.utilization_pct??0}))
 const pred=report.predictions.map((p,i)=>({i:i+history.length,v:p.mean}))
 const upper=report.predictions.map((p,i)=>({i:i+history.length,v:p.upper}))
 const lower=report.predictions.map((p,i)=>({i:i+history.length,v:p.lower})).reverse()
 const all=[...history.map(p=>({timestamp:p.timestamp,value:p.utilization_pct??0})),...report.predictions.map(p=>({timestamp:p.timestamp,value:p.mean}))]
 return <div className="forecast-plot" ref={root}><svg viewBox="0 0 900 260" role="img" aria-label="Historical utilization and numerical forecast with uncertainty band">
  {[0,40,80,100,120].map(v=><g key={v}><path d={`M40 ${y(v)}H860`} stroke="var(--line)" strokeDasharray={v===80||v===100?'4 4':'1 5'}/><text x="8" y={y(v)+4}>{v}%</text></g>)}
  <path className="forecast-band" d={`${path(upper)} ${path(lower).replace('M','L')}Z`} fill="var(--color-accent)" opacity=".12"/>
  <path className="forecast-history" d={path(past)} fill="none" stroke="var(--color-ink)" strokeWidth="2"/>
  <path d={path(pred)} fill="none" stroke="var(--color-accent)" strokeWidth="2" strokeDasharray="5 3"/>
  {history.map((p,i)=>p.is_regime_shift||p.is_transient_spike?<g key={p.timestamp}><circle cx={x(i)} cy={y(p.utilization_pct??0)} r="4" fill="var(--color-accent)"/><title>{p.timestamp}: {p.is_regime_shift?'Regime change':'Resolved transient spike'}</title></g>:null)}
  <path d={`M${x(history.length-1)} 25V220`} stroke="var(--color-muted)" strokeDasharray="3 4"/>
  <text x="40" y="250">{history[0]?.timestamp.slice(0,10)}</text><text x="650" y="250">Projected · {report.predictions.at(-1)?.timestamp.slice(0,10)}</text>
  {all.map((p,i)=><rect key={p.timestamp} x={x(i)-3} y="22" width="6" height="200" fill="transparent" onMouseEnter={()=>setHover(i)} onMouseLeave={()=>setHover(null)}><title>{p.timestamp.slice(0,10)}: {p.value.toFixed(2)}%</title></rect>)}
  {hover!==null&&all[hover]&&<g><circle cx={x(hover)} cy={y(all[hover].value)} r="4" fill="var(--color-accent)"/><text x="45" y="15">{all[hover].timestamp.slice(0,10)} · {all[hover].value.toFixed(2)}%</text></g>}
 </svg><p className="plot-key">Solid: observed telemetry · Dashed: forecast · Shaded: approximate prediction interval · 80% safety / 100% capacity</p></div>
}
