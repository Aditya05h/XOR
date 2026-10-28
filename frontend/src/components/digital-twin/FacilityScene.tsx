import { useEffect, useRef, useState, type PointerEvent } from 'react'
import { animate, createScope, stagger, type Scope } from 'animejs'
import type { RackLayout } from '../../types/ao02'
import './FacilityScene.css'
export interface SceneCoolingMetric { fanSpeedRpm: number; status?: string; supplyTempCelsius?: number; returnTempCelsius?: number; fanStatus?: 'running' | 'degraded' | 'stopped' }
export interface SceneRackMetric { temperature?: number; powerLoadKw?: number; utilizationPct?: number; status?: string }
interface Props {
  racks: RackLayout[]; coolingUnits: string[]; selected: string | null; onSelect: (rackId: string) => void; zoom: number
  coolingMetrics?: SceneCoolingMetric[]; onCoolingSelect?: (unitId: string) => void; selectedCoolingUnit?: string | null
  onZoom?: (zoom: number) => void; exploded?: boolean; airflow?: boolean; resetKey?: number
  onComponentSelect?: (rackId: string, component: string) => void; metrics?: Record<string, SceneRackMetric>; dayIndex?: number
}
const components = ['Network', 'Compute A', 'Compute B', 'Storage A', 'Storage B', 'Power', 'Cooling']
const position = (rack: RackLayout) => ({ x: 300 + rack.gridPosition.col * 115 - rack.gridPosition.row * 77, y: 211 + rack.gridPosition.col * 66 + rack.gridPosition.row * 44 })
const bounded = (value: number, limit: number) => Math.max(-limit, Math.min(limit, value))

export function FacilityScene({ racks, coolingUnits, selected, onSelect, zoom, onZoom, exploded = false, airflow = false, resetKey = 0, onComponentSelect, metrics = {}, dayIndex, coolingMetrics = [], onCoolingSelect, selectedCoolingUnit = null }: Props) {
  const root = useRef<SVGSVGElement>(null)
  const motion = useRef<Scope | null>(null)
  const drag = useRef<{ id: number; x: number; y: number; panX: number; panY: number } | null>(null)
  const [panState, setPanState] = useState({ key: resetKey, x: 0, y: 0 })
  const pan = panState.key === resetKey ? panState : { x: 0, y: 0 }
  const setPan = (next: { x: number; y: number } | ((current: { x: number; y: number }) => { x: number; y: number })) => {
    setPanState({ key: resetKey, ...(typeof next === 'function' ? next(pan) : next) })
  }
  const componentKey = `${selected}:${exploded}:${resetKey}`
  const [componentState, setComponentState] = useState<{ key: string; name: string } | null>(null)
  const component = componentState?.key === componentKey ? componentState.name : null
  useEffect(() => {
    const scope = createScope({ root, mediaQueries: { reduced: '(prefers-reduced-motion: reduce)' } }).add(self => {
      if (!self) return
      if (!self.matches.reduced) animate('.rack-body', { opacity: [0, 1], duration: 550, delay: stagger(35), ease: 'out(3)' })
      self.add('sync', (rackId: string | null, isExploded: boolean) => {
        const duration = self.matches.reduced ? 0 : 450
        const rack = racks.find(item => item.rackId === rackId)
        const focus = rack ? position(rack) : null
        animate('.scene-focus', { translateX: focus ? bounded((440 - focus.x) * .18, 45) : 0, translateY: focus ? bounded((290 - focus.y) * .15, 28) : 0, duration, ease: 'out(3)' })
        root.current?.querySelectorAll<SVGGElement>('.rack').forEach(element => {
          const active = element.dataset.rack === rackId
          const body = element.querySelector('.rack-body')
          if (body) animate(body, { translateY: active ? -12 : 0, duration, ease: 'out(3)' })
          element.querySelectorAll<SVGGElement>('.server-layer').forEach((layer, index) => {
            const separate = active && isExploded
            animate(layer, { translateX: separate ? 35 + index * 8 : 0, translateY: separate ? -42 + index * 4 : 0, duration, delay: self.matches.reduced ? 0 : index * 25, ease: 'out(3)' })
          })
        })
      })
    })
    motion.current = scope
    return () => { scope.revert(); motion.current = null }
  }, [racks])
  useEffect(() => { motion.current?.methods.sync(selected, exploded) }, [selected, exploded, racks])
  useEffect(() => {
    const svg = root.current
    if (!svg || !onZoom) return
    const wheel = (event: WheelEvent) => {
      if (!event.ctrlKey) return
      event.preventDefault()
      onZoom(Math.max(.8, Math.min(1.3, +(zoom + (event.deltaY < 0 ? .1 : -.1)).toFixed(1))))
    }
    svg.addEventListener('wheel', wheel, { passive: false })
    return () => svg.removeEventListener('wheel', wheel)
  }, [onZoom, zoom])
  useEffect(() => {
    if (!airflow) return
    const scope = createScope({ root, mediaQueries: { reduced: '(prefers-reduced-motion: reduce)' } }).add(self => {
      if (!self || self.matches.reduced) return
      animate('.air-particle', { translateY: [0, -30], opacity: [{ to: .8, duration: 500 }, { to: 0, duration: 1700 }], duration: 2200, delay: stagger(170), loop: true, ease: 'linear' })
      animate('.exhaust-particle', { translateY: [0, -28], opacity: [{ to: .7, duration: 500 }, { to: 0, duration: 1900 }], duration: 2400, delay: stagger(190), loop: true, ease: 'linear' })
    })
    return () => scope.revert()
  }, [airflow, dayIndex])
  useEffect(() => {
    if (!airflow) return
    const scope = createScope({ root, mediaQueries: { reduced: '(prefers-reduced-motion: reduce)' } }).add(self => {
      if (!self || self.matches.reduced) return
      coolingMetrics.forEach((metric, index) => {
        const fan = root.current?.querySelector(`[data-fan='${index}']`)
        if (fan && metric.fanStatus !== 'stopped' && metric.fanSpeedRpm > 0) {
          animate(fan, { rotate: [0, 360], duration: Math.max(80, 1200000 / metric.fanSpeedRpm), loop: true, ease: 'linear' })
        }
        if (metric.status && !['healthy', 'operational'].includes(metric.status.toLowerCase())) {
          const beacon = root.current?.querySelector(`[data-beacon='${index}']`)
          if (beacon) animate(beacon, { opacity: [.3, 1], duration: 800, alternate: true, loop: true, ease: 'inOut(2)' })
        }
      })
    })
    return () => scope.revert()
  }, [airflow, coolingMetrics])
  function startDrag(event: PointerEvent<SVGSVGElement>) {
    if (event.button !== 0 || (event.target as Element).closest('[role="button"]')) return
    drag.current = { id: event.pointerId, x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y }
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  function moveDrag(event: PointerEvent<SVGSVGElement>) {
    const active = drag.current
    if (!active || active.id !== event.pointerId) return
    const scale = 960 / event.currentTarget.getBoundingClientRect().width
    setPan({ x: bounded(active.panX + (event.clientX - active.x) * scale, 200), y: bounded(active.panY + (event.clientY - active.y) * scale, 130) })
  }
  function endDrag(event: PointerEvent<SVGSVGElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
    drag.current = null
  }
  function selectComponent(rackId: string, name: string) { setComponentState({ key: componentKey, name }); onComponentSelect?.(rackId, name) }
  function renderCoolingUnit(index: number) {
    const metric = coolingMetrics[index]
    const label = coolingUnits[index]
    const fault = metric?.status && !['healthy', 'operational'].includes(metric.status.toLowerCase())
    return <g className={`cooling-unit ${selectedCoolingUnit === label ? 'cooling-selected' : ''}`} transform={index === 0 ? 'translate(330 120)' : 'translate(640 486)'} role={onCoolingSelect ? 'button' : undefined} tabIndex={onCoolingSelect ? 0 : undefined} aria-label={onCoolingSelect ? `Inspect ${label}` : undefined} onClick={() => onCoolingSelect?.(label)} onKeyDown={event => { if (onCoolingSelect && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onCoolingSelect(label) } }}>
      <title>{label}{metric ? ` · ${metric.fanSpeedRpm} RPM · ${metric.status ?? 'status unavailable'} · fan rotation is a slowed illustration` : ''}</title>
      <path d={index === 0 ? 'M0 0 110 64 145 44 35 -20Z M0 0V-38L35 -58 145 6V44 M0 -38 110 26 145 6 M110 26V64' : 'M0 0 74 43 110 22 36 -21Z M0 0V-36L36 -57 110 -14V22 M0 -36 74 7 110 -14 M74 7V43'} />
      <g transform={index === 0 ? 'translate(64 -11)' : 'translate(45 -15)'} className="cooling-fan"><circle r="9" /><g data-fan={index} className="fan-impeller"><path d="M-7 0H7M0-7V7M-5-5 5 5M-5 5 5-5" /></g><circle r="2" /></g>
      <circle cx={index === 0 ? 13 : 9} cy={index === 0 ? -26 : -23} r={fault ? 2.6 : 1.5} className="cooling-beacon" data-beacon={index} />
      <text x={index === 0 ? 5 : -20} y={index === 0 ? -75 : 71}>{label}</text>
      {metric && <text className="cooling-reading" x={index === 0 ? 5 : -20} y={index === 0 ? -62 : 83}>{metric.supplyTempCelsius === undefined ? '' : `${metric.supplyTempCelsius.toFixed(1)}°C · `}{metric.fanSpeedRpm} RPM{fault ? ' · REVIEW' : ''}</text>}
    </g>
  }
  return <svg ref={root} className="facility-scene" viewBox="0 0 960 590" role="group" tabIndex={0} aria-label="Isometric facility. Drag empty floor or use arrow keys to pan." onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag} onKeyDown={event => {
    if (event.target !== event.currentTarget) return
    const shifts: Record<string, [number, number]> = { ArrowLeft: [24, 0], ArrowRight: [-24, 0], ArrowUp: [0, 24], ArrowDown: [0, -24] }
    if (shifts[event.key]) { event.preventDefault(); const [x, y] = shifts[event.key]; setPan(p => ({ x: bounded(p.x + x, 200), y: bounded(p.y + y, 130) })) }
    if (event.key === 'Home') { event.preventDefault(); setPan({ x: 0, y: 0 }); onZoom?.(1) }
  }}>
    <defs><pattern id="floor-grid" width="66" height="38" patternUnits="userSpaceOnUse"><path d="M0 19 33 0 66 19 33 38Z" fill="none" stroke="var(--line)" strokeWidth=".65" /></pattern></defs>
    <g className="scene-pan" transform={`translate(${pan.x} ${pan.y})`} data-pan-x={pan.x} data-pan-y={pan.y}>
      <g transform={`translate(${460 * (1 - zoom)} ${300 * (1 - zoom)}) scale(${zoom})`}><g className="scene-focus">
        <path d="M70 292 405 99 864 365 530 558Z" fill="url(#floor-grid)" stroke="var(--line)" />
        <path d="M69 312 529 579 864 386" fill="none" stroke="var(--line)" strokeDasharray="3 5" />
        <text x="355" y="565" className="diagram-label">SOUTH / SERVICE AISLE</text>
        {renderCoolingUnit(0)}
        {airflow && <g aria-label="Illustrative airflow paths" className="airflow-layer">{Array.from({ length: 12 }, (_, i) => <g key={i} transform={`translate(${170 + i * 51} ${335 + i * 12})`}><path d="M0 0 0 -32" stroke="var(--color-accent)" strokeWidth=".7" strokeDasharray="2 3" /><g className="air-particle"><path d="m-3 3 3 -3 3 3" fill="none" stroke="var(--color-accent)" strokeWidth="1.3" /><circle cy="14" r="1" fill="var(--color-accent)" /></g><g transform="translate(0 -110)"><g className="exhaust-particle"><path d="m-3 3 3 -3 3 3" fill="none" stroke="var(--color-muted)" strokeWidth="1" /></g></g></g>)}</g>}
        {racks.map(rack => {
          const { x, y } = position(rack), active = selected === rack.rackId, reading = metrics[rack.rackId]
          return <g key={rack.rackId} transform={`translate(${x} ${y})`} data-rack={rack.rackId} className={`rack ${active ? 'selected' : ''}`} role="button" tabIndex={0} aria-label={`Inspect ${rack.rackId}`} aria-pressed={active} onClick={() => onSelect(rack.rackId)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(rack.rackId) } }}>
            <title>{rack.rackId}{reading ? ` · ${reading.temperature === undefined ? '' : `${reading.temperature.toFixed(1)}°C · `}${reading.powerLoadKw === undefined ? '' : `${reading.powerLoadKw.toFixed(1)} kW`}` : ''}</title>
            <path className="rack-footprint" d="M-7 4 38 30 77 7 32 -19Z" />
            <g className="rack-body">
              <path className="rack-side" d="M37 -88 70 -107V8L37 27Z" /><path className="rack-face" d="M0 -110 37 -88V27L0 5Z" /><path className="rack-top" d="M0 -110 33 -129 70 -107 37 -88Z" />
              {components.map((name, index) => <g key={name} transform={`translate(5 ${-96 + index * 13})`}><g className={`server-layer ${active && component === name ? 'component-active' : ''}`} data-component={name} role={active && exploded ? 'button' : undefined} tabIndex={active && exploded ? 0 : undefined} aria-label={active && exploded ? `${rack.rackId} ${name} component` : undefined} onClick={event => { if (active && exploded) { event.stopPropagation(); selectComponent(rack.rackId, name) } }} onKeyDown={event => { if (active && exploded && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); event.stopPropagation(); selectComponent(rack.rackId, name) } }}><path d="M0 0 26 15V24L0 9Z" fill="var(--color-canvas)" /><path d="M4 6 17 13" /><circle cx="22" cy="17" r="1" fill="currentColor" stroke="none" />{active && exploded && <text className="component-label" x="34" y="18">{name}</text>}</g></g>)}
              <path d="M44 -78 62 -89M44 -69 62 -80M44 -60 62 -71" fill="none" /><text x="15" y="-143" className="rack-name">{rack.rackId}</text>
              {reading?.status && <text x="15" y="-156" className="metric-label">{reading.status}</text>}
            </g>
          </g>
        })}
        {renderCoolingUnit(1)}
      </g></g>
    </g>
    <g className="orientation" transform="translate(70 480)"><path d="M0 35V0L-5 9M0 0 5 9M0 35 25 50M0 35 -25 50" fill="none" /><text x="-4" y="-10">N</text></g>
    <text x="32" y="566" className="scene-help">DRAG FLOOR / ARROW KEYS TO PAN · HOME TO CENTER</text>
  </svg>
}
