import { useEffect, useRef } from 'react'
import { animate, createScope, stagger } from 'animejs'
import type { RackLayout } from '../../types/ao02'

interface Props {
  racks: RackLayout[]
  coolingUnits: string[]
  selected: string | null
  onSelect: (rackId: string) => void
  zoom: number
}

export function FacilityScene({ racks, coolingUnits, selected, onSelect, zoom }: Props) {
  const root = useRef<SVGSVGElement>(null)
  useEffect(() => {
    const scope = createScope({ root, mediaQueries: { reduced: '(prefers-reduced-motion: reduce)' } }).add(self => {
      if (!self || self.matches.reduced) return
      animate('.rack-body', { opacity: [0, 1], duration: 550, delay: stagger(35), ease: 'out(3)' })
    })
    return () => scope.revert()
  }, [])
  useEffect(() => {
    if (!selected) return
    const scope = createScope({ root, mediaQueries: { reduced: '(prefers-reduced-motion: reduce)' } }).add(self => {
      animate('.selected .rack-body', { translateY: -12, duration: self?.matches.reduced ? 0 : 350, ease: 'out(3)' })
    })
    return () => scope.revert()
  }, [selected])
  return <svg ref={root} className="facility-scene" viewBox="0 0 960 590" role="group" aria-label="Isometric reference layout with twelve selectable racks">
    <defs><pattern id="floor-grid" width="66" height="38" patternUnits="userSpaceOnUse"><path d="M0 19 33 0 66 19 33 38Z" fill="none" stroke="var(--line)" strokeWidth=".65" /></pattern></defs>
    <g transform={`translate(${460 * (1 - zoom)} ${300 * (1 - zoom)}) scale(${zoom})`}>
      <path d="M70 292 405 99 864 365 530 558Z" fill="url(#floor-grid)" stroke="var(--line)" />
      <path d="M69 312 529 579 864 386" fill="none" stroke="var(--line)" strokeDasharray="3 5" />
      <text x="355" y="565" className="diagram-label">SOUTH / SERVICE AISLE</text>
      <g className="cooling-unit" transform="translate(330 120)"><path d="M0 0 110 64 145 44 35 -20Z M0 0V-38L35 -58 145 6V44 M0 -38 110 26 145 6 M110 26V64" /><text x="5" y="-75">{coolingUnits[0]}</text></g>
      {racks.map(rack => {
        const x = 300 + rack.gridPosition.col * 115 - rack.gridPosition.row * 77
        const y = 211 + rack.gridPosition.col * 66 + rack.gridPosition.row * 44
        return <g key={rack.rackId} transform={`translate(${x} ${y})`} className={`rack ${selected === rack.rackId ? 'selected' : ''}`} role="button" tabIndex={0} aria-label={`Inspect ${rack.rackId}`} aria-pressed={selected === rack.rackId} onClick={() => onSelect(rack.rackId)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(rack.rackId) } }}>
          <path className="rack-footprint" d="M-7 4 38 30 77 7 32 -19Z" />
          <g className="rack-body">
            <path className="rack-side" d="M37 -88 70 -107V8L37 27Z" />
            <path className="rack-face" d="M0 -110 37 -88V27L0 5Z" />
            <path className="rack-top" d="M0 -110 33 -129 70 -107 37 -88Z" />
            {Array.from({ length: 7 }, (_, index) => <g key={index} transform={`translate(5 ${-96 + index * 13})`}><path d="M0 0 26 15V24L0 9Z" fill="none" /><path d="M4 6 17 13" /><circle cx="22" cy="17" r="1" fill="currentColor" stroke="none" /></g>)}
            <path d="M44 -78 62 -89M44 -69 62 -80M44 -60 62 -71" fill="none" />
            <text x="15" y="-143" className="rack-name">{rack.rackId}</text>
          </g>
        </g>
      })}
      <g className="cooling-unit" transform="translate(640 486)"><path d="M0 0 74 43 110 22 36 -21Z M0 0V-36L36 -57 110 -14V22 M0 -36 74 7 110 -14 M74 7V43" /><text x="-20" y="71">{coolingUnits[1]}</text></g>
    </g>
    <g className="orientation" transform="translate(70 480)"><path d="M0 35V0L-5 9M0 0 5 9M0 35 25 50M0 35 -25 50" fill="none" /><text x="-4" y="-10">N</text></g>
  </svg>
}
