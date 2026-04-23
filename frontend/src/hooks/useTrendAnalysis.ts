import { useCallback, useState } from 'react'
import { analyzeTrends } from '../services/opusClient'
import { toApiError } from '../services/apiClient'
import type { ApiError, TrendsResponse } from '../types/api'
import type { PatientInput } from '../types/medical'

interface UseTrendAnalysisResult {
  run: (history: PatientInput[]) => Promise<TrendsResponse | null>
  loading: boolean
  error: ApiError | null
  result: TrendsResponse | null
  reset: () => void
}

export function useTrendAnalysis(): UseTrendAnalysisResult {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [result, setResult] = useState<TrendsResponse | null>(null)

  const run = useCallback(async (history: PatientInput[]) => {
    setLoading(true)
    setError(null)
    try {
      const data = await analyzeTrends({ history })
      setResult(data)
      return data
    } catch (err) {
      const e = toApiError(err)
      setError(e)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const reset = useCallback(() => {
    setResult(null)
    setError(null)
    setLoading(false)
  }, [])

  return { run, loading, error, result, reset }
}
