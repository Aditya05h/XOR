import { useState } from 'react'
import { FacilityScene } from './components/digital-twin/FacilityScene'
import { useFacility } from './hooks/useFacility'
import './App.css'
import {useObservatory} from './hooks/useObservatory'
import {Operations} from './components/operations/Operations'

function App() {
  const { data, error, retry } = useFacility()
  const [selected, setSelected] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)
  const [exploded,setExploded]=useState(false)
  const [airflow,setAirflow]=useState(false)
  const [resetKey,setResetKey]=useState(0)
  const [cooler,setCooler]=useState<string|null>(null)
  const [component,setComponent]=useState<string|null>(null)
  const ops=useObservatory(selected??'R-04')
  const readings=ops.facility?.readings.filter(p=>p.rack_id===selected)??[]
  const metricMap=Object.fromEntries((data?.racks??[]).flatMap(r=>{const rows=ops.facility?.readings.filter(p=>p.rack_id===r.rackId)??[];return rows.length?[[r.rackId,{utilizationPct:Math.max(0,...rows.map(p=>p.utilization_pct??0)),powerLoadKw:rows.find(p=>p.resource_type==='POWER')?.value,temperature:rows.find(p=>p.resource_type==='THERMAL_COOLING')?.value}]]:[]}))
  const coolingMetrics=['CRAC-01','CRAC-02'].map(id=>{const rows=ops.facility?.cooling.filter(p=>p.rack_id===id)??[];return {fanSpeedRpm:rows.find(p=>p.metric==='fan_speed')?.value??0,supplyTempCelsius:rows.find(p=>p.metric==='supply_temperature')?.value,returnTempCelsius:rows.find(p=>p.metric==='return_temperature')?.value}})
  return (
    <div className="app-shell">
      <header className="flex items-center justify-between gap-4">
        <a href="#main" className="brand" aria-label="XOR Capacity Observatory"><span className="brand-mark">X</span> XOR <span className="brand-caption">CAPACITY OBSERVATORY</span></a>
        <span className="mode-label">AO–02 <span aria-hidden="true">/</span> SYNTHETIC ENVIRONMENT</span>
      </header>
      <main id="main">
        <div className="intro flex justify-between gap-8">
          <div><p className="eyebrow">01 / FACILITY EXPLORER</p><h1>Understand the space.<br /><span>See what comes next.</span></h1><p className="intro-copy">A technical view of your data center.<br />Explore capacity, investigate risk, and review the evidence before acting.</p></div>
          <div className="connection" role="status"><span className={`connection-dot ${data ? 'connected' : ''}`} />{data ? 'API connected' : error ? 'API unavailable' : 'Connecting to API'}<small>Capacity advisory · Read-only</small></div>
        </div>
        {error ? <section className="error-panel" role="alert"><h2>Could not load the facility</h2><p>{error} Start the backend, then retry.</p><button onClick={retry}>Retry connection ↗</button></section> : !data ? <p className="loading" role="status">Loading reference layout…</p> : <>
          <section className="workspace" aria-label="Reference facility explorer">
            <div className="drawing-caption"><span>FIG. 01</span> ISOMETRIC FACILITY PLAN <span>/ NOT TO SCALE</span></div>
            <FacilityScene racks={data.racks} coolingUnits={data.coolingUnits} selected={selected} onSelect={id=>{setSelected(id);setCooler(null)}} zoom={zoom} onZoom={setZoom} exploded={exploded} airflow={airflow} resetKey={resetKey} onComponentSelect={(_rack,name)=>setComponent(name)} metrics={ops.principal?metricMap:undefined} dayIndex={ops.day} coolingMetrics={ops.principal?coolingMetrics:undefined} onCoolingSelect={id=>{setCooler(id);setSelected(null)}} selectedCoolingUnit={cooler} />
            <aside className="inspector" aria-label="Rack inspector">
              <p className="eyebrow">{selected ? 'RACK INSPECTION' : 'REFERENCE LAYOUT'}</p>
              <h2>{cooler??selected??'The facility'}</h2>
              <p>{selected ? ops.principal?'Historical synthetic readings at the selected timeline cursor.':'Connect below to inspect synthetic resource telemetry.' : 'Twelve racks. Two cooling units. One spatial view of the infrastructure.'}</p>
              <dl><div><dt>{selected ? 'Telemetry' : 'Rack positions'}</dt><dd>{selected ? ops.principal?'Synthetic':'Not connected' : '12'}</dd></div><div><dt>{selected ? 'Forecast' : 'Cooling units'}</dt><dd>{selected ? ops.forecast?.model.lead_time_weeks!=null?`${ops.forecast.model.lead_time_weeks.toFixed(1)} weeks`:'No estimate' : '02'}</dd></div><div><dt>Operating mode</dt><dd>Read-only</dd></div></dl>
              {readings.map(p=><div className="rack-reading" key={p.resource_type}><small>{p.resource_type.replaceAll('_',' ')}</small><strong>{p.value.toFixed(1)} {p.unit}</strong></div>)}
              {cooler&&ops.facility?.cooling.filter(p=>p.rack_id===(cooler===data.coolingUnits[0]?'CRAC-01':'CRAC-02')).map(p=><div className="rack-reading" key={p.metric}><small>{p.metric?.replaceAll('_',' ')}</small><strong>{p.value.toFixed(1)} {p.unit}</strong></div>)}
              {component&&selected&&<p>Component: {component}</p>}
              {selected && <button className="text-button" onClick={() => setSelected(null)}>← Back to facility</button>}
              <div className="inspector-note"><span aria-hidden="true">◇</span> {ops.principal?'Synthetic · No facility actuation':'Layout only · No live readings'}</div>
            </aside>
            <div className="view-controls" aria-label="View controls"><span>VIEW</span><button aria-label="Zoom out" disabled={zoom <= .8} onClick={() => setZoom(value => Math.max(.8, +(value - .1).toFixed(1)))}>−</button><output aria-label="Zoom level">{Math.round(zoom * 100)}%</output><button aria-label="Zoom in" disabled={zoom >= 1.3} onClick={() => setZoom(value => Math.min(1.3, +(value + .1).toFixed(1)))}>+</button><button onClick={() => { setZoom(1); setSelected(null); setCooler(null); setExploded(false); setComponent(null); setResetKey(v=>v+1) }}>Reset view ↗</button></div>
          </section>
          <div className="rack-selector" aria-label="Select a rack"><span className="eyebrow">INSPECT A RACK</span>{data.racks.map(rack => <button key={rack.rackId} aria-pressed={selected === rack.rackId} onClick={() => {setSelected(rack.rackId);setCooler(null)}}>{rack.rackId}</button>)}</div>
          <div className="scene-options"><button aria-pressed={exploded} disabled={!selected} onClick={()=>setExploded(v=>!v)}>{exploded?'Reassemble rack':'Explode selected rack'}</button><button aria-pressed={airflow} onClick={()=>setAirflow(v=>!v)}>Illustrative airflow</button><small>Drag floor to pan · Arrow keys / Home · Ctrl + wheel to zoom</small></div>
          <section className="resource-strip" aria-label="Planned resource coverage">{data.resources.map((resource, index) => <div key={resource}><span className="resource-number">0{index + 1}</span><h3>{resource.replaceAll('_', ' ').toLowerCase()}</h3><span className="pending">{ops.principal?`Synthetic · ${ops.facility?.readings.filter(p=>p.resource_type===resource).length??0} rack readings`: 'Awaiting telemetry'}</span></div>)}</section>
        </>}
      <Operations ops={ops} rack={selected??'R-04'}/></main>
      <footer><span>TEAM XOR / AO–02</span><p>Advisory by design. Infrastructure controls remain outside this application.</p><span>ADVISORY v0.3</span></footer>
    </div>
  )
}
export default App
