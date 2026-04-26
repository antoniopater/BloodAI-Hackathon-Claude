import { useCallback, useState } from 'react'
import { analyzeTrends } from '../services/opusClient'
import { toApiError } from '../services/apiClient'
import type { ApiError, TrendsHistoryEntry, TrendsResponse } from '../types/api'
import type { HistoryEntry } from '../types/medical'

interface UseTrendAnalysisResult {
  run: (history: HistoryEntry[]) => Promise<TrendsResponse | null>
  loading: boolean
  error: ApiError | null
  result: TrendsResponse | null
  reset: () => void
}

export function useTrendAnalysis(): UseTrendAnalysisResult {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [result, setResult] = useState<TrendsResponse | null>(null)

  const run = useCallback(async (history: HistoryEntry[]) => {
    setLoading(true)
    setError(null)
    try {
      const payload: TrendsHistoryEntry[] = history.map((h) => ({
        ...h.input,
        collectedAt: h.input.collectedAt ?? h.createdAt,
      }))
      const data = await analyzeTrends({ history: payload })
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
