export const resourceTypes = ['STORAGE', 'POWER', 'THERMAL_COOLING', 'NETWORK', 'VM_COMPUTE', 'SOFTWARE_LICENSE'] as const
export type ResourceType = typeof resourceTypes[number]
export type SeverityStatus = 'HEALTHY' | 'WARNING' | 'CRITICAL'
export type PipelinePhase = 'RESOURCE_MONITORING' | 'INCIDENT_REPORTING' | 'ROOT_CAUSE_ANALYSIS' | 'REMEDIATION_CHECKING' | 'RISK_ANALYSIS' | 'HUMAN_VERIFICATION' | 'RESOLVED' | 'HALTED_LOOP_GUARD'

export interface RackLayout {
  rackId: string
  gridPosition: { row: number; col: number }
}
export interface RackSpatialNode extends RackLayout {
  status: SeverityStatus
  activeBadge?: ResourceType | null
  powerLoadKw: number
  maxPowerKw: number
  activeTokenIds: string[]
}
export interface CoolingUnitNode {
  unitId: string
  supplyTempCelsius: number
  fanSpeedRpm: number
  status: SeverityStatus
}
export interface QueuedIncidentTokenDTO {
  tokenId: string
  priorityNumber: number
  rackId: string
  tenantId: string | null
  resourceType: ResourceType
  currentPhase: PipelinePhase
  utilizationPct: number
  leadTimeWeeks: number | null
  hopCount: number
}
export interface BootstrapDTO {
  appName: string
  milestone: 1
  dataMode: 'reference-layout'
  telemetryAvailable: false
  resources: ResourceType[]
  racks: RackLayout[]
  coolingUnits: string[]
}
