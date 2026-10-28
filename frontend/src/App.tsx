import { useState } from 'react'
import { FacilityScene } from './components/digital-twin/FacilityScene'
import { useFacility } from './hooks/useFacility'
import './App.css'

function App() {
  const { data, error, retry } = useFacility()
  const [selected, setSelected] = useState<string | null>(null)
  const [zoom, setZoom] = useState(1)
  return (
    <div className="app-shell">
      <header className="flex items-center justify-between gap-4">
        <a href="#main" className="brand" aria-label="XOR Capacity Observatory"><span className="brand-mark">X</span> XOR <span className="brand-caption">CAPACITY OBSERVATORY</span></a>
        <span className="mode-label">AO–02 <span aria-hidden="true">/</span> REFERENCE ENVIRONMENT</span>
      </header>
      <main id="main">
        <div className="intro flex justify-between gap-8">
          <div><p className="eyebrow">01 / FACILITY EXPLORER</p><h1>Understand the space.<br /><span>See what comes next.</span></h1><p className="intro-copy">A technical view of your data center.<br />Explore the reference floor while the telemetry foundation takes shape.</p></div>
          <div className="connection" role="status"><span className={`connection-dot ${data ? 'connected' : ''}`} />{data ? 'API connected' : error ? 'API unavailable' : 'Connecting to API'}<small>Foundation · Milestone 01</small></div>
        </div>
        {error ? <section className="error-panel" role="alert"><h2>Could not load the facility</h2><p>{error} Start the backend, then retry.</p><button onClick={retry}>Retry connection ↗</button></section> : !data ? <p className="loading" role="status">Loading reference layout…</p> : <>
          <section className="workspace" aria-label="Reference facility explorer">
            <div className="drawing-caption"><span>FIG. 01</span> ISOMETRIC FACILITY PLAN <span>/ NOT TO SCALE</span></div>
            <FacilityScene racks={data.racks} coolingUnits={data.coolingUnits} selected={selected} onSelect={setSelected} zoom={zoom} />
            <aside className="inspector" aria-label="Rack inspector">
              <p className="eyebrow">{selected ? 'RACK INSPECTION' : 'REFERENCE LAYOUT'}</p>
              <h2>{selected ?? 'The facility'}</h2>
              <p>{selected ? 'Reference geometry selected. Resource readings will appear when telemetry is connected.' : 'Twelve racks. Two cooling units. One spatial view of the infrastructure.'}</p>
              <dl><div><dt>{selected ? 'Telemetry' : 'Rack positions'}</dt><dd>{selected ? 'Not connected' : '12'}</dd></div><div><dt>{selected ? 'Forecast' : 'Cooling units'}</dt><dd>{selected ? 'Not available' : '02'}</dd></div><div><dt>Operating mode</dt><dd>Read-only</dd></div></dl>
              {selected && <button className="text-button" onClick={() => setSelected(null)}>← Back to facility</button>}
              <div className="inspector-note"><span aria-hidden="true">◇</span> Layout only · No live readings</div>
            </aside>
            <div className="view-controls" aria-label="View controls"><span>VIEW</span><button aria-label="Zoom out" disabled={zoom <= .8} onClick={() => setZoom(value => Math.max(.8, +(value - .1).toFixed(1)))}>−</button><output aria-label="Zoom level">{Math.round(zoom * 100)}%</output><button aria-label="Zoom in" disabled={zoom >= 1.3} onClick={() => setZoom(value => Math.min(1.3, +(value + .1).toFixed(1)))}>+</button><button onClick={() => { setZoom(1); setSelected(null) }}>Reset view ↗</button></div>
          </section>
          <div className="rack-selector" aria-label="Select a rack"><span className="eyebrow">INSPECT A RACK</span>{data.racks.map(rack => <button key={rack.rackId} aria-pressed={selected === rack.rackId} onClick={() => setSelected(rack.rackId)}>{rack.rackId}</button>)}</div>
          <section className="resource-strip" aria-label="Planned resource coverage">{data.resources.map((resource, index) => <div key={resource}><span className="resource-number">0{index + 1}</span><h3>{resource.replaceAll('_', ' ').toLowerCase()}</h3><span className="pending">Awaiting telemetry</span></div>)}</section>
        </>}
      </main>
      <footer><span>TEAM XOR / AO–02</span><p>Advisory by design. Infrastructure controls remain outside this application.</p><span>FOUNDATION v0.1</span></footer>
    </div>
  )
}
export default App
