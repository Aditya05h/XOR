import { resourceTypes, type BootstrapDTO } from '../types/ao02'

export async function getBootstrap(signal: AbortSignal): Promise<BootstrapDTO> {
  const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
  const response = await fetch(`${base}/api/bootstrap`, { signal })
  if (!response.ok) throw new Error(`API request failed (${response.status}).`)
  const data = await response.json()
  if (data.milestone !== 1 || data.dataMode !== 'reference-layout' || data.telemetryAvailable !== false ||
    typeof data.appName !== 'string' || !Array.isArray(data.racks) ||
    !data.racks.every((rack: BootstrapDTO['racks'][number]) => typeof rack?.rackId === 'string' &&
      Number.isInteger(rack.gridPosition?.row) && Number.isInteger(rack.gridPosition?.col)) ||
    !Array.isArray(data.resources) || !data.resources.every((resource: typeof resourceTypes[number]) => resourceTypes.includes(resource)) ||
    !Array.isArray(data.coolingUnits) || !data.coolingUnits.every((unit: unknown) => typeof unit === 'string')) {
    throw new Error('The API returned an incompatible facility contract.')
  }
  return data
}
