import { useEffect, useState } from 'react'
import { getBootstrap } from '../services/api'
import type { BootstrapDTO } from '../types/ao02'

export function useFacility() {
  const [data, setData] = useState<BootstrapDTO | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    getBootstrap(controller.signal).then(setData).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Unable to reach the API.')
    })
    return () => controller.abort()
  }, [revision])
  return { data, error, retry: () => { setError(null); setRevision(value => value + 1) } }
}
