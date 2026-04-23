import { useCallback, useState } from 'react'
import { explainResult } from '../services/opusClient'
import { toApiError } from '../services/apiClient'
import type { ApiError, ExplainRequest, ExplainResponse } from '../types/api'

interface UseOpusExplainerResult {
  run: (req: ExplainRequest) => Promise<ExplainResponse | null>
  loading: boolean
  error: ApiError | null
  result: ExplainResponse | null
  reset: () => void
}

export function useOpusExplainer(): UseOpusExplainerResult {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [result, setResult] = useState<ExplainResponse | null>(null)

  const run = useCallback(async (req: ExplainRequest) => {
    setLoading(true)
    setError(null)
    try {
      const data = await explainResult(req)
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
